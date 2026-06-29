"""Atomic lifecycle helpers for analysis job records."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from threading import Lock

from security_sanitizer import sanitize_error_message


def create_or_attach_active_job(
    connect: Callable,
    lock: Lock,
    active_statuses: tuple[str, ...],
    stale_seconds: int,
    append_event: Callable[[str, dict], None],
    ticker: str,
    pipeline_id: str = "v1",
    *,
    force: bool = False,
    resume: bool = True,
    job_id: str | None = None,
    worker_instance_id: str | None = None,
    preserve_ticker_case: bool = False,
) -> dict:
    normalized_ticker = str(ticker or "").strip()
    if not preserve_ticker_case:
        normalized_ticker = normalized_ticker.upper()
    normalized_pipeline = str(pipeline_id or "v1").strip() or "v1"
    new_job_id = str(job_id or uuid.uuid4().hex).strip()
    now = time.time()
    owner = str(worker_instance_id or "").strip() or None
    cancelled_job_ids: list[str] = []

    with lock:
        conn = connect()
        try:
            if conn.in_transaction:
                conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            active = _find_active_job_in_conn(
                conn,
                active_statuses,
                stale_seconds,
                normalized_ticker,
                normalized_pipeline,
            )
            if active and not force and resume:
                conn.commit()
                return {"job": dict(active), "created": False, "cancelled_job_ids": []}

            if force and active:
                cancelled_job_ids = _cancel_active_jobs(
                    conn,
                    active_statuses,
                    normalized_ticker,
                    normalized_pipeline,
                    now,
                )

            try:
                conn.execute(
                    """
                    INSERT INTO analysis_jobs (
                        job_id, ticker, pipeline_id, status, created_at, updated_at,
                        worker_instance_id, claimed_at
                    )
                    VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
                    """,
                    (
                        new_job_id,
                        normalized_ticker,
                        normalized_pipeline,
                        now,
                        now,
                        owner,
                        now if owner else None,
                    ),
                )
            except Exception:
                active_after_conflict = _find_active_job_in_conn(
                    conn,
                    active_statuses,
                    stale_seconds,
                    normalized_ticker,
                    normalized_pipeline,
                )
                if active_after_conflict and not force:
                    conn.commit()
                    return {"job": dict(active_after_conflict), "created": False, "cancelled_job_ids": []}
                raise

            row = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (new_job_id,)).fetchone()
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    for old_job_id in cancelled_job_ids:
        append_event(
            old_job_id,
            {
                "type": "error",
                "phase": "superseded",
                "level": "warning",
                "message": "此分析任務已被 force=true 的新任務取代。",
                "replacement_job_id": new_job_id,
                "pipeline_id": normalized_pipeline,
            },
        )
    append_event(
        new_job_id,
        {
            "type": "status",
            "message": f"已建立 {normalized_ticker} 分析任務",
            "pipeline_id": normalized_pipeline,
        },
    )
    return {"job": dict(row), "created": True, "cancelled_job_ids": cancelled_job_ids}


def find_active_job_in_conn(conn, active_statuses: tuple[str, ...], stale_seconds: int, ticker: str, pipeline_id: str = "v1"):
    return _find_active_job_in_conn(conn, active_statuses, stale_seconds, ticker, pipeline_id)


def _find_active_job_in_conn(conn, active_statuses: tuple[str, ...], stale_seconds: int, ticker: str, pipeline_id: str):
    cutoff = time.time() - stale_seconds
    return conn.execute(
        f"""
        SELECT * FROM analysis_jobs
        WHERE ticker = ? AND pipeline_id = ? AND status IN ({_placeholders(active_statuses)}) AND updated_at >= ?
          AND COALESCE(cancel_requested, 0) = 0
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (ticker, pipeline_id, *active_statuses, cutoff),
    ).fetchone()


def _cancel_active_jobs(
    conn,
    active_statuses: tuple[str, ...],
    ticker: str,
    pipeline_id: str,
    now: float,
) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT job_id
        FROM analysis_jobs
        WHERE ticker = ? AND pipeline_id = ?
          AND status IN ({_placeholders(active_statuses)})
          AND COALESCE(cancel_requested, 0) = 0
        """,
        (ticker, pipeline_id, *active_statuses),
    ).fetchall()
    job_ids = [row["job_id"] for row in rows]
    if job_ids:
        conn.executemany(
            """
            UPDATE analysis_jobs
            SET status = 'cancelled',
                cancel_requested = 1,
                cancelled_at = COALESCE(cancelled_at, ?),
                finished_at = COALESCE(finished_at, ?),
                error = COALESCE(error, ?),
                updated_at = ?
            WHERE job_id = ?
            """,
            [
                (
                    now,
                    now,
                    sanitize_error_message("Superseded by force=true analysis job."),
                    now,
                    old_job_id,
                )
                for old_job_id in job_ids
            ],
        )
    return job_ids


def _placeholders(values: tuple[str, ...]) -> str:
    return ", ".join("?" for _ in values)
