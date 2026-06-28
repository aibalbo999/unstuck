import asyncio
import inspect
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import decision_tracking_scheduler
import watchlist_scheduler
import worker_main


ROOT = Path(__file__).resolve().parents[1]


class FakeWorkerRuntime:
    def __init__(self, calls):
        self.calls = calls
        self.settings = SimpleNamespace(output_dir="/tmp/reports")
        self.task_queue = type("TaskQueue", (), {"queue": "queue", "redis": "redis"})()
        self.data_refresh_service = "refresh-service"

    def close(self):
        self.calls.append("close")


def test_queue_role_only_runs_rq_worker_and_closes_runtime(monkeypatch):
    calls = []
    runtime = FakeWorkerRuntime(calls)

    monkeypatch.setattr(worker_main, "reconcile_abandoned_rq_jobs", lambda value: calls.append(("reconcile", value)) or 0)
    monkeypatch.setattr(
        worker_main,
        "run_rq_worker",
        lambda value, *, burst=False, max_jobs=None: calls.append(("queue", value, burst, max_jobs)),
    )

    worker_main.run_role("queue", runtime_factory=lambda _settings: runtime, burst=True, max_jobs=1)

    assert calls == [("reconcile", runtime), ("queue", runtime, True, 1), "close"]


def test_run_role_initializes_runtime_storage_before_creating_runtime(monkeypatch):
    calls = []
    runtime = FakeWorkerRuntime(calls)

    def fake_ensure_runtime_storage(**kwargs):
        calls.append(("ensure-storage", kwargs))

    def fake_runtime_factory(settings):
        calls.append(("factory", settings))
        return runtime

    monkeypatch.setattr(worker_main, "ensure_runtime_storage", fake_ensure_runtime_storage)
    monkeypatch.setattr(worker_main, "reconcile_abandoned_rq_jobs", lambda value: calls.append(("reconcile", value)) or 0)
    monkeypatch.setattr(
        worker_main,
        "run_rq_worker",
        lambda value, *, burst=False, max_jobs=None: calls.append(("queue", value, burst, max_jobs)),
    )

    worker_main.run_role("queue", runtime_factory=fake_runtime_factory, burst=True, max_jobs=1)

    assert calls[0][0] == "ensure-storage"
    assert calls[1][0] == "factory"
    assert calls[0][1]["output_dir"] == calls[1][1].output_dir
    assert calls[-1] == "close"


def test_reconcile_abandoned_rq_jobs_marks_only_sqlite_jobs_missing_from_rq(monkeypatch):
    calls = []
    runtime = FakeWorkerRuntime(calls)
    runtime.task_queue.queue = object()
    active_jobs = [
        {"job_id": "analysis-present", "pipeline_id": "v1"},
        {"job_id": "rerun-present", "pipeline_id": "rerun:full_report"},
        {"job_id": "missing", "pipeline_id": "v4"},
    ]

    monkeypatch.setattr(worker_main, "list_active_jobs", lambda: active_jobs)
    monkeypatch.setattr(
        worker_main,
        "_rq_active_job_ids",
        lambda _queue: {"analysis:analysis-present", "report-rerun:rerun-present"},
    )

    def fake_mark_jobs_abandoned(job_ids, reason):
        calls.append((list(job_ids), reason))
        return len(job_ids)

    monkeypatch.setattr(worker_main, "mark_jobs_abandoned", fake_mark_jobs_abandoned)
    monkeypatch.setattr(worker_main, "emit_log", calls.append)

    abandoned = worker_main.reconcile_abandoned_rq_jobs(runtime)

    assert abandoned == 1
    assert calls[0][0] == ["missing"]
    assert "Redis/RQ" in calls[0][1]
    assert any("abandoned" in str(call) and "1" in str(call) for call in calls)


def test_scheduler_role_runs_scheduler_process_and_closes_runtime(monkeypatch):
    calls = []
    runtime = FakeWorkerRuntime(calls)

    async def fake_run_scheduler_process(value):
        calls.append(("schedulers", value))

    monkeypatch.setattr(worker_main, "run_scheduler_process", fake_run_scheduler_process)

    worker_main.run_role("schedulers", runtime_factory=lambda _settings: runtime)

    assert calls == [("schedulers", runtime), "close"]


