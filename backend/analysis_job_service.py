"""Service layer for analysis job lifecycle APIs."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from job_store import (
    append_event,
    create_or_attach_active_job,
    get_job,
    list_node_telemetry,
    request_job_cancel,
    sanitize_error_message,
    update_job,
)


_STATUS_MAP = {
    "queued": "queued",
    "running": "running",
    "waiting_retry": "running",
    "done": "completed",
    "error": "failed",
    "cancelled": "cancelled",
}


def create_or_attach_analysis_job(
    *,
    ticker: str,
    pipeline_id: str,
    force: bool = False,
    resume: bool = True,
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
) -> dict:
    normalized_ticker = str(ticker or "").strip().upper()
    normalized_pipeline = str(pipeline_id or "v1").strip() or "v1"
    job_id = build_analysis_job_id(normalized_ticker, normalized_pipeline, force=force)
    result = create_or_attach_active_job(
        normalized_ticker,
        normalized_pipeline,
        force=bool(force),
        resume=bool(resume),
        job_id=job_id,
    )
    job = dict(result["job"])
    if not result.get("created"):
        return serialize_analysis_job(job)

    task_id = f"analysis:{job['job_id']}"
    try:
        if not _queue_has_task(task_queue, task_id):
            task_queue.enqueue(
                task_id,
                run_stock_analysis_job,
                job["job_id"],
                normalized_ticker,
                normalized_pipeline,
            )
    except Exception as exc:
        if _looks_like_duplicate_queue_job(exc):
            append_event(
                job["job_id"],
                {
                    "type": "status",
                    "phase": "queue_attach",
                    "message": "佇列中已有相同任務，已附加到既有 RQ job。",
                    "pipeline_id": normalized_pipeline,
                },
            )
        else:
            message = sanitize_error_message(f"分析任務送入佇列失敗：{exc}")
            update_job(job["job_id"], "error", error=message)
            append_event(job["job_id"], {"type": "error", "message": message, "pipeline_id": normalized_pipeline})
            job = get_job(job["job_id"])
    else:
        job = get_job(job["job_id"]) or job
    return serialize_analysis_job(job)


def cancel_analysis_job(job_id: str, *, task_queue: Any | None = None) -> dict | None:
    job = get_job(job_id)
    if not job:
        return None

    if job.get("status") == "queued" and task_queue is not None:
        cancel = getattr(task_queue, "cancel", None)
        if callable(cancel):
            try:
                cancel(f"analysis:{job_id}")
            except Exception:
                pass
    request_job_cancel(job_id, "使用者要求取消分析任務。")
    return serialize_analysis_job(get_job(job_id) or job)


def serialize_analysis_job(job: dict) -> dict:
    job_id = str(job.get("job_id") or "")
    filename = str(job.get("filename") or "").strip()
    return {
        "job_id": job_id,
        "ticker": job.get("ticker"),
        "pipeline_id": job.get("pipeline_id") or "v1",
        "status": _STATUS_MAP.get(str(job.get("status") or ""), str(job.get("status") or "")),
        "created_at": _iso_timestamp(job.get("created_at")),
        "updated_at": _iso_timestamp(job.get("updated_at")),
        "started_at": _iso_timestamp(job.get("started_at")),
        "finished_at": _iso_timestamp(job.get("finished_at")),
        "report_path": f"/api/report/{filename}" if filename else None,
        "error": sanitize_error_message(job.get("error")),
        "events_url": f"/api/analysis-jobs/{job_id}/events",
        "status_url": f"/api/analysis-jobs/{job_id}",
    }


def serialize_node_telemetry(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "telemetry": [_serialize_telemetry_row(row) for row in list_node_telemetry(job_id)],
    }


def build_analysis_job_id(ticker: str, pipeline_id: str, *, force: bool = False) -> str:
    ticker_slug = _slug(ticker.replace(".TW", "tw"))
    pipeline_slug = _slug(pipeline_id)
    timestamp_ms = int(time.time() * 1000)
    suffix = uuid.uuid4().hex[:8] if force else uuid.uuid5(uuid.NAMESPACE_URL, f"{ticker}:{pipeline_id}:{timestamp_ms}").hex[:8]
    return f"analysis-{ticker_slug}-{pipeline_slug}-{timestamp_ms}-{suffix}"


def _serialize_telemetry_row(row: dict) -> dict:
    serialized = dict(row)
    serialized["started_at"] = _iso_timestamp(row.get("started_at"))
    serialized["finished_at"] = _iso_timestamp(row.get("finished_at"))
    serialized["error"] = sanitize_error_message(row.get("error"))
    return serialized


def _iso_timestamp(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(number, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "job"


def _queue_has_task(task_queue: Any, task_id: str) -> bool:
    queue = getattr(task_queue, "queue", None)
    fetch_job = getattr(queue, "fetch_job", None)
    if callable(fetch_job):
        return fetch_job(task_id) is not None
    return False


def _looks_like_duplicate_queue_job(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    return "duplicate" in name or "already" in message or "exists" in message
