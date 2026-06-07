"""Shared runtime event helpers for pipeline, jobs, and SSE logging."""

from __future__ import annotations

import inspect
from typing import Any, Callable
from runtime_logging import log_runtime_message

RuntimeEvent = dict[str, Any]
RUNTIME_EVENT_CALLBACK_KEY = "_runtime_event_callback"
RUNTIME_EVENT_LOG_KEY = "_runtime_events"

_EVENT_FIELDS = (
    "type",
    "phase",
    "level",
    "message",
    "detail",
    "current",
    "total",
    "name",
    "agent_num",
    "pipeline_id",
    "pipeline_label",
    "metadata",
)


def make_runtime_event(event_type: str = "status", **fields: Any) -> RuntimeEvent:
    event: RuntimeEvent = {"type": event_type}
    for key in _EVENT_FIELDS:
        if key == "type":
            continue
        value = fields.get(key)
        if value is not None:
            event[key] = value
    for key, value in fields.items():
        if key not in _EVENT_FIELDS and value is not None:
            event[key] = value
    return event


def classify_runtime_error(exc: BaseException | str, *, default: str = "provider") -> str:
    text = str(exc or "").lower()
    kind = exc.__class__.__name__.lower() if isinstance(exc, BaseException) else ""
    if any(marker in text for marker in ("quota", "rate limit", "429", "resource_exhausted")):
        return "quota"
    if any(marker in text for marker in ("timeout", "deadline", "timed out")) or "timeout" in kind:
        return "timeout"
    if any(marker in text for marker in ("model not found", "not found for api version", "missing model", "unknown model")):
        return "missing_model"
    if any(marker in text for marker in ("json", "schema", "structured", "validation", "pydantic")):
        return "schema"
    return default


def make_runtime_error_event(
    phase: str,
    exc: BaseException,
    *,
    message: str | None = None,
    level: str = "warning",
    error_category: str | None = None,
    **fields: Any,
) -> RuntimeEvent:
    metadata = dict(fields.pop("metadata", {}) or {})
    metadata.setdefault("error_kind", exc.__class__.__name__)
    metadata.setdefault("error_category", error_category or classify_runtime_error(exc))
    metadata.setdefault("error_message", str(exc)[:240])
    return make_runtime_event(
        "status",
        phase=phase,
        level=level,
        message=message or str(exc)[:240],
        metadata=metadata,
        **fields,
    )


def _legacy_callback_args(event: RuntimeEvent) -> tuple[Any, Any, Any, str, Any]:
    phase = event.get("phase")
    if not phase:
        phase = "completed" if event.get("type") == "progress" else "status"
    return (
        event.get("current", 0),
        event.get("total", 0),
        event.get("name") or event.get("message") or "",
        str(phase),
        event.get("message"),
    )


def emit_runtime_event(callback: Callable[..., Any] | None, event: RuntimeEvent) -> Any:
    """Emit an event to either a new-style callback(event) or legacy progress callback."""
    if not callback:
        return None

    try:
        result = callback(event)
    except TypeError:
        current, total, name, phase, message = _legacy_callback_args(event)
        try:
            result = callback(current, total, name, phase, message)
        except TypeError:
            if phase != "completed":
                return None
            result = callback(current, total, name)
    return result


async def emit_runtime_event_async(callback: Callable[..., Any] | None, event: RuntimeEvent) -> Any:
    result = emit_runtime_event(callback, event)
    if inspect.isawaitable(result):
        return await result
    return result


def emit_status(
    callback: Callable[..., Any] | None,
    message: str,
    *,
    phase: str = "status",
    level: str = "info",
    **fields: Any,
) -> Any:
    return emit_runtime_event(
        callback,
        make_runtime_event("status", phase=phase, level=level, message=message, **fields),
    )


async def emit_status_async(
    callback: Callable[..., Any] | None,
    message: str,
    *,
    phase: str = "status",
    level: str = "info",
    **fields: Any,
) -> Any:
    return await emit_runtime_event_async(
        callback,
        make_runtime_event("status", phase=phase, level=level, message=message, **fields),
    )


def emit_progress(
    callback: Callable[..., Any] | None,
    current: int,
    total: int,
    name: str,
    *,
    phase: str = "completed",
    message: str | None = None,
    level: str = "info",
    **fields: Any,
) -> Any:
    return emit_runtime_event(
        callback,
        make_runtime_event(
            "progress",
            phase=phase,
            level=level,
            current=current,
            total=total,
            name=name,
            message=message,
            **fields,
        ),
    )


async def emit_progress_async(
    callback: Callable[..., Any] | None,
    current: int,
    total: int,
    name: str,
    *,
    phase: str = "completed",
    message: str | None = None,
    level: str = "info",
    **fields: Any,
) -> Any:
    return await emit_runtime_event_async(
        callback,
        make_runtime_event(
            "progress",
            phase=phase,
            level=level,
            current=current,
            total=total,
            name=name,
            message=message,
            **fields,
        ),
    )


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


def _context_event_copy(event: RuntimeEvent) -> RuntimeEvent:
    copied = {
        key: value
        for key, value in dict(event).items()
        if not key.startswith("_") and key not in {"callback"}
    }
    return copied


def emit_context_event(
    context: dict | None,
    event: RuntimeEvent,
    callback: Callable[..., Any] | None = None,
    *,
    store: bool = True,
) -> Any:
    """Record a runtime event on the analysis context and optionally forward it."""
    if isinstance(context, dict) and store:
        context.setdefault(RUNTIME_EVENT_LOG_KEY, []).append(_context_event_copy(event))
    callback = callback or (context or {}).get(RUNTIME_EVENT_CALLBACK_KEY)
    return emit_runtime_event(callback, event)


def emit_context_error(
    context: dict | None,
    phase: str,
    exc: BaseException,
    *,
    message: str | None = None,
    level: str = "warning",
    error_category: str | None = None,
    callback: Callable[..., Any] | None = None,
    store: bool = True,
    **fields: Any,
) -> Any:
    return emit_context_event(
        context,
        make_runtime_error_event(
            phase,
            exc,
            message=message,
            level=level,
            error_category=error_category,
            **fields,
        ),
        callback=callback,
        store=store,
    )


async def emit_context_event_async(
    context: dict | None,
    event: RuntimeEvent,
    callback: Callable[..., Any] | None = None,
    *,
    store: bool = True,
) -> Any:
    if isinstance(context, dict) and store:
        context.setdefault(RUNTIME_EVENT_LOG_KEY, []).append(_context_event_copy(event))
    callback = callback or (context or {}).get(RUNTIME_EVENT_CALLBACK_KEY)
    return await emit_runtime_event_async(callback, event)


async def emit_context_error_async(
    context: dict | None,
    phase: str,
    exc: BaseException,
    *,
    message: str | None = None,
    level: str = "warning",
    error_category: str | None = None,
    callback: Callable[..., Any] | None = None,
    store: bool = True,
    **fields: Any,
) -> Any:
    return await emit_context_event_async(
        context,
        make_runtime_error_event(
            phase,
            exc,
            message=message,
            level=level,
            error_category=error_category,
            **fields,
        ),
        callback=callback,
        store=store,
    )
