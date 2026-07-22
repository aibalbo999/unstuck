"""Summary and rendering helpers for the daily operator decision queue."""

from __future__ import annotations

from typing import Any

from daily_decision_source_labels import source_labels, source_texts
from mapping_fields import mapping_field as _field, safe_int

SOURCE_ORDER = {source: index for index, source in enumerate((
    "free_mode", "report_repair", "provider_impact", "notification_delivery", "backtest_due",
    "rerun_report", "model_route_budget", "watchlist", "screener", "monitor",
))}


def queue_response(
    actionable: list[dict[str, Any]],
    *,
    limit: Any,
    schema_version: str,
) -> dict[str, Any]:
    actionable.sort(key=_sort_key)
    render_items = actionable or [_monitor_item()]
    display_limit = _int(limit) or 5
    displayed = render_items[: max(1, display_limit)]
    source_counts = _source_counts(actionable)
    return {
        "schema_version": schema_version,
        "summary": {
            "total_actionable": len(actionable),
            "displayed_count": len(displayed),
            "top_priority_score": int(_field(displayed[0], "priority_score") or 0) if displayed else 0,
            "sources": source_counts,
            "source_labels": source_labels(source_counts),
            "source_texts": source_texts(source_counts),
        },
        "items": displayed,
        "secondary_count": max(0, len(actionable) - len(displayed)),
    }


def _monitor_item() -> dict[str, Any]:
    return {
        "source": "monitor",
        "type": "monitor",
        "priority_score": 0,
        "title": "目前沒有急件",
        "detail": "保持每日追蹤。",
    }


def _source_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        source = str(_field(item, "source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


def _sort_key(item: dict[str, Any]) -> tuple[int, int, str, str]:
    source = str(_field(item, "source") or "")
    return (
        -_int(_field(item, "priority_score")),
        SOURCE_ORDER.get(source, 8),
        str(_field(item, "ticker") or ""),
        str(_field(item, "filename") or _field(item, "route") or ""),
    )


def _int(value: Any) -> int:
    return safe_int(value)


__all__ = ["SOURCE_ORDER", "queue_response"]
