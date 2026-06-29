"""Analysis job observability helpers."""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from pathlib import Path

from config import TASK_DB_PATH
from job_ops_dashboard import build_ops_dashboard_snapshot
from job_store import ACTIVE_JOB_STATUSES


def _active_status_placeholders() -> str:
    return ", ".join("?" for _ in ACTIVE_JOB_STATUSES)


def build_active_jobs_snapshot(limit: int = 10, event_limit: int = 80, db_path: str | None = None) -> dict:
    path = Path(db_path or TASK_DB_PATH)
    if not path.exists():
        return {"jobs": [], "active_count": 0, "db_exists": False}

    safe_limit = max(1, min(int(limit or 10), 50))
    safe_event_limit = max(1, min(int(event_limit or 80), 300))
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            jobs = conn.execute(
                f"""
                SELECT *
                FROM analysis_jobs
                WHERE status IN ({_active_status_placeholders()})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*ACTIVE_JOB_STATUSES, safe_limit),
            ).fetchall()
            if not jobs:
                jobs = conn.execute(
                    """
                    SELECT *
                    FROM analysis_jobs
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
            snapshots = [_job_snapshot(conn, dict(job), safe_event_limit) for job in jobs]
    except sqlite3.Error as exc:
        return {"jobs": [], "active_count": 0, "db_exists": True, "error": str(exc)[:160]}
    return {
        "jobs": snapshots,
        "active_count": sum(1 for job in snapshots if job.get("status") in ACTIVE_JOB_STATUSES),
        "db_exists": True,
    }


def _job_snapshot(conn: sqlite3.Connection, job: dict, event_limit: int) -> dict:
    rows = conn.execute(
        """
        SELECT id, payload, created_at, event_type, phase, level
        FROM analysis_events
        WHERE job_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (job["job_id"], event_limit),
    ).fetchall()
    events = [_decode_event(row) for row in rows]
    latest = events[0] if events else {}
    llm_errors = Counter()
    llm_retries = Counter()
    model_calls = Counter()
    for event in events:
        metadata = event.get("metadata") or {}
        model_id = metadata.get("model_id") or "unknown"
        if event.get("phase") == "llm_model_error":
            llm_errors[(model_id, metadata.get("error_category") or "unknown")] += 1
        if event.get("phase") in {"llm_transient_retry", "llm_rate_limit_retry", "llm_server_error_retry"}:
            llm_retries[model_id] += 1
        if event.get("phase") == "llm_model_call":
            model_calls[model_id] += 1

    now = time.time()
    stage_summary = _stage_summary(events, job, llm_errors, llm_retries, model_calls)
    return {
        "job_id": job.get("job_id"),
        "ticker": job.get("ticker"),
        "pipeline_id": job.get("pipeline_id"),
        "status": job.get("status"),
        "filename": job.get("filename"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "seconds_since_update": round(now - float(job.get("updated_at") or now), 1),
        "last_event": latest,
        "stage_summary": stage_summary,
        "llm_error_counts": _counter_to_dict(llm_errors),
        "llm_retry_counts": dict(llm_retries),
        "llm_model_call_counts": dict(model_calls),
        "token_estimate": _token_estimate_summary(events),
        "recent_events": events[:10],
    }


def _token_estimate_summary(events: list[dict]) -> dict:
    sampled_total = 0
    latest = None
    by_model = Counter()
    event_count = 0
    for event in events:
        metadata = event.get("metadata") or {}
        try:
            estimated = int(metadata.get("estimated_tokens"))
        except (TypeError, ValueError):
            continue
        if estimated <= 0:
            continue
        model_id = str(metadata.get("model_id") or "unknown")
        sampled_total += estimated
        by_model[model_id] += estimated
        event_count += 1
        if latest is None:
            latest = estimated
    return {
        "mode": "display_only",
        "sampled_total": sampled_total,
        "latest": latest or 0,
        "event_count_sampled": event_count,
        "by_model": dict(by_model),
    }


def _stage_summary(
    events: list[dict],
    job: dict,
    llm_errors: Counter,
    llm_retries: Counter,
    model_calls: Counter,
) -> dict:
    latest = events[0] if events else {}
    progress_events = [event for event in events if event.get("event_type") == "progress"]
    latest_progress = progress_events[0] if progress_events else {}
    report_count = sum(1 for event in events if event.get("event_type") == "report_done")
    error_count = sum(1 for event in events if event.get("event_type") == "error")
    current = latest_progress.get("current")
    total = latest_progress.get("total")
    return {
        "phase": latest.get("phase") or ("done" if job.get("status") == "done" else job.get("status") or "idle"),
        "message": latest.get("message") or job.get("error") or "",
        "progress_current": current,
        "progress_total": total,
        "latest_agent": latest.get("agent_num"),
        "event_count_sampled": len(events),
        "report_done_count_sampled": report_count,
        "error_count_sampled": error_count,
        "llm_retry_count_sampled": sum(llm_retries.values()),
        "llm_error_count_sampled": sum(llm_errors.values()),
        "llm_call_count_sampled": sum(model_calls.values()),
    }


def _decode_event(row: sqlite3.Row) -> dict:
    try:
        payload = json.loads(row["payload"])
    except (TypeError, json.JSONDecodeError):
        payload = {"type": "error", "message": "event payload decode failed"}
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "event_type": row["event_type"],
        "phase": row["phase"],
        "level": row["level"],
        "message": payload.get("message"),
        "current": payload.get("current"),
        "total": payload.get("total"),
        "name": payload.get("name"),
        "agent_num": payload.get("agent_num"),
        "pipeline_id": payload.get("pipeline_id"),
        "metadata": payload.get("metadata"),
    }


def _counter_to_dict(counter: Counter) -> dict:
    return {f"{model}:{category}": count for (model, category), count in counter.items()}
