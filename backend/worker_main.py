"""Independent worker process entrypoints for analysis and maintenance roles."""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import signal
import sys
from collections.abc import Callable
from types import FrameType
from typing import Literal

from analysis_job_service import RQ_ABANDONED_JOB_REASON, analysis_task_id, task_queue_has_task
from decision_tracking_scheduler import run_decision_tracking_scheduler
from job_store import create_job, find_active_job, list_active_jobs, mark_jobs_abandoned
from runtime_dependencies import RuntimeSettings, WorkerRuntime, create_worker_runtime
from runtime_events import emit_log
from storage_inventory import ensure_runtime_storage
from watchlist_scheduler import run_watchlist_scheduler
from worker_maintenance import run_maintenance_process
from worker_rq_reconciliation import (
    RQ_WORKER_HEARTBEAT_GRACE_SECONDS,
    coerce_datetime as _coerce_datetime,
    pid_exists as _pid_exists,
    rq_active_job_ids as _rq_active_job_ids,
    rq_live_started_job_ids as _rq_live_started_job_ids,
    rq_worker_appears_live as _rq_worker_appears_live,
    rq_worker_current_job_id as _rq_worker_current_job_id,
    rq_worker_heartbeat_is_fresh as _rq_worker_heartbeat_is_fresh,
    rq_worker_is_local as _rq_worker_is_local,
    rq_worker_pid as _rq_worker_pid,
    rq_worker_pid_exists as _rq_worker_pid_exists,
)
from worker_shutdown import (
    handle_rq_pubsub_thread_exception as _handle_rq_pubsub_thread_exception,
    run_async_process as _run_async_process,
)
from worker_queue_runners import run_arq_worker as _run_arq_worker
from worker_queue_runners import run_rq_worker as _run_rq_worker
from worker_child_processes import (
    all_children_exited as _all_children_exited,
    has_nonzero_exit as _has_nonzero_exit,
    join_children as _join_children,
    terminate_live_children as _terminate_live_children,
)


Role = Literal["queue", "schedulers", "maintenance", "all"]
CHILD_ROLES: tuple[Role, ...] = ("queue", "schedulers", "maintenance")
ROLES: tuple[Role, ...] = (*CHILD_ROLES, "all")
SUPERVISOR_POLL_SECONDS = 1.0
SHUTDOWN_JOIN_TIMEOUT_SECONDS = 10.0


def _load_stock_analysis_job_runner():
    from analysis_jobs import run_stock_analysis_job

    return run_stock_analysis_job


def run_rq_worker(
    runtime: WorkerRuntime,
    *,
    burst: bool = False,
    max_jobs: int | None = None,
) -> None:
    _run_rq_worker(runtime, burst=burst, max_jobs=max_jobs, emit=emit_log)


def run_arq_worker(
    runtime: WorkerRuntime,
    *,
    burst: bool = False,
    max_jobs: int | None = None,
) -> None:
    _run_arq_worker(runtime, burst=burst, max_jobs=max_jobs)


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
        checkpoint_backend=runtime_settings.checkpoint_backend,
        checkpoint_path=runtime_settings.checkpoint_path,
    )
    runtime = runtime_factory(runtime_settings)
    try:
        if role == "queue":
            if getattr(runtime.task_queue, "backend_name", "rq") == "arq":
                run_arq_worker(runtime, burst=burst, max_jobs=max_jobs)
            else:
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
