"""Persistent job/event store for analysis task progress."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Iterable
from sqlite3 import Row

from config import ANALYSIS_JOB_STALE_SECONDS
import job_store_events
from job_store_cancellation import (
    is_job_cancel_requested as _is_job_cancel_requested,
    request_job_cancel as _request_job_cancel,
)
from job_store_event_writer import append_job_event
import job_store_lifecycle
import job_store_telemetry
from job_store_schema import init_job_store_schema
from job_store_updates import (
    ABANDON_JOB_UPDATE_SQL,
    abandoned_job_update_rows,
    build_job_update_assignment,
)
from runtime_paths import current_runtime_paths; TASK_DB_PATH = str(current_runtime_paths().task_db)
from security_sanitizer import sanitize_error_message
from storage.sqlite_resource import ThreadLocalSqliteResource

_JOB_LOCK = threading.Lock()
ACTIVE_JOB_STATUSES = ("queued", "running", "waiting_retry")
TERMINAL_JOB_STATUSES = {"done", "error", "cancelled"}
PUBLIC_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}

_resource = ThreadLocalSqliteResource(
    lambda: TASK_DB_PATH,
    init_schema=init_job_store_schema,
    row_factory=Row,
    busy_timeout_ms=3000,
)


def _active_status_placeholders() -> str:
    return ", ".join("?" for _ in ACTIVE_JOB_STATUSES)


def _connect():
    return _resource.connect()


def close_job_store() -> None:
    _resource.close_current_thread()


def reset_job_store_for_tests() -> None:
    _resource.reset()


def create_job(ticker: str, pipeline_id: str = "v1", worker_instance_id: str | None = None) -> str:
    job_id = uuid.uuid4().hex
    now = time.time()
    owner = str(worker_instance_id or "").strip() or None
    with _JOB_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_jobs (
                job_id, ticker, pipeline_id, status, created_at, updated_at,
                worker_instance_id, claimed_at
            )
            VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
            """,
            (job_id, ticker, pipeline_id, now, now, owner, now if owner else None),
        )
    append_event(job_id, {"type": "status", "message": f"已建立 {ticker} 分析任務", "pipeline_id": pipeline_id})
    return job_id


def create_or_attach_active_job(
    ticker: str, pipeline_id: str = "v1",
    *,
    force: bool = False,
    resume: bool = True,
    job_id: str | None = None,
    worker_instance_id: str | None = None,
    preserve_ticker_case: bool = False,
) -> dict:
    return job_store_lifecycle.create_or_attach_active_job(
        _connect,
        _JOB_LOCK,
        ACTIVE_JOB_STATUSES,
        ANALYSIS_JOB_STALE_SECONDS,
        append_event,
        ticker,
        pipeline_id,
        force=force,
        resume=resume,
        job_id=job_id,
        worker_instance_id=worker_instance_id,
        preserve_ticker_case=preserve_ticker_case,
    )


