"""Analysis job public payload and telemetry serialization helpers."""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from analysis_job_payload_values import (
    _iso_timestamp,
    _safe_bool_field,
    _safe_bool_flag,
    _safe_int,
    _safe_optional_int,
)
from job_store import list_node_telemetry, sanitize_error_message
from mapping_fields import safe_mapping_dict, safe_text


STATUS_MAP = {
    "queued": "queued",
    "running": "running",
    "waiting_retry": "running",
    "done": "completed",
    "error": "failed",
    "cancelled": "cancelled",
}
UNSAFE_PERCENT_ENCODED_URL_TOKENS = ("%00", "%09", "%0a", "%0d", "%23", "%2f", "%3f", "%5c", "%7f")


def serialize_analysis_job(job: dict) -> dict:
    job = safe_mapping_dict(job) or {}
    job_id = safe_text(job.get("job_id")).strip()
    job_url_id = _safe_public_url_segment(job_id)
    filename = _safe_report_filename(job.get("filename"))
    pipeline_id = safe_text(job.get("pipeline_id")).strip() or "v1"
    ticker = safe_text(job.get("ticker")).strip()
    status = safe_text(job.get("status")).strip()
    status_key = status.lower()
    return {
        "job_id": job_id,
        "ticker": ticker,
        "pipeline_id": pipeline_id,
        "status": STATUS_MAP.get(status_key, status),
        "created_at": _iso_timestamp(job.get("created_at")),
        "updated_at": _iso_timestamp(job.get("updated_at")),
        "started_at": _iso_timestamp(job.get("started_at")),
        "finished_at": _iso_timestamp(job.get("finished_at")),
        "report_path": f"/api/report/{filename}" if filename else None,
        "error": sanitize_error_message(job.get("error")),
        "events_url": f"/api/analysis-jobs/{job_url_id}/events" if job_url_id else None,
        "status_url": f"/api/analysis-jobs/{job_url_id}" if job_url_id else None,
    }


def _safe_report_filename(value: Any) -> str:
    return _safe_public_url_segment(value)


def _safe_public_url_segment(value: Any) -> str:
    segment = safe_text(value).strip()
    if not segment or segment in {".", ".."}:
        return ""
    if any(character.isspace() for character in segment):
        return ""
    if any(ord(character) < 32 or ord(character) == 127 for character in segment):
        return ""
    if "/" in segment or "\\" in segment:
        return ""
    lowered = segment.lower()
    if "?" in segment or "#" in segment:
        return ""
    if "%25" in lowered:
        return ""
    if any(token in lowered for token in UNSAFE_PERCENT_ENCODED_URL_TOKENS):
        return ""
    return segment


def serialize_node_telemetry(job_id: str, telemetry_fetcher=list_node_telemetry) -> dict:
    safe_job_id = safe_text(job_id).strip()
    rows = _safe_telemetry_rows(telemetry_fetcher(safe_job_id))
    return {
        "job_id": safe_job_id,
        "telemetry": [_serialize_telemetry_row(row) for row in rows],
    }


def build_analysis_job_id(ticker: str, pipeline_id: str, *, force: bool = False) -> str:
    ticker_text = safe_text(ticker).strip()
    pipeline_text = safe_text(pipeline_id).strip()
    ticker_slug = _slug(ticker_text.replace(".TW", "tw"))
    pipeline_slug = _slug(pipeline_text)
    timestamp_ms = int(time.time() * 1000)
    force_flag = _safe_bool_flag(force)
    suffix = uuid.uuid4().hex[:8] if force_flag else uuid.uuid5(uuid.NAMESPACE_URL, f"{ticker_text}:{pipeline_text}:{timestamp_ms}").hex[:8]
    return f"analysis-{ticker_slug}-{pipeline_slug}-{timestamp_ms}-{suffix}"


def analysis_task_id(job_id: str) -> str:
    return f"analysis:{_safe_public_url_segment(job_id)}"


def _serialize_telemetry_row(row: dict) -> dict:
    serialized = safe_mapping_dict(row) or {}
    for key in ("job_id", "ticker", "pipeline_id", "node_name", "model", "status"):
        if key in serialized:
            serialized[key] = safe_text(serialized.get(key)).strip()
    serialized["started_at"] = _iso_timestamp(serialized.get("started_at"))
    serialized["finished_at"] = _iso_timestamp(serialized.get("finished_at"))
    for key in ("id", "latency_ms", "input_tokens", "output_tokens"):
        if key in serialized:
            serialized[key] = _safe_optional_int(serialized.get(key))
    if "retry_count" in serialized:
        serialized["retry_count"] = _safe_int(serialized.get("retry_count"))
    for key in ("cache_hit", "quality_gate_pass"):
        if key in serialized:
            serialized[key] = _safe_bool_field(serialized.get(key))
    serialized["error"] = sanitize_error_message(serialized.get("error"))
    return serialized


def _safe_telemetry_rows(rows: Any) -> tuple[Any, ...]:
    if rows is None or isinstance(rows, (str, bytes, bytearray, memoryview, Mapping)):
        return ()
    if not isinstance(rows, Iterable):
        return ()
    try:
        iterator = iter(rows)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ()
    safe_rows = []
    while True:
        try:
            safe_rows.append(next(iterator))
        except StopIteration:
            break
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            break
    return tuple(safe_rows)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "job"


__all__ = [
    "analysis_task_id",
    "build_analysis_job_id",
    "serialize_analysis_job",
    "serialize_node_telemetry",
]
