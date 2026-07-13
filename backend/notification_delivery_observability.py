"""Notification delivery observability helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mapping_fields import mapping_field as _field
from mapping_fields import safe_mapping_dict, safe_mapping_items, safe_text
from notification_delivery_audit_context import safe_int


def notification_delivery_dashboard_summary(summary: dict) -> dict:
    copied = _payload_dict(summary)
    copied["total_count"] = _metric_int(_field(copied, "total_count"))
    copied["sent_count"] = _metric_int(_field(copied, "sent_count"))
    copied["failed_count"] = _metric_int(_field(copied, "failed_count"))
    copied["pending_count"] = _metric_int(_field(copied, "pending_count"))
    copied["retry_exhausted_count"] = _metric_int(_field(copied, "retry_exhausted_count"))
    copied["channel_counts"] = _count_map(_field(copied, "channel_counts"))
    copied["failure_reason_counts"] = _count_map(_field(copied, "failure_reason_counts"))
    copied["attention_required"] = notification_delivery_attention_required(copied)
    copied["health"] = "warning" if copied["attention_required"] else "ok"
    return copied


def notification_delivery_attention_required(summary: dict) -> bool:
    return _metric_int(_field(summary, "failed_count")) > 0 or _metric_int(_field(summary, "retry_exhausted_count")) > 0


def notification_delivery_prometheus_lines(summary: dict, labels: Callable[..., str]) -> list[str]:
    delivery = notification_delivery_dashboard_summary(summary)
    lines = [
        "# HELP stock_agent_notification_delivery_count Notification delivery audit row count by status.",
        "# TYPE stock_agent_notification_delivery_count gauge",
    ]
    for status, key in (
        ("total", "total_count"),
        ("sent", "sent_count"),
        ("failed", "failed_count"),
        ("pending", "pending_count"),
        ("retry_exhausted", "retry_exhausted_count"),
    ):
        lines.append(f"stock_agent_notification_delivery_count{labels(status=status)} {_metric_int(_field(delivery, key))}")
    lines.extend([
        "# HELP stock_agent_notification_delivery_channel_count Notification delivery audit row count by channel.",
        "# TYPE stock_agent_notification_delivery_channel_count gauge",
    ])
    for channel, count in safe_mapping_items(_field(delivery, "channel_counts", {})):
        lines.append(f"stock_agent_notification_delivery_channel_count{labels(channel=_metric_label(channel))} {_metric_int(count)}")
    lines.extend([
        "# HELP stock_agent_notification_delivery_failure_reason_count Failed notification delivery row count by reason bucket.",
        "# TYPE stock_agent_notification_delivery_failure_reason_count gauge",
    ])
    for reason, count in sorted(safe_mapping_items(_field(delivery, "failure_reason_counts", {})), key=lambda item: _metric_label(item[0])):
        lines.append(f"stock_agent_notification_delivery_failure_reason_count{labels(reason=_metric_label(reason))} {_metric_int(count)}")
    lines.extend([
        "# HELP stock_agent_notification_delivery_health Notification delivery health state; 1 means current state.",
        "# TYPE stock_agent_notification_delivery_health gauge",
    ])
    for state in ("ok", "warning"):
        lines.append(f"stock_agent_notification_delivery_health{labels(state=state)} {1 if _field(delivery, 'health') == state else 0}")
    return lines


def _metric_int(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)


def _metric_label(value: Any) -> str:
    return safe_text(value).strip() or "unknown"


def _count_map(value: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw_key, raw_count in safe_mapping_items(_payload_dict(value)):
        key = _metric_label(raw_key)
        counts[key] = counts.get(key, 0) + _metric_int(raw_count)
    return counts


def _payload_dict(value: Any) -> dict[Any, Any]:
    return safe_mapping_dict(value) or {}
