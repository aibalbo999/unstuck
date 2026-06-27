"""Event query helpers for the analysis job store."""

from __future__ import annotations

import json
from collections.abc import Callable


def get_events_since(connect: Callable, job_id: str, after_id: int = 0) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, payload, created_at
            FROM analysis_events
            WHERE job_id = ? AND id > ?
            ORDER BY id ASC
            """,
            (job_id, after_id),
        ).fetchall()

    events = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"type": "error", "message": "任務事件解析失敗"}
        events.append({"id": row["id"], "payload": payload, "created_at": row["created_at"]})
    return events


def query_events(
    connect: Callable,
    job_id: str | None = None,
    *,
    event_type: str | None = None,
    phase: str | None = None,
    level: str | None = None,
    limit: int = 100,
) -> list[dict]:
    clauses = []
    params = []
    if job_id:
        clauses.append("job_id = ?")
        params.append(job_id)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if phase:
        clauses.append("phase = ?")
        params.append(phase)
    if level:
        clauses.append("level = ?")
        params.append(level)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    safe_limit = max(1, min(int(limit or 100), 1000))
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, job_id, payload, created_at, event_type, phase, level
            FROM analysis_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            (*params, safe_limit),
        ).fetchall()
    results = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"type": "error", "message": "任務事件解析失敗"}
        results.append({
            "id": row["id"],
            "job_id": row["job_id"],
            "payload": payload,
            "created_at": row["created_at"],
            "event_type": row["event_type"],
            "phase": row["phase"],
            "level": row["level"],
        })
    return results
