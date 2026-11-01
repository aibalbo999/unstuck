"""Cooperative RQ dequeue isolation, never a formal canary allowlist."""
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import subprocess
from types import ModuleType, SimpleNamespace
import sys

import pytest


@pytest.fixture
def fake_gate(monkeypatch):
    module = ModuleType('maintenance_guard')
    class MaintenanceError(RuntimeError): pass
    class MaintenanceBlocked(MaintenanceError): pass
    class MaintenanceUnavailable(MaintenanceError): pass
    class MaintenanceBusy(MaintenanceError): pass
    state = {'phase': 'normal', 'active': 0, 'entered': 0, 'released': 0}
    @contextmanager
    def admission(root=None):
        if state['phase'] != 'normal':
            raise MaintenanceBlocked('maintenance is armed')
        state['active'] += 1
        state['entered'] += 1
        try:
            yield
        finally:
            state['active'] -= 1
            state['released'] += 1
    for name, value in locals().copy().items():
        if name.startswith('Maintenance') or name == 'admission':
            setattr(module, name, value)
    monkeypatch.setitem(sys.modules, 'maintenance_guard', module)
    return state


def test_armed_gate_does_not_start_rq_consumption(monkeypatch, fake_gate):
    import worker_rq_scheduler
    from worker_queue_runners import run_rq_worker
    calls = []
    class FakeSimpleWorker:
        def __init__(self, queues, *, connection): pass
        def work(self, **kwargs): calls.append('dequeue')
    monkeypatch.setattr(worker_rq_scheduler, 'BoundedSchedulerWorker', FakeSimpleWorker)
    fake_gate['phase'] = 'arming'
    runtime = SimpleNamespace(task_queue=SimpleNamespace(queue='own-queue', redis='not-real-redis'))
    run_rq_worker(runtime, emit=calls.append)
    assert 'dequeue' not in calls
    assert any('maintenance' in item for item in calls)


def real_rq_worker(monkeypatch, state, pop, *, perform=None, fetch=None, modern=False, fake_scheduler_signals=True):
    """Real installed RQ loops/hooks, replacing only Redis and process I/O."""
    from rq import Queue, SimpleWorker
    from rq.worker import StopRequested
    from maintenance_rq_worker import maintenance_worker_class
    import rq.queue
    import rq.worker
    events = []
    queue = SimpleNamespace(name='owned', key='rq:queue:owned')
    class Job:
        @classmethod
        def fetch(cls, job_id, **kwargs):
            if fetch is not None: fetch(job_id)
            return SimpleNamespace(id=job_id, description='OFFLINE FIXTURE')
    class OfflineQueue(Queue):
        @classmethod
        def lpop(cls, queue_keys, timeout, connection=None):
            return pop('lpop', timeout)
        @classmethod
        def lmove(cls, connection, queue_key, timeout):
            return pop('lmove', timeout)
        @classmethod
        def from_queue_key(cls, *args, **kwargs):
            return queue
    class OfflineSimpleWorker(SimpleWorker):
        @property
        def should_run_maintenance_tasks(self): return False
        def bootstrap(self, *args): events.append(('bootstrap', state['active']))
        def check_for_suspension(self, burst): pass
        def _install_signal_handlers(self): pass
        def procline(self, message): pass
        def heartbeat(self): events.append(('heartbeat', state['active']))
        def set_state(self, value): self._state = value
        def get_redis_server_version(self): return (6, 2, 0)
        def register_death(self): events.append(('death', state['active']))
        def unsubscribe(self): events.append(('unsubscribe', state['active']))
        def _start_scheduler(self, *args):
            process = SimpleNamespace(pid=987654321, join=lambda: events.append(('scheduler_join', state['active'])))
            self.scheduler = SimpleNamespace(_process=process)
        def perform_job(self, job, queue):
            events.append(('job', state['active']))
            try:
                if perform is not None: perform(self, job)
            finally:
                events.append(('job_cleanup', state['active']))
    monkeypatch.setattr(rq.queue, 'get_version', lambda connection: (6, 2, 0) if modern else (6, 0, 0))
    if fake_scheduler_signals:
        monkeypatch.setattr(rq.worker.os, 'kill', lambda pid, signum: events.append(('scheduler_signal', pid, signum)))
    guarded = maintenance_worker_class(OfflineSimpleWorker)
    worker = object.__new__(guarded)
    worker.name = 'offline-maintenance-worker'
    worker.queue_class, worker.job_class = OfflineQueue, Job
    worker.queues = worker._ordered_queues = [queue]
    worker.connection = object()
    worker.serializer = None
    worker.scheduler = None
    worker.worker_ttl = 420
    worker.log_job_description = False
    worker.log = logging.getLogger('offline-maintenance-rq')
    worker._state = 'idle'
    worker._is_horse = False
    worker._stop_requested = False
    worker._dequeue_strategy = None
    return worker, events, OfflineQueue


