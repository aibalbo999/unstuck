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

    monkeypatch.setattr(worker_main, "run_rq_worker", lambda value: calls.append(("queue", value)))

    worker_main.run_role("queue", runtime_factory=lambda _settings: runtime)

    assert calls == [("queue", runtime), "close"]


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
