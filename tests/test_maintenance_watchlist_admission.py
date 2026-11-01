"""Private watchlist admission and cancellation integration; no source HTTP."""
import asyncio
from datetime import datetime
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import job_store
import maintenance_guard as guard
import watchlist_service as service
import watchlist_scheduler as scheduler
import api_routes.watchlist as routes
from data_fetch import FetchResult
from test_maintenance_analysis_admission import HEADERS, authorized, control, maintenance_plan


NOW = datetime(2026, 9, 14, 18, 1, tzinfo=service.TAIPEI)


@pytest.fixture
def watchlist(tmp_path, monkeypatch):
    monkeypatch.setattr(service, 'WATCHLIST_PATH', tmp_path / 'watchlist.json')
    service.reset_watchlist_store_for_tests()
    for ticker in ('2330.TW', '2317.TW'):
        service.upsert_watchlist_item({'ticker': ticker, 'pipeline': 'v4', 'enabled': True,
            'schedule_slots': ['post_market'], 'triggers': [{'type': 'vix_above', 'threshold': 30}]})
    monkeypatch.setattr(service.time, 'sleep', lambda seconds: None)
    yield
    service.reset_watchlist_store_for_tests()


class Queue:
    def __init__(self): self.calls = []
    def enqueue(self, *args, **kwargs):
        with guard.admission():
            self.calls.append((args, kwargs))
    def enqueue_once(self, task_id, function, *args, **kwargs):
        self.enqueue(task_id, function, *args, **kwargs)
        return {'task_id':task_id,'created':True}


def test_dispatch_maintenance_rejection_does_not_release_or_continue(control, monkeypatch):
    import watchlist_dispatch_service
    import watchlist_dispatch_store
    calls=[];released=[]
    def blocked(item, **kwargs):
        calls.append(item['dispatch_id'])
        raise guard.MaintenanceUnavailable('offline maintenance refusal')
    monkeypatch.setattr(watchlist_dispatch_service,'dispatch_item',blocked)
    monkeypatch.setattr(watchlist_dispatch_store,'release',lambda *args:released.append(args))
    items=[{'dispatch_id':str(i),'ticker':'FIXTURE','pipeline':'v4','due_slot':'post_market'} for i in (1,2)]
    with pytest.raises(guard.MaintenanceUnavailable):
        service.enqueue_watchlist_items(items,**deps(Queue()))
    assert calls==['1'] and released==[]


def deps(queue, **changes):
    values = dict(create_job=job_store.create_job, find_active_job=job_store.find_active_job,
        task_queue=queue, run_stock_analysis_job=lambda *args: None)
    values.update(changes)
    return values


def app(queue):
    value = FastAPI()
    value.include_router(routes.create_watchlist_router(routes.WatchlistRouteDeps(
        get_output_dir=lambda: '/private/tmp/offline-fixture', get_task_queue=lambda: queue,
        run_stock_analysis_job=lambda *args: None, create_job=job_store.create_job,
        find_active_job=job_store.find_active_job, require_mutation_authorized=authorized)))
    return value


def test_armed_scheduled_batch_does_not_consume_due_dates(control, watchlist, monkeypatch):
    original = service.claim_due_watchlist_items
    monkeypatch.setattr(service, 'claim_due_watchlist_items', lambda: original(NOW))
    before = service.list_watchlist()
    queue = Queue()
    guard.arm(control, maintenance_plan())
    with pytest.raises(guard.MaintenanceBlocked):
        scheduler._run_due_watchlist_batch(**deps(queue), emit_log=lambda message: None)
    assert service.list_watchlist() == before
    assert job_store.list_active_jobs() == [] and queue.calls == []


def test_armed_manual_batch_stops_before_queue_aware_lookup(control, watchlist):
    seen, queue = [], Queue()
    items = service.list_watchlist()['items']
    guard.arm(control, maintenance_plan())
    with pytest.raises(guard.MaintenanceBlocked):
        service.enqueue_watchlist_items(items, **deps(queue,
            find_active_job=lambda *args: seen.append('may-mark-abandoned') or {}))
    assert seen == [] and job_store.list_active_jobs() == [] and queue.calls == []


