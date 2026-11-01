"""Analysis admission never leaves half-created work when maintenance starts.

Only provider/queue boundaries are fixtures. SQLite is isolated by conftest and
the required prompt-boundary runner. The seam gate supplies deterministic race
points; separate tests exercise the real cross-process guard once initialized.
"""
from contextlib import contextmanager
from dataclasses import fields
import threading

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

import analysis_job_service as service
import job_store
import maintenance_guard as guard
from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
from api_routes.reports import ReportRouteDeps, create_reports_router
import api_routes.reports as reports


class SeamGate:
    def __init__(self):
        self.blocked = False
        self.depth = 0
        self.entries = 0

    @contextmanager
    def admission(self, root=None):
        if not self.depth and self.blocked:
            raise guard.MaintenanceBlocked('fixture private control path must not escape')
        self.depth += 1
        self.entries += 1
        try:
            yield
        finally:
            self.depth -= 1


@pytest.fixture
def gate(monkeypatch):
    value = SeamGate()
    monkeypatch.setattr(guard, 'admission', value.admission)
    return value


class Queue:
    def __init__(self, gate, *, complete=False):
        self.gate, self.complete, self.calls = gate, complete, []
        self.queue = self

    def fetch_job(self, task_id):
        return None

    def enqueue(self, task_id, fn, job_id, *args):
        with self.gate.admission():
            self.calls.append((task_id, job_id))
            if self.complete:
                job_store.update_job(job_id, 'done', filename='fixture.html')
                job_store.append_event(job_id, {'type': 'done', 'filename': 'fixture.html'})


def authorized(request):
    if request.headers.get('X-Test-Auth') != 'approved':
        raise HTTPException(403, 'Not authorized')


def analysis_app(queue, **changes):
    values = dict(active_analyses_lock=threading.Lock(), get_analysis_task_queue=lambda: queue,
        run_stock_analysis_job=lambda *args: None, has_api_keys=lambda: True,
        api_key_setup_message=lambda: '', normalize_pipeline_run_id=lambda value: value,
        get_pipeline_run_sequence=lambda value: (value,), get_pipeline_run_label=lambda value: value,
        get_pipeline_run_agent_total=lambda value: 3, get_job=job_store.get_job,
        find_active_job=job_store.find_active_job, create_job=job_store.create_job,
        get_events_since=job_store.get_events_since, update_job=job_store.update_job,
        append_event=job_store.append_event, request_job_cancel=job_store.request_job_cancel,
        print_streamed_event=lambda *args: None, require_mutation_authorized=authorized,
        create_or_attach_analysis_job=service.create_or_attach_analysis_job)
    values.update(changes)
    app = FastAPI()
    app.include_router(create_analysis_router(AnalysisRouteDeps(**values)))
    return app


def report_app(queue, monkeypatch, **changes):
    values = {field.name: lambda *args, **kwargs: None for field in fields(ReportRouteDeps)}
    values.update(get_output_dir=lambda: '/private/tmp/offline-fixture',
        get_report_storage=lambda: object(), get_task_queue=lambda: queue,
        create_job=job_store.create_job, get_job=job_store.get_job,
        update_job=job_store.update_job, append_event=job_store.append_event,
        create_or_attach_job=lambda ticker, pipeline: job_store.create_or_attach_active_job(ticker, pipeline),
        require_mutation_authorized=authorized)
    values.update(changes)
    monkeypatch.setattr(reports, 'existing_storage_key', lambda storage, name, kind: name)
    app = FastAPI()
    app.include_router(create_reports_router(ReportRouteDeps(**values)))
    return app


HEADERS = {'X-Test-Auth': 'approved'}


@pytest.mark.parametrize('orphan', [False, True])
def test_service_paused_before_lifecycle_does_not_create_or_recover(gate, orphan):
    old = job_store.create_job('2330.TW', 'v4') if orphan else None
    before = job_store.get_job(old) if old else None
    queue = Queue(gate)
    gate.blocked = True
    with pytest.raises(guard.MaintenanceBlocked):
        service.create_or_attach_analysis_job(ticker='2330.TW', pipeline_id='v4',
            task_queue=queue, run_stock_analysis_job=lambda *args: None)
    assert queue.calls == []
    assert job_store.get_job(old) == before if old else job_store.find_active_job('2330.TW', 'v4') == {}


