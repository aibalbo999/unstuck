"""Notification delivery repair items for the daily decision queue."""

from __future__ import annotations

from numbers import Number
from typing import Any

from mapping_fields import (
    mapping_field as _field,
    safe_int,
    safe_mapping_dict,
    safe_mapping_items,
    safe_sequence_items,
    safe_text,
)

_FAILURE_REASON_BUCKETS = frozenset({
    "timeout",
    "auth",
    "rate_limited",
    "configuration",
    "network",
    "other",
    "unknown",
})


def notification_delivery_items(ops: dict[str, Any]) -> list[dict[str, Any]]:
    raw_summary = _field(ops, "notification_delivery")
    summary = _safe_mapping(raw_summary)
    failed_count = _int(_field(summary, "failed_count"))
    exhausted_count = _int(_field(summary, "retry_exhausted_count"))
    health = safe_text(_field(summary, "health")).strip().lower()
    if failed_count <= 0 and exhausted_count <= 0 and health != "warning":
        return []
    raw_reason_counts = _field(summary, "failure_reason_counts")
    reason_counts = _safe_count_map(raw_reason_counts, key_normalizer=_safe_reason_text)
    raw_channel_counts = _field(summary, "channel_counts")
    channel_counts = _safe_count_map(raw_channel_counts, key_normalizer=_safe_channel_text)
    raw_attention_contexts = _field(summary, "attention_contexts")
    attention_contexts = raw_attention_contexts if isinstance(raw_attention_contexts, (list, tuple)) else []
    return [{
        "source": "notification_delivery",
        "type": "fix_notification_delivery",
        "priority_score": 840,
        "title": "外部通知通道需檢查",
        "detail": _notification_delivery_detail(failed_count, exhausted_count, reason_counts),
        "failed_count": failed_count,
        "retry_exhausted_count": exhausted_count,
        "channel_counts": dict(channel_counts),
        "failure_reason_counts": dict(reason_counts),
        "attention_contexts": _safe_contexts(attention_contexts),
        "operator_action": "open-ops",
        "operator_action_label": "查看通知通道",
        "target_tab": "ops",
        "suppress_notification": True,
    }]


def _notification_delivery_detail(failed_count: int, exhausted_count: int, reason_counts: dict[str, Any]) -> str:
    detail = f"failed={failed_count}, exhausted={exhausted_count}"
    try:
        reason_totals: dict[str, int] = {}
        for key, value in safe_mapping_items(reason_counts):
            summary_item = _reason_summary_item(key, value)
            if summary_item is None:
                continue
            reason, count = summary_item
            reason_totals[reason] = reason_totals.get(reason, 0) + count
        reason_summary = ", ".join(f"{reason} {count}" for reason, count in reason_totals.items())
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        reason_summary = ""
    if not reason_summary:
        return detail
    return f"{detail}, reason={reason_summary}"


def _reason_summary_part(key: Any, value: Any) -> str:
    summary_item = _reason_summary_item(key, value)
    if summary_item is None:
        return ""
    reason, count = summary_item
    return f"{reason} {count}"


def _reason_summary_item(key: Any, value: Any) -> tuple[str, int] | None:
    reason = _safe_reason_text(key)
    if not reason:
        return None
    count = _safe_positive_count(value)
    if count <= 0:
        return None
    return reason, count


def _safe_reason_text(key: Any) -> str:
    if not isinstance(key, str):
        return ""
    reason = safe_text(key).strip().lower()
    if reason not in _FAILURE_REASON_BUCKETS:
        return ""
    return reason


def _safe_channel_text(key: Any) -> str:
    return safe_text(key).strip() or "unknown"


def _safe_count_map(value: Any, *, key_normalizer) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw_key, raw_count in safe_mapping_items(_safe_mapping(value)):
        key = key_normalizer(raw_key)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + _strict_count(raw_count)
    return counts


def _safe_positive_count_text(value: Any) -> str:
    count = _safe_positive_count(value)
    if count <= 0:
        return ""
    return str(count)


def _safe_positive_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    numeric_count = _int(value)
    if numeric_count <= 0:
        return 0
    if isinstance(value, Number):
        try:
            if value != numeric_count:
                return 0
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return 0
    return numeric_count


def _int(value: Any) -> int:
    return _strict_count(value)


def _strict_count(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)


def _safe_mapping(value: Any) -> dict[str, Any]:
    result = safe_mapping_dict(value)
    if result is None:
        return {}
    return result


def _safe_list(value: list[Any] | tuple[Any, ...]) -> list[Any]:
    return safe_sequence_items(value)


def _safe_contexts(value: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    rows = []
    for raw_row in _safe_list(value):
        row = safe_mapping_dict(raw_row)
        if row is None:
            continue
        row = _plain_value(row)
        nested_context = safe_mapping_dict(_field(row, "context"))
        if nested_context is not None:
            row["context"] = _plain_value(nested_context)
        rows.append(row)
    return rows


def _plain_value(value: Any) -> Any:
    mapping = safe_mapping_dict(value)
    if mapping is not None:
        return {key: _plain_value(child) for key, child in safe_mapping_items(mapping)}
    if isinstance(value, (list, tuple)):
        return [_plain_value(item) for item in safe_sequence_items(value)]
    return value


__all__ = ["notification_delivery_items"]
