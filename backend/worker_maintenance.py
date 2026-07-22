"""Maintenance loop helpers for worker role processes."""

from __future__ import annotations

import asyncio

import report_history_service
from cache_store import cleanup_expired_cache_entries
from config import REPORT_CLEANUP_INTERVAL_SECONDS, REPORT_RETENTION_DAYS
from database_maintenance import run_sqlite_maintenance
from job_store_maintenance import cleanup_analysis_history
from provider_sla_maintenance import cleanup_provider_sla_events
from report_index_maintenance import cleanup_report_index_orphans
from runtime_dependencies import WorkerRuntime
from runtime_events import emit_log


async def run_maintenance_process(runtime: WorkerRuntime) -> None:
    report_cache: dict[str, str] = {}
    while True:
        await run_maintenance_iteration(runtime, report_cache)
        await asyncio.sleep(REPORT_CLEANUP_INTERVAL_SECONDS)


async def run_maintenance_iteration(runtime: WorkerRuntime, report_cache: dict[str, str]) -> None:
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
        (
            "sqlite backup/checkpoint/vacuum",
            lambda: run_sqlite_maintenance(
                cache_db_path=runtime.settings.cache_db_path,
                checkpoint_backend=runtime.settings.checkpoint_backend,
                checkpoint_path=runtime.settings.checkpoint_path,
                write=True,
            ),
        ),
    ]
    for label, action in steps:
        try:
            await asyncio.to_thread(action)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            emit_log(f"maintenance cleanup failed ({label}): {exc}")


__all__ = ["run_maintenance_iteration", "run_maintenance_process"]
