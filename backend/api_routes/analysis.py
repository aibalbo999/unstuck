"""Analysis job and SSE routes."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from api_routes.analysis_payloads import (
    _legacy_create_and_enqueue_via_deps,
    _safe_api_key_ready,
    _safe_bool_result,
    _safe_intro_count,
    _safe_json_response_mapping,
    _safe_pipeline_id,
    _serialize_create_result,
    _serialize_job,
)
from api_routes.analysis_sse import analysis_event_generator, next_sse_poll_interval, resolve_resume_after_id
from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text


@dataclass(frozen=True)
class AnalysisRouteDeps:
    active_analyses_lock: Any
    get_analysis_task_queue: Callable[[], Any]
    run_stock_analysis_job: Callable[[str, str, str], str]
    has_api_keys: Callable[[], bool]
    api_key_setup_message: Callable[[], str]
    normalize_pipeline_run_id: Callable[[str], str]
    get_pipeline_run_sequence: Callable[[str], tuple]
    get_pipeline_run_label: Callable[[str], str]
    get_pipeline_run_agent_total: Callable[[str], int]
    get_job: Callable[[str], dict]
    find_active_job: Callable[[str, str], dict]
    create_job: Callable[[str, str], str]
    get_events_since: Callable[[str, int], list[dict]]
    update_job: Callable[..., Any]
    append_event: Callable[[str, dict], Any]
    request_job_cancel: Callable[[str, str], bool]
    print_streamed_event: Callable[[str, dict], None]
    require_mutation_authorized: Callable[[Request], None]
    create_or_attach_analysis_job: Callable[..., dict] | None = None
    cancel_analysis_job: Callable[..., dict | None] | None = None
    serialize_analysis_job: Callable[[dict], dict] | None = None
    serialize_node_telemetry: Callable[[str], dict] | None = None


class AnalysisJobCreateRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    pipeline_id: str = Field("v1", max_length=24)
    force: bool = False
    resume: bool = True


def create_analysis_router(deps: AnalysisRouteDeps) -> APIRouter:
    router = APIRouter()

    @router.post("/api/analysis-jobs")
    async def create_analysis_job(request: Request, body: AnalysisJobCreateRequest):
        deps.require_mutation_authorized(request)
        ticker_upper = body.ticker.strip().upper()
        pipeline_id = _safe_pipeline_id(deps.normalize_pipeline_run_id(body.pipeline_id))
        if deps.create_or_attach_analysis_job is not None:
            created = safe_mapping_dict(deps.create_or_attach_analysis_job(
                ticker=ticker_upper,
                pipeline_id=pipeline_id,
                force=body.force,
                resume=body.resume,
                task_queue=deps.get_analysis_task_queue(),
                run_stock_analysis_job=deps.run_stock_analysis_job,
            ))
            if not created:
                return _serialize_create_result(deps, {"pipeline_id": pipeline_id}, pipeline_id)
            return _serialize_create_result(deps, created, pipeline_id)
        return _legacy_create_and_enqueue_via_deps(deps, ticker_upper, pipeline_id)

    @router.get("/api/analysis-jobs/{job_id}")
    async def get_analysis_job(job_id: str):
        job = deps.get_job(job_id)
        job_row = safe_mapping_dict(job)
        if not job_row:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        serialized = safe_mapping_dict(_serialize_job(deps, job_row)) or {}
        return _safe_json_response_mapping(serialized)

    @router.get("/api/analysis-jobs/{job_id}/telemetry")
    async def get_analysis_job_telemetry(job_id: str):
        job = deps.get_job(job_id)
        job_row = safe_mapping_dict(job)
        if not job_row:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        if deps.serialize_node_telemetry is None:
            return {"job_id": job_id, "telemetry": []}
        telemetry_payload = safe_mapping_dict(deps.serialize_node_telemetry(job_id))
        if telemetry_payload is None:
            return {"job_id": job_id, "telemetry": []}
        return _safe_json_response_mapping(telemetry_payload)

    @router.get("/api/analysis-jobs/{job_id}/events")
    async def stream_analysis_job_events(
        job_id: str,
        request: Request,
        last_event_id: Optional[int] = Query(None, ge=0),
        since_id: Optional[int] = Query(None, ge=0),
        cancel_on_disconnect: bool = Query(False),
    ):
        job = deps.get_job(job_id)
        job_row = safe_mapping_dict(job)
        if not job_row:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        resume_after_id = resolve_resume_after_id(request, last_event_id, since_id)
        return EventSourceResponse(
            analysis_event_generator(
                deps,
                request,
                job_id=job_id,
                resume_after_id=resume_after_id,
                cancel_on_disconnect=cancel_on_disconnect,
                intro_payload={
                    "type": "job",
                    "job_id": job_id,
                    "ticker": safe_text(job_row.get("ticker")).strip().upper(),
                    "resume_after_id": resume_after_id,
                    "pipeline_id": safe_text(job_row.get("pipeline_id")).strip() or "v1",
                },
            )
        )

    @router.get("/api/analyze/{ticker}")
    async def analyze_stock(
        ticker: str,
        request: Request,
        job_id: Optional[str] = Query(None),
        last_event_id: Optional[int] = Query(None, ge=0),
        pipeline: str = Query("v1", max_length=24),
        cancel_on_disconnect: bool = Query(False),
    ):
        ticker_upper = ticker.strip().upper()
        pipeline_id = _safe_pipeline_id(deps.normalize_pipeline_run_id(pipeline))
        pipeline_sequence = [
            text
            for item in safe_sequence_items(deps.get_pipeline_run_sequence(pipeline_id))
            if (text := safe_text(item).strip())
        ]
        pipeline_label = safe_text(deps.get_pipeline_run_label(pipeline_id)).strip()
        agent_total = _safe_intro_count(deps.get_pipeline_run_agent_total(pipeline_id))

        if not _safe_api_key_ready(deps.has_api_keys()):
            async def missing_key_event_generator():
                message = safe_text(deps.api_key_setup_message()).strip()
                yield {"data": json.dumps({"type": "error", "message": message}, ensure_ascii=False)}

            return EventSourceResponse(missing_key_event_generator())

        resume_after_id = resolve_resume_after_id(request, last_event_id, since_id=None)

        should_enqueue = False
        with deps.active_analyses_lock:
            requested_job = safe_mapping_dict(deps.get_job(job_id)) if job_id else {}
            requested_job_id = ""
            requested_ticker = ""
            requested_pipeline_id = ""
            if requested_job:
                requested_job_id = safe_text(requested_job.get("job_id")).strip()
                requested_ticker = safe_text(requested_job.get("ticker")).strip().upper()
                requested_pipeline_id = safe_text(requested_job.get("pipeline_id")).strip() or "v1"
            if (
                requested_job
                and requested_job_id
                and requested_ticker == ticker_upper
                and requested_pipeline_id == pipeline_id
            ):
                job_id = requested_job_id
            else:
                active_job = safe_mapping_dict(deps.find_active_job(ticker_upper, pipeline_id))
                active_job_id = safe_text(active_job.get("job_id")).strip() if active_job else ""
                if active_job_id:
                    job_id = active_job_id
                else:
                    if deps.create_or_attach_analysis_job is not None:
                        created = safe_mapping_dict(deps.create_or_attach_analysis_job(
                            ticker=ticker_upper,
                            pipeline_id=pipeline_id,
                            force=False,
                            resume=True,
                            task_queue=deps.get_analysis_task_queue(),
                            run_stock_analysis_job=deps.run_stock_analysis_job,
                        ))
                        created_job_id = safe_text(created.get("job_id")).strip() if created else ""
                        if created_job_id:
                            job_id = created_job_id
                            should_enqueue = False
                        else:
                            job_id = safe_text(deps.create_job(ticker_upper, pipeline_id)).strip()
                            should_enqueue = bool(job_id)
                    else:
                        job_id = safe_text(deps.create_job(ticker_upper, pipeline_id)).strip()
                        should_enqueue = bool(job_id)

        if should_enqueue:
            try:
                deps.get_analysis_task_queue().enqueue(
                    f"analysis:{job_id}",
                    deps.run_stock_analysis_job,
                    job_id,
                    ticker_upper,
                    pipeline_id,
                )
            except Exception as exc:
                detail = safe_text(exc).strip()
                message = f"分析任務送入佇列失敗：{detail}" if detail else "分析任務送入佇列失敗"
                deps.update_job(job_id, "error", error=message)
                deps.append_event(job_id, {"type": "error", "message": message})

        response = EventSourceResponse(
            analysis_event_generator(
                deps,
                request,
                job_id=job_id,
                resume_after_id=resume_after_id,
                cancel_on_disconnect=cancel_on_disconnect,
                intro_payload={
                    "type": "job",
                    "job_id": job_id,
                    "ticker": ticker_upper,
                    "resume_after_id": resume_after_id,
                    "pipeline_id": pipeline_id,
                    "pipeline_label": pipeline_label,
                    "pipeline_sequence": pipeline_sequence,
                    "agent_total": agent_total,
                    "deprecated": True,
                    "replacement_endpoint": "/api/analysis-jobs",
                },
            )
        )
        response.headers["Deprecation"] = "true"
        response.headers["Link"] = '</api/analysis-jobs>; rel="successor-version"'
        return response

    @router.post("/api/analyze/{ticker}/cancel")
    async def cancel_analysis_job(
        request: Request,
        ticker: str,
        job_id: str = Query(..., min_length=1),
        pipeline: str = Query("v1", max_length=24),
    ):
        deps.require_mutation_authorized(request)
        ticker_upper = ticker.strip().upper()
        pipeline_id = _safe_pipeline_id(deps.normalize_pipeline_run_id(pipeline))
        job = deps.get_job(job_id)
        job_row = safe_mapping_dict(job)
        job_ticker = safe_text(job_row.get("ticker")).strip().upper() if job_row else ""
        job_pipeline_id = safe_text(job_row.get("pipeline_id")).strip() or "v1" if job_row else ""
        if not job_row or job_ticker != ticker_upper or job_pipeline_id != pipeline_id:
            return {"ok": False, "message": "找不到可取消的分析任務"}
        ok = _safe_bool_result(deps.request_job_cancel(job_id, "使用者要求取消分析任務。"))
        return {"ok": ok, "job_id": job_id, "status": "cancelling" if ok else "not_found"}

    @router.post("/api/analysis-jobs/{job_id}/cancel")
    async def cancel_analysis_job_by_id(request: Request, job_id: str):
        deps.require_mutation_authorized(request)
        job = deps.get_job(job_id)
        job_row = safe_mapping_dict(job)
        if not job_row:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        if deps.cancel_analysis_job is not None:
            result = safe_mapping_dict(deps.cancel_analysis_job(job_id, task_queue=deps.get_analysis_task_queue()))
            if result is None:
                raise HTTPException(status_code=404, detail="Analysis job not found")
            return _safe_json_response_mapping(result)
        ok = _safe_bool_result(deps.request_job_cancel(job_id, "使用者要求取消分析任務。"))
        return {"job_id": job_id, "status": "cancelled" if ok else "not_found"}

    return router
