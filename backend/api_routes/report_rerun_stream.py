"""Report rerun SSE event replay helpers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from api_routes.analysis_sse import persist_terminal_event_if_missing
from data_trust import sanitize_for_snapshot
from mapping_fields import safe_int, safe_mapping_dict, safe_sequence_items, safe_text


async def report_rerun_event_generator(
    deps: Any,
    request: Any,
    *,
    filename: str,
    job_id: str,
    resume_after_id: int,
    rerun_scope: str,
    cancel_on_disconnect: bool = False,
):
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
                payload = malformed_replay_payload(rerun_scope, filename)
                deps.print_streamed_event(job_id, payload)
                yield {"data": json.dumps(payload, ensure_ascii=False)}
                continue
            last_sent_event_id = event_id
            payload = normalize_replay_payload(event_row.get("payload"), rerun_scope, filename)
            payload_type = safe_text(payload.get("type")).strip() or "status"
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
            payload = terminal_job_payload(job_row, job_status, filename, rerun_scope)
            if await asyncio.to_thread(persist_terminal_event_if_missing, deps, job_id, payload):
                continue
            yield {"data": json.dumps(payload, ensure_ascii=False)}
            break

        if not events:
            if await request.is_disconnected():
                break
            yield {"event": "ping", "data": "ping"}
        await asyncio.sleep(0.5)


def malformed_replay_payload(rerun_scope: str, filename: str) -> dict[str, str]:
    return {
        "type": "status",
        "level": "warning",
        "message": "略過格式異常的報告重跑事件",
        "rerun_scope": rerun_scope,
        "source_filename": filename,
    }


def normalize_replay_payload(value: Any, rerun_scope: str, filename: str) -> dict:
    payload = safe_mapping_dict(value)
    if payload is None:
        return malformed_replay_payload(rerun_scope, filename)
    payload_type = replay_payload_type(payload.get("type"))
    if not payload_type:
        return malformed_replay_payload(rerun_scope, filename)
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
        "filename", "md_filename", "data_filename", "source_filename", "rerun_scope",
        "scope_label", "pipeline_id", "pipeline_label", "name", "detail",
    ):
        if text_field in payload:
            payload[text_field] = replay_text_field(payload.get(text_field))
    return payload


def terminal_job_payload(job_row: dict, job_status: str, filename: str, rerun_scope: str) -> dict:
    job_filename = safe_text(job_row.get("filename")).strip() or None
    if job_status == "done":
        return {
            "type": "done",
            "filename": job_filename,
            "rerun_scope": rerun_scope,
            "source_filename": filename,
        }
    if job_status == "cancelled":
        message = safe_text(job_row.get("error")).strip() or "報告重跑任務已取消"
        return {
            "type": "error",
            "phase": "cancelled",
            "message": message,
            "rerun_scope": rerun_scope,
            "source_filename": filename,
        }
    message = safe_text(job_row.get("error")).strip() or "報告重跑任務失敗"
    return {
        "type": "error",
        "message": message,
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