def test_armed_trigger_does_not_fetch_or_consume_event_dedupe(control, watchlist, monkeypatch):
    seen, queue = [], Queue()
    async def fetch(*args):
        seen.append('fetch')
        return {'macro_indicators': {'indicators': {'vix': {'value': 35}}}}
    monkeypatch.setattr(service, 'fetch_radar_data', fetch)
    before = service.list_watchlist()
    guard.arm(control, maintenance_plan())
    with pytest.raises(guard.MaintenanceBlocked):
        asyncio.run(service.monitor_watchlist_triggers(data_service=object(), now=NOW, **deps(queue)))
    assert seen == [] and service.list_watchlist() == before
    assert job_store.list_active_jobs() == [] and queue.calls == []


@pytest.mark.parametrize('route', ['run', 'screener/run'])
def test_manual_routes_return_503_without_creation_or_screener(control, watchlist, monkeypatch, route):
    seen, queue = [], Queue()
    monkeypatch.setattr(routes.market_screener, 'run_daily_market_screener',
        lambda **kwargs: seen.append(kwargs) or {'success': True})
    guard.arm(control, maintenance_plan())
    response = TestClient(app(queue)).post('/api/watchlist/' + route, headers=HEADERS, json={})
    assert response.status_code == 503 and '維護' in response.json()['detail']
    assert seen == [] and queue.calls == [] and job_store.list_active_jobs() == []


def test_scheduled_screener_does_not_scan_or_mark_while_armed(control, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler.market_screener, 'screener_already_ran', lambda day: calls.append('lookup') or False)
    monkeypatch.setattr(scheduler.market_screener, 'run_daily_market_screener', lambda **kwargs: calls.append('scan') or {'success': True})
    monkeypatch.setattr(scheduler.market_screener, 'mark_screener_ran', lambda day: calls.append('mark'))
    guard.arm(control, maintenance_plan())
    with pytest.raises(guard.MaintenanceBlocked):
        scheduler._run_daily_market_screener(now=NOW, emit_log=lambda message: None)
    assert calls == []


def test_scheduler_logs_typed_pause_and_skips_remaining_phases(control, monkeypatch):
    calls, logs = [], []
    def blocked(**kwargs): raise guard.MaintenanceUnavailable('private control path secret')
    def no_screener(**kwargs): calls.append('screener')
    async def no_trigger(**kwargs): calls.append('trigger')
    async def stop(seconds): raise asyncio.CancelledError()
    monkeypatch.setattr(scheduler, '_run_due_watchlist_batch', blocked)
    monkeypatch.setattr(scheduler, '_run_daily_market_screener', no_screener)
    monkeypatch.setattr(service, 'monitor_watchlist_triggers', no_trigger)
    monkeypatch.setattr(scheduler.asyncio, 'sleep', stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler._watchlist_scheduler_forever(**deps(Queue()), data_service=object(), emit_log=logs.append))
    assert calls == []
    assert len(logs) == 1 and '維護暫停' in logs[0]
    assert 'secret' not in logs[0] and '檢查失敗' not in logs[0]