def test_maintenance_role_runs_maintenance_process_and_closes_runtime(monkeypatch):
    calls = []
    runtime = FakeWorkerRuntime(calls)

    async def fake_run_maintenance_process(value):
        calls.append(("maintenance", value))

    monkeypatch.setattr(worker_main, "run_maintenance_process", fake_run_maintenance_process)

    worker_main.run_role("maintenance", runtime_factory=lambda _settings: runtime)

    assert calls == [("maintenance", runtime), "close"]


def test_all_role_uses_spawn_and_three_children(monkeypatch):
    class FakeProcess:
        def __init__(self, target, args):
            self.target = target
            self.args = args
            self.started = False
            self.joined = False
            self.exitcode = 0

        def start(self):
            self.started = True

        def join(self, timeout=None):
            self.joined = True

        def is_alive(self):
            return False

        def terminate(self):
            raise AssertionError("terminate should not be called on normal exit")

    class FakeSpawnContext:
        def __init__(self):
            self.processes = []

        def assert_method(self, method):
            assert method == "spawn"
            return self

        def Process(self, *, target, args):
            process = FakeProcess(target, args)
            self.processes.append(process)
            return process

    context = FakeSpawnContext()
    monkeypatch.setattr(worker_main.multiprocessing, "get_context", context.assert_method)

    exit_code = worker_main.run_all_roles()

    assert exit_code == 0
    assert [process.args[0] for process in context.processes] == ["queue", "schedulers", "maintenance"]
    assert all(process.started for process in context.processes)
    assert all(process.joined for process in context.processes)


def test_all_role_terminates_siblings_when_child_exits_nonzero(monkeypatch):
    class FakeProcess:
        def __init__(self, target, args):
            self.args = args
            self.started = False
            self.joined = False
            self.terminated = False
            self.exitcode = None if args[0] == "queue" else (1 if args[0] == "schedulers" else 0)

        def start(self):
            self.started = True

        def join(self, timeout=None):
            self.joined = True

        def is_alive(self):
            return self.exitcode is None and not self.terminated

        def terminate(self):
            self.terminated = True
            self.exitcode = -15

    class FakeSpawnContext:
        def __init__(self):
            self.processes = []

        def assert_method(self, method):
            assert method == "spawn"
            return self

        def Process(self, *, target, args):
            process = FakeProcess(target, args)
            self.processes.append(process)
            return process

    context = FakeSpawnContext()
    monkeypatch.setattr(worker_main.multiprocessing, "get_context", context.assert_method)

    exit_code = worker_main.run_all_roles()

    assert exit_code == 1
    queue_process = context.processes[0]
    assert queue_process.terminated is True


def test_all_role_start_failure_only_joins_started_children(monkeypatch):
    class FakeProcess:
        def __init__(self, target, args):
            self.args = args
            self.started = False
            self.joined = False
            self.terminated = False
            self.exitcode = None

        def start(self):
            if self.args[0] == "schedulers":
                raise RuntimeError("start failed")
            self.started = True

        def join(self, timeout=None):
            if not self.started:
                raise AssertionError("can only join a started process")
            self.joined = True

        def is_alive(self):
            return self.started and self.exitcode is None and not self.terminated

        def terminate(self):
            self.terminated = True
            self.exitcode = -15

    class FakeSpawnContext:
        def __init__(self):
            self.processes = []

        def assert_method(self, method):
            assert method == "spawn"
            return self

        def Process(self, *, target, args):
            process = FakeProcess(target, args)
            self.processes.append(process)
            return process

    context = FakeSpawnContext()
    monkeypatch.setattr(worker_main.multiprocessing, "get_context", context.assert_method)

    with pytest.raises(RuntimeError, match="start failed"):
        worker_main.run_all_roles()

    queue_process, scheduler_process, maintenance_process = context.processes
    assert queue_process.terminated is True
    assert queue_process.joined is True
    assert scheduler_process.joined is False
    assert maintenance_process.joined is False


