"""Shared SSE helpers for analysis job routes."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from api_routes.analysis_sse_payloads import (
    replay_bool_field,
    replay_count_field,
    replay_event_id,
    replay_float_field,
    replay_payload_type,
    replay_text_field,
    sanitize_replay_payload,
)
from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text


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
            if cancel_on_disconnect:
                await asyncio.to_thread(deps.request_job_cancel, job_id, "SSE 客戶端斷線，已要求取消分析任務。")
            break

        events = _event_rows(await asyncio.to_thread(deps.get_events_since, job_id, last_sent_event_id))
        replay_advanced = False
        for event in events:
            if await request.is_disconnected():
                terminal_sent = True
                break
            event_row = safe_mapping_dict(event)
            event_id = replay_event_id(event_row.get("id")) if event_row is not None else 0
            if event_row is None or event_id <= 0:
                payload = {
                    "type": "status",
                    "level": "warning",
                    "message": "略過格式異常的分析任務事件",
                    "job_id": job_id,
                }
                deps.print_streamed_event(job_id, payload)
                yield {"data": json.dumps(payload, ensure_ascii=False)}
                continue
            last_sent_event_id = event_id
            replay_advanced = True
            payload = sanitize_replay_payload(event_row.get("payload"), job_id=job_id)
            deps.print_streamed_event(job_id, payload)
            yield {"id": str(event_id), "data": json.dumps(payload, ensure_ascii=False)}
            if payload.get("type") in ["done", "error"]:
                terminal_sent = True
                break

        if terminal_sent:
            break
        if replay_advanced:
            poll_interval = next_sse_poll_interval(had_events=True, current_interval=poll_interval)
            continue

        job = await asyncio.to_thread(deps.get_job, job_id)
        job_row = safe_mapping_dict(job)
        if not job_row:
            payload = {
                "type": "error",
                "phase": "missing_job",
                "message": "找不到分析任務",
            }
            if await asyncio.to_thread(persist_terminal_event_if_missing, deps, job_id, payload):
                continue
            yield {"data": json.dumps(payload, ensure_ascii=False)}
            break

        job_status = safe_text(job_row.get("status")).strip()
        if job_status in ["done", "error", "cancelled"]:
            payload = terminal_payload_for_job(deps, job_row)
            if await asyncio.to_thread(persist_terminal_event_if_missing, deps, job_id, payload):
                continue
            yield {"data": json.dumps(payload, ensure_ascii=False)}
            break

        if await request.is_disconnected():
            break
        yield {"event": "ping", "data": json.dumps({"ts": _now_iso()}, ensure_ascii=False)}
        poll_interval = next_sse_poll_interval(had_events=False, current_interval=poll_interval)
        await asyncio.sleep(poll_interval)


def terminal_payload_for_job(deps: Any, job: dict) -> dict:
    status = safe_text(job.get("status")).strip()
    pipeline_id = safe_text(job.get("pipeline_id")).strip() or "v1"
    if status == "done":
        sequence = deps.get_pipeline_run_sequence(pipeline_id)
        pipeline_sequence = [
            text
            for item in (sequence or ())
            if (text := safe_text(item).strip())
        ]
        return {
            "type": "done",
            "filename": safe_text(job.get("filename")).strip() or None,
            "pipeline_id": pipeline_id,
            "last_pipeline_id": pipeline_sequence[-1] if pipeline_sequence else pipeline_id,
        }
    if status == "cancelled":
        message = safe_text(job.get("error")).strip() or "分析任務已取消"
        return {"type": "error", "phase": "cancelled", "message": message}
    message = safe_text(job.get("error")).strip() or "分析任務失敗"
    return {"type": "error", "message": message}


def persist_terminal_event_if_missing(deps: Any, job_id: str, payload: dict) -> bool:
    try:
        existing_events = _event_rows(deps.get_events_since(job_id, 0))
    except Exception:
        return False
    for event in existing_events:
        if _terminal_event_type(event) in {"done", "error"}:
            return False
    try:
        deps.append_event(job_id, payload)
    except Exception:
        return False
    try:
        updated_events = _event_rows(deps.get_events_since(job_id, 0))
    except Exception:
        return False
    return any(_terminal_event_type(event) in {"done", "error"} for event in updated_events)


def _terminal_event_type(event: Any) -> str:
    event_row = safe_mapping_dict(event)
    if event_row is None:
        return ""
    payload = safe_mapping_dict(event_row.get("payload"))
    if payload is None:
        return ""
    return safe_text(payload.get("type")).strip()


def _event_rows(events: Any) -> list[Any]:
    return safe_sequence_items(events)


def resolve_resume_after_id(request: Request, last_event_id: int | None, since_id: int | None) -> int:
    if since_id is not None:
        resume_after_id = _resume_id_or_none(since_id)
        if resume_after_id is not None:
            return resume_after_id
    if last_event_id is None:
        header_last_event_id = request.headers.get("last-event-id")
        if header_last_event_id:
            last_event_id = _resume_id_or_none(header_last_event_id)
    return _resume_id_or_none(last_event_id) or 0


def _resume_id_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        resume_id = int(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    if resume_id < 0:
        return None
    return resume_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
