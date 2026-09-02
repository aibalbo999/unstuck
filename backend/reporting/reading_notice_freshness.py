"""Decision-freshness values used by report reading notices."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number
from report_freshness_summary import safe_bool


def _status(value: Any, default: str = "") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if not text:
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def is_recorded(context: dict) -> bool:
    return any(
        key in context
        for key in (
            "decision_freshness",
            "analysis_text_stale",
            "analysis_text_stale_message",
            "decision_validity_status",
            "refreshed_without_analysis_rerun",
        )
    )


def decision_freshness(context: dict) -> dict:
    if "decision_freshness" in context:
        return safe_mapping_dict(dict.get(context, "decision_freshness")) or {
            "status": "unknown",
            "requires_rerun": False,
        }

    stale = (
        safe_bool(dict.get(context, "analysis_text_stale"))
        or safe_bool(dict.get(context, "refreshed_without_analysis_rerun"))
        or _status(dict.get(context, "decision_validity_status")).lower() == "needs_rerun"
    )
    if stale:
        reason = _status(
            dict.get(context, "requires_rerun_reason")
            or dict.get(context, "analysis_text_stale_message")
        )
        return {
            "status": "needs_rerun",
            "requires_rerun": True,
            "requires_rerun_reason": reason,
            "message": reason,
        }

    if is_recorded(context):
        return {
            "status": _status(dict.get(context, "decision_validity_status"), "unknown"),
            "requires_rerun": False,
        }
    return {}


def requires_rerun(freshness: dict) -> bool:
    return (
        safe_bool(dict.get(freshness, "requires_rerun"))
        or _status(dict.get(freshness, "status")).lower() == "needs_rerun"
    )


def label(freshness: dict) -> str:
    if requires_rerun(freshness):
        return "需完整重跑"
    status = _status(dict.get(freshness, "status"), "unknown").lower()
    return {
        "current": "目前一致",
        "unknown": "無法判定",
        "unavailable": "無法判定",
        "not_recorded": "未記錄",
    }.get(status, status or "無法判定")


def reason(freshness: dict, context: dict) -> str:
    return _status(
        dict.get(freshness, "message")
        or dict.get(freshness, "requires_rerun_reason")
        or dict.get(context, "requires_rerun_reason")
        or dict.get(context, "analysis_text_stale_message")
    )


__all__ = ["decision_freshness", "is_recorded", "label", "reason", "requires_rerun"]
