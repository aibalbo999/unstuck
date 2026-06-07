"""Shared runtime event helper facade."""

from __future__ import annotations

from runtime_event_core import (
    RUNTIME_EVENT_CALLBACK_KEY,
    RUNTIME_EVENT_LOG_KEY,
    RuntimeEvent,
    classify_runtime_error,
    make_runtime_error_event,
    make_runtime_event,
)
from runtime_event_emitters import (
    emit_context_error,
    emit_context_error_async,
    emit_context_event,
    emit_context_event_async,
    emit_progress,
    emit_progress_async,
    emit_runtime_event,
    emit_runtime_event_async,
    emit_status,
    emit_status_async,
)
from runtime_event_logs import format_event_log_line
from runtime_logging import log_runtime_message


def emit_log(message_or_event: str | RuntimeEvent, *, level: str = "info") -> None:
    if isinstance(message_or_event, dict):
        message = message_or_event.get("message") or message_or_event.get("detail") or ""
    else:
        message = str(message_or_event)
    if message:
        log_runtime_message(message, level=level)


__all__ = [
    "RUNTIME_EVENT_CALLBACK_KEY",
    "RUNTIME_EVENT_LOG_KEY",
    "RuntimeEvent",
    "classify_runtime_error",
    "emit_context_error",
    "emit_context_error_async",
    "emit_context_event",
    "emit_context_event_async",
    "emit_log",
    "emit_progress",
    "emit_progress_async",
    "emit_runtime_event",
    "emit_runtime_event_async",
    "emit_status",
    "emit_status_async",
    "format_event_log_line",
    "make_runtime_error_event",
    "make_runtime_event",
]