@pytest.mark.parametrize('late_failure', [False, True])
def test_trigger_cancel_does_not_release_lease_while_shielded_fetch_survives(control, watchlist, late_failure):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        class Data:
            async def fetch_async(self, request):
                entered.set()
                await release.wait()
                if late_failure:
                    raise RuntimeError('late source failure')
                return FetchResult(request=request, data={'ticker': request.ticker,
                    'macro_indicators': {'indicators': {'vix': {'value': 35}}}})
        data, queue = Data(), Queue()
        monitor = asyncio.create_task(service.monitor_watchlist_triggers(data_service=data, now=NOW, **deps(queue)))
        await entered.wait()
        source_tasks = list(data._watchlist_radar_cache.inflight.values())
        assert len(source_tasks) == 1 and not source_tasks[0].done()
        monitor.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        guard.arm(control, maintenance_plan())
        try:
            assert guard.wait_drained(control, 0) is False
            assert not monitor.done()
            for _ in range(3):
                monitor.cancel()
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert not monitor.done()
                assert guard.wait_drained(control, 0) is False
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError): await monitor
            # The owned waiter already joined the shared fetch; gathering is
            # cleanup only, not what makes the admission assertion pass.
            assert all(task.done() for task in source_tasks)
            await asyncio.gather(*source_tasks, return_exceptions=True)
        assert queue.calls == [] and job_store.list_active_jobs() == []
        assert all(not item['latest_trigger_event'] for item in service.list_watchlist()['items'])
        assert guard.wait_drained(control, 0.5) is True
    asyncio.run(scenario())


@pytest.mark.parametrize('scheduled', [False, True])
def test_accepted_whole_batch_finishes_after_arm_with_original_throttle(control, watchlist, monkeypatch, scheduled):
    queue, sleeps = Queue(), []
    original_enqueue = queue.enqueue
    def enqueue(*args, **kwargs):
        original_enqueue(*args, **kwargs)
        if len(queue.calls) == 1:
            guard.arm(control, maintenance_plan())
        assert guard.wait_drained(control, 0) is False
    def throttle(seconds):
        sleeps.append(seconds)
        assert guard.wait_drained(control, 0) is False
    monkeypatch.setattr(queue, 'enqueue', enqueue)
    monkeypatch.setattr(service.time, 'sleep', throttle)
    if scheduled:
        original_claim = service.claim_due_watchlist_items
        monkeypatch.setattr(service, 'claim_due_watchlist_items', lambda: original_claim(NOW))
        result = scheduler._run_due_watchlist_batch(**deps(queue), emit_log=lambda message: None)
    else:
        result = service.enqueue_watchlist_items(service.list_watchlist()['items'], **deps(queue))
    assert result['success'] is True and len(result['queued']) == 2
    assert len(queue.calls) == 2 and len(job_store.list_active_jobs()) == 2
    assert sleeps == [45, 45]
    if scheduled:
        assert all(item['last_run_dates']['post_market'] == NOW.date().isoformat()
                   for item in service.list_watchlist()['items'])
    assert guard.wait_drained(control, 0) is True


def test_accepted_trigger_fetch_finishes_dedupe_and_enqueue_after_arm(control, watchlist, monkeypatch):
    seen, queue = [], Queue()
    async def fetch(*args):
        if not seen:
            guard.arm(control, maintenance_plan())
        seen.append('fetch')
        assert guard.wait_drained(control, 0) is False
        return {'macro_indicators': {'indicators': {'vix': {'value': 35}}}}
    monkeypatch.setattr(service, 'fetch_radar_data', fetch)
    result = asyncio.run(service.monitor_watchlist_triggers(data_service=object(), now=NOW, **deps(queue)))
    assert result['success'] is True and len(result['queued']) == 2
    assert len(queue.calls) == 2
    assert all(item['latest_trigger_event'] for item in service.list_watchlist()['items'])
    assert guard.wait_drained(control, 0) is True


def test_fetch_exception_does_not_consume_dedupe_or_create_and_releases_lease(control, watchlist, monkeypatch):
    queue = Queue()
    async def broken(*args): raise RuntimeError('offline source failure')
    monkeypatch.setattr(service, 'fetch_radar_data', broken)
    result = asyncio.run(service.monitor_watchlist_triggers(data_service=object(), now=NOW, **deps(queue)))
    assert result['success'] is False and len(result['errors']) == 2
    assert queue.calls == [] and job_store.list_active_jobs() == []
    assert all(not item['latest_trigger_event'] for item in service.list_watchlist()['items'])
    guard.arm(control, maintenance_plan())
    assert guard.wait_drained(control, 0) is True


