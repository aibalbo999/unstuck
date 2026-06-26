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
from job_store import create_job, find_active_job
from report_index_maintenance import cleanup_report_index_orphans
from runtime_dependencies import RuntimeSettings, WorkerRuntime, create_worker_runtime
from runtime_events import emit_log
from watchlist_scheduler import run_watchlist_scheduler


Role = Literal["queue", "schedulers", "maintenance", "all"]
CHILD_ROLES: tuple[Role, ...] = ("queue", "schedulers", "maintenance")
ROLES: tuple[Role, ...] = (*CHILD_ROLES, "all")
SUPERVISOR_POLL_SECONDS = 1.0
SHUTDOWN_JOIN_TIMEOUT_SECONDS = 10.0


def _load_stock_analysis_job_runner():
    from analysis_jobs import run_stock_analysis_job

    return run_stock_analysis_job


def run_rq_worker(runtime: WorkerRuntime) -> None:
    task_queue = runtime.task_queue
    rq_queue = getattr(task_queue, "queue", None)
    redis = getattr(task_queue, "redis", None)
    if rq_queue is None or redis is None:
        raise RuntimeError("RQ worker requires an RQ task queue with queue and redis attributes.")

    from rq import Worker

    Worker([rq_queue], connection=redis).work(with_scheduler=True)


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
) -> None:
    if role not in CHILD_ROLES:
        raise ValueError(f"Unknown worker role: {role}")

    runtime = runtime_factory(RuntimeSettings.from_environment())
    try:
        if role == "queue":
            run_rq_worker(runtime)
        elif role == "schedulers":
            asyncio.run(run_scheduler_process(runtime))
        elif role == "maintenance":
            asyncio.run(run_maintenance_process(runtime))
    finally:
        runtime.close()


def child_main(role: str) -> None:
    def _raise_keyboard_interrupt(_signum: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt()

    previous_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    try:
        run_role(role)
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


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
    args = parser.parse_args(argv)
    if args.role == "all":
        return run_all_roles()
    run_role(args.role)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
