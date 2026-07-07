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
RQ_ABANDONED_JOB_REASON = "Redis/RQ 已無執行中或等待中的對應任務，判定前一次 Worker 已中斷；請重新送出分析或重跑。"
ACTIVE_RQ_JOB_STATUSES = {"queued", "started", "deferred", "scheduled"}


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
    task_id = analysis_task_id(job["job_id"])
    if not result.get("created"):
        if str(job.get("status") or "") == "queued" and task_queue_has_task(task_queue, task_id) is False:
            try:
                task_queue.enqueue(
                    task_id,
                    run_stock_analysis_job,
                    job["job_id"],
                    normalized_ticker,
                    normalized_pipeline,
                )
            except Exception as exc:
                message = sanitize_error_message(f"分析任務重新排入佇列失敗：{exc}")
                update_job(job["job_id"], "error", error=message)
                append_event(job["job_id"], {"type": "error", "message": message, "pipeline_id": normalized_pipeline})
                job = get_job(job["job_id"]) or job
            else:
                append_event(
                    job["job_id"],
                    {
                        "type": "status",
                        "phase": "queue_recovered",
                        "level": "warning",
                        "message": "佇列中已找不到此分析任務，已重新排入分析佇列。",
                        "pipeline_id": normalized_pipeline,
                    },
                )
                job = get_job(job["job_id"]) or job
        return serialize_analysis_job(job)

    try:
        if task_queue_has_task(task_queue, task_id) is not True:
            _enqueue_analysis_job(
                task_queue,
                task_id,
                run_stock_analysis_job,
                job["job_id"],
                normalized_ticker,
                normalized_pipeline,
                force_refresh=bool(force),
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


def analysis_task_id(job_id: str) -> str:
    return f"analysis:{job_id}"


def _enqueue_analysis_job(
    task_queue: Any,
    task_id: str,
    run_stock_analysis_job: Callable[[str, str, str], str],
    job_id: str,
    ticker: str,
    pipeline_id: str,
    *,
    force_refresh: bool = False,
) -> None:
    args = [task_id, run_stock_analysis_job, job_id, ticker, pipeline_id]
    if force_refresh:
        args.append(True)
    task_queue.enqueue(*args)


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


def task_queue_has_task(task_queue: Any, task_id: str) -> bool | None:
    """Return None when the queue implementation cannot inspect existing jobs."""
    queues = []
    queue_map = getattr(task_queue, "queues", None)
    if isinstance(queue_map, dict):
        queues.extend(queue for queue in queue_map.values() if queue is not None)
    queue = getattr(task_queue, "queue", None)
    if queue is not None and queue not in queues:
        queues.append(queue)
    if not queues and hasattr(task_queue, "fetch_job"):
        queues.append(task_queue)

    inspected = False
    for queue in queues:
        fetch_job = getattr(queue, "fetch_job", None)
        if not callable(fetch_job):
            continue
        inspected = True
        try:
            job = fetch_job(task_id)
        except Exception:
            return None
        if job is not None and _rq_job_is_active(job):
            return True
    return False if inspected else None


def _rq_job_is_active(job: Any) -> bool:
    get_status = getattr(job, "get_status", None)
    if callable(get_status):
        try:
            status = get_status(refresh=True)
        except TypeError:
            status = get_status()
    else:
        status = getattr(job, "status", None)
    if status is None:
        return True
    return str(status).lower() in ACTIVE_RQ_JOB_STATUSES


def _looks_like_duplicate_queue_job(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    return "duplicate" in name or "already" in message or "exists" in message
