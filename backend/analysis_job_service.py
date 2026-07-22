"""Service layer for analysis job lifecycle APIs."""

from __future__ import annotations

from typing import Any, Callable

from analysis_job_payloads import (
    _safe_bool_flag,
    analysis_task_id,
    build_analysis_job_id,
    serialize_analysis_job,
    serialize_node_telemetry as _serialize_node_telemetry,
)
from analysis_job_queue_state import (
    _looks_like_duplicate_queue_job,
    _queue_exception_message,
    _safe_getattr,
    task_queue_has_task,
)
from job_store import (
    append_event,
    create_or_attach_active_job,
    get_job,
    list_node_telemetry,
    request_job_cancel,
    update_job,
)
from mapping_fields import safe_mapping_dict, safe_text


RQ_ABANDONED_JOB_REASON = "Redis/RQ 已無執行中或等待中的對應任務，判定前一次 Worker 已中斷；請重新送出分析或重跑。"


def create_or_attach_analysis_job(
    *,
    ticker: str,
    pipeline_id: str,
    force: bool = False,
    resume: bool = True,
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
) -> dict:
    normalized_ticker = safe_text(ticker).strip().upper()
    normalized_pipeline = safe_text(pipeline_id).strip() or "v1"
    if not normalized_ticker:
        return serialize_analysis_job({"pipeline_id": normalized_pipeline})
    force_flag = _safe_bool_flag(force)
    resume_flag = _safe_bool_flag(resume, default=True)
    job_id = build_analysis_job_id(normalized_ticker, normalized_pipeline, force=force_flag)
    result = safe_mapping_dict(
        create_or_attach_active_job(
            normalized_ticker,
            normalized_pipeline,
            force=force_flag,
            resume=resume_flag,
            job_id=job_id,
        )
    ) or {}
    job = safe_mapping_dict(result.get("job"))
    job_id = safe_text(job.get("job_id")).strip() if job else ""
    if not job or not job_id:
        return serialize_analysis_job(job or {})

    task_id = analysis_task_id(job_id)
    created = result.get("created")
    if created is False:
        if safe_text(job.get("status")) == "queued" and task_queue_has_task(task_queue, task_id) is False:
            try:
                task_queue.enqueue(
                    task_id,
                    run_stock_analysis_job,
                    job_id,
                    normalized_ticker,
                    normalized_pipeline,
                )
            except Exception as exc:
                message = _queue_exception_message("分析任務重新排入佇列失敗", exc)
                update_job(job_id, "error", error=message)
                append_event(job_id, {"type": "error", "message": message, "pipeline_id": normalized_pipeline})
                job = safe_mapping_dict(get_job(job_id)) or job
            else:
                append_event(
                    job_id,
                    {
                        "type": "status",
                        "phase": "queue_recovered",
                        "level": "warning",
                        "message": "佇列中已找不到此分析任務，已重新排入分析佇列。",
                        "pipeline_id": normalized_pipeline,
                    },
                )
                job = safe_mapping_dict(get_job(job_id)) or job
        return serialize_analysis_job(job)
    if created is not True:
        return serialize_analysis_job(job)

    try:
        if task_queue_has_task(task_queue, task_id) is not True:
            _enqueue_analysis_job(
                task_queue,
                task_id,
                run_stock_analysis_job,
                job_id,
                normalized_ticker,
                normalized_pipeline,
                force_refresh=force_flag,
            )
    except Exception as exc:
        if _looks_like_duplicate_queue_job(exc):
            append_event(
                job_id,
                {
                    "type": "status",
                    "phase": "queue_attach",
                    "message": "佇列中已有相同任務，已附加到既有 RQ job。",
                    "pipeline_id": normalized_pipeline,
                },
            )
        else:
            message = _queue_exception_message("分析任務送入佇列失敗", exc)
            update_job(job_id, "error", error=message)
            append_event(job_id, {"type": "error", "message": message, "pipeline_id": normalized_pipeline})
            job = safe_mapping_dict(get_job(job_id)) or job
    else:
        job = safe_mapping_dict(get_job(job_id)) or job
    return serialize_analysis_job(job)


def cancel_analysis_job(job_id: str, *, task_queue: Any | None = None) -> dict | None:
    safe_job_id = safe_text(job_id).strip()
    job = safe_mapping_dict(get_job(safe_job_id))
    if not job:
        return None

    if safe_text(job.get("status")) == "queued" and task_queue is not None:
        cancel = _safe_getattr(task_queue, "cancel")
        if callable(cancel):
            try:
                cancel(f"analysis:{safe_job_id}")
            except Exception:
                pass
    request_job_cancel(safe_job_id, "使用者要求取消分析任務。")
    updated_job = safe_mapping_dict(get_job(safe_job_id)) or job
    return serialize_analysis_job(updated_job)


def serialize_node_telemetry(job_id: str) -> dict:
    return _serialize_node_telemetry(job_id, list_node_telemetry)


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
