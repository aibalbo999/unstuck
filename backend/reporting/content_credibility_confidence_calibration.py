"""Project confidence calibration limits into content credibility evidence."""

from __future__ import annotations

from typing import Any

from confidence_calibration import build_confidence_calibration, has_unresolved_cross_source_conflict
from mapping_fields import safe_mapping_dict, safe_text
from report_freshness_summary import safe_bool


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _issue(issue_id: str, message: str, details: dict) -> dict:
    return {"id": issue_id, "message": message, "details": details}


def _check(check_id: str, status: str, message: str, details: dict) -> dict:
    return {"id": check_id, "status": status, "message": message, "details": details}


def _safe_recommendation(value: Any) -> dict:
    """Keep malformed report fields from crossing into the shared calibrator."""
    source = _as_dict(value)
    result: dict[str, Any] = {}
    for key, item in source.items():
        key_text = safe_text(key).strip()
        if not key_text:
            continue
        if key_text == "confidence_basis":
            result[key_text] = _as_dict(item)
        elif safe_mapping_dict(item) is not None:
            result[key_text] = _safe_recommendation(item)
        else:
            result[key_text] = safe_text(item)
    return result


def evaluate_confidence_data_trust_calibration(
    context: dict[str, Any],
    recommendation: dict[str, Any],
    data_trust: dict[str, Any],
) -> dict:
    """Expose the existing final-audit confidence cap without changing its policy."""
    context = _as_dict(context)
    data = _as_dict(context.get("data"))
    circuit_ever_opened = safe_bool(_as_dict(context.get("circuit_breaker")).get("_ever_opened", False))
    has_conflict = has_unresolved_cross_source_conflict(data)
    calibration = build_confidence_calibration(
        _safe_recommendation(recommendation),
        data_trust,
        circuit_ever_opened,
        has_conflict,
    )
    details = {
        "status": calibration.get("status"),
        "raw_confidence": calibration.get("raw_confidence"),
        "confidence_score": calibration.get("confidence_score"),
        "data_trust_status": calibration.get("data_trust_status"),
        "max_recommended_confidence": calibration.get("max_recommended_confidence"),
        "reasons": calibration.get("reasons", []),
        "circuit_ever_opened": circuit_ever_opened,
        "has_unresolved_conflict": has_conflict,
    }

    if calibration.get("status") == "needs_downgrade":
        issue = _issue(
            "confidence_exceeds_data_trust_cap",
            "報告信心超過目前資料可信度上限，需要下調信心或明確揭露資料限制。",
            details,
        )
        return {
            "blocking_issues": [],
            "warnings": [issue],
            "checks": [_check("confidence_data_trust_calibration", "warning", issue["message"], details)],
        }

    if calibration.get("status") == "unavailable":
        message = "未解析到信心分數，無法完成資料可信度上限檢查。"
        check_status = "unavailable"
    else:
        message = "報告信心未超過目前資料可信度上限。"
        check_status = "passed"
    return {
        "blocking_issues": [],
        "warnings": [],
        "checks": [_check("confidence_data_trust_calibration", check_status, message, details)],
    }


__all__ = ["evaluate_confidence_data_trust_calibration"]
