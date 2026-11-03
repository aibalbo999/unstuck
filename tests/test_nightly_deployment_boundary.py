"""Pause boundaries retain genuine prepared work without duplicate acquisition."""
import asyncio
from datetime import timedelta
import json
import os

import job_store
import nightly_analysis as nightly
import nightly_analysis_store as store
from deployment_rq_pause import KEY
from test_nightly_analysis import env, tick, NOW
from test_watchlist_dispatch_recovery import noop
import pytest
from nightly_deployment_gate import NightlyWorkFence


def suspension(env, monkeypatch):
    state = {'paused': False}
    monkeypatch.setattr(env.redis, 'get', lambda key: b'stock-agent:deployment:v1:' + b'a' * 32 if state['paused'] and key == KEY else None, raising=False)
    monkeypatch.setattr(env.redis, 'pttl', lambda key: -1, raising=False)
    return state


def test_paused_tick_does_not_seed_claim_or_fetch(env, monkeypatch):
    state = suspension(env, monkeypatch)
    state['paused'] = True
    assert tick(env)['status'] == 'deployment_paused'
    assert store.read_rows() == [] and not env.calls and not env.redis.lists


def test_pause_after_seed_does_not_claim(env, monkeypatch):
    state = suspension(env, monkeypatch)
    seed = store.seed
    def pause_after_seed(*args):
        result = seed(*args)
        state['paused'] = True
        return result
    monkeypatch.setattr(store, 'seed', pause_after_seed)
    assert tick(env)['status'] == 'deployment_paused'
    row = store.read_rows()[0]
    assert row['state'] == 'pending' and row['lease_token'] is None
    assert row['attempts'] == 0 and not env.calls and not env.redis.lists


def test_pause_after_claim_releases_owner_without_source_attempt(env, monkeypatch):
    state = suspension(env, monkeypatch)
    claim = store.claim
    def pause_after_claim(*args):
        item = claim(*args)
        state['paused'] = True
        return item
    monkeypatch.setattr(store, 'claim', pause_after_claim)
    assert tick(env)['status'] == 'deployment_paused'
    row = store.read_rows()[0]
    assert row['state'] == 'pending' and row['lease_token'] is None
    assert row['attempts'] == 0 and not env.calls and not env.redis.lists


def test_pause_during_fetch_saves_bound_input_and_resumes_once(env, monkeypatch):
    state = suspension(env, monkeypatch)
    fetch = env.service.fetch_async
    async def pause_after_fetch(request):
        result = await fetch(request)
        state['paused'] = True
        return result
    monkeypatch.setattr(env.service, 'fetch_async', pause_after_fetch)
    assert tick(env)['status'] == 'deployment_paused'
    first = store.read_rows()[0]
    assert first['state'] == 'prepared' and first['lease_token'] is None and first['lease_until'] == 0
    assert first['attempts'] == 1 and not job_store.get_job(first['job_id'])
    assert not env.redis.lists and len(env.calls) == 1
    assert nightly.prepared_input(first['job_id'], first['ticker'], first['pipeline'])
    state['paused'] = False
    assert tick(env, NOW + timedelta(minutes=1))['status'] == 'dispatched'
    final = store.read_rows()[0]
    assert (final['job_id'], final['session_date'], final['data_json'], final['data_sha256'], final['attempts']) == (first['job_id'], first['session_date'], first['data_json'], first['data_sha256'], first['attempts'])
    assert env.redis.lists['rq:queue:watchlist'] == [('analysis:' + first['job_id']).encode()]
    assert len(env.calls) == 1
    assert tick(env, NOW + timedelta(minutes=2))['status'] == 'idle'


def test_unavailable_pause_state_does_not_touch_work(env, monkeypatch):
    suspension(env, monkeypatch)
    def unavailable(key):
        raise ConnectionError('isolated unavailable pause witness')
    monkeypatch.setattr(env.redis, 'get', unavailable)
    assert tick(env)['status'] == 'deployment_pause_unavailable'
    assert not store.read_rows() and not env.calls and not env.redis.lists


def test_controller_fence_prevents_new_claims_without_redis_pause(env, monkeypatch):
    suspension(env, monkeypatch)
    with NightlyWorkFence() as controller:
        assert controller.acquire()
        assert tick(env)['status'] == 'deployment_paused'
        assert not store.read_rows() and not env.calls
    assert tick(env)['status'] == 'dispatched'


