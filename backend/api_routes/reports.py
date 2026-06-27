"""Report and history routes."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from data_trust import data_snapshot_filename_for_report
from report_index import is_safe_report_filename
import report_history_service
import report_refresh_service
import report_rerun_service
import report_compare_service
from storage.report_storage import ReportStorage


@dataclass(frozen=True)
class ReportRouteDeps:
    get_output_dir: Callable[[], str]
    get_report_storage: Callable[[], ReportStorage]
    get_report_cache: Callable[[], dict]
    get_refresh_service: Callable[[], Any]
    get_pipeline_runner: Callable[[], Any]
    get_report_renderer: Callable[[], Any]
    get_task_queue: Callable[[], Any]
    run_report_rerun_job: Callable[[str, str, str], str]
    create_job: Callable[[str, str], str]
    get_job: Callable[[str], dict]
    get_events_since: Callable[[str, int], list[dict]]
    update_job: Callable[..., Any]
    append_event: Callable[[str, dict], Any]
    request_job_cancel: Callable[[str, str], bool]
    print_streamed_event: Callable[[str, dict], None]
    require_mutation_authorized: Callable[[Request], None]
    get_report_cache_lock: Callable[[], Any] | None = None


def create_reports_router(deps: ReportRouteDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/api/reports")
    def get_reports(
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=100),
        q: str = Query("", max_length=80),
        pipeline: str = Query("all", max_length=24),
        recommendation: str = Query("all", max_length=24),
        data_trust: str = Query("all", max_length=24),
        include_versions: bool = Query(False),
    ):
        return report_history_service.list_reports(
            page=page,
            limit=limit,
            q=q,
            pipeline=pipeline,
            recommendation=recommendation,
            data_trust=data_trust,
            include_versions=include_versions,
            output_dir=deps.get_output_dir(),
            report_cache=deps.get_report_cache(),
            storage=deps.get_report_storage(),
        )

    @router.get("/api/reports/compare")
    def compare_reports(
        left: str = Query(..., min_length=1, max_length=180),
        right: str = Query(..., min_length=1, max_length=180),
    ):
        return report_compare_service.compare_reports(
            left,
            right,
            output_dir=deps.get_output_dir(),
        )

    @router.delete("/api/reports/{filename}")
    def delete_report(filename: str, request: Request):
        deps.require_mutation_authorized(request)
        report_cache_lock = deps.get_report_cache_lock() if deps.get_report_cache_lock else None
        return report_history_service.delete_report_files(
            filename,
            deps.get_output_dir(),
            deps.get_report_cache(),
            report_cache_lock=report_cache_lock,
            storage=deps.get_report_storage(),
        )

    @router.get("/api/report/{filename}")
    async def get_report(filename: str):
        return report_history_service.get_report_file(filename, deps.get_output_dir(), storage=deps.get_report_storage())

    @router.get("/api/report/{filename}/download/html")
    async def download_html_report(filename: str):
        return report_history_service.download_report_file(filename, deps.get_output_dir(), "html", storage=deps.get_report_storage())

    @router.get("/api/report/{filename}/download/md")
    async def download_md_report(filename: str):
        return report_history_service.download_report_file(filename, deps.get_output_dir(), "md", storage=deps.get_report_storage())

    @router.get("/api/report/{filename}/download/data")
    async def download_data_snapshot(filename: str):
        return report_history_service.download_report_file(filename, deps.get_output_dir(), "data", storage=deps.get_report_storage())

    @router.post("/api/report/{filename}/refresh/data")
    async def refresh_report_data_snapshot(filename: str, request: Request):
        deps.require_mutation_authorized(request)
        return await report_refresh_service.refresh_report_data_snapshot(
            filename,
            output_dir=deps.get_output_dir(),
            refresh_service=deps.get_refresh_service(),
            storage=deps.get_report_storage(),
        )

    @router.post("/api/report/{filename}/rerun")
    async def rerun_report_analysis(
        filename: str,
        request: Request,
        scope: str = Query("final_recommendation", max_length=32),
    ):
        deps.require_mutation_authorized(request)
        normalized_scope = report_rerun_service.normalize_rerun_scope(scope)
        if not is_safe_report_filename(filename, ".html"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        html_path = os.path.join(deps.get_output_dir(), filename)
        if not os.path.exists(html_path):
            raise HTTPException(status_code=404, detail="找不到報告")
        data_path = os.path.join(deps.get_output_dir(), data_snapshot_filename_for_report(filename))
        if not os.path.exists(data_path):
            raise HTTPException(status_code=404, detail="舊報告沒有資料快照，無法局部重跑")

        job_id = deps.create_job(filename, f"rerun:{normalized_scope}")
        try:
            deps.get_task_queue().enqueue(
                f"report-rerun:{job_id}",
                deps.run_report_rerun_job,
                job_id,
                filename,
                normalized_scope,
            )
        except Exception as exc:
            message = f"報告重跑任務送入佇列失敗：{exc}"
            deps.update_job(job_id, "error", error=message)
            deps.append_event(job_id, {"type": "error", "message": message, "rerun_scope": normalized_scope})

        return {
            "success": True,
            "queued": True,
            "job_id": job_id,
            "filename": filename,
            "scope": normalized_scope,
            "scope_label": report_rerun_service.RERUN_SCOPE_LABELS.get(normalized_scope, normalized_scope),
            "stream_url": f"/api/report/{filename}/rerun/stream?job_id={job_id}",
        }

    @router.get("/api/report/{filename}/rerun/stream")
    async def stream_report_rerun(
        filename: str,
        request: Request,
        job_id: str = Query(..., min_length=1),
        last_event_id: Optional[int] = Query(None, ge=0),
        cancel_on_disconnect: bool = Query(False),
    ):
        if not is_safe_report_filename(filename, ".html"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        job = deps.get_job(job_id)
        if not job or job.get("ticker") != filename or not str(job.get("pipeline_id", "")).startswith("rerun:"):
            raise HTTPException(status_code=404, detail="找不到報告重跑任務")

        header_last_event_id = request.headers.get("last-event-id")
        if last_event_id is None and header_last_event_id:
            try:
                last_event_id = int(header_last_event_id)
            except ValueError:
                last_event_id = 0
        resume_after_id = int(last_event_id or 0)
        rerun_scope = str(job.get("pipeline_id") or "rerun:final_recommendation").split(":", 1)[-1]

        async def event_generator():
            last_sent_event_id = resume_after_id
            terminal_sent = False
            yield {
                "data": json.dumps(
                    {
                        "type": "job",
                        "job_id": job_id,
                        "filename": filename,
                        "rerun_scope": rerun_scope,
                        "resume_after_id": resume_after_id,
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
                        "rerun_scope": rerun_scope,
                        "source_filename": filename,
                    })
                    if cancel_on_disconnect:
                        await asyncio.to_thread(deps.request_job_cancel, job_id, "SSE 客戶端斷線，已要求取消報告重跑任務。")
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
                        payload = {
                            "type": "done",
                            "filename": job.get("filename"),
                            "rerun_scope": rerun_scope,
                            "source_filename": filename,
                        }
                    elif job.get("status") == "cancelled":
                        payload = {"type": "error", "phase": "cancelled", "message": job.get("error", "報告重跑任務已取消")}
                    else:
                        payload = {"type": "error", "message": job.get("error", "報告重跑任務失敗")}
                    yield {"data": json.dumps(payload, ensure_ascii=False)}
                    break

                if not events:
                    if await request.is_disconnected():
                        break
                    yield {"event": "ping", "data": "ping"}
                await asyncio.sleep(0.5)

        return EventSourceResponse(event_generator())

    @router.post("/api/report/{filename}/rerun/cancel")
    async def cancel_report_rerun(
        filename: str,
        request: Request,
        job_id: str = Query(..., min_length=1),
    ):
        deps.require_mutation_authorized(request)
        job = deps.get_job(job_id)
        if not job or job.get("ticker") != filename or not str(job.get("pipeline_id", "")).startswith("rerun:"):
            return {"ok": False, "message": "找不到可取消的報告重跑任務"}
        ok = deps.request_job_cancel(job_id, "使用者要求取消報告重跑任務。")
        return {"ok": ok, "job_id": job_id, "status": "cancelling" if ok else "not_found"}

    return router