@pytest.mark.parametrize('modern', [False, True])
def test_real_rq_pop_lease_survives_arm_through_job_cleanup(monkeypatch, fake_gate, modern):
    seen = []
    def pop(kind, timeout):
        assert fake_gate['active'] == 1
        seen.append((kind, timeout))
        fake_gate['phase'] = 'arming'
        return b'rq:queue:owned', b'job'
    worker, events, original = real_rq_worker(monkeypatch, fake_gate, pop, modern=modern)
    assert worker.work(max_jobs=1, with_scheduler=True) is True
    assert seen == [('lmove' if modern else 'lpop', 5)]
    assert ('job', 1) in events and ('job_cleanup', 1) in events
    assert worker.queue_class is original
    assert fake_gate['active'] == 0
    assert fake_gate['entered'] == fake_gate['released'] == 2
    assert len([e for e in events if e[0] == 'scheduler_signal']) == 1
    assert ('scheduler_join', 0) in events


@pytest.mark.parametrize('kind', ['timeout', 'stale'])
def test_internal_retry_releases_and_rechecks_before_another_pop(monkeypatch, fake_gate, kind):
    from rq.exceptions import DequeueTimeout, NoSuchJobError
    calls = []
    def pop(operation, timeout):
        assert fake_gate['active'] == 1
        calls.append(operation)
        if kind == 'timeout':
            fake_gate['phase'] = 'arming'
            raise DequeueTimeout(timeout, ['rq:queue:owned'])
        return b'rq:queue:owned', b'stale'
    def fetch(job_id):
        assert fake_gate['active'] == 1
        fake_gate['phase'] = 'arming'
        raise NoSuchJobError('OFFLINE stale ID')
    worker, events, original = real_rq_worker(monkeypatch, fake_gate, pop, fetch=fetch)
    assert worker.work(with_scheduler=True) is False
    assert calls == ['lpop']
    assert worker.maintenance_pause_reason == 'MaintenanceBlocked'
    assert fake_gate['active'] == 0
    assert not any(e[0] == 'job' for e in events)
    assert worker.queue_class is original
    assert len([e for e in events if e[0] == 'scheduler_signal']) == 1


def test_empty_burst_queue_releases_lease_and_keeps_nonblocking_timeout(monkeypatch, fake_gate):
    calls = []
    def pop(kind, timeout):
        assert fake_gate['active'] == 1
        calls.append(timeout)
        return None
    worker, events, original = real_rq_worker(monkeypatch, fake_gate, pop)
    assert worker.work(burst=True) is False
    assert calls == [None]
    assert fake_gate['active'] == 0
    assert worker.queue_class is original


@pytest.mark.parametrize('error_type', [RuntimeError, KeyboardInterrupt, SystemExit])
def test_dequeue_exception_always_restores_queue_and_releases(monkeypatch, fake_gate, error_type):
    def pop(kind, timeout):
        assert fake_gate['active'] == 1
        raise error_type('OFFLINE stop')
    worker, events, original = real_rq_worker(monkeypatch, fake_gate, pop)
    with pytest.raises(error_type):
        worker.dequeue_job_and_maintain_ttl(100)
    assert fake_gate['active'] == 0
    assert worker.queue_class is original


def test_work_interruption_between_dequeue_and_execute_releases_after_teardown(monkeypatch, fake_gate):
    from rq.worker import StopRequested
    worker, events, original = real_rq_worker(monkeypatch, fake_gate,
        lambda *args: (b'rq:queue:owned', b'job'))
    def interrupted(*args): raise StopRequested()
    worker.execute_job = interrupted
    assert worker.work(with_scheduler=True) is False
    assert ('unsubscribe', 1) in events
    assert fake_gate['active'] == 0
    assert worker.queue_class is original


