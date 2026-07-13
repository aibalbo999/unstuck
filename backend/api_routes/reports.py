"""Report and history routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from analysis_job_service import task_queue_has_task
from api_routes.analysis_sse import persist_terminal_event_if_missing, resolve_resume_after_id
from data_trust import sanitize_for_snapshot
from mapping_fields import safe_int, safe_mapping_dict, safe_sequence_items, safe_text
from report_index import is_safe_report_filename
from report_history_storage import existing_storage_key
import report_history_service
import report_refresh_service
import report_rerun_service
import report_compare_service
from storage.report_storage import ReportStorage


@dataclass(frozen=True)
class ReportRouteDeps:
    get_output_dir: Callable[[], str]
    get_report_storage: Callable[[], ReportStorage]
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
    create_or_attach_job: Callable[..., dict] | None = None


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
        return report_history_service.delete_report_files(
            filename,
            deps.get_output_dir(),
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
        report_storage = deps.get_report_storage()
        if existing_storage_key(report_storage, filename, kind="html") is None:
            raise HTTPException(status_code=404, detail="找不到報告")
        if existing_storage_key(report_storage, filename, kind="data") is None:
            raise HTTPException(status_code=404, detail="舊報告沒有資料快照，無法局部重跑")

        pipeline_id = f"rerun:{normalized_scope}"
        should_enqueue = True
        recovered_orphaned_queue_task = False
        if deps.create_or_attach_job is not None:
            result = deps.create_or_attach_job(filename, pipeline_id)
            job = result["job"]
            job_id = job["job_id"]
            should_enqueue = result.get("created") is True
            task_id = f"report-rerun:{job_id}"
            task_queue = deps.get_task_queue()
            job_status = safe_text(job.get("status")).strip()
            if (
                not should_enqueue
                and job_status == "queued"
                and task_queue_has_task(task_queue, task_id) is False
            ):
                should_enqueue = True
                recovered_orphaned_queue_task = True
        else:
            job_id = deps.create_job(filename, pipeline_id)
            task_queue = deps.get_task_queue()

        if should_enqueue:
            try:
                task_queue.enqueue(
                    f"report-rerun:{job_id}",
                    deps.run_report_rerun_job,
                    job_id,
                    filename,
                    normalized_scope,
                )
            except Exception as exc:
                failure_detail = safe_text(exc).strip() or "未知錯誤"
                message = f"報告重跑任務送入佇列失敗：{failure_detail}"
                deps.update_job(job_id, "error", error=message)
                deps.append_event(job_id, {
                    "type": "error",
                    "message": message,
                    "rerun_scope": normalized_scope,
                    "source_filename": filename,
                })
            else:
                if recovered_orphaned_queue_task:
                    deps.append_event(job_id, {
                        "type": "status",
                        "phase": "queue_recovered",
                        "level": "warning",
                        "message": "佇列中已找不到此報告重跑任務，已重新排入重跑佇列。",
                        "rerun_scope": normalized_scope,
                        "source_filename": filename,
                    })

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
        job_row = safe_mapping_dict(job)
        pipeline_id = safe_text(job_row.get("pipeline_id")).strip() if job_row is not None else ""
        job_ticker = safe_text(job_row.get("ticker")).strip() if job_row is not None else ""
        if job_row is None or job_ticker != filename or not pipeline_id.startswith("rerun:"):
            raise HTTPException(status_code=404, detail="找不到報告重跑任務")

        resume_after_id = resolve_resume_after_id(request, last_event_id, None)
        rerun_scope = (
            pipeline_id
            .strip()
            .split(":", 1)[-1]
            .strip()
            .lower()
            .replace("-", "_")
            or "final_recommendation"
        )

        async def event_generator():
            last_sent_event_id = resume_after_id
            terminal_sent = False

            def malformed_replay_payload() -> dict[str, str]:
                return {
                    "type": "status",
                    "level": "warning",
                    "message": "略過格式異常的報告重跑事件",
                    "rerun_scope": rerun_scope,
                    "source_filename": filename,
                }

            def replay_text_field(value: Any) -> str:
                if isinstance(value, Mapping) or isinstance(value, (list, tuple, set, frozenset)):
                    return ""
                return safe_text(value).strip()

            def replay_payload_type(value: Any) -> str:
                if not isinstance(value, str):
                    return ""
                return safe_text(value).strip()

            def replay_count_field(value: Any) -> int:
                if isinstance(value, (bool, bytes, bytearray, memoryview)):
                    return 0
                return safe_int(value)

            def replay_event_id(value: Any) -> int:
                if isinstance(value, (bool, bytes, bytearray, memoryview)):
                    return 0
                return safe_int(value)

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
                    if cancel_on_disconnect:
                        await asyncio.to_thread(deps.request_job_cancel, job_id, "SSE 客戶端斷線，已要求取消報告重跑任務。")
                    break

                events = safe_sequence_items(await asyncio.to_thread(deps.get_events_since, job_id, last_sent_event_id))
                for event in events:
                    if await request.is_disconnected():
                        terminal_sent = True
                        break
                    event_row = safe_mapping_dict(event)
                    event_id = replay_event_id(event_row.get("id")) if event_row is not None else 0
                    if event_row is None or event_id <= 0:
                        payload = malformed_replay_payload()
                        deps.print_streamed_event(job_id, payload)
                        yield {"data": json.dumps(payload, ensure_ascii=False)}
                        continue
                    last_sent_event_id = event_id
                    payload = safe_mapping_dict(event_row.get("payload"))
                    if payload is None:
                        payload = malformed_replay_payload()
                        payload_type = "status"
                    else:
                        payload_type = replay_payload_type(payload.get("type"))
                        if not payload_type:
                            payload = malformed_replay_payload()
                            payload_type = "status"
                        else:
                            payload = {**payload, "type": payload_type}
                            for control_field in ("phase", "level"):
                                if control_field in payload:
                                    payload[control_field] = replay_text_field(payload.get(control_field))
                            for count_field in ("current", "total", "agent_num", "status_code"):
                                if count_field in payload:
                                    payload[count_field] = replay_count_field(payload.get(count_field))
                            for structured_field in ("data_trust", "partial_rerun", "metadata", "details"):
                                if structured_field in payload:
                                    payload[structured_field] = sanitize_for_snapshot(payload.get(structured_field))
                            if "message" in payload:
                                payload["message"] = replay_text_field(payload.get("message"))
                            for text_field in (
                                "filename",
                                "md_filename",
                                "data_filename",
                                "source_filename",
                                "rerun_scope",
                                "scope_label",
                                "pipeline_id",
                                "pipeline_label",
                                "name",
                                "detail",
                            ):
                                if text_field in payload:
                                    payload[text_field] = replay_text_field(payload.get(text_field))
                    deps.print_streamed_event(job_id, payload)
                    yield {"id": str(event_id), "data": json.dumps(payload, ensure_ascii=False)}
                    if payload_type in ["done", "error"]:
                        terminal_sent = True
                        break

                if terminal_sent:
                    break

                job = await asyncio.to_thread(deps.get_job, job_id)
                job_row = safe_mapping_dict(job)
                if not job_row:
                    payload = {
                        "type": "error",
                        "message": "找不到報告重跑任務",
                        "rerun_scope": rerun_scope,
                        "source_filename": filename,
                    }
                    if await asyncio.to_thread(persist_terminal_event_if_missing, deps, job_id, payload):
                        continue
                    yield {"data": json.dumps(payload, ensure_ascii=False)}
                    break
                job_status = safe_text(job_row.get("status")).strip()
                if job_status in ["done", "error", "cancelled"]:
                    job_filename = safe_text(job_row.get("filename")).strip() or None
                    if job_status == "done":
                        payload = {
                            "type": "done",
                            "filename": job_filename,
                            "rerun_scope": rerun_scope,
                            "source_filename": filename,
                        }
                    elif job_status == "cancelled":
                        message = safe_text(job_row.get("error")).strip() or "報告重跑任務已取消"
                        payload = {
                            "type": "error",
                            "phase": "cancelled",
                            "message": message,
                            "rerun_scope": rerun_scope,
                            "source_filename": filename,
                        }
                    else:
                        message = safe_text(job_row.get("error")).strip() or "報告重跑任務失敗"
                        payload = {
                            "type": "error",
                            "message": message,
                            "rerun_scope": rerun_scope,
                            "source_filename": filename,
                        }
                    if await asyncio.to_thread(persist_terminal_event_if_missing, deps, job_id, payload):
                        continue
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
        job_row = safe_mapping_dict(job)
        pipeline_id = safe_text(job_row.get("pipeline_id")).strip() if job_row is not None else ""
        job_ticker = safe_text(job_row.get("ticker")).strip() if job_row is not None else ""
        if job_row is None or job_ticker != filename or not pipeline_id.startswith("rerun:"):
            return {"ok": False, "message": "找不到可取消的報告重跑任務"}
        ok = deps.request_job_cancel(job_id, "使用者要求取消報告重跑任務。")
        return {"ok": ok, "job_id": job_id, "status": "cancelling" if ok else "not_found"}

    return router