def test_accepted_scheduled_screener_still_marks_after_arm(control, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler.market_screener, 'screener_already_ran', lambda day: False)
    def scan(**kwargs):
        guard.arm(control, maintenance_plan())
        return {'success': True}
    def mark(day):
        assert guard.wait_drained(control, 0) is False
        calls.append(day)
    monkeypatch.setattr(scheduler.market_screener, 'run_daily_market_screener', scan)
    monkeypatch.setattr(scheduler.market_screener, 'mark_screener_ran', mark)
    assert scheduler._run_daily_market_screener(now=NOW, emit_log=lambda message: None)['success'] is True
    assert calls == [NOW.date().isoformat()]
    assert guard.wait_drained(control, 0) is True


@pytest.mark.parametrize('path', ['/api/watchlist/run', '/api/watchlist/screener/run'])
def test_canceled_manual_route_keeps_actual_worker_thread_lease(control, watchlist, monkeypatch, path):
    async def scenario():
        loop = asyncio.get_running_loop()
        entered, finished = asyncio.Event(), asyncio.Event()
        release = threading.Event()
        queue = Queue()
        def block():
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5), 'test must release the offline worker'
            assert guard.wait_drained(control, 0) is False
        if path.endswith('screener/run'):
            def scan(**kwargs):
                block()
                return {'success': True}
            monkeypatch.setattr(routes.market_screener, 'run_daily_market_screener', scan)
        else:
            original = job_store.create_job
            def create(*args):
                if not queue.calls:
                    block()
                return original(*args)
            monkeypatch.setattr(job_store, 'create_job', create)
        helper_name = '_run_manual_screener' if path.endswith('screener/run') else '_run_manual_watchlist'
        original_helper = getattr(routes, helper_name)
        def actual_thread(*args):
            try:
                return original_helper(*args)
            finally:
                loop.call_soon_threadsafe(finished.set)
        monkeypatch.setattr(routes, helper_name, actual_thread)
        endpoint = next(route.endpoint for route in app(queue).routes if getattr(route, 'path', None) == path)
        class Request:
            headers = HEADERS
            async def json(self): return {}
        caller = asyncio.create_task(endpoint(Request()))
        await asyncio.wait_for(entered.wait(), 3)
        caller.cancel()
        try:
            with pytest.raises(asyncio.CancelledError): await caller
            guard.arm(control, maintenance_plan())
            assert guard.wait_drained(control, 0) is False
        finally:
            release.set()
            await asyncio.wait_for(finished.wait(), 3)
        # The wrapper signals after the real guarded helper exits, not when
        # its canceled asyncio caller returns. Do not shut down a shared loop.
        assert guard.wait_drained(control, 0) is True
        if not path.endswith('screener/run'):
            assert len(queue.calls) == 2
    asyncio.run(scenario())


@pytest.mark.parametrize('route', ['run', 'screener/run'])
def test_manual_authorization_precedes_maintenance(control, watchlist, route):
    guard.arm(control, maintenance_plan())
    response = TestClient(app(Queue())).post('/api/watchlist/' + route, json={})
    assert response.status_code == 403
    assert job_store.list_active_jobs() == []


def test_readonly_watchlist_route_remains_available_while_armed(control, monkeypatch):
    monkeypatch.setattr(service, 'list_watchlist_with_report_alerts', lambda *args: {'items': []})
    guard.arm(control, maintenance_plan())
    assert TestClient(app(Queue())).get('/api/watchlist').json() == {'items': []}


def test_manual_business_exception_is_not_converted_to_maintenance_and_releases(control, watchlist):
    original = RuntimeError('ordinary lookup failure')
    def broken(*args): raise original
    with pytest.raises(RuntimeError) as caught:
        service.enqueue_watchlist_items(service.list_watchlist()['items'],
            **deps(Queue(), find_active_job=broken))
    assert caught.value is original
    guard.arm(control, maintenance_plan())
    assert guard.wait_drained(control, 0) is True
