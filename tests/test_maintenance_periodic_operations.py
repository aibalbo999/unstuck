"""Decision/maintenance admission: private guard files, no source/provider calls."""
import asyncio
from dataclasses import fields
from datetime import datetime
from types import SimpleNamespace
import threading

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

import maintenance_guard as guard
import decision_tracking_service as service
import decision_backtest_service as backtests
import decision_tracking_scheduler as scheduler
import worker_maintenance as worker
from api_routes.decision_tracking import DecisionTrackingRouteDeps, create_decision_tracking_router
from api_routes.maintenance import MaintenanceRouteDeps, create_maintenance_router


PLAN = dict(campaign_id='offline-periodic', old_revision='1' * 40,
    new_revision='2' * 40, control_sha256='3' * 64, queue_name='private-canary',
    canaries=[dict(mode=f'v{i}', job_id=f'canary-{i}', manifest_sha256=str(i) * 64)
        for i in range(1, 5)])


@pytest.fixture
def namespace(tmp_path, monkeypatch):
    root = tmp_path / 'maintenance'
    guard.initialize(root)
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    return root


@pytest.fixture
def sources(monkeypatch):
    calls = []
    monkeypatch.setattr(service.report_history_service, 'list_reports',
        lambda **kwargs: calls.append(('history', kwargs.get('sync_metadata', True))) or {'reports': []})
    monkeypatch.setattr(service.decision_tracking_store, 'list_items', lambda: [])
    monkeypatch.setattr(service.decision_tracking_store, 'upsert_item', lambda *a, **k: calls.append('upsert'))
    monkeypatch.setattr(service.decision_tracking_store, 'delete_item', lambda *a, **k: calls.append('delete') or {})
    monkeypatch.setattr(service.decision_tracking_store, 'mark_refresh', lambda *a, **k: calls.append('mark'))
    return calls


@pytest.mark.parametrize('operation', ['upsert', 'delete', 'latest', 'list', 'backtest', 'refresh'])
def test_armed_direct_service_stops_before_first_metadata_or_mutation(namespace, sources, operation):
    guard.arm(namespace, PLAN)
    actions = dict(upsert=lambda: service.upsert_tracking_item({}, '/private/tmp/no-reports'),
        delete=lambda: service.delete_tracking_item('2330.TW', '/private/tmp/no-reports'),
        latest=lambda: service.latest_reports_for_ticker('2330.TW', '/private/tmp/no-reports'),
        list=lambda: service.list_decision_tracking('/private/tmp/no-reports'),
        backtest=lambda: backtests.run_due_backtests(output_dir='/private/tmp/no-reports'),
        refresh=lambda: asyncio.run(service.refresh_tracking_items(output_dir='/private/tmp/no-reports', refresh_service=object())))
    with pytest.raises(guard.MaintenanceBlocked):
        actions[operation]()
    assert sources == []


def authorized(request):
    if request.headers.get('X-Test-Auth') != 'approved':
        raise HTTPException(403, 'Not authorized')


HEADERS = {'X-Test-Auth': 'approved'}


def decision_client():
    app = FastAPI()
    app.include_router(create_decision_tracking_router(DecisionTrackingRouteDeps(
        get_output_dir=lambda: '/private/tmp/no-reports', get_refresh_service=lambda: object(),
        require_mutation_authorized=authorized)))
    return TestClient(app)


@pytest.mark.parametrize('method,path,payload', [
    ('post', '', {}), ('delete', '/2330.TW', None), ('post', '/refresh', {})])
def test_manual_decision_mutation_returns_typed_503(namespace, sources, method, path, payload):
    guard.arm(namespace, PLAN)
    client = decision_client()
    kwargs = {'json': payload} if payload is not None else {}
    response = client.request(method, '/api/decision-tracking' + path, headers=HEADERS, **kwargs)
    assert response.status_code == 503
    assert '維護' in response.json()['detail']
    assert str(namespace) not in response.text
    assert sources == []
    assert client.request(method, '/api/decision-tracking' + path, **kwargs).status_code == 403


def test_tracking_get_remains_read_only_while_armed(namespace, sources):
    guard.arm(namespace, PLAN)
    response = decision_client().get('/api/decision-tracking')
    assert response.status_code == 200
    assert sources == []


def test_tracking_get_keeps_normal_metadata_sync(namespace, sources):
    response = decision_client().get('/api/decision-tracking')
    assert response.status_code == 200
    assert sources == [('history', True)]


