"""Independent worker process entrypoints for analysis and maintenance roles."""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import os
import signal
import socket
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from types import FrameType
from typing import Literal

import report_history_service
from analysis_job_service import RQ_ABANDONED_JOB_REASON, analysis_task_id, task_queue_has_task
from cache_store import cleanup_expired_cache_entries
from config import REPORT_CLEANUP_INTERVAL_SECONDS, REPORT_RETENTION_DAYS
from database_maintenance import run_sqlite_maintenance
from decision_tracking_scheduler import run_decision_tracking_scheduler
from job_store import create_job, find_active_job, list_active_jobs, mark_jobs_abandoned
from job_store_maintenance import cleanup_analysis_history
from provider_sla_maintenance import cleanup_provider_sla_events
from report_index_maintenance import cleanup_report_index_orphans
from runtime_dependencies import RuntimeSettings, WorkerRuntime, create_worker_runtime
from runtime_events import emit_log
from storage_inventory import ensure_runtime_storage
from watchlist_scheduler import run_watchlist_scheduler
from worker_shutdown import (
    handle_rq_pubsub_thread_exception as _handle_rq_pubsub_thread_exception,
    install_shutdown_quiet_pubsub as _install_shutdown_quiet_pubsub,
    rq_worker_shutdown_requested as _rq_worker_shutdown_requested,
    run_async_process as _run_async_process,
)


Role = Literal["queue", "schedulers", "maintenance", "all"]
CHILD_ROLES: tuple[Role, ...] = ("queue", "schedulers", "maintenance")
ROLES: tuple[Role, ...] = (*CHILD_ROLES, "all")
SUPERVISOR_POLL_SECONDS = 1.0
SHUTDOWN_JOIN_TIMEOUT_SECONDS = 10.0
RQ_WORKER_HEARTBEAT_GRACE_SECONDS = 300.0


def _load_stock_analysis_job_runner():
    from analysis_jobs import run_stock_analysis_job

    return run_stock_analysis_job


def run_rq_worker(
    runtime: WorkerRuntime,
    *,
    burst: bool = False,
    max_jobs: int | None = None,
) -> None:
    task_queue = runtime.task_queue
    rq_queue = getattr(task_queue, "queue", None)
    redis = getattr(task_queue, "redis", None)
    if rq_queue is None or redis is None:
        raise RuntimeError("RQ worker requires an RQ task queue with queue and redis attributes.")

    from rq import SimpleWorker
    from redis.exceptions import ConnectionError as RedisConnectionError

    rq_queues = list(getattr(task_queue, "queues", {}) .values()) or [rq_queue]
    worker = SimpleWorker(rq_queues, connection=redis)
    _install_shutdown_quiet_pubsub(worker)
    try:
        worker.work(
            burst=burst,
            max_jobs=max_jobs,
            # RQ retries are stored in ScheduledJobRegistry; without the RQ
            # scheduler they stay there forever and the UI appears silent.
            with_scheduler=True,
        )
    except RedisConnectionError as exc:
        if _rq_worker_shutdown_requested(worker):
            emit_log("queue worker stopped after Redis shutdown.")
            return
        raise


def reconcile_abandoned_rq_jobs(runtime: WorkerRuntime) -> int:
    """Mark SQLite-active jobs abandoned when Redis/RQ no longer tracks them."""
    task_queue = runtime.task_queue
    rq_queues = list(getattr(task_queue, "queues", {}) .values()) or [getattr(task_queue, "queue", None)]
    rq_queues = [queue for queue in rq_queues if queue is not None]
    if not rq_queues:
        return 0

    try:
        rq_job_ids = _rq_active_job_ids(rq_queues)
    except Exception as exc:
        emit_log(f"queue reconciliation skipped: could not inspect RQ registries: {exc}")
        return 0

    abandoned_job_ids = [
        str(job.get("job_id") or "")
        for job in list_active_jobs()
        if not _sqlite_job_has_active_rq_job(job, rq_job_ids)
    ]
    abandoned_job_ids = [job_id for job_id in abandoned_job_ids if job_id]
    if not abandoned_job_ids:
        return 0

    count = mark_jobs_abandoned(abandoned_job_ids, RQ_ABANDONED_JOB_REASON)
    if count:
        emit_log(f"queue reconciliation marked {count} abandoned SQLite job(s).")
    return count


def find_queue_backed_active_job(task_queue, ticker: str, pipeline_id: str = "v1") -> dict:
    job = find_active_job(ticker, pipeline_id)
    if not job:
        return {}
    task_id = analysis_task_id(str(job.get("job_id") or ""))
    if task_queue_has_task(task_queue, task_id) is not False:
        return job
    mark_jobs_abandoned([job["job_id"]], RQ_ABANDONED_JOB_REASON)
    return {}


