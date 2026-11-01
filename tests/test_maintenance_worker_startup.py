"""Worker startup gating with private control state and dependency spies."""
from types import SimpleNamespace

import pytest

import maintenance_guard as guard
import worker_main


def plan():
    return {'campaign_id': 'private-startup', 'old_revision': 'a' * 40,
        'new_revision': 'b' * 40, 'control_sha256': 'c' * 64, 'queue_name': 'private-canary',
        'canaries': [{'mode': mode, 'job_id': mode, 'manifest_sha256': 'd' * 64}
                     for mode in ('v1', 'v2', 'v3', 'v4')]}


@pytest.mark.parametrize('role', ['queue', 'schedulers', 'maintenance'])
@pytest.mark.parametrize('state', ['arming', 'missing', 'corrupt'])
def test_worker_startup_denies_before_storage_runtime_or_reconciliation(tmp_path, monkeypatch, role, state):
    root = tmp_path / 'maintenance'
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    if state != 'missing':
        guard.initialize(root)
        guard.arm(root, plan())
        if state == 'corrupt': (root / 'state.json').write_text('invalid')
    calls = []
    monkeypatch.setattr(worker_main, 'ensure_runtime_storage', lambda **kw: calls.append('storage'))
    def factory(settings):
        calls.append('factory')
        raise AssertionError('Must not create runtime while maintenance is unavailable')
    monkeypatch.setattr(worker_main, 'emit_log', lambda text: calls.append(('log', text)))
    worker_main.run_role(role, runtime_factory=factory)
    assert all(isinstance(item, tuple) and item[0] == 'log' for item in calls)
    assert calls and str(root) not in calls[0][1]


def test_startup_admitted_before_arm_finishes_reconciliation_under_same_lease(tmp_path, monkeypatch):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    calls = []
    def storage(**kw):
        guard.arm(root, plan())
        assert not guard.wait_drained(root, 0)
        calls.append('storage')
    def factory(settings):
        with guard.admission(): calls.append('factory')
        return SimpleNamespace(task_queue=SimpleNamespace(backend_name='rq'), close=lambda: calls.append('close'))
    def reconcile(runtime):
        with guard.admission(): calls.append('reconcile')
        assert not guard.wait_drained(root, 0)
    def work(runtime, **kw):
        # The startup lease is not authority to consume future jobs.
        assert guard.wait_drained(root, 0)
        with pytest.raises(guard.MaintenanceBlocked):
            with guard.admission(): pass
        calls.append('worker')
    monkeypatch.setattr(worker_main, 'ensure_runtime_storage', storage)
    monkeypatch.setattr(worker_main, 'reconcile_abandoned_rq_jobs', reconcile)
    monkeypatch.setattr(worker_main, 'run_rq_worker', work)
    worker_main.run_role('queue', runtime_factory=factory)
    assert calls == ['storage', 'factory', 'reconcile', 'worker', 'close']


def test_startup_failure_closes_constructed_runtime_before_lease_release(tmp_path, monkeypatch):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    monkeypatch.setattr(worker_main, 'ensure_runtime_storage', lambda **kw: None)
    closed = []
    def close():
        assert not guard.wait_drained(root, 0)
        closed.append(True)
    runtime = SimpleNamespace(task_queue=SimpleNamespace(backend_name='rq'), close=close)
    def reconcile(value):
        guard.arm(root, plan())
        raise ValueError('preserved business exception')
    monkeypatch.setattr(worker_main, 'reconcile_abandoned_rq_jobs', reconcile)
    with pytest.raises(ValueError, match='business exception'):
        worker_main.run_role('queue', runtime_factory=lambda settings: runtime)
    assert closed == [True]
    assert guard.wait_drained(root, 0)
