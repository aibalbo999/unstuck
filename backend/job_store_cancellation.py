"""Cancellation helpers for analysis jobs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from security_sanitizer import sanitize_error_message


@dataclass(frozen=True)
class CancelJobUpdate:
    sql: str
    params: tuple


def build_cancel_job_update(status: str, *, job_id: str, reason: str, now: float) -> CancelJobUpdate:
    sanitized_reason = sanitize_error_message(reason)
    if status == "queued":
        return CancelJobUpdate(
            sql="""
                UPDATE analysis_jobs
                SET status = 'cancelled',
                    cancel_requested = 1,
                    cancelled_at = COALESCE(cancelled_at, ?),
                    finished_at = COALESCE(finished_at, ?),
                    error = COALESCE(error, ?),
                    updated_at = ?
                WHERE job_id = ?
                """,
            params=(now, now, sanitized_reason, now, job_id),
        )
    return CancelJobUpdate(
        sql="""
            UPDATE analysis_jobs
            SET cancel_requested = 1,
                cancelled_at = COALESCE(cancelled_at, ?),
                error = COALESCE(error, ?),
                updated_at = ?
            WHERE job_id = ?
            """,
        params=(now, sanitized_reason, now, job_id),
    )


def should_emit_cancel_event(status: str, active_statuses: tuple[str, ...]) -> bool:
    return status in active_statuses


def request_job_cancel(
    connect: Callable,
    lock,
    active_statuses: tuple[str, ...],
    append_event: Callable[[str, dict], None],
    job_id: str,
    reason: str = "使用者要求取消分析任務。",
    *,
    now_fn: Callable[[], float] = time.time,
) -> bool:
    now = now_fn()
    with lock, connect() as conn:
        row = conn.execute("SELECT status FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return False
        status = row["status"]
        update = build_cancel_job_update(status, job_id=job_id, reason=reason, now=now)
        conn.execute(update.sql, update.params)
    if should_emit_cancel_event(status, active_statuses):
        append_event(job_id, {"type": "status", "phase": "cancelling", "level": "warning", "message": reason})
    return True


def is_job_cancel_requested(connect: Callable, job_id: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT cancel_requested FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return bool(row and row["cancel_requested"])
