"""Shared SSE helpers for analysis job routes."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import Request


INITIAL_SSE_POLL_INTERVAL_SECONDS = 0.5
MAX_SSE_POLL_INTERVAL_SECONDS = 5.0


def next_sse_poll_interval(*, had_events: bool, current_interval: float) -> float:
    if had_events:
        return INITIAL_SSE_POLL_INTERVAL_SECONDS
    if current_interval < 1.0:
        return 1.0
    if current_interval < 2.0:
        return 2.0
    return MAX_SSE_POLL_INTERVAL_SECONDS


async def analysis_event_generator(
    deps: Any,
    request: Request,
    *,
    job_id: str,
    resume_after_id: int,
    cancel_on_disconnect: bool,
    intro_payload: dict,
):
    last_sent_event_id = resume_after_id
    terminal_sent = False
    poll_interval = INITIAL_SSE_POLL_INTERVAL_SECONDS
    yield {"data": json.dumps(intro_payload, ensure_ascii=False)}
    while True:
        if await request.is_disconnected():
            deps.append_event(job_id, {
                "type": "status",
                "phase": "client_disconnected",
                "level": "info",
                "message": "SSE 客戶端已斷線。",
                "pipeline_id": intro_payload.get("pipeline_id", "v1"),
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
        if events:
            poll_interval = next_sse_poll_interval(had_events=True, current_interval=poll_interval)
            continue

        job = await asyncio.to_thread(deps.get_job, job_id)
        if job.get("status") in ["done", "error", "cancelled"]:
            yield {"data": json.dumps(terminal_payload_for_job(deps, job), ensure_ascii=False)}
            break

        if await request.is_disconnected():
            break
        yield {"event": "ping", "data": json.dumps({"ts": _now_iso()}, ensure_ascii=False)}
        poll_interval = next_sse_poll_interval(had_events=False, current_interval=poll_interval)
        await asyncio.sleep(poll_interval)


def terminal_payload_for_job(deps: Any, job: dict) -> dict:
    status = job.get("status")
    pipeline_id = job.get("pipeline_id", "v1")
    if status == "done":
        sequence = deps.get_pipeline_run_sequence(pipeline_id)
        return {
            "type": "done",
            "filename": job.get("filename"),
            "pipeline_id": pipeline_id,
            "last_pipeline_id": sequence[-1] if sequence else pipeline_id,
        }
    if status == "cancelled":
        return {"type": "error", "phase": "cancelled", "message": job.get("error", "分析任務已取消")}
    return {"type": "error", "message": job.get("error", "分析任務失敗")}


def resolve_resume_after_id(request: Request, last_event_id: int | None, since_id: int | None) -> int:
    if since_id is not None:
        return int(since_id)
    if last_event_id is None:
        header_last_event_id = request.headers.get("last-event-id")
        if header_last_event_id:
            try:
                last_event_id = int(header_last_event_id)
            except ValueError:
                last_event_id = 0
    return int(last_event_id or 0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