def test_accepted_upsert_finishes_nested_readback_after_arm(namespace, sources, monkeypatch):
    def mutate(payload):
        sources.append('upsert')
        guard.arm(namespace, PLAN)
        assert not guard.wait_drained(namespace, 0)
    monkeypatch.setattr(service.decision_tracking_store, 'upsert_item', mutate)
    assert service.upsert_tracking_item({}, '/private/tmp/no-reports')['items'] == []
    assert sources == ['upsert', ('history', True)]
    assert guard.wait_drained(namespace, 0)


def maintenance_client(action):
    values = {field.name: action for field in fields(MaintenanceRouteDeps)}
    values['require_mutation_authorized'] = authorized
    app = FastAPI()
    app.include_router(create_maintenance_router(MaintenanceRouteDeps(**values)))
    return TestClient(app)


@pytest.mark.parametrize('path', ['cleanup-failed-queue', 'cleanup-report-index',
    'cleanup-provider-sla', 'cleanup-analysis-history', 'sqlite-maintenance'])
@pytest.mark.parametrize('write', [False, True])
def test_maintenance_write_pauses_but_preview_keeps_existing_behavior(namespace, path, write):
    calls = []
    guard.arm(namespace, PLAN)
    client = maintenance_client(lambda **kwargs: calls.append(kwargs) or {'write': kwargs['write']})
    response = client.post(f'/api/maintenance/{path}?write={str(write).lower()}', headers=HEADERS)
    assert response.status_code == (503 if write else 200)
    assert bool(calls) is not write
    if write:
        assert '維護' in response.json()['detail'] and str(namespace) not in response.text
    assert client.post(f'/api/maintenance/{path}?write=true').status_code == 403


def runtime():
    return SimpleNamespace(settings=SimpleNamespace(output_dir='/private/tmp/no-reports',
        cache_db_path='/private/tmp/not-opened', checkpoint_backend='sqlite', checkpoint_path='/private/tmp/not-opened'))


def worker_actions(monkeypatch, first):
    rest = []
    monkeypatch.setattr(worker.report_history_service, 'cleanup_expired_reports', first)
    monkeypatch.setattr(worker.report_history_service, 'cleanup_orphan_markdown_reports', lambda *a: rest.append('markdown'))
    for name in ('cleanup_expired_cache_entries', 'cleanup_report_index_orphans',
        'cleanup_analysis_history', 'cleanup_provider_sla_events', 'run_sqlite_maintenance'):
        monkeypatch.setattr(worker, name, lambda *a, **k: rest.append('other'))
    return rest


def test_periodic_maintenance_pauses_before_any_action(namespace, monkeypatch):
    calls, logs = [], []
    rest = worker_actions(monkeypatch, lambda *a: calls.append('first'))
    monkeypatch.setattr(worker, 'emit_log', logs.append)
    guard.arm(namespace, PLAN)
    asyncio.run(worker.run_maintenance_iteration(runtime(), {}))
    assert calls == rest == []
    assert logs and '暫停' in logs[0] and 'failed' not in logs[0]


@pytest.mark.parametrize('kind', ['periodic', 'backtest', 'manual'])
def test_thread_action_owns_lease_after_outer_cancellation(namespace, sources, monkeypatch, kind):
    started, finish, done = threading.Event(), threading.Event(), threading.Event()
    def action(*args, **kwargs):
        started.set()
        try:
            assert finish.wait(3), 'private test barrier timed out'
            assert not guard.wait_drained(namespace, 0)
            return {'reports': []}
        finally:
            done.set()
    if kind == 'periodic':
        worker_actions(monkeypatch, action)
        factory = lambda: worker.run_maintenance_iteration(runtime(), {})
    elif kind == 'backtest':
        monkeypatch.setattr(backtests.report_history_service, 'list_reports', action)
        operation_done = threading.Event()
        def complete_backtest():
            try:
                return backtests.run_due_backtests(output_dir='/private/tmp/no-reports')
            finally:
                operation_done.set()
        factory = lambda: asyncio.to_thread(complete_backtest)
    else:
        client = maintenance_client(action)
        route = next(r for r in client.app.routes if r.path == '/api/maintenance/cleanup-report-index')
        request = SimpleNamespace(headers=HEADERS)
        factory = lambda: route.endpoint(request, write=True)
    async def scenario():
        task = asyncio.create_task(factory())
        try:
            assert await asyncio.to_thread(started.wait, 2)
            guard.arm(namespace, PLAN)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert not guard.wait_drained(namespace, 0)
        finally:
            finish.set()
            assert await asyncio.to_thread(done.wait, 2)
            if kind == 'backtest':
                assert await asyncio.to_thread(operation_done.wait, 2)
    asyncio.run(scenario())
    assert guard.wait_drained(namespace, 0)


