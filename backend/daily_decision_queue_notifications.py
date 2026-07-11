"""Notification delivery repair items for the daily decision queue."""

from __future__ import annotations

from typing import Any

from mapping_fields import mapping_field as _field


def notification_delivery_items(ops: dict[str, Any]) -> list[dict[str, Any]]:
    raw_summary = _field(ops, "notification_delivery")
    summary = raw_summary if isinstance(raw_summary, dict) else {}
    failed_count = _int(_field(summary, "failed_count"))
    exhausted_count = _int(_field(summary, "retry_exhausted_count"))
    if failed_count <= 0 and exhausted_count <= 0 and str(_field(summary, "health") or "").lower() != "warning":
        return []
    raw_reason_counts = _field(summary, "failure_reason_counts")
    reason_counts = raw_reason_counts if isinstance(raw_reason_counts, dict) else {}
    raw_attention_contexts = _field(summary, "attention_contexts")
    attention_contexts = raw_attention_contexts if isinstance(raw_attention_contexts, list) else []
    return [{
        "source": "notification_delivery",
        "type": "fix_notification_delivery",
        "priority_score": 840,
        "title": "外部通知通道需檢查",
        "detail": _notification_delivery_detail(failed_count, exhausted_count, reason_counts),
        "failed_count": failed_count,
        "retry_exhausted_count": exhausted_count,
        "channel_counts": dict(_field(summary, "channel_counts") or {}),
        "failure_reason_counts": dict(reason_counts),
        "attention_contexts": list(attention_contexts),
        "operator_action": "open-ops",
        "operator_action_label": "查看通知通道",
        "target_tab": "ops",
        "suppress_notification": True,
    }]


def _notification_delivery_detail(failed_count: int, exhausted_count: int, reason_counts: dict[str, Any]) -> str:
    detail = f"failed={failed_count}, exhausted={exhausted_count}"
    if not reason_counts:
        return detail
    reason_summary = ", ".join(f"{key} {value}" for key, value in reason_counts.items())
    return f"{detail}, reason={reason_summary}"


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = ["notification_delivery_items"]
