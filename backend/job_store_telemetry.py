"""Telemetry persistence helpers for the analysis job store."""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

from security_sanitizer import sanitize_error_message


def record_node_telemetry(connect: Callable, lock: Lock, payload: dict) -> int:
    now = time.time()
    job_id = str(payload.get("job_id") or "").strip()
    ticker = str(payload.get("ticker") or "").strip().upper()
    pipeline_id = str(payload.get("pipeline_id") or "v1").strip() or "v1"
    node_name = str(payload.get("node_name") or "").strip()
    if not job_id or not node_name:
        raise ValueError("job_id and node_name are required for telemetry")
    started_at = float(payload.get("started_at") or now)
    finished_at = payload.get("finished_at")
    finished_value = float(finished_at) if finished_at is not None else None
    quality_gate_pass = payload.get("quality_gate_pass")
    quality_gate_value = None if quality_gate_pass is None else int(bool(quality_gate_pass))
    with lock, connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO analysis_node_telemetry (
                job_id, ticker, pipeline_id, node_name, model,
                started_at, finished_at, latency_ms, status, retry_count,
                input_tokens, output_tokens, cache_hit, quality_gate_pass, error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                ticker,
                pipeline_id,
                node_name,
                str(payload.get("model") or "").strip() or None,
                started_at,
                finished_value,
                _optional_int(payload.get("latency_ms")),
                str(payload.get("status") or "success").strip() or "success",
                int(payload.get("retry_count") or 0),
                _optional_int(payload.get("input_tokens")),
                _optional_int(payload.get("output_tokens")),
                int(bool(payload.get("cache_hit", False))),
                quality_gate_value,
                sanitize_error_message(payload.get("error")),
                now,
            ),
        )
        return int(cursor.lastrowid)


def list_node_telemetry(connect: Callable, job_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, job_id, ticker, pipeline_id, node_name, model,
                   started_at, finished_at, latency_ms, status, retry_count,
                   input_tokens, output_tokens, cache_hit, quality_gate_pass, error
            FROM analysis_node_telemetry
            WHERE job_id = ?
            ORDER BY id ASC
            """,
            (job_id,),
        ).fetchall()
    return [_telemetry_row_to_dict(row) for row in rows]


def _telemetry_row_to_dict(row) -> dict:
    quality_gate_pass = row["quality_gate_pass"]
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "ticker": row["ticker"],
        "pipeline_id": row["pipeline_id"],
        "node_name": row["node_name"],
        "model": row["model"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "latency_ms": row["latency_ms"],
        "status": row["status"],
        "retry_count": row["retry_count"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "cache_hit": bool(row["cache_hit"]),
        "quality_gate_pass": None if quality_gate_pass is None else bool(quality_gate_pass),
        "error": sanitize_error_message(row["error"]),
    }


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
