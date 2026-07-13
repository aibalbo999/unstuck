"""Operator dashboard aggregation over analysis job storage."""

from __future__ import annotations

import math
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path

from config import TASK_DB_PATH
from job_store import ACTIVE_JOB_STATUSES
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
        "job_latency": _job_latency_summary(jobs),
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
        "node_telemetry": _node_telemetry_summary(telemetry_rows),
        "prompt_budget": _prompt_budget_summary(telemetry_rows),
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
        "prompt_budget": _prompt_budget_summary([]),
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


def _job_latency_summary(rows: list[dict]) -> dict:
    durations = sorted(
        max(
            0.0,
            float(row.get("finished_at") or row.get("updated_at"))
            - float(row.get("started_at") or row.get("created_at")),
        )
        for row in rows
    )
    if not durations:
        return {
            "completed_count": 0,
            "p50_seconds": None,
            "p95_seconds": None,
            "p99_seconds": None,
            "max_seconds": None,
        }
    return {
        "completed_count": len(durations),
        "p50_seconds": _nearest_rank_percentile(durations, 50),
        "p95_seconds": _nearest_rank_percentile(durations, 95),
        "p99_seconds": _nearest_rank_percentile(durations, 99),
        "max_seconds": round(durations[-1], 1),
    }


def _node_telemetry_summary(rows: list[dict]) -> dict:
    node_stats = defaultdict(_blank_telemetry_bucket)
    model_stats = defaultdict(_blank_telemetry_bucket)
    totals = _blank_telemetry_bucket()
    for row in rows:
        node_name = str(row.get("node_name") or "unknown")
        model = str(row.get("model") or "unknown")
        for bucket in (node_stats[node_name], model_stats[model], totals):
            _add_telemetry_row(bucket, row)
        error = str(row.get("error") or "").lower()
        if error:
            if "429" in error or "rate" in error or "quota" in error:
                model_stats[model]["rate_limit_errors"] += 1
            if "timeout" in error or "timed out" in error:
                model_stats[model]["timeout_errors"] += 1
            if " 5" in error or "500" in error or "503" in error or "server" in error:
                model_stats[model]["server_errors"] += 1
    return {
        "sample_size": len(rows),
        "nodes": {name: _finalize_telemetry_bucket(bucket) for name, bucket in sorted(node_stats.items())},
        "models": {name: _finalize_telemetry_bucket(bucket) for name, bucket in sorted(model_stats.items())},
        "totals": _finalize_telemetry_bucket(totals),
    }


def _blank_telemetry_bucket() -> dict:
    return {
        "calls": 0,
        "successes": 0,
        "failures": 0,
        "retry_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_hits": 0,
        "quality_gate_failures": 0,
        "latencies": [],
        "rate_limit_errors": 0,
        "timeout_errors": 0,
        "server_errors": 0,
    }


def _add_telemetry_row(bucket: dict, row: dict) -> None:
    status = str(row.get("status") or "").lower()
    bucket["calls"] += 1
    if status == "success":
        bucket["successes"] += 1
    else:
        bucket["failures"] += 1
    bucket["retry_count"] += int(row.get("retry_count") or 0)
    bucket["input_tokens"] += int(row.get("input_tokens") or 0)
    bucket["output_tokens"] += int(row.get("output_tokens") or 0)
    bucket["cache_hits"] += int(bool(row.get("cache_hit")))
    if row.get("quality_gate_pass") == 0:
        bucket["quality_gate_failures"] += 1
    latency = row.get("latency_ms")
    if latency is not None:
        try:
            bucket["latencies"].append(float(latency))
        except (TypeError, ValueError):
            pass


def _finalize_telemetry_bucket(bucket: dict) -> dict:
    calls = int(bucket["calls"])
    latencies = sorted(bucket["latencies"])
    finalized = {
        "calls": calls,
        "successes": int(bucket["successes"]),
        "failures": int(bucket["failures"]),
        "failure_rate": round(bucket["failures"] / calls, 4) if calls else 0.0,
        "retry_count": int(bucket["retry_count"]),
        "input_tokens": int(bucket["input_tokens"]),
        "output_tokens": int(bucket["output_tokens"]),
        "cache_hit_rate": round(bucket["cache_hits"] / calls, 4) if calls else 0.0,
        "quality_gate_failures": int(bucket["quality_gate_failures"]),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "p95_latency_ms": _nearest_rank_percentile(latencies, 95) if latencies else None,
    }
    for key in ("rate_limit_errors", "timeout_errors", "server_errors"):
        if bucket.get(key):
            finalized[key] = int(bucket[key])
    return finalized


def _prompt_budget_summary(rows: list[dict]) -> dict:
    totals = _blank_prompt_bucket()
    nodes = defaultdict(_blank_prompt_bucket)
    models = defaultdict(_blank_prompt_bucket)
    for row in rows:
        node_name = str(row.get("node_name") or "unknown")
        model = str(row.get("model") or "unknown")
        for bucket in (totals, nodes[node_name], models[model]):
            _add_prompt_budget_row(bucket, row)
    return {
        **_finalize_prompt_bucket(totals),
        "sample_size": len(rows),
        "nodes": {name: _finalize_prompt_bucket(bucket) for name, bucket in sorted(nodes.items())},
        "models": {name: _finalize_prompt_bucket(bucket) for name, bucket in sorted(models.items())},
    }


def _blank_prompt_bucket() -> dict:
    return {
        "tokenized_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_hit_count": 0,
        "estimated_cached_input_tokens": 0,
    }


def _add_prompt_budget_row(bucket: dict, row: dict) -> None:
    input_tokens = int(row.get("input_tokens") or 0)
    output_tokens = int(row.get("output_tokens") or 0)
    if input_tokens or output_tokens:
        bucket["tokenized_calls"] += 1
    bucket["input_tokens"] += input_tokens
    bucket["output_tokens"] += output_tokens
    if row.get("cache_hit"):
        bucket["cache_hit_count"] += 1
        bucket["estimated_cached_input_tokens"] += input_tokens


def _finalize_prompt_bucket(bucket: dict) -> dict:
    tokenized_calls = int(bucket["tokenized_calls"])
    input_tokens = int(bucket["input_tokens"])
    output_tokens = int(bucket["output_tokens"])
    total_tokens = input_tokens + output_tokens
    return {
        "tokenized_calls": tokenized_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "avg_input_tokens": round(input_tokens / tokenized_calls, 1) if tokenized_calls else 0.0,
        "avg_output_tokens": round(output_tokens / tokenized_calls, 1) if tokenized_calls else 0.0,
        "avg_total_tokens": round(total_tokens / tokenized_calls, 1) if tokenized_calls else 0.0,
        "cache_hit_count": int(bucket["cache_hit_count"]),
        "estimated_cached_input_tokens": int(bucket["estimated_cached_input_tokens"]),
    }


def _nearest_rank_percentile(sorted_values: list[float], percentile: int) -> float | None:
    if not sorted_values:
        return None
    rank = max(1, math.ceil((percentile / 100) * len(sorted_values)))
    return round(sorted_values[min(rank, len(sorted_values)) - 1], 1)