def test_controller_cannot_capture_baseline_during_fetch_or_dispatch(env, monkeypatch):
    state = suspension(env, monkeypatch)
    fetch = env.service.fetch_async
    enqueue = env.queue.enqueue_once
    observations = []
    async def fetch_while_controller_waits(request):
        with NightlyWorkFence() as controller:
            observations.append(controller.acquire())
        return await fetch(request)
    def enqueue_during_pause(*args, **kwargs):
        # Pause can begin after the final Redis read; EX still cannot pass the
        # admitted SH tick until the same real dispatch is fully acknowledged.
        state['paused'] = True
        with NightlyWorkFence() as controller:
            observations.append(controller.acquire())
        return enqueue(*args, **kwargs)
    monkeypatch.setattr(env.service, 'fetch_async', fetch_while_controller_waits)
    monkeypatch.setattr(env.queue, 'enqueue_once', enqueue_during_pause)
    assert tick(env)['status'] == 'dispatched'
    assert observations == [False, False]
    with NightlyWorkFence() as controller:
        assert controller.acquire()
    first = store.read_rows()[0]
    assert first['attempts'] == 1 and first['state'] == 'dispatched'
    assert len(env.calls) == 1


@pytest.mark.parametrize('change', ['hash', 'session', 'sources'])
def test_resumed_prepared_input_is_revalidated_before_job_creation(env, monkeypatch, change):
    state = suspension(env, monkeypatch)
    fetch = env.service.fetch_async
    async def pause_after_fetch(request):
        result = await fetch(request)
        state['paused'] = True
        return result
    monkeypatch.setattr(env.service, 'fetch_async', pause_after_fetch)
    assert tick(env)['status'] == 'deployment_paused'
    first = store.read_rows()[0]
    if change == 'hash':
        with store.connection() as db:
            db.execute(f'UPDATE {store.TABLE} SET data_sha256=? WHERE job_id=?', ('wrong', first['job_id']))
    elif change == 'session':
        data = json.loads(first['data_json'])
        data['nightly_analysis']['session_date'] = '2026-10-29'
        with store.connection() as db:
            db.execute(f'UPDATE {store.TABLE} SET data_json=?,data_sha256=? WHERE job_id=?', (store.encoded(data), store.digest(data), first['job_id']))
    else:
        monkeypatch.setattr(nightly, 'source_readiness', lambda *a: {'eligible': False, 'reason_codes': ['stale']})
    state['paused'] = False
    assert tick(env, NOW + timedelta(minutes=1))['status'] == 'waiting_error'
    assert not job_store.get_job(first['job_id']) and not env.redis.lists
    assert len(env.calls) == 1


def test_cancelled_fetch_waiter_keeps_fence_until_input_is_saved(env, monkeypatch):
    suspension(env, monkeypatch)
    fetch = env.service.fetch_async
    async def exercise():
        started, release = asyncio.Event(), asyncio.Event()
        async def controlled(request):
            started.set()
            await release.wait()
            return await fetch(request)
        monkeypatch.setattr(env.service, 'fetch_async', controlled)
        task = asyncio.create_task(nightly.process_one(service=env.service, queue=env.queue, runner=noop, now=NOW))
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        with NightlyWorkFence() as controller:
            assert not controller.acquire()
        assert not task.done() and not env.redis.lists
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        row = store.read_rows()[0]
        assert row['state'] == 'prepared' and row['lease_token'] is None
        assert row['attempts'] == 1 and not job_store.get_job(row['job_id'])
        assert not env.redis.lists
        with NightlyWorkFence() as controller:
            assert controller.acquire()
    asyncio.run(exercise())
    assert tick(env, NOW + timedelta(minutes=1))['status'] == 'dispatched'
    assert len(env.calls) == 1


@pytest.mark.skipif(not hasattr(os, 'fork'), reason='Mac/Linux kernel-lock boundary')
def test_kernel_fence_blocks_independent_process(env, monkeypatch):
    suspension(env, monkeypatch)
    read_fd, write_fd = os.pipe()
    with NightlyWorkFence() as admitted:
        assert admitted.acquire(shared=True)
        pid = os.fork()
        if pid == 0:
            try:
                os.close(read_fd)
                os.close(admitted.fd)  # Close inherited SH; parent still owns it.
                with NightlyWorkFence() as controller:
                    os.write(write_fd, b'blocked' if not controller.acquire() else b'unsafe')
            finally:
                os._exit(0)
        os.close(write_fd)
        try:
            assert os.read(read_fd, 16) == b'blocked'
            assert os.waitpid(pid, 0)[1] == 0
        finally:
            os.close(read_fd)
    with NightlyWorkFence() as controller:
        assert controller.acquire()
