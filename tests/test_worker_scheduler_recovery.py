"""Exercise installed RQ takeover/due checks with only I/O boundaries simulated."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from redis import Redis
from rq import SimpleWorker
from rq.defaults import DEFAULT_WORKER_TTL
from rq.exceptions import DequeueTimeout
from rq.job import Job
from rq.scheduler import RQScheduler

import rq.scheduler as scheduler_module
import rq.worker as worker_module
import worker_queue_runners


@pytest.fixture
def launched_worker(monkeypatch):
    original_init = SimpleWorker.__init__
    captured = []

    def isolated_init(self, *args, **kwargs):
        kwargs['prepare_for_work'] = False  # Do not issue CLIENT SETNAME/LIST.
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(SimpleWorker, '__init__', isolated_init)
    monkeypatch.setattr(SimpleWorker, 'work', lambda self, **kwargs: captured.append((self, kwargs)))

    def launch(*, burst=False, max_jobs=None):
        # This object never connects: all external I/O is replaced below.
        connection = Redis(host='isolated-no-network.invalid')
        queue = SimpleNamespace(queue='analysis.normal', redis=connection,
                                queues={'analysis.normal': 'analysis.normal'})
        worker_queue_runners.run_rq_worker(SimpleNamespace(task_queue=queue), burst=burst, max_jobs=max_jobs)
        return captured[-1]
    return launch


@pytest.mark.parametrize('burst,max_jobs', [(False, None), (True, 2)])
def test_launcher_bounds_polling_without_changing_ttl_or_work_options(launched_worker, burst, max_jobs):
    worker, kwargs = launched_worker(burst=burst, max_jobs=max_jobs)
    assert worker.worker_ttl == DEFAULT_WORKER_TTL == 420
    assert worker.maintenance_interval == 30
    assert worker.dequeue_timeout == 30
    assert worker.execute_job.__func__ is SimpleWorker.execute_job
    assert kwargs == {'burst': burst, 'max_jobs': max_jobs, 'with_scheduler': True}


class Clock:
    seconds = 0.0
    def now(self):
        return datetime(2026, 9, 23, 12, 43, 40, tzinfo=timezone.utc) + timedelta(seconds=self.seconds)


class MemoryRedis:
    """Only locks and scheduled sorted-set commands needed by real RQ methods."""
    def __init__(self, clock):
        self.clock = clock
        self.locks = {}
        self.scheduled = {'later': 120}
        self.enqueued = []

    def set(self, key, value, *, nx, ex):
        assert nx is True  # Recovery must retain atomic ownership acquisition.
        existing = self.locks.get(key)
        if existing and existing[1] > self.clock.seconds:
            return False
        self.locks[key] = (value, self.clock.seconds + ex)
        return True

    def zrangebyscore(self, key, minimum, maximum, *, start, num):
        return [job_id.encode() for job_id, due in self.scheduled.items() if minimum <= due <= maximum][start:start + num]

    def zrem(self, key, job_id):
        return self.scheduled.pop(job_id, None)

    def pipeline(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self):
        return []


@pytest.fixture
def takeover(monkeypatch, launched_worker):
    worker, _ = launched_worker()
    clock = Clock()
    memory = MemoryRedis(clock)
    scheduler = RQScheduler(worker.queues, connection=worker.connection)
    scheduler._connection = memory
    started = []
    lock = scheduler.get_locking_key('analysis.normal')
    memory.locks[lock] = ('previous-owner', 61)

    def start():
        started.append(clock.seconds)
        scheduler._process = SimpleNamespace(is_alive=lambda: True)

    monkeypatch.setattr(scheduler, 'start', start)  # No subprocess or signal handlers.
    monkeypatch.setattr(worker_module, 'RQScheduler', lambda *args, **kwargs: scheduler)
    monkeypatch.setattr(worker_module, 'utcnow', clock.now)
    monkeypatch.setattr(worker, 'clean_registries', lambda: setattr(worker, 'last_cleaned_at', clock.now()))
    worker._start_scheduler()
    worker.run_maintenance_tasks()
    assert not started and scheduler.acquired_locks == set()
    return worker, scheduler, clock, memory, lock, started


def test_expired_startup_lock_is_taken_over_by_normal_maintenance(takeover):
    worker, scheduler, clock, memory, lock, started = takeover
    for second in (31, 62):
        clock.seconds = second
        assert worker.should_run_maintenance_tasks
        worker.run_maintenance_tasks()
        if second == 31:
            assert not started
            assert memory.locks[lock][0] == 'previous-owner'
    assert started == [62]
    assert scheduler.acquired_locks == {'analysis.normal'}
    assert memory.locks[lock][0] != 'previous-owner'
    assert memory.scheduled == {'later': 120}  # Taking ownership never promotes jobs itself.


def test_active_scheduler_owner_is_not_replaced(takeover):
    worker, scheduler, clock, memory, lock, started = takeover
    for second in (31, 62, 93, 124):
        clock.seconds = second
        memory.locks[lock] = ('live-owner', second + 61)
        if worker.should_run_maintenance_tasks:
            worker.run_maintenance_tasks()
        assert memory.locks[lock][0] == 'live-owner'
    assert not started and not scheduler.acquired_locks
    assert memory.scheduled == {'later': 120}


def test_idle_dequeue_loop_rechecks_expired_locks_with_bounded_wait(monkeypatch, takeover):
    worker, scheduler, clock, memory, lock, started = takeover
    waits = []
    class StopProbe(Exception):
        pass

    def dequeue(*args, **kwargs):
        timeout = args[1]
        waits.append(timeout)
        assert timeout <= 30
        if started:
            raise StopProbe()
        clock.seconds += timeout + 0.01
        raise DequeueTimeout()

    monkeypatch.setattr(worker, 'heartbeat', lambda *a, **kw: None)
    monkeypatch.setattr(worker, 'set_state', lambda *a, **kw: None)
    monkeypatch.setattr(worker, 'procline', lambda *a, **kw: None)
    monkeypatch.setattr(worker.queue_class, 'dequeue_any', dequeue)
    with pytest.raises(StopProbe):
        worker.dequeue_job_and_maintain_ttl(worker.dequeue_timeout)
    assert started and 61 <= started[0] <= 91
    assert waits and max(waits) == 30
    assert memory.scheduled == {'later': 120}


def test_real_rq_scheduler_keeps_future_due_time_and_enqueues_only_once(monkeypatch, takeover):
    worker, scheduler, clock, memory, lock, started = takeover
    clock.seconds = 62
    scheduler.acquire_locks(auto_start=True)
    monkeypatch.setattr(scheduler_module, 'current_timestamp', lambda: int(clock.seconds))
    monkeypatch.setattr(Job, 'fetch_many', lambda ids, **kwargs: [Job(job_id, connection=worker.connection) for job_id in ids])

    class QueueSink:
        def __init__(self, *args, **kwargs):
            pass
        def _enqueue_job(self, job, *, pipeline, at_front):
            memory.enqueued.append(job.id)

    monkeypatch.setattr(scheduler_module, 'Queue', QueueSink)
    for second in (62, 90, 119):
        clock.seconds = second
        scheduler.enqueue_scheduled_jobs()
        assert memory.scheduled == {'later': 120} and memory.enqueued == []
    clock.seconds = 120
    scheduler.enqueue_scheduled_jobs()
    scheduler.enqueue_scheduled_jobs()
    assert memory.scheduled == {} and memory.enqueued == ['later']


def test_installed_default_explains_observed_startup_gap():
    worker = SimpleWorker(['analysis.normal'], connection=Redis(host='isolated-no-network.invalid'), prepare_for_work=False)
    assert worker.maintenance_interval == 600
    assert worker.dequeue_timeout == 405