def test_scheduler_pause_does_not_fall_through_to_backtest(namespace, monkeypatch):
    calls, logs = [], []
    async def blocked(**kwargs):
        raise guard.MaintenanceUnavailable('private path must not escape')
    async def stop_after_iteration(seconds):
        raise asyncio.CancelledError
    monkeypatch.setattr(service, 'refresh_tracking_items', blocked)
    monkeypatch.setattr(service, 'run_due_backtests', lambda **kwargs: calls.append('backtest'))
    monkeypatch.setattr(scheduler.asyncio, 'sleep', stop_after_iteration)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_decision_tracking_scheduler(get_output_dir=lambda: '',
            get_refresh_service=lambda: object(), emit_log=logs.append))
    assert calls == []
    assert logs and '暫停' in logs[0] and '失敗' not in logs[0]
    assert 'private path' not in logs[0]


@pytest.mark.parametrize('fetch_error', [False, True])
def test_refresh_cancel_drains_real_fetch_thread_without_snapshot_or_mark(namespace, sources, monkeypatch, fetch_error):
    import report_refresh_service
    started, finish, done = threading.Event(), threading.Event(), threading.Event()
    saved = []
    class Storage:
        def save_report(self, *args, **kwargs):
            saved.append('snapshot')
    class Bundle:
        data_key = 'fixture.json'
        def read_data_snapshot(self):
            return {'ticker': '2330.TW', 'pipeline_id': 'v4'}
    monkeypatch.setattr(report_refresh_service, 'storage_for_existing_output_dir', lambda *a: Storage())
    monkeypatch.setattr(report_refresh_service, 'ReportArtifactLocator',
        lambda storage: SimpleNamespace(require_bundle=lambda *a, **k: Bundle()))
    monkeypatch.setattr(service.decision_tracking_store, 'list_items', lambda: [{'ticker': '2330.TW', 'enabled': True}])
    monkeypatch.setattr(service, 'latest_reports_for_ticker', lambda *a, **k: [{'filename': '2330_v4_report_20260915_090000.html'}])
    def actual_fetch():
        started.set()
        try:
            assert finish.wait(3), 'private test barrier timed out'
            assert not guard.wait_drained(namespace, 0)
            if fetch_error:
                raise ValueError('private provider detail')
            return SimpleNamespace(data={'ticker': '2330.TW'})
        finally:
            done.set()
    class Fetcher:
        async def fetch_async(self, request):
            return await asyncio.to_thread(actual_fetch)
    async def scenario():
        task = asyncio.create_task(service.refresh_tracking_items(output_dir='/private/tmp/no-reports', refresh_service=Fetcher()))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            guard.arm(namespace, PLAN)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            assert not guard.wait_drained(namespace, 0)
        finally:
            finish.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert await asyncio.to_thread(done.wait, 2)
    asyncio.run(scenario())
    assert saved == [] and 'mark' not in sources
    assert guard.wait_drained(namespace, 0)


def test_refresh_owner_finishes_after_arm_but_new_task_cannot_borrow(namespace, sources, monkeypatch):
    monkeypatch.setattr(service.decision_tracking_store, 'list_items', lambda: [{'ticker': '2330.TW', 'enabled': True}])
    monkeypatch.setattr(service, 'latest_reports_for_ticker', lambda *a, **k: [{'filename': 'fixture.html'}])
    async def new_task():
        with pytest.raises(guard.MaintenanceBlocked):
            service.upsert_tracking_item({}, '/private/tmp/no-reports')
    async def refresh(*args, **kwargs):
        guard.arm(namespace, PLAN)
        await asyncio.sleep(0)
        with guard.admission():
            assert not guard.wait_drained(namespace, 0)
        await asyncio.create_task(new_task())
        return SimpleNamespace(refreshed_reports_count=1)
    monkeypatch.setattr(service, 'refresh_ticker_reports', refresh)
    result = asyncio.run(service.refresh_tracking_items(output_dir='/private/tmp/no-reports', refresh_service=object()))
    assert result['success'] and result['updated_count'] == 1
    assert sources == [('history', True), 'mark', ('history', True)]
    assert guard.wait_drained(namespace, 0)


@pytest.mark.parametrize('error_type', [guard.MaintenanceBlocked, guard.MaintenanceUnavailable])
def test_refresh_nested_maintenance_error_never_becomes_refresh_error(namespace, sources, monkeypatch, error_type):
    monkeypatch.setattr(service.decision_tracking_store, 'list_items', lambda: [{'ticker': '2330.TW', 'enabled': True}])
    monkeypatch.setattr(service, 'latest_reports_for_ticker', lambda *a, **k: [{'filename': 'fixture.html'}])
    async def blocked(*args, **kwargs):
        raise error_type('private detail')
    monkeypatch.setattr(service, 'refresh_ticker_reports', blocked)
    with pytest.raises(error_type):
        asyncio.run(service.refresh_tracking_items(output_dir='/private/tmp/no-reports', refresh_service=object()))
    assert sources == [('history', True)]