@pytest.mark.parametrize('legacy', [False, True])
def test_post_create_paused_is_503_without_job(gate, legacy):
    queue = Queue(gate)
    app = analysis_app(queue, **({'create_or_attach_analysis_job': None} if legacy else {}))
    gate.blocked = True
    response = TestClient(app).post('/api/analysis-jobs', headers=HEADERS,
        json={'ticker': '2330.TW', 'pipeline_id': 'v4'})
    assert response.status_code == 503
    assert '維護' in response.json()['detail']
    assert 'private control path' not in response.text
    assert job_store.find_active_job('2330.TW', 'v4') == {}
    assert queue.calls == []


def test_legacy_new_admission_is_blocked_before_mutating_active_lookup(gate):
    old = job_store.create_job('2330.TW', 'v4')
    seen = []
    def queue_aware_lookup(ticker, pipeline):
        seen.append('lookup')
        job_store.update_job(old, 'error', error='orphan')
        return {}
    queue = Queue(gate, complete=True)
    app = analysis_app(queue, find_active_job=queue_aware_lookup)
    gate.blocked = True
    response = TestClient(app).get('/api/analyze/2330.TW?pipeline=v4')
    assert response.status_code == 503
    assert seen == []
    assert job_store.get_job(old)['status'] == 'queued'
    assert queue.calls == []


@pytest.mark.parametrize('legacy', [False, True])
def test_report_rerun_paused_is_503_before_create(gate, monkeypatch, legacy):
    queue = Queue(gate)
    app = report_app(queue, monkeypatch, **({'create_or_attach_job': None} if legacy else {}))
    gate.blocked = True
    response = TestClient(app).post('/api/report/fixture.html/rerun', headers=HEADERS)
    assert response.status_code == 503
    assert job_store.find_active_job('fixture.html', 'rerun:final_recommendation') == {}
    assert queue.calls == []


def test_accepted_service_finishes_enqueue_when_armed_after_create(gate, monkeypatch):
    original = service.create_or_attach_active_job
    def arm_after_create(*args, **kwargs):
        result = original(*args, **kwargs)
        gate.blocked = True
        return result
    monkeypatch.setattr(service, 'create_or_attach_active_job', arm_after_create)
    queue = Queue(gate)
    result = service.create_or_attach_analysis_job(ticker='2330.TW', pipeline_id='v4',
        task_queue=queue, run_stock_analysis_job=lambda *args: None)
    assert result['status'] == 'queued'
    assert len(queue.calls) == 1
    assert gate.depth == 0


def test_paused_existing_job_sse_and_user_cancel_keep_existing_behavior(gate):
    job_id = job_store.create_job('2330.TW', 'v4')
    job_store.update_job(job_id, 'done', filename='fixture.html')
    job_store.append_event(job_id, {'type': 'done', 'filename': 'fixture.html'})
    queue = Queue(gate)
    app = analysis_app(queue)
    gate.blocked = True
    client = TestClient(app)
    assert client.get('/api/analysis-jobs/' + job_id).status_code == 200
    response = client.get('/api/analyze/2330.TW?pipeline=v4&job_id=' + job_id)
    assert response.status_code == 200
    assert 'fixture.html' in response.text
    assert client.get('/api/analysis-jobs/' + job_id + '/events').status_code == 200
    assert client.post('/api/analysis-jobs/' + job_id + '/cancel', headers=HEADERS).status_code == 200
    assert client.post('/api/analysis-jobs/' + job_id + '/cancel').status_code == 403
    assert queue.calls == []


def maintenance_plan():
    return {'campaign_id': 'offline-admission', 'old_revision': 'a' * 40,
        'new_revision': 'b' * 40, 'control_sha256': 'c' * 64, 'queue_name': 'canary-fixture',
        'canaries': [{'mode': f'v{i}', 'job_id': f'fixture-{i}', 'manifest_sha256': 'd' * 64}
                     for i in range(1, 5)]}


@pytest.fixture
def control(tmp_path, monkeypatch):
    root = tmp_path / 'maintenance'
    guard.initialize(root)
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    return root