def test_all_role_signal_during_start_does_not_join_unstarted_children(monkeypatch):
    class FakeProcess:
        def __init__(self, target, args):
            self.args = args
            self.started = False
            self.joined = False
            self.terminated = False
            self.exitcode = None

        def start(self):
            self.started = True
            if self.args[0] == "queue":
                handler = worker_main.signal.getsignal(worker_main.signal.SIGTERM)
                handler(worker_main.signal.SIGTERM, None)

        def join(self, timeout=None):
            if not self.started:
                raise AssertionError("can only join a started process")
            self.joined = True

        def is_alive(self):
            return self.started and self.exitcode is None and not self.terminated

        def terminate(self):
            self.terminated = True
            self.exitcode = -15

    class FakeSpawnContext:
        def __init__(self):
            self.processes = []

        def assert_method(self, method):
            assert method == "spawn"
            return self

        def Process(self, *, target, args):
            process = FakeProcess(target, args)
            self.processes.append(process)
            return process

    context = FakeSpawnContext()
    monkeypatch.setattr(worker_main.multiprocessing, "get_context", context.assert_method)

    exit_code = worker_main.run_all_roles()

    queue_process, scheduler_process, maintenance_process = context.processes
    assert exit_code == 130
    assert queue_process.terminated is True
    assert queue_process.joined is True
    assert scheduler_process.started is False
    assert scheduler_process.joined is False
    assert maintenance_process.started is False
    assert maintenance_process.joined is False


def test_child_main_suppresses_keyboard_interrupt_shutdown(monkeypatch):
    def fake_run_role(role):
        assert role == "maintenance"
        raise KeyboardInterrupt()

    monkeypatch.setattr(worker_main, "run_role", fake_run_role)

    worker_main.child_main("maintenance")


def test_worker_main_rejects_unknown_role():
    with pytest.raises(ValueError, match="Unknown worker role"):
        worker_main.run_role("bogus", runtime_factory=lambda _settings: FakeWorkerRuntime([]))


def test_scheduler_modules_expose_public_run_coroutines():
    assert inspect.iscoroutinefunction(watchlist_scheduler.run_watchlist_scheduler)
    assert inspect.iscoroutinefunction(decision_tracking_scheduler.run_decision_tracking_scheduler)


def test_scheduler_process_starts_both_schedulers_and_cancels_them(monkeypatch):
    calls = []
    runtime = FakeWorkerRuntime(calls)
    started = asyncio.Event()

    async def fake_watchlist_scheduler(**kwargs):
        calls.append(("watchlist", kwargs["data_service"]))
        if len(calls) == 2:
            started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            calls.append("watchlist-cancelled")
            raise

    async def fake_decision_tracking_scheduler(**kwargs):
        calls.append(("decision", kwargs["get_refresh_service"]()))
        if len(calls) == 2:
            started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            calls.append("decision-cancelled")
            raise

    monkeypatch.setattr(worker_main, "run_watchlist_scheduler", fake_watchlist_scheduler)
    monkeypatch.setattr(worker_main, "run_decision_tracking_scheduler", fake_decision_tracking_scheduler)

    async def exercise():
        task = asyncio.create_task(worker_main.run_scheduler_process(runtime))
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())

    assert ("watchlist", "refresh-service") in calls
    assert ("decision", "refresh-service") in calls
    assert "watchlist-cancelled" in calls
    assert "decision-cancelled" in calls


def test_run_rq_worker_rejects_non_rq_queue():
    runtime = FakeWorkerRuntime([])
    runtime.task_queue = object()

    with pytest.raises(RuntimeError, match="RQ"):
        worker_main.run_rq_worker(runtime)


def test_run_rq_worker_uses_simple_worker_to_avoid_macos_fork_abort(monkeypatch):
    import rq

    calls = []
    runtime = FakeWorkerRuntime(calls)

    class ForkingWorker:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("forking Worker should not be used by the local launcher")

    class FakeSimpleWorker:
        def __init__(self, queues, *, connection):
            calls.append(("simple-worker", queues, connection))

        def work(self, *, burst=False, max_jobs=None, with_scheduler=False):
            calls.append(("work", burst, max_jobs, with_scheduler))

    monkeypatch.setattr(rq, "Worker", ForkingWorker)
    monkeypatch.setattr(rq, "SimpleWorker", FakeSimpleWorker)

    worker_main.run_rq_worker(runtime, burst=True, max_jobs=2)

    assert calls == [
        ("simple-worker", ["queue"], "redis"),
        ("work", True, 2, False),
    ]


