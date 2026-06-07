"""Runtime event terminal log formatting."""

from __future__ import annotations

from runtime_event_core import RuntimeEvent
from runtime_logging import log_runtime_message


def format_event_log_line(job_id: str | None, payload: RuntimeEvent, prefix: str = "job") -> str:
    event_type = payload.get("type", "event")
    message = payload.get("message") or payload.get("name") or payload.get("filename") or ""
    if event_type == "progress":
        message = f"Agent {payload.get('current')}/{payload.get('total')} 完成：{payload.get('name', '')}"
    elif event_type == "done":
        message = f"報告生成完成：{payload.get('filename', '')}"
    elif event_type == "error":
        message = f"錯誤：{message}"

    job_label = (job_id or "")[:8]
    line = f"[{prefix} {job_label}] {event_type}: {message}"
    detail = payload.get("detail")
    if detail:
        line += f" | {detail}"
    return line[:500]


def emit_log(message_or_event: str | RuntimeEvent, *, level: str = "info") -> None:
    if isinstance(message_or_event, dict):
        message = message_or_event.get("message") or message_or_event.get("detail") or ""
    else:
        message = str(message_or_event)
    if message:
        log_runtime_message(message, level=level)