def _rq_active_job_ids(rq_queues) -> set[str]:
    from rq.registry import DeferredJobRegistry, ScheduledJobRegistry, StartedJobRegistry

    if not isinstance(rq_queues, (list, tuple, set)):
        rq_queues = [rq_queues]
    job_ids: set[str] = set()
    for rq_queue in rq_queues:
        job_ids.update(str(job_id) for job_id in getattr(rq_queue, "job_ids", []))
        started_registry = StartedJobRegistry(queue=rq_queue)
        started_job_ids = {str(job_id) for job_id in started_registry.get_job_ids()}
        job_ids.update(_rq_live_started_job_ids(rq_queue, started_job_ids))
        for registry_class in (DeferredJobRegistry, ScheduledJobRegistry):
            registry = registry_class(queue=rq_queue)
            job_ids.update(str(job_id) for job_id in registry.get_job_ids())
    return job_ids


def _rq_live_started_job_ids(rq_queue, started_job_ids: set[str]) -> set[str]:
    if not started_job_ids:
        return set()
    try:
        from rq import Worker

        workers = Worker.all(connection=getattr(rq_queue, "connection", None))
    except Exception:
        return set(started_job_ids)

    live_job_ids: set[str] = set()
    for worker in workers:
        current_job_id = _rq_worker_current_job_id(worker)
        if current_job_id in started_job_ids and _rq_worker_appears_live(worker):
            live_job_ids.add(current_job_id)
    return live_job_ids


def _rq_worker_current_job_id(worker) -> str:
    getter = getattr(worker, "get_current_job_id", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            value = None
    else:
        value = getattr(worker, "current_job_id", None)
    return str(value or "")


def _rq_worker_appears_live(worker) -> bool:
    pid = _rq_worker_pid(worker)
    if pid > 0:
        if _pid_exists(pid):
            return True
        if _rq_worker_is_local(worker):
            return False
    return _rq_worker_heartbeat_is_fresh(worker)


def _rq_worker_pid_exists(worker) -> bool:
    return _pid_exists(_rq_worker_pid(worker))


def _rq_worker_pid(worker) -> int:
    try:
        return int(getattr(worker, "pid", None) or 0)
    except (TypeError, ValueError):
        return 0


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _rq_worker_is_local(worker) -> bool:
    hostname = str(getattr(worker, "hostname", "") or "").strip().lower()
    if not hostname:
        return False
    local_names = {
        str(value or "").strip().lower()
        for value in (socket.gethostname(), socket.getfqdn(), "localhost")
        if str(value or "").strip()
    }
    local_short_names = {name.split(".", 1)[0] for name in local_names if name}
    return hostname in local_names or hostname.split(".", 1)[0] in local_short_names


def _rq_worker_heartbeat_is_fresh(worker) -> bool:
    heartbeat = _coerce_datetime(getattr(worker, "last_heartbeat", None))
    if heartbeat is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - heartbeat).total_seconds()
    return age_seconds <= RQ_WORKER_HEARTBEAT_GRACE_SECONDS


def _coerce_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sqlite_job_has_active_rq_job(job: dict, rq_job_ids: set[str]) -> bool:
    job_id = str(job.get("job_id") or "")
    if not job_id:
        return False
    pipeline_id = str(job.get("pipeline_id") or "")
    if pipeline_id.startswith("rerun:"):
        return f"report-rerun:{job_id}" in rq_job_ids
    return f"analysis:{job_id}" in rq_job_ids