def test_run_rq_worker_suppresses_redis_disconnect_after_warm_shutdown(monkeypatch):
    import rq
    from redis.exceptions import ConnectionError as RedisConnectionError

    calls = []
    runtime = FakeWorkerRuntime(calls)

    class FakeSimpleWorker:
        def __init__(self, queues, *, connection):
            self._shutdown_requested_date = object()
            calls.append(("simple-worker", queues, connection))

        def work(self, *, burst=False, max_jobs=None, with_scheduler=False):
            calls.append(("work", burst, max_jobs, with_scheduler))
            raise RedisConnectionError("Connection closed by server.")

    monkeypatch.setattr(rq, "SimpleWorker", FakeSimpleWorker)
    monkeypatch.setattr(worker_main, "emit_log", calls.append)

    worker_main.run_rq_worker(runtime)

    assert ("work", False, None, False) in calls
    assert "queue worker stopped after Redis shutdown." in calls


def test_run_rq_worker_reraises_redis_disconnect_before_shutdown(monkeypatch):
    import rq
    from redis.exceptions import ConnectionError as RedisConnectionError

    runtime = FakeWorkerRuntime([])

    class FakeSimpleWorker:
        def __init__(self, queues, *, connection):
            pass

        def work(self, *, burst=False, max_jobs=None, with_scheduler=False):
            raise RedisConnectionError("Error 61 connecting to localhost:6379. Connection refused.")

    monkeypatch.setattr(rq, "SimpleWorker", FakeSimpleWorker)

    with pytest.raises(RedisConnectionError):
        worker_main.run_rq_worker(runtime)


def test_rq_pubsub_exception_handler_stops_thread_after_shutdown():
    from redis.exceptions import ConnectionError as RedisConnectionError

    class FakeThread:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    worker = SimpleNamespace(_shutdown_requested_date=object(), _stop_requested=False)
    thread = FakeThread()

    worker_main._handle_rq_pubsub_thread_exception(
        worker,
        RedisConnectionError("Connection closed by server."),
        None,
        thread,
    )

    assert thread.stopped is True


def test_rq_pubsub_exception_handler_reraises_before_shutdown():
    from redis.exceptions import ConnectionError as RedisConnectionError

    worker = SimpleNamespace(_shutdown_requested_date=None, _stop_requested=False)

    with pytest.raises(RedisConnectionError):
        worker_main._handle_rq_pubsub_thread_exception(
            worker,
            RedisConnectionError("Connection closed by server."),
            None,
            SimpleNamespace(stop=lambda: None),
        )


def test_run_async_process_cancels_pending_tasks_after_keyboard_interrupt():
    cancelled = []

    async def interrupted_process():
        background = asyncio.create_task(asyncio.sleep(3600))
        background.add_done_callback(lambda task: cancelled.append(task.cancelled()))
        raise KeyboardInterrupt()

    worker_main._run_async_process(interrupted_process)

    assert cancelled == [True]


def test_maintenance_process_logs_cleanup_errors_and_keeps_running(monkeypatch):
    calls = []
    runtime = FakeWorkerRuntime(calls)

    def failing_cleanup(*_args, **_kwargs):
        raise RuntimeError("cleanup exploded")

    async def cancel_after_iteration(_seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr(worker_main.report_history_service, "cleanup_expired_reports", failing_cleanup)
    monkeypatch.setattr(worker_main.report_history_service, "cleanup_orphan_markdown_reports", lambda *_args: calls.append("orphan"))
    monkeypatch.setattr(worker_main, "cleanup_expired_cache_entries", lambda: calls.append("cache"))
    monkeypatch.setattr(worker_main, "cleanup_report_index_orphans", lambda **_kwargs: calls.append("index"))
    monkeypatch.setattr(worker_main, "emit_log", calls.append)
    monkeypatch.setattr(worker_main.asyncio, "sleep", cancel_after_iteration)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker_main.run_maintenance_process(runtime))

    assert any("maintenance" in str(call) and "cleanup exploded" in str(call) for call in calls)
    assert "orphan" in calls
    assert "cache" in calls
    assert "index" in calls


def test_worker_main_import_does_not_import_analysis_jobs_in_parent_process():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str(ROOT / 'backend')!r}); "
                "import worker_main; "
                "print('analysis_jobs' in sys.modules)"
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "False"
