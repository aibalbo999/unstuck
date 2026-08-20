"""Bounded provider-error evidence for the operator dashboard."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def provider_error_rows(conn: sqlite3.Connection, limit: int) -> list[dict]:
    """Read sanitized provider errors and recover their analysis pipeline."""
    try:
        rows = conn.execute(
            """
            SELECT id, model_id, status, metadata_json
            FROM api_usage_events
            WHERE service = 'Gemini / Google AI'
              AND operation = 'llm_model_error'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        return []

    metadata_rows = []
    job_ids = set()
    for row in rows:
        metadata = _safe_metadata(row["metadata_json"])
        job_id = str(metadata.get("job_id") or "").strip()
        if job_id:
            job_ids.add(job_id)
        metadata_rows.append((row, metadata, job_id))

    pipeline_by_job = _pipelines_by_job(conn, job_ids)
    return [
        {
            "pipeline_id": pipeline_by_job.get(job_id) or str(metadata.get("pipeline_id") or "unknown"),
            "model": str(row["model_id"] or metadata.get("model_id") or "unknown"),
            "status": str(row["status"] or "error"),
        }
        for row, metadata, job_id in metadata_rows
    ]


def _pipelines_by_job(conn: sqlite3.Connection, job_ids: set[str]) -> dict[str, str]:
    if not job_ids:
        return {}
    placeholders = ", ".join("?" for _ in job_ids)
    try:
        rows = conn.execute(
            f"SELECT job_id, pipeline_id FROM analysis_jobs WHERE job_id IN ({placeholders})",
            tuple(sorted(job_ids)),
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {
        str(row["job_id"]): str(row["pipeline_id"] or "unknown")
        for row in rows
    }


def _safe_metadata(value: Any) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


__all__ = ["provider_error_rows"]