@pytest.mark.parametrize('route', ['post', 'legacy', 'rerun'])
def test_real_uninitialized_control_is_503_and_does_not_create(tmp_path, monkeypatch, route):
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(tmp_path / 'not-initialized'))
    queue = Queue(guard, complete=True)
    app = report_app(queue, monkeypatch) if route == 'rerun' else analysis_app(queue)
    client = TestClient(app)
    if route == 'post':
        response = client.post('/api/analysis-jobs', headers=HEADERS, json={'ticker': '2330.TW', 'pipeline_id': 'v4'})
    elif route == 'legacy':
        response = client.get('/api/analyze/2330.TW?pipeline=v4')
    else:
        response = client.post('/api/report/fixture.html/rerun', headers=HEADERS)
    assert response.status_code == 503
    assert str(tmp_path) not in response.text
    assert queue.calls == []
    assert job_store.list_active_jobs() == []


@pytest.mark.parametrize('force', [False, True])
def test_real_armed_service_preserves_old_job_and_events(control, force):
    old = job_store.create_job('2330.TW', 'v4')
    before, events = job_store.get_job(old), job_store.get_events_since(old)
    queue = Queue(guard)
    guard.arm(control, maintenance_plan())
    with pytest.raises(guard.MaintenanceBlocked):
        service.create_or_attach_analysis_job(ticker='2330.TW', pipeline_id='v4', force=force,
            task_queue=queue, run_stock_analysis_job=lambda *args: None)
    assert job_store.get_job(old) == before
    assert job_store.get_events_since(old) == events
    assert queue.calls == []


def test_real_arm_after_create_waits_for_accepted_api_nested_enqueue(control, monkeypatch):
    created = threading.Event()
    armed = threading.Event()
    errors, states = [], []
    original = service.create_or_attach_active_job
    def create_then_wait(*args, **kwargs):
        result = original(*args, **kwargs)
        created.set()
        assert armed.wait(3), 'controller did not arm while the API held admission'
        return result
    monkeypatch.setattr(service, 'create_or_attach_active_job', create_then_wait)
    def controller():
        try:
            assert created.wait(3)
            guard.arm(control, maintenance_plan())
            try:
                guard.wait_drained(control, 0.05)
            except guard.MaintenanceError:
                pass
            states.append(guard.read_state(control)['phase'])
        except BaseException as error:
            errors.append(error)
        finally:
            armed.set()
    thread = threading.Thread(target=controller)
    thread.start()
    queue = Queue(guard)
    try:
        response = TestClient(analysis_app(queue)).post('/api/analysis-jobs', headers=HEADERS,
            json={'ticker': '2330.TW', 'pipeline_id': 'v4'})
    finally:
        thread.join(3)
    assert not thread.is_alive() and not errors
    assert states == ['arming']
    assert response.status_code == 200 and response.json()['status'] == 'queued'
    assert len(queue.calls) == 1
    guard.wait_drained(control, 0.5)
    assert guard.read_state(control)['phase'] == 'cooperatively_drained'
    blocked = TestClient(analysis_app(queue)).post('/api/analysis-jobs', headers=HEADERS,
        json={'ticker': '2317.TW', 'pipeline_id': 'v4'})
    assert blocked.status_code == 503 and len(queue.calls) == 1


@pytest.mark.parametrize('kind', ['post', 'legacy', 'rerun'])
def test_normal_business_error_is_not_masked_and_releases_lease(gate, monkeypatch, kind):
    def fail(*args, **kwargs):
        assert gate.depth > 0
        raise ValueError('original business failure')
    queue = Queue(gate)
    if kind == 'post':
        client = TestClient(analysis_app(queue, create_or_attach_analysis_job=fail))
        call = lambda: client.post('/api/analysis-jobs', headers=HEADERS, json={'ticker': '2330.TW'})
    elif kind == 'legacy':
        client = TestClient(analysis_app(queue, find_active_job=fail))
        call = lambda: client.get('/api/analyze/2330.TW')
    else:
        client = TestClient(report_app(queue, monkeypatch, create_or_attach_job=fail))
        call = lambda: client.post('/api/report/fixture.html/rerun', headers=HEADERS)
    with pytest.raises(ValueError, match='original business failure'):
        call()
    assert gate.depth == 0
    assert queue.calls == []


