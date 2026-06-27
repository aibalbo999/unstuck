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

import report_history_service
from cache_store import cleanup_expired_cache_entries
from config import REPORT_CLEANUP_INTERVAL_SECONDS, REPORT_RETENTION_DAYS
from decision_tracking_scheduler import run_decision_tracking_scheduler
from job_store import create_job, find_active_job, list_active_jobs, mark_jobs_abandoned
from report_index_maintenance import cleanup_report_index_orphans
from runtime_dependencies import RuntimeSettings, WorkerRuntime, create_worker_runtime
from runtime_events import emit_log
from watchlist_scheduler import run_watchlist_scheduler


Role = Literal["queue", "schedulers", "maintenance", "all"]
CHILD_ROLES: tuple[Role, ...] = ("queue", "schedulers", "maintenance")
ROLES: tuple[Role, ...] = (*CHILD_ROLES, "all")
SUPERVISOR_POLL_SECONDS = 1.0
SHUTDOWN_JOIN_TIMEOUT_SECONDS = 10.0
RQ_ABANDONED_JOB_REASON = "Redis/RQ 已無執行中或等待中的對應任務，判定前一次 Worker 已中斷；請重新送出分析或重跑。"


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

    SimpleWorker([rq_queue], connection=redis).work(
        burst=burst,
        max_jobs=max_jobs,
        with_scheduler=True,
    )


def reconcile_abandoned_rq_jobs(runtime: WorkerRuntime) -> int:
    """Mark SQLite-active jobs abandoned when Redis/RQ no longer tracks them."""
    task_queue = runtime.task_queue
    rq_queue = getattr(task_queue, "queue", None)
    if rq_queue is None:
        return 0

    try:
        rq_job_ids = _rq_active_job_ids(rq_queue)
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


def _rq_active_job_ids(rq_queue) -> set[str]:
    from rq.registry import DeferredJobRegistry, ScheduledJobRegistry, StartedJobRegistry

    job_ids = {str(job_id) for job_id in getattr(rq_queue, "job_ids", [])}
    for registry_class in (StartedJobRegistry, DeferredJobRegistry, ScheduledJobRegistry):
        registry = registry_class(queue=rq_queue)
        job_ids.update(str(job_id) for job_id in registry.get_job_ids())
    return job_ids


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
                find_active_job=lambda ticker, pipeline_id: find_active_job(ticker, pipeline_id),
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

    runtime = runtime_factory(RuntimeSettings.from_environment())
    try:
        if role == "queue":
            reconcile_abandoned_rq_jobs(runtime)
            run_rq_worker(runtime, burst=burst, max_jobs=max_jobs)
        elif role == "schedulers":
            asyncio.run(run_scheduler_process(runtime))
        elif role == "maintenance":
            asyncio.run(run_maintenance_process(runtime))
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