@pytest.mark.parametrize('mode', ['v1', 'v4'])
def test_backtest_nested_maintenance_error_is_not_counted_as_report_failure(namespace, sources, monkeypatch, mode):
    from datetime import date
    monkeypatch.setattr(backtests.report_history_service, 'list_reports', lambda **k: {'reports': [
        {'filename': f'2330_TW_{mode}_report_20260101_090000.html', 'pipeline_id': mode, 'date': '2026-01-01 09:00'}]})
    monkeypatch.setattr(backtests.decision_tracking_store, 'backtest_result_exists', lambda *a: False)
    def blocked(*args, **kwargs):
        raise guard.MaintenanceUnavailable('private detail')
    monkeypatch.setattr(backtests, 'evaluate_report_trades', blocked)
    with pytest.raises(guard.MaintenanceUnavailable):
        backtests.run_due_backtests(output_dir='/private/tmp/no-reports', as_of=date(2026, 9, 15), price_fetcher=blocked)


def test_scheduler_backtest_pause_is_not_reported_as_failure(namespace, monkeypatch):
    logs = []
    async def refreshed(**kwargs):
        return {'updated_count': 0, 'errors': []}
    def blocked(**kwargs):
        raise guard.MaintenanceBlocked('private detail')
    async def stop(seconds):
        raise asyncio.CancelledError
    monkeypatch.setattr(service, 'refresh_tracking_items', refreshed)
    monkeypatch.setattr(service, 'run_due_backtests', blocked)
    monkeypatch.setattr(scheduler.asyncio, 'sleep', stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_decision_tracking_scheduler(get_output_dir=lambda: '',
            get_refresh_service=lambda: object(), emit_log=logs.append))
    assert logs == ['每日決策追蹤回測暫停：系統維護中或維護狀態尚未確認。']


def test_periodic_action_that_arms_finishes_but_no_next_step_starts(namespace, monkeypatch):
    calls = []
    def first(*args):
        guard.arm(namespace, PLAN)
        assert not guard.wait_drained(namespace, 0)
        calls.append('finished')
    rest = worker_actions(monkeypatch, first)
    asyncio.run(worker.run_maintenance_iteration(runtime(), {}))
    assert calls == ['finished'] and rest == []
    assert guard.wait_drained(namespace, 0)


def test_storage_status_and_tracking_stats_still_readable_while_armed(namespace, monkeypatch):
    guard.arm(namespace, PLAN)
    response = maintenance_client(lambda: {'fixture': True}).get('/api/maintenance/storage-summary', headers=HEADERS)
    assert response.status_code == 200 and response.json()['summary'] == {'fixture': True}
    monkeypatch.setattr(service, 'compute_performance_stats', lambda **kwargs: {'summary': {'total': 3}})
    assert service.compute_tracking_performance_stats('/private/tmp/no-reports') == {'summary': {'total': 3}}


@pytest.mark.parametrize('path', ['cleanup-failed-queue?stale_after_seconds=59',
    'cleanup-provider-sla?retention_days=0', 'cleanup-analysis-history?keep_recent_jobs=501'])
def test_existing_maintenance_query_bounds_are_preserved(namespace, path):
    calls = []
    response = maintenance_client(lambda **kwargs: calls.append(kwargs)).post('/api/maintenance/' + path, headers=HEADERS)
    assert response.status_code == 422 and calls == []


def test_decision_validation_error_remains_400(namespace, sources, monkeypatch):
    def invalid(payload):
        raise ValueError('invalid ticker')
    monkeypatch.setattr(service.decision_tracking_store, 'upsert_item', invalid)
    response = decision_client().post('/api/decision-tracking', json={}, headers=HEADERS)
    assert response.status_code == 400 and response.json()['detail'] == 'invalid ticker'


@pytest.mark.parametrize('kind', ['decision', 'maintenance'])
def test_missing_state_is_typed_503_without_side_effect(namespace, sources, kind):
    # Exact private fixture state only: simulate loss, never auto-initialize it.
    (namespace / 'state.json').unlink()
    calls = []
    if kind == 'decision':
        response = decision_client().post('/api/decision-tracking', json={}, headers=HEADERS)
    else:
        response = maintenance_client(lambda **k: calls.append(k)).post('/api/maintenance/cleanup-report-index?write=true', headers=HEADERS)
    assert response.status_code == 503 and calls == [] and sources == []