@pytest.mark.parametrize('route', ['post', 'rerun'])
def test_maintenance_does_not_replace_mutation_authorization(gate, monkeypatch, route):
    gate.blocked = True
    queue = Queue(gate)
    client = TestClient(report_app(queue, monkeypatch) if route == 'rerun' else analysis_app(queue))
    response = (client.post('/api/report/fixture.html/rerun') if route == 'rerun'
                else client.post('/api/analysis-jobs', json={'ticker': '2330.TW'}))
    assert response.status_code == 403
    assert gate.entries == 0 and queue.calls == []


def test_legacy_fallback_guard_failure_is_503_not_business_job_error(gate):
    queue = Queue(gate)
    def unavailable(*args, **kwargs):
        raise guard.MaintenanceUnavailable('sensitive control path /private/tmp/fixture-secret')
    queue.enqueue = unavailable
    client = TestClient(analysis_app(queue, create_or_attach_analysis_job=None))
    response = client.post('/api/analysis-jobs', headers=HEADERS, json={'ticker': '2330.TW'})
    assert response.status_code == 503
    assert 'fixture-secret' not in response.text
    jobs = job_store.list_active_jobs()
    assert len(jobs) == 1  # An integrity failure after create cannot be undone.
    assert not any(e['payload'].get('type') == 'error' for e in job_store.get_events_since(jobs[0]['job_id']))


@pytest.mark.parametrize('kind', ['service', 'orphan', 'legacy_post', 'legacy_get', 'rerun'])
def test_queue_business_failure_evidence_is_written_before_lease_exit(gate, monkeypatch, kind):
    if kind == 'orphan':
        job_store.create_job('2330.TW', 'v4')
    seen = []
    update, append = job_store.update_job, job_store.append_event
    def record_update(*args, **kwargs):
        seen.append(('update', gate.depth))
        return update(*args, **kwargs)
    def record_event(*args, **kwargs):
        seen.append(('event', gate.depth))
        return append(*args, **kwargs)
    monkeypatch.setattr(job_store, 'update_job', record_update)
    monkeypatch.setattr(job_store, 'append_event', record_event)
    monkeypatch.setattr(service, 'update_job', record_update)
    monkeypatch.setattr(service, 'append_event', record_event)
    queue = Queue(gate)
    def failure(*args, **kwargs):
        assert gate.depth > 0
        raise RuntimeError('offline queue unavailable')
    queue.enqueue = failure
    if kind in ('service', 'orphan'):
        result = service.create_or_attach_analysis_job(ticker='2330.TW', pipeline_id='v4',
            task_queue=queue, run_stock_analysis_job=lambda *args: None)
        assert result['status'] == 'failed'
    elif kind == 'rerun':
        response = TestClient(report_app(queue, monkeypatch)).post('/api/report/fixture.html/rerun', headers=HEADERS)
        assert response.status_code == 200
    else:
        client = TestClient(analysis_app(queue, create_or_attach_analysis_job=None))
        response = (client.post('/api/analysis-jobs', headers=HEADERS, json={'ticker': '2330.TW'})
                    if kind == 'legacy_post' else client.get('/api/analyze/2330.TW'))
        assert response.status_code == 200
    assert {'update', 'event'} <= {kind for kind, _ in seen}
    assert all(depth > 0 for _, depth in seen)
    assert gate.depth == 0


@pytest.mark.parametrize('route', ['legacy_get', 'legacy_post', 'rerun'])
def test_real_accepted_fallback_keeps_lease_through_enqueue(control, monkeypatch, route):
    original = job_store.create_job
    def create_and_arm(*args, **kwargs):
        job_id = original(*args, **kwargs)
        guard.arm(control, maintenance_plan())
        return job_id
    queue = Queue(guard, complete=True)
    if route == 'rerun':
        app = report_app(queue, monkeypatch, create_or_attach_job=None, create_job=create_and_arm)
        response = TestClient(app).post('/api/report/fixture.html/rerun', headers=HEADERS)
    else:
        app = analysis_app(queue, create_or_attach_analysis_job=None, create_job=create_and_arm)
        client = TestClient(app)
        response = (client.get('/api/analyze/2330.TW') if route == 'legacy_get'
                    else client.post('/api/analysis-jobs', headers=HEADERS, json={'ticker': '2330.TW'}))
    assert response.status_code == 200
    assert len(queue.calls) == 1
    guard.wait_drained(control, 0.5)
    assert guard.read_state(control)['phase'] == 'cooperatively_drained'
