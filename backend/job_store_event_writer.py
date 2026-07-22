"""Append analysis job events and related operational side effects."""

from __future__ import annotations

import json
import time
from typing import Callable

from api_usage_recorders import record_runtime_event_usage
from runtime_events import emit_log, format_event_log_line


def append_job_event(
    connect: Callable,
    lock,
    active_statuses: tuple[str, ...],
    task_db_path: str,
    job_id: str,
    payload: dict,
    *,
    now_fn: Callable[[], float] = time.time,
    usage_recorder: Callable = record_runtime_event_usage,
    event_logger: Callable[[str, dict], None] | None = None,
) -> None:
    now = now_fn()
    event_type = str(payload.get("type") or "event")
    phase = str(payload.get("phase") or "")
    level = str(payload.get("level") or "")
    placeholders = _active_status_placeholders(active_statuses)
    with lock, connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_events (job_id, payload, created_at, event_type, phase, level)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, json.dumps(payload, ensure_ascii=False), now, event_type, phase, level),
        )
        conn.execute(
            f"UPDATE analysis_jobs SET updated_at = ? WHERE job_id = ? AND status IN ({placeholders})",
            (now, job_id, *active_statuses),
        )
    try:
        usage_recorder(job_id, payload, created_at=now, db_path=task_db_path)
    except Exception:
        pass
    (event_logger or emit_job_event_log)(job_id, payload)


def emit_job_event_log(job_id: str, payload: dict) -> None:
    emit_log(format_event_log_line(job_id, payload, prefix="job"))


def _active_status_placeholders(active_statuses: tuple[str, ...]) -> str:
    return ", ".join("?" for _ in active_statuses)
