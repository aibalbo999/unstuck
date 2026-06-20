"""Analysis job and SSE routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse


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


def create_analysis_router(deps: AnalysisRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/analyze")

    @router.get("/{ticker}")
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

        async def event_generator():
            last_sent_event_id = resume_after_id
            terminal_sent = False
            yield {
                "data": json.dumps(
                    {
                        "type": "job",
                        "job_id": job_id,
                        "ticker": ticker_upper,
                        "resume_after_id": resume_after_id,
                        "pipeline_id": pipeline_id,
                        "pipeline_label": pipeline_label,
                        "pipeline_sequence": list(pipeline_sequence),
                        "agent_total": agent_total,
                    },
                    ensure_ascii=False,
                )
            }
            while True:
                if await request.is_disconnected():
                    deps.append_event(job_id, {
                        "type": "status",
                        "phase": "client_disconnected",
                        "level": "info",
                        "message": "SSE 客戶端已斷線。",
                        "pipeline_id": pipeline_id,
                        "pipeline_label": pipeline_label,
                    })
                    if cancel_on_disconnect:
                        await asyncio.to_thread(deps.request_job_cancel, job_id, "SSE 客戶端斷線，已要求取消分析任務。")
                    break

                events = await asyncio.to_thread(deps.get_events_since, job_id, last_sent_event_id)
                for event in events:
                    if await request.is_disconnected():
                        terminal_sent = True
                        break
                    last_sent_event_id = event["id"]
                    payload = event["payload"]
                    deps.print_streamed_event(job_id, payload)
                    yield {"id": str(event["id"]), "data": json.dumps(payload, ensure_ascii=False)}
                    if payload.get("type") in ["done", "error"]:
                        terminal_sent = True
                        break

                if terminal_sent:
                    break

                job = await asyncio.to_thread(deps.get_job, job_id)
                if job.get("status") in ["done", "error", "cancelled"]:
                    if job.get("status") == "done":
                        job_pipeline_id = job.get("pipeline_id", pipeline_id)
                        job_pipeline_sequence = deps.get_pipeline_run_sequence(job_pipeline_id)
                        payload = {
                            "type": "done",
                            "filename": job.get("filename"),
                            "pipeline_id": job_pipeline_id,
                            "last_pipeline_id": job_pipeline_sequence[-1] if job_pipeline_sequence else job_pipeline_id,
                        }
                    elif job.get("status") == "cancelled":
                        payload = {"type": "error", "phase": "cancelled", "message": job.get("error", "分析任務已取消")}
                    else:
                        payload = {"type": "error", "message": job.get("error", "分析任務失敗")}
                    yield {"data": json.dumps(payload, ensure_ascii=False)}
                    break

                if not events:
                    if await request.is_disconnected():
                        break
                    yield {"event": "ping", "data": "ping"}
                await asyncio.sleep(0.5)

        return EventSourceResponse(event_generator())

    @router.post("/{ticker}/cancel")
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

    return router