async def run_scheduler_process(runtime: WorkerRuntime) -> None:
    if runtime.task_queue is None:
        raise RuntimeError("Scheduler runtime must provide a task queue.")

    tasks = [
        asyncio.create_task(
            run_watchlist_scheduler(
                create_job=lambda ticker, pipeline_id: create_job(ticker, pipeline_id),
                find_active_job=lambda ticker, pipeline_id: find_queue_backed_active_job(runtime.task_queue, ticker, pipeline_id),
                task_queue=runtime.task_queue,
                run_stock_analysis_job=_load_stock_analysis_job_runner(),
                data_service=runtime.data_refresh_service,
                emit_log=emit_log,
            )
        ),
        asyncio.create_task(
            run_decision_tracking_scheduler(
                get_output_dir=lambda: runtime.settings.output_dir,
                get_refresh_service=lambda: runtime.data_refresh_service,
                emit_log=emit_log,
            )
        ),
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def run_maintenance_process(runtime: WorkerRuntime) -> None:
    report_cache: dict[str, str] = {}
    while True:
        await _run_maintenance_iteration(runtime, report_cache)
        await asyncio.sleep(REPORT_CLEANUP_INTERVAL_SECONDS)


async def _run_maintenance_iteration(runtime: WorkerRuntime, report_cache: dict[str, str]) -> None:
    steps = [
        (
            "expired reports",
            lambda: report_history_service.cleanup_expired_reports(
                runtime.settings.output_dir,
                report_cache,
                REPORT_RETENTION_DAYS,
            ),
        ),
        (
            "orphan markdown reports",
            lambda: report_history_service.cleanup_orphan_markdown_reports(runtime.settings.output_dir),
        ),
        ("expired cache entries", cleanup_expired_cache_entries),
        ("report index orphans", lambda: cleanup_report_index_orphans(write=True)),
        ("analysis job history", lambda: cleanup_analysis_history(write=True)),
        ("provider SLA events", lambda: cleanup_provider_sla_events(write=True)),
        ("sqlite backup/checkpoint/vacuum", lambda: run_sqlite_maintenance(write=True)),
    ]
    for label, action in steps:
        try:
            await asyncio.to_thread(action)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            emit_log(f"maintenance cleanup failed ({label}): {exc}")


def run_role(
    role: str,
    runtime_factory: Callable[[RuntimeSettings], WorkerRuntime] = create_worker_runtime,
    *,
    burst: bool = False,
    max_jobs: int | None = None,
) -> None:
    if role not in CHILD_ROLES:
        raise ValueError(f"Unknown worker role: {role}")

    runtime_settings = RuntimeSettings.from_environment()
    ensure_runtime_storage(
        output_dir=runtime_settings.output_dir,
        cache_db_path=runtime_settings.cache_db_path,
        checkpoint_path=runtime_settings.checkpoint_path,
    )
    runtime = runtime_factory(runtime_settings)
    try:
        if role == "queue":
            reconcile_abandoned_rq_jobs(runtime)
            run_rq_worker(runtime, burst=burst, max_jobs=max_jobs)
        elif role == "schedulers":
            _run_async_process(lambda: run_scheduler_process(runtime))
        elif role == "maintenance":
            _run_async_process(lambda: run_maintenance_process(runtime))
    finally:
        runtime.close()


def child_main(role: str) -> None:
    def _raise_keyboard_interrupt(_signum: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt()

    previous_handlers = {
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
        signal.SIGINT: signal.getsignal(signal.SIGINT),
    }
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    signal.signal(signal.SIGINT, _raise_keyboard_interrupt)
    try:
        run_role(role)
    except KeyboardInterrupt:
        return
    finally:
        for sig, previous_handler in previous_handlers.items():
            signal.signal(sig, previous_handler)


def _terminate_live_children(processes) -> None:
    for process in processes:
        if process.is_alive():
            process.terminate()


def _join_children(processes, timeout: float | None = None) -> None:
    for process in processes:
        process.join(timeout=timeout)


def _has_nonzero_exit(processes) -> bool:
    return any(process.exitcode not in (None, 0) for process in processes)


def _all_children_exited(processes) -> bool:
    return all(process.exitcode is not None for process in processes)


def run_all_roles() -> int:
    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(target=child_main, args=(role,))
        for role in CHILD_ROLES
    ]
    started_processes = []

    shutdown_requested = False

    def _handle_signal(_signum: int, _frame: FrameType | None) -> None:
        nonlocal shutdown_requested
        shutdown_requested = True
        _terminate_live_children(started_processes)

    previous_handlers = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[sig] = signal.getsignal(sig)
        signal.signal(sig, _handle_signal)

    try:
        for process in processes:
            if shutdown_requested:
                break
            process.start()
            started_processes.append(process)
            if shutdown_requested:
                _terminate_live_children(started_processes)
                break
        while True:
            _join_children(started_processes, timeout=SUPERVISOR_POLL_SECONDS)
            if shutdown_requested:
                _join_children(started_processes, timeout=SHUTDOWN_JOIN_TIMEOUT_SECONDS)
                return 130
            if _has_nonzero_exit(started_processes):
                _terminate_live_children(started_processes)
                _join_children(started_processes, timeout=SHUTDOWN_JOIN_TIMEOUT_SECONDS)
                return 1
            if _all_children_exited(started_processes):
                return 0
    except BaseException:
        _terminate_live_children(started_processes)
        _join_children(started_processes, timeout=SHUTDOWN_JOIN_TIMEOUT_SECONDS)
        raise
    finally:
        for sig, previous in previous_handlers.items():
            signal.signal(sig, previous)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run stock-agent worker roles.")
    parser.add_argument("--role", choices=ROLES, default="all")
    parser.add_argument("--burst", action="store_true", help="Queue role exits when the RQ queue is empty.")
    parser.add_argument("--max-jobs", type=int, default=None, help="Queue role exits after processing this many jobs.")
    args = parser.parse_args(argv)
    if args.role == "all":
        return run_all_roles()
    run_role(args.role, burst=args.burst, max_jobs=args.max_jobs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
