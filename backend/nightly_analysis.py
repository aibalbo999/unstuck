"""Acquire qualified overnight inputs before allowing one paid analysis job."""
import asyncio
from contextlib import ExitStack
from datetime import datetime
import json

import nightly_analysis_store as store
from deployment_rq_pause import deployment_pause_active
from nightly_deployment_gate import NightlyWorkFence
from nightly_analysis_policy import TZ, POLICY, enabled, session_for_acquisition, source_readiness


def prepared_input(job_id, ticker, pipeline):
    work = store.get_work(job_id)
    if work is None:
        return None
    if (work['ticker'], work['pipeline']) != (ticker, pipeline) or not work.get('data_json'):
        raise ValueError('Nightly analysis has no qualified bound input')
    data = json.loads(work['data_json'])
    if store.digest(data) != work['data_sha256']:
        raise ValueError('Nightly prepared input integrity mismatch')
    validate_input(work, data)
    return data


def validate_input(work, data):
    marker = data.get('nightly_analysis') or {}
    if marker != {'policy': POLICY, 'session_date': work['session_date'], 'job_id': work['job_id']}:
        raise ValueError('Nightly analysis session binding mismatch')
    result = source_readiness(data, work['session_date'], work['ticker'])
    if not result['eligible']:
        raise ValueError('Nightly sources not ready: ' + ','.join(result['reason_codes']))


async def process_one(*, service, queue, runner, now=None):
    # Hold SH across async acquisition and dispatch. A controller cannot capture
    # its root baseline until this tick has persisted/deferred or dispatched.
    with ExitStack() as stack:
        try:
            fence = stack.enter_context(NightlyWorkFence())
            if not fence.acquire(shared=True):
                return {'status': 'deployment_paused'}
        except (OSError, RuntimeError) as exc:
            return {'status': 'deployment_pause_unavailable', 'error': type(exc).__name__}
        if status := _pause_status(queue):
            return {'status': status}
        return await _process_admitted(service=service, queue=queue, runner=runner, now=now, fence=fence)


def _pause_status(queue):
    try:
        return 'deployment_paused' if deployment_pause_active(getattr(queue, 'redis', None)) else None
    except Exception:
        # An unavailable witness is not authority to seed, claim or dispatch.
        return 'deployment_pause_unavailable'


async def _fetch_owned(service, request):
    # Do not release the source/dispatch fence merely because its async waiter
    # was cancelled. Settle the accepted bounded fetch before acknowledging it.
    task = asyncio.create_task(asyncio.wait_for(service.fetch_async(request), timeout=240))
    cancelled = None
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError as exc:
        cancelled = exc
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
    try:
        return task.result(), cancelled
    except BaseException:
        if cancelled is not None:
            raise cancelled
        raise


