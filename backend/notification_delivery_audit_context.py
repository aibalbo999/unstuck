"""Context snapshot helpers for notification delivery audit rows."""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
import time
from typing import Any

from daily_decision_source_labels import source_key, source_label, source_text
from mapping_fields import mapping_field as _field, safe_mapping_items, safe_sequence_items, safe_text_list


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
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, dict)):
        try:
            return len(value) > 0
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return True
    return True


def safe_text(value: Any) -> str:
    try:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value).decode("utf-8", errors="replace")
        return str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


def safe_int(value: Any) -> int:
    try:
        return int(0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0


def safe_float(value: Any) -> float:
    try:
        number = float(0.0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def safe_timestamp(now: float | None) -> float:
    try:
        timestamp = float(time.time() if now is None else now)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        timestamp = float(time.time())
    if math.isfinite(timestamp):
        return timestamp
    try:
        fallback = float(time.time())
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0.0
    return fallback if math.isfinite(fallback) else 0.0


def safe_dict(value: Any) -> dict[str, Any]:
    try:
        return {} if value is None else _json_safe_context(dict(value))
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return {}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (list, tuple)):
        items = []
        for item in safe_sequence_items(value):
            safe_item = _json_safe_value(item)
            if _present(safe_item):
                items.append(safe_item)
        return items
    if isinstance(value, Mapping):
        return {
            key: safe_item
            for key, item in safe_mapping_items(value)
            if isinstance(key, str)
            for safe_item in [_json_safe_value(item)]
            if _present(safe_item)
        }
    text = safe_text(value).strip()
    return text if text else None


def _json_safe_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        key: safe_value
        for key, value in safe_mapping_items(context)
        if isinstance(key, str)
        for safe_value in [_json_safe_value(value)]
        if _present(safe_value)
    }


def context_json_from_outbox(outbox_entry: dict[str, Any]) -> str:
    context = {
        key: value
        for key, value in safe_mapping_items(outbox_entry)
        if isinstance(key, str) and key not in AUDIT_RUNTIME_KEYS
    }
    reason_codes = safe_text_list(_field(context, "reason_codes"))
    if reason_codes:
        context["reason_codes"] = reason_codes
    else:
        context.pop("reason_codes", None)
    source = source_key(safe_text(_field(context, "source")))
    if source:
        context["source"] = source
        if not _has_text(_field(context, "source_label")):
            context["source_label"] = source_label(source)
        if not _has_text(_field(context, "source_text")):
            context["source_text"] = source_text(source)
    context = _json_safe_context(context)
    return json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)


def context_from_json(payload: str | None) -> dict[str, Any]:
    try:
        context = json.loads("{}" if payload is None else safe_text(payload))
    except (TypeError, ValueError, RuntimeError):
        return {}
    return _json_safe_context(context) if isinstance(context, dict) else {}


def attention_contexts_from_records(records: list[dict[str, Any]], *, limit: int | None = 5) -> list[dict[str, Any]]:
    contexts = []
    for record in records:
        delivery_status = safe_text(_field(record, "delivery_status")).strip().lower()
        if delivery_status != "failed":
            continue
        contexts.append(
            {
                "delivery_key": safe_text(_field(record, "delivery_key")).strip(),
                "channel_id": safe_text(_field(record, "channel_id")).strip(),
                "delivery_status": delivery_status,
                "attempt_count": safe_int(_field(record, "attempt_count")),
                "last_error": safe_text(_field(record, "last_error")),
                "context": safe_dict(_field(record, "context")),
            }
        )
    output_limit = 5 if limit is None else max(0, safe_int(limit))
    return contexts[:output_limit]
