"""Operator dashboard aggregation over analysis job storage."""

from __future__ import annotations

import sqlite3
import time
from collections import Counter
from pathlib import Path

from config import TASK_DB_PATH
from job_store import ACTIVE_JOB_STATUSES
from job_ops_dashboard_metrics import job_latency_summary, node_telemetry_summary, prompt_budget_summary
from model_route_budget import build_model_route_budget
from security_sanitizer import sanitize_error_message


def build_ops_dashboard_snapshot(
    *,
    db_path: str | None = None,
    now: float | None = None,
    stuck_after_seconds: int = 15 * 60,
    completed_limit: int = 500,
    telemetry_limit: int = 5000,
) -> dict:
    path = Path(db_path or TASK_DB_PATH)
    current_time = float(now if now is not None else time.time())
    safe_completed_limit = max(1, min(int(completed_limit or 500), 5000))
    safe_telemetry_limit = max(1, min(int(telemetry_limit or 5000), 50000))
    safe_stuck_after = max(60, int(stuck_after_seconds or 15 * 60))
    if not path.exists():
        return _empty_ops_dashboard(db_exists=False, stuck_after_seconds=safe_stuck_after)

    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            jobs = _job_latency_rows(conn, safe_completed_limit)
            active_counts = _active_job_counts(conn)
            stuck_jobs = _stuck_job_rows(conn, current_time, safe_stuck_after)
            telemetry_rows = _telemetry_rows(conn, safe_telemetry_limit)
    except sqlite3.Error as exc:
        payload = _empty_ops_dashboard(db_exists=True, stuck_after_seconds=safe_stuck_after)
        payload["error"] = sanitize_error_message(exc)
        return payload

    return {
        "db_exists": True,
        "job_latency": job_latency_summary(jobs),
        "jobs": {
            "active_count": sum(active_counts.values()),
            "active_by_status": dict(active_counts),
            "completed_sample_size": len(jobs),
        },
        "stuck_jobs": {
            "stuck_after_seconds": safe_stuck_after,
            "count": len(stuck_jobs),
            "jobs": stuck_jobs,
        },
        "node_telemetry": node_telemetry_summary(telemetry_rows),
        "prompt_budget": prompt_budget_summary(telemetry_rows),
        "model_route_budget": build_model_route_budget(telemetry_rows),
    }


def _active_status_placeholders() -> str:
    return ", ".join("?" for _ in ACTIVE_JOB_STATUSES)


def _empty_ops_dashboard(*, db_exists: bool, stuck_after_seconds: int) -> dict:
    return {
        "db_exists": db_exists,
        "job_latency": {
            "completed_count": 0,
            "p50_seconds": None,
            "p95_seconds": None,
            "p99_seconds": None,
            "max_seconds": None,
        },
        "jobs": {
            "active_count": 0,
            "active_by_status": {},
            "completed_sample_size": 0,
        },
        "stuck_jobs": {
            "stuck_after_seconds": stuck_after_seconds,
            "count": 0,
            "jobs": [],
        },
        "node_telemetry": {
            "sample_size": 0,
            "nodes": {},
            "models": {},
            "totals": {
                "calls": 0,
                "failures": 0,
                "retry_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            },
        },
        "prompt_budget": prompt_budget_summary([]),
        "model_route_budget": build_model_route_budget([]),
    }


def _job_latency_rows(conn: sqlite3.Connection, limit: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT job_id, ticker, pipeline_id, status, created_at, updated_at, started_at, finished_at
        FROM analysis_jobs
        WHERE status = 'done'
          AND COALESCE(finished_at, updated_at) > COALESCE(started_at, created_at)
        ORDER BY COALESCE(finished_at, updated_at) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]

def _active_job_counts(conn: sqlite3.Connection) -> Counter:
    rows = conn.execute(
        f"""
        SELECT status, COUNT(*) AS count
        FROM analysis_jobs
        WHERE status IN ({_active_status_placeholders()})
        GROUP BY status
        """,
        ACTIVE_JOB_STATUSES,
    ).fetchall()
    return Counter({row["status"]: int(row["count"] or 0) for row in rows})


def _stuck_job_rows(conn: sqlite3.Connection, now: float, stuck_after_seconds: int) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT job_id, ticker, pipeline_id, status, updated_at, started_at, created_at
        FROM analysis_jobs
        WHERE status IN ({_active_status_placeholders()})
          AND updated_at <= ?
        ORDER BY updated_at ASC
        LIMIT 20
        """,
        (*ACTIVE_JOB_STATUSES, now - stuck_after_seconds),
    ).fetchall()
    return [
        {
            "job_id": row["job_id"],
            "ticker": row["ticker"],
            "pipeline_id": row["pipeline_id"],
            "status": row["status"],
            "updated_at": row["updated_at"],
            "seconds_since_update": round(max(0.0, now - float(row["updated_at"] or now)), 1),
            "runtime_seconds": round(max(0.0, now - float(row["started_at"] or row["created_at"] or now)), 1),
        }
        for row in rows
    ]


def _telemetry_rows(conn: sqlite3.Connection, limit: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT pipeline_id, node_name, model, latency_ms, status, retry_count,
               input_tokens, output_tokens, cache_hit, quality_gate_pass, error
        FROM analysis_node_telemetry
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]