async def _process_admitted(*, service, queue, runner, now=None, fence):
    from analysis_job_helpers import build_data_fetch_blocking_notice
    from data_fetch import FetchRequest
    from data_trust_snapshot_sanitizer import sanitize_for_snapshot
    from job_store import create_job, get_job, find_active_job
    from watchlist_service import list_watchlist
    explicit_now = now
    clock = lambda: datetime.now(TZ) if explicit_now is None else explicit_now
    now = clock()
    session = session_for_acquisition(now)
    if not enabled() or session is None:
        return {'status': 'outside_window'}
    seeded = store.seed(session, list_watchlist()['items'], now)
    if seeded in {'waiting_calendar', 'no_open_scope'}:
        return {'status': seeded, 'session_date': session}
    fence.check()
    if status := _pause_status(queue):
        return {'status': status}
    item = store.claim(session, now)
    if item is None:
        return {'status': 'idle', 'session_date': session}
    # Tests and the scheduler pass an explicit tick time; leases are bounded and
    # acquisition has a shorter timeout than the lease.
    cancelled = None
    try:
        if status := _pause_status(queue):
            store.update_owned(item, clock(), lease_until=0, lease_token=None)
            return {'status': status, 'job_id': item['job_id']}
        active = find_active_job(item['ticker'], item['pipeline'])
        if active and active['job_id'] != item['job_id']:
            store.update_owned(item, now, next_attempt=now.timestamp()+300, lease_until=0, lease_token=None,
                               last_error='waiting_for_other_analysis;never_attach_old_job')
            return {'status': 'waiting_active', 'ticker': item['ticker']}
        existing = get_job(item['job_id'])
        if existing and existing['status'] in {'running','waiting_retry','done','error','cancelled'}:
            store.update_owned(item, now, state='dispatched', lease_until=0, lease_token=None)
            return {'status': 'existing_execution', 'job_id': item['job_id']}
        if not item.get('data_json'):
            fetched, cancelled = await _fetch_owned(service, FetchRequest.from_ticker(item['ticker'], force_refresh=True))
            now = clock()
            data = sanitize_for_snapshot(fetched.data)
            evidence = source_readiness(data, session, item['ticker'])
            if build_data_fetch_blocking_notice(fetched):
                evidence['eligible'] = False
                evidence['reason_codes'].append('data_fetch_blocked')
            if not evidence['eligible']:
                store.update_owned(item, now, attempts=item['attempts']+1, next_attempt=now.timestamp()+900,
                                   evidence_json=store.encoded(evidence), last_error=','.join(evidence['reason_codes']),
                                   lease_until=0, lease_token=None)
                return {'status': 'waiting_source', 'ticker': item['ticker'], 'reasons': evidence['reason_codes']}
            data['nightly_analysis'] = {'policy': POLICY, 'session_date': session, 'job_id': item['job_id']}
            if not store.update_owned(item, now, state='prepared', attempts=item['attempts']+1,
                                      data_json=store.encoded(data), data_sha256=store.digest(data),
                                      evidence_json=store.encoded(evidence), last_error=None):
                return {'status': 'lease_lost'}
        if cancelled is not None:
            # The finally block releases ownership and propagates cancellation;
            # the prepared original survives, without dispatch or a new fetch.
            return {'status': 'cancelled_before_dispatch'}
        if status := _pause_status(queue):
            if not store.update_owned(item, clock(), lease_until=0, lease_token=None):
                return {'status': 'lease_lost'}
            return {'status': status, 'job_id': item['job_id']}
        # Resuming a prepared input never refetches it or bypasses its binding,
        # integrity and original source gates before creating a paid job.
        prepared_input(item['job_id'], item['ticker'], item['pipeline'])
        fence.check()
        create_job(item['ticker'], item['pipeline'], job_id=item['job_id'])
        receipt = queue.enqueue_once('analysis:'+item['job_id'], runner, item['job_id'], item['ticker'], item['pipeline'], queue_name='watchlist')
        if not receipt or receipt.get('task_id') != 'analysis:'+item['job_id']:
            raise RuntimeError('Nightly queue acknowledgement unavailable')
        store.update_owned(item, clock(), state='dispatched', lease_until=0, lease_token=None, last_error=None)
        return {'status': 'dispatched', 'job_id': item['job_id'], 'session_date': session, 'newly_enqueued': receipt['created']}
    except asyncio.CancelledError:
        store.update_owned(item, clock(), lease_until=0, lease_token=None)
        raise
    except Exception as exc:
        now = clock()
        store.update_owned(item, now, next_attempt=now.timestamp()+900, last_error=type(exc).__name__,
                           attempts=item['attempts']+1, lease_until=0, lease_token=None)
        return {'status': 'waiting_error', 'ticker': item['ticker'], 'error': type(exc).__name__}
    finally:
        if cancelled is not None:
            store.update_owned(item, clock(), lease_until=0, lease_token=None)
            raise cancelled


async def run_nightly_scheduler(runtime, *, runner, emit):
    emit('夜間交易日分析排程已啟動：' + json.dumps({'enabled': enabled(), 'start': '22:35 Asia/Taipei',
        'end': '07:00 next calendar day', 'source_gate': '22:30; unchanged', 'scope': 'existing enabled post_market Taiwan items'}, ensure_ascii=False))
    while True:
        try:
            result = await process_one(service=runtime.data_refresh_service, queue=runtime.task_queue, runner=runner)
            if result['status'] not in {'idle','outside_window'}:
                emit('夜間交易日分析：' + json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            emit('夜間交易日分析等待：' + type(exc).__name__)
        await asyncio.sleep(60)