def test_execute_exception_retains_lease_through_cleanup(monkeypatch, fake_gate):
    def failed(worker, job): raise RuntimeError('OFFLINE failed execution')
    worker, events, original = real_rq_worker(monkeypatch, fake_gate,
        lambda *args: (b'rq:queue:owned', b'job'), perform=failed)
    job, queue = worker.dequeue_job_and_maintain_ttl(None)
    with pytest.raises(RuntimeError, match='OFFLINE failed'):
        worker.execute_job(job, queue)
    assert ('job_cleanup', 1) in events
    assert fake_gate['active'] == 0


def test_direct_execution_without_dequeue_lease_is_rejected(monkeypatch, fake_gate):
    worker, events, original = real_rq_worker(monkeypatch, fake_gate, lambda *args: None)
    with pytest.raises(RuntimeError, match='owned dequeue'):
        worker.execute_job(object(), object())
    assert not any(e[0] == 'job' for e in events)


def offline_plan():
    return {'campaign_id': 'OFFLINE-TEST-ONLY', 'old_revision': 'a' * 40,
        'new_revision': 'b' * 40, 'control_sha256': 'c' * 64, 'queue_name': 'canary.offline',
        'canaries': [{'mode': f'v{i}', 'job_id': f'canary-{i}', 'manifest_sha256': 'd' * 64} for i in range(1, 5)]}


def child_control(tmp_path, root, *, arm=False):
    code = '''import json, sys
sys.path.insert(0, sys.argv[2])
import maintenance_guard as guard
root = sys.argv[1]
if sys.argv[3] != 'null': guard.arm(root, json.loads(sys.argv[3]))
print(json.dumps({'drained': guard.wait_drained(root, 0), 'phase': guard.read_state(root)['phase']}))
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(root),
        str(Path(__file__).resolve().parents[1] / 'backend'), json.dumps(offline_plan() if arm else None)],
        env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}, cwd=tmp_path,
        capture_output=True, text=True, timeout=5, check=True)
    return json.loads(result.stdout)


def test_real_guard_child_arm_preserves_accepted_job_and_blocks_next_pop(tmp_path, monkeypatch):
    import maintenance_guard as guard
    root = tmp_path / 'gate'
    guard.initialize(root)
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    original = guard.admission
    counts = {'active': 0}
    @contextmanager
    def traced(root=None):
        with original(root) as lease:
            counts['active'] += 1
            try: yield lease
            finally: counts['active'] -= 1
    monkeypatch.setattr(guard, 'admission', traced)
    pops = []
    def pop(kind, timeout):
        assert counts['active'] == 1
        pops.append(kind)
        assert child_control(tmp_path, root, arm=True) == {'drained': False, 'phase': 'arming'}
        return b'rq:queue:owned', b'accepted-before-arm'
    def perform(worker, job):
        assert counts['active'] == 1
        assert child_control(tmp_path, root) == {'drained': False, 'phase': 'arming'}
        with guard.admission():
            assert job.id == 'accepted-before-arm'
    worker, events, original_queue = real_rq_worker(monkeypatch, counts, pop,
        perform=perform, fake_scheduler_signals=False)
    assert worker.work() is True
    assert pops == ['lpop']
    assert ('job_cleanup', 1) in events
    assert counts['active'] == 0
    assert worker.maintenance_pause_reason == 'MaintenanceBlocked'
    assert worker.queue_class is original_queue
    assert child_control(tmp_path, root) == {'drained': True, 'phase': 'cooperatively_drained'}


@pytest.mark.parametrize('case', ['missing', 'corrupt'])
def test_real_unavailable_gate_never_initializes_or_dequeues(tmp_path, monkeypatch, case):
    import maintenance_guard as guard
    root = tmp_path / 'gate'
    if case == 'corrupt':
        guard.initialize(root)
        (root / 'state.json').write_bytes(b'{}')
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    def forbidden(*args): pytest.fail('unavailable gate attempted Redis pop')
    worker, events, original = real_rq_worker(monkeypatch, {'active': 0}, forbidden)
    assert worker.work() is False
    assert worker.maintenance_pause_reason == 'MaintenanceUnavailable'
    assert events == []
    if case == 'missing': assert not root.exists()


def test_adapter_import_is_inert_in_fresh_process(tmp_path):
    code = '''import sys
sys.path.insert(0, sys.argv[1])
import maintenance_rq_worker
assert not {'config', 'maintenance_guard', 'rq'} & set(sys.modules)
'''
    subprocess.run([sys.executable, '-I', '-B', '-c', code,
        str(Path(__file__).resolve().parents[1] / 'backend')],
        env={'PATH': '/usr/bin:/bin'}, cwd=tmp_path, check=True, capture_output=True, timeout=5)
