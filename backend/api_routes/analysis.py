"""Analysis job and SSE routes."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from api_routes.analysis_sse import analysis_event_generator, next_sse_poll_interval, resolve_resume_after_id


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
        pipeline_id = deps.normalize_pipeline_run_id(body.pipeline_id)
        if deps.create_or_attach_analysis_job is not None:
            return deps.create_or_attach_analysis_job(
                ticker=ticker_upper,
                pipeline_id=pipeline_id,
                force=body.force,
                resume=body.resume,
                task_queue=deps.get_analysis_task_queue(),
                run_stock_analysis_job=deps.run_stock_analysis_job,
            )
        return _legacy_create_and_enqueue_via_deps(deps, ticker_upper, pipeline_id)

    @router.get("/api/analysis-jobs/{job_id}")
    async def get_analysis_job(job_id: str):
        job = deps.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        return _serialize_job(deps, job)

    @router.get("/api/analysis-jobs/{job_id}/telemetry")
    async def get_analysis_job_telemetry(job_id: str):
        job = deps.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        if deps.serialize_node_telemetry is None:
            return {"job_id": job_id, "telemetry": []}
        return deps.serialize_node_telemetry(job_id)

    @router.get("/api/analysis-jobs/{job_id}/events")
    async def stream_analysis_job_events(
        job_id: str,
        request: Request,
        last_event_id: Optional[int] = Query(None, ge=0),
        since_id: Optional[int] = Query(None, ge=0),
        cancel_on_disconnect: bool = Query(False),
    ):
        job = deps.get_job(job_id)
        if not job:
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
                    "ticker": job.get("ticker"),
                    "resume_after_id": resume_after_id,
                    "pipeline_id": job.get("pipeline_id", "v1"),
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
        pipeline_id = deps.normalize_pipeline_run_id(pipeline)
        pipeline_sequence = deps.get_pipeline_run_sequence(pipeline_id)
        pipeline_label = deps.get_pipeline_run_label(pipeline_id)
        agent_total = deps.get_pipeline_run_agent_total(pipeline_id)

        if not deps.has_api_keys():
            async def missing_key_event_generator():
                yield {"data": json.dumps({"type": "error", "message": deps.api_key_setup_message()}, ensure_ascii=False)}

            return EventSourceResponse(missing_key_event_generator())

        header_last_event_id = request.headers.get("last-event-id")
        if last_event_id is None and header_last_event_id:
            try:
                last_event_id = int(header_last_event_id)
            except ValueError:
                last_event_id = 0
        resume_after_id = int(last_event_id or 0)

        should_enqueue = False
        with deps.active_analyses_lock:
            requested_job = deps.get_job(job_id) if job_id else {}
            if requested_job and requested_job.get("ticker") == ticker_upper and requested_job.get("pipeline_id", "v1") == pipeline_id:
                job_id = requested_job["job_id"]
            else:
                active_job = deps.find_active_job(ticker_upper, pipeline_id)
                if active_job:
                    job_id = active_job["job_id"]
                else:
                    if deps.create_or_attach_analysis_job is not None:
                        created = deps.create_or_attach_analysis_job(
                            ticker=ticker_upper,
                            pipeline_id=pipeline_id,
                            force=False,
                            resume=True,
                            task_queue=deps.get_analysis_task_queue(),
                            run_stock_analysis_job=deps.run_stock_analysis_job,
                        )
                        job_id = created["job_id"]
                        should_enqueue = False
                    else:
                        job_id = deps.create_job(ticker_upper, pipeline_id)
                        should_enqueue = True

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
                message = f"分析任務送入佇列失敗：{exc}"
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
                    "pipeline_sequence": list(pipeline_sequence),
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
        pipeline_id = deps.normalize_pipeline_run_id(pipeline)
        job = deps.get_job(job_id)
        if not job or job.get("ticker") != ticker_upper or job.get("pipeline_id", "v1") != pipeline_id:
            return {"ok": False, "message": "找不到可取消的分析任務"}
        ok = deps.request_job_cancel(job_id, "使用者要求取消分析任務。")
        return {"ok": ok, "job_id": job_id, "status": "cancelling" if ok else "not_found"}

    @router.post("/api/analysis-jobs/{job_id}/cancel")
    async def cancel_analysis_job_by_id(request: Request, job_id: str):
        deps.require_mutation_authorized(request)
        job = deps.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        if deps.cancel_analysis_job is not None:
            result = deps.cancel_analysis_job(job_id, task_queue=deps.get_analysis_task_queue())
            if result is None:
                raise HTTPException(status_code=404, detail="Analysis job not found")
            return result
        ok = deps.request_job_cancel(job_id, "使用者要求取消分析任務。")
        return {"job_id": job_id, "status": "cancelled" if ok else "not_found"}

    return router


def _serialize_job(deps: AnalysisRouteDeps, job: dict) -> dict:
    if deps.serialize_analysis_job is not None:
        return deps.serialize_analysis_job(job)
    return dict(job)


def _legacy_create_and_enqueue_via_deps(deps: AnalysisRouteDeps, ticker: str, pipeline_id: str) -> dict:
    job_id = deps.create_job(ticker, pipeline_id)
    try:
        deps.get_analysis_task_queue().enqueue(
            f"analysis:{job_id}",
            deps.run_stock_analysis_job,
            job_id,
            ticker,
            pipeline_id,
        )
    except Exception as exc:
        message = f"分析任務送入佇列失敗：{exc}"
        deps.update_job(job_id, "error", error=message)
        deps.append_event(job_id, {"type": "error", "message": message})
    return _serialize_job(deps, deps.get_job(job_id))
