"""Maintenance helpers for local analysis job/event history."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from config import ANALYSIS_JOB_HISTORY_RETENTION_DAYS, TASK_DB_PATH


TERMINAL_STATUSES = ("done", "error", "cancelled")
DEFAULT_KEEP_RECENT_JOBS = 20


def analysis_history_summary(
    *,
    task_db_path: Optional[str] = None,
    retention_days: Optional[int] = None,
    keep_recent_jobs: int = DEFAULT_KEEP_RECENT_JOBS,
) -> dict:
    return cleanup_analysis_history(
        task_db_path=task_db_path,
        retention_days=retention_days,
        keep_recent_jobs=keep_recent_jobs,
        write=False,
    )


def cleanup_analysis_history(
    *,
    task_db_path: Optional[str] = None,
    retention_days: Optional[int] = None,
    keep_recent_jobs: int = DEFAULT_KEEP_RECENT_JOBS,
    write: bool = False,
) -> dict:
    path = Path(task_db_path or TASK_DB_PATH)
    days = int(retention_days or ANALYSIS_JOB_HISTORY_RETENTION_DAYS)
    keep_recent = max(0, int(keep_recent_jobs or 0))
    cutoff = time.time() - max(days, 1) * 24 * 60 * 60
    base = {
        "exists": path.exists(),
        "retention_days": days,
        "keep_recent_jobs": keep_recent,
        "cutoff": cutoff,
        "stale_terminal_jobs": 0,
        "orphan_events": 0,
        "deleted_jobs": 0,
        "deleted_events": 0,
        "dry_run": not write,
    }
    if not path.exists():
        return {**base, "jobs_before": 0, "events_before": 0, "remaining_jobs": 0, "remaining_events": 0}

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        if not _table_exists(conn, "analysis_jobs") or not _table_exists(conn, "analysis_events"):
            return {**base, "jobs_before": None, "events_before": None, "remaining_jobs": None, "remaining_events": None}

        jobs_before = _count(conn, "analysis_jobs")
        events_before = _count(conn, "analysis_events")
        stale_job_ids = _stale_terminal_job_ids(conn, cutoff, keep_recent)
        orphan_events = _orphan_event_count(conn)
        stale_job_events = _event_count_for_jobs(conn, stale_job_ids)
        result = {
            **base,
            "jobs_before": jobs_before,
            "events_before": events_before,
            "stale_terminal_jobs": len(stale_job_ids),
            "orphan_events": orphan_events,
        }
        if not write:
            return {
                **result,
                "remaining_jobs": jobs_before,
                "remaining_events": events_before,
            }

        deleted_events = stale_job_events
        if stale_job_ids:
            conn.execute(
                f"DELETE FROM analysis_events WHERE job_id IN ({_placeholders(stale_job_ids)})",
                stale_job_ids,
            )
            conn.execute(
                f"DELETE FROM analysis_jobs WHERE job_id IN ({_placeholders(stale_job_ids)})",
                stale_job_ids,
            )
        orphan_cursor = conn.execute(
            """
            DELETE FROM analysis_events
            WHERE NOT EXISTS (
                SELECT 1 FROM analysis_jobs WHERE analysis_jobs.job_id = analysis_events.job_id
            )
            """
        )
        deleted_events += int(orphan_cursor.rowcount or 0)
        return {
            **result,
            "deleted_jobs": len(stale_job_ids),
            "deleted_events": deleted_events,
            "remaining_jobs": _count(conn, "analysis_jobs"),
            "remaining_events": _count(conn, "analysis_events"),
            "dry_run": False,
        }


def _stale_terminal_job_ids(conn: sqlite3.Connection, cutoff: float, keep_recent: int) -> list[str]:
    keep_ids = set()
    if keep_recent:
        keep_rows = conn.execute(
            f"""
            SELECT job_id
            FROM analysis_jobs
            WHERE status IN ({_placeholders(TERMINAL_STATUSES)})
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ?
            """,
            (*TERMINAL_STATUSES, keep_recent),
        ).fetchall()
        keep_ids = {str(row["job_id"]) for row in keep_rows}
    stale_rows = conn.execute(
        f"""
        SELECT job_id
        FROM analysis_jobs
        WHERE status IN ({_placeholders(TERMINAL_STATUSES)}) AND updated_at < ?
        ORDER BY updated_at ASC, created_at ASC
        """,
        (*TERMINAL_STATUSES, cutoff),
    ).fetchall()
    return [str(row["job_id"]) for row in stale_rows if str(row["job_id"]) not in keep_ids]


def _event_count_for_jobs(conn: sqlite3.Connection, job_ids: list[str]) -> int:
    if not job_ids:
        return 0
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM analysis_events WHERE job_id IN ({_placeholders(job_ids)})",
            job_ids,
        ).fetchone()[0]
    )


def _orphan_event_count(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM analysis_events
            WHERE NOT EXISTS (
                SELECT 1 FROM analysis_jobs WHERE analysis_jobs.job_id = analysis_events.job_id
            )
            """
        ).fetchone()[0]
    )


def _count(conn: sqlite3.Connection, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _placeholders(values) -> str:
    return ", ".join("?" for _ in values)
