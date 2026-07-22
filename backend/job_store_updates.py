"""SQL assignment helpers for analysis job status updates."""

from __future__ import annotations

import json
from collections.abc import Container
from dataclasses import dataclass
from typing import Any

from security_sanitizer import sanitize_error_message


ABANDON_JOB_UPDATE_SQL = """
UPDATE analysis_jobs
SET status = 'error',
    error = ?,
    cancel_requested = 1,
    cancelled_at = COALESCE(cancelled_at, ?),
    finished_at = COALESCE(finished_at, ?),
    updated_at = ?
WHERE job_id = ?
"""


@dataclass(frozen=True)
class JobUpdateAssignment:
    set_clauses: list[str]
    params: list[Any]


def build_job_update_assignment(
    *,
    status: str,
    filename: str | None,
    error: str | None,
    data_snapshot: dict | None,
    metrics_snapshot: dict | None,
    now: float,
    terminal_statuses: Container[str],
) -> JobUpdateAssignment:
    set_clauses = ["status = ?", "filename = COALESCE(?, filename)", "error = ?", "updated_at = ?"]
    params: list[Any] = [status, filename, sanitize_error_message(error), now]

    if status == "running":
        set_clauses.append("started_at = COALESCE(started_at, ?)")
        params.append(now)
    if status in terminal_statuses:
        set_clauses.append("finished_at = COALESCE(finished_at, ?)")
        params.append(now)

    if data_snapshot is not None:
        set_clauses.append("data_snapshot = ?")
        params.append(json.dumps(data_snapshot, ensure_ascii=False))
    if metrics_snapshot is not None:
        set_clauses.append("metrics_snapshot = ?")
        params.append(json.dumps(metrics_snapshot, ensure_ascii=False))

    return JobUpdateAssignment(set_clauses=set_clauses, params=params)


def abandoned_job_update_rows(job_ids: list[str], reason: str, now: float) -> list[tuple[Any, ...]]:
    sanitized_reason = sanitize_error_message(reason)
    rows: list[tuple[Any, ...]] = []
    for job_id in job_ids:
        normalized_id = str(job_id).strip()
        if normalized_id:
            rows.append((sanitized_reason, now, now, now, normalized_id))
    return rows
