"""Runtime event schema and error classification helpers."""

from __future__ import annotations

from typing import Any


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
