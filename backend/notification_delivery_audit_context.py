"""Context snapshot helpers for notification delivery audit rows."""

from __future__ import annotations

import json
from typing import Any

from daily_decision_source_labels import source_key, source_label, source_text
from mapping_fields import mapping_field as _field


AUDIT_RUNTIME_KEYS = {
    "schema_version",
    "delivery_key",
    "channel_id",
    "message_id",
    "dedupe_key",
    "delivery_status",
    "attempt_count",
    "audit_status",
    "audit_attempt_count",
    "already_sent",
    "should_send",
    "retry_exhausted",
    "retry_wait_seconds",
    "next_retry_at",
    "next_attempt_count",
    "skip_reason",
    "last_error",
    "last_response_id",
    "last_success_at",
}


def _has_text(value: Any) -> bool:
    return safe_text(value).strip() != ""


def _present(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or value != "")


def safe_text(value: Any) -> str:
    try:
        return "" if value is None else value if isinstance(value, str) else str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


def safe_int(value: Any) -> int:
    try:
        return int(0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(0.0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0.0


def safe_dict(value: Any) -> dict[str, Any]:
    try:
        return {} if value is None else dict(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return {}


def context_json_from_outbox(outbox_entry: dict[str, Any]) -> str:
    context = {
        key: value
        for key, value in outbox_entry.items()
        if key not in AUDIT_RUNTIME_KEYS and _present(value)
    }
    source = source_key(safe_text(_field(context, "source")))
    if source:
        context["source"] = source
        if not _has_text(_field(context, "source_label")):
            context["source_label"] = source_label(source)
        if not _has_text(_field(context, "source_text")):
            context["source_text"] = source_text(source)
    return json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)


def context_from_json(payload: str | None) -> dict[str, Any]:
    try:
        context = json.loads(payload or "{}")
    except (TypeError, ValueError):
        return {}
    return context if isinstance(context, dict) else {}


def attention_contexts_from_records(records: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    contexts = []
    for record in records:
        delivery_status = safe_text(_field(record, "delivery_status"))
        if delivery_status != "failed":
            continue
        contexts.append(
            {
                "delivery_key": safe_text(_field(record, "delivery_key")),
                "channel_id": safe_text(_field(record, "channel_id")),
                "delivery_status": delivery_status,
                "attempt_count": safe_int(_field(record, "attempt_count")),
                "last_error": safe_text(_field(record, "last_error")),
                "context": safe_dict(_field(record, "context")),
            }
        )
    return contexts[: max(0, safe_int(limit))]
