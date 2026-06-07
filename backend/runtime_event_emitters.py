"""Runtime event callback and context emitters."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from runtime_event_core import (
    RUNTIME_EVENT_CALLBACK_KEY,
    RUNTIME_EVENT_LOG_KEY,
    RuntimeEvent,
    make_runtime_error_event,
    make_runtime_event,
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


def emit_status(callback: Callable[..., Any] | None, message: str, *, phase: str = "status", level: str = "info", **fields: Any) -> Any:
    return emit_runtime_event(callback, make_runtime_event("status", phase=phase, level=level, message=message, **fields))


async def emit_status_async(callback: Callable[..., Any] | None, message: str, *, phase: str = "status", level: str = "info", **fields: Any) -> Any:
    return await emit_runtime_event_async(callback, make_runtime_event("status", phase=phase, level=level, message=message, **fields))


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
        make_runtime_event("progress", phase=phase, level=level, current=current, total=total, name=name, message=message, **fields),
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
        make_runtime_event("progress", phase=phase, level=level, current=current, total=total, name=name, message=message, **fields),
    )


def _context_event_copy(event: RuntimeEvent) -> RuntimeEvent:
    return {key: value for key, value in dict(event).items() if not key.startswith("_") and key not in {"callback"}}


def emit_context_event(context: dict | None, event: RuntimeEvent, callback: Callable[..., Any] | None = None, *, store: bool = True) -> Any:
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
        make_runtime_error_event(phase, exc, message=message, level=level, error_category=error_category, **fields),
        callback=callback,
        store=store,
    )


async def emit_context_event_async(context: dict | None, event: RuntimeEvent, callback: Callable[..., Any] | None = None, *, store: bool = True) -> Any:
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
        make_runtime_error_event(phase, exc, message=message, level=level, error_category=error_category, **fields),
        callback=callback,
        store=store,
    )