def update_job(job_id: str, status: str, filename: str = None, error: str = None, data_snapshot: dict = None, metrics_snapshot: dict = None) -> None:
    with _JOB_LOCK, _connect() as conn:
        current = conn.execute(
            "SELECT status, error, cancel_requested FROM analysis_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if current is None:
            return
        if current["status"] in TERMINAL_JOB_STATUSES and current["status"] != status:
            return
        next_status = status
        next_filename = filename
        next_error = error
        if current["cancel_requested"] and status == "done":
            next_status = "cancelled"
            next_filename = None
            next_error = current["error"] or "任務已取消，忽略完成狀態。"
        now = time.time()
        assignment = build_job_update_assignment(
            status=next_status,
            filename=next_filename,
            error=next_error,
            data_snapshot=data_snapshot,
            metrics_snapshot=metrics_snapshot,
            now=now,
            terminal_statuses=TERMINAL_JOB_STATUSES,
        )
        params = list(assignment.params)
        params.append(job_id)

        conn.execute(
            f"""
            UPDATE analysis_jobs
            SET {', '.join(assignment.set_clauses)}
            WHERE job_id = ?
            """,
            tuple(params),
        )


def get_job(job_id: str) -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else {}


def find_active_job(ticker: str, pipeline_id: str = "v1") -> dict:
    with _connect() as conn:
        row = job_store_lifecycle.find_active_job_in_conn(
            conn,
            ACTIVE_JOB_STATUSES,
            ANALYSIS_JOB_STALE_SECONDS,
            ticker,
            pipeline_id,
        )
    return dict(row) if row else {}


def list_active_jobs() -> list[dict]:
    """Return all jobs that the UI/API still considers active."""
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM analysis_jobs
            WHERE status IN ({_active_status_placeholders()})
            ORDER BY updated_at DESC
            """,
            ACTIVE_JOB_STATUSES,
        ).fetchall()
    return [dict(row) for row in rows]


def mark_jobs_abandoned(job_ids: Iterable[str], reason: str) -> int:
    """Mark selected active jobs as abandoned by the queue runtime."""
    normalized_ids = [str(job_id).strip() for job_id in job_ids if str(job_id).strip()]
    if not normalized_ids:
        return 0

    now = time.time()
    with _JOB_LOCK, _connect() as conn:
        active_rows = conn.execute(
            f"""
            SELECT job_id
            FROM analysis_jobs
            WHERE status IN ({_active_status_placeholders()})
              AND job_id IN ({', '.join('?' for _ in normalized_ids)})
            """,
            (*ACTIVE_JOB_STATUSES, *normalized_ids),
        ).fetchall()
        active_ids = [row["job_id"] for row in active_rows]
        if active_ids:
            conn.executemany(ABANDON_JOB_UPDATE_SQL, abandoned_job_update_rows(active_ids, reason, now))

    for job_id in active_ids:
        append_event(job_id, {"type": "error", "phase": "queue_abandoned", "message": reason})

    return len(active_ids)


def mark_incomplete_jobs_abandoned(reason: str, worker_instance_id: str | None = None) -> int:
    """Mark active local jobs as abandoned after a worker restart."""
    now = time.time()
    owner = str(worker_instance_id or "").strip()
    owner_clause = "AND worker_instance_id = ?" if owner else ""
    params = (owner,) if owner else ()
    with _JOB_LOCK, _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT job_id
            FROM analysis_jobs
            WHERE status IN ({_active_status_placeholders()})
            {owner_clause}
            """,
            (*ACTIVE_JOB_STATUSES, *params),
        ).fetchall()
        job_ids = [row["job_id"] for row in rows]
        if job_ids:
            conn.executemany(ABANDON_JOB_UPDATE_SQL, abandoned_job_update_rows(job_ids, reason, now))

    for job_id in job_ids:
        append_event(job_id, {"type": "error", "message": reason})

    return len(job_ids)


def request_job_cancel(job_id: str, reason: str = "使用者要求取消分析任務。") -> bool:
    return _request_job_cancel(
        _connect,
        _JOB_LOCK,
        ACTIVE_JOB_STATUSES,
        append_event,
        job_id,
        reason,
        now_fn=time.time,
    )


def is_job_cancel_requested(job_id: str) -> bool:
    return _is_job_cancel_requested(_connect, job_id)

def append_event(job_id: str, payload: dict) -> None:
    append_job_event(_connect, _JOB_LOCK, ACTIVE_JOB_STATUSES, TASK_DB_PATH, job_id, payload, now_fn=time.time)


def get_events_since(job_id: str, after_id: int = 0) -> list[dict]:
    return job_store_events.get_events_since(_connect, job_id, after_id)


def query_events(
    job_id: str | None = None,
    *,
    event_type: str | None = None,
    phase: str | None = None,
    level: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return job_store_events.query_events(
        _connect,
        job_id,
        event_type=event_type,
        phase=phase,
        level=level,
        limit=limit,
    )


def record_node_telemetry(payload: dict) -> int:
    return job_store_telemetry.record_node_telemetry(_connect, _JOB_LOCK, payload)


def list_node_telemetry(job_id: str) -> list[dict]:
    return job_store_telemetry.list_node_telemetry(_connect, job_id)
