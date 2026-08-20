"""Horizon-target sequence checks for content credibility."""

from __future__ import annotations

from typing import Any

from forward_consistency_checker import check_target_price_sequence
from mapping_fields import safe_mapping_dict, safe_text
from recommendation_labels import normalize_recommendation_label

from .content_credibility_target_prices import target_price_candidates


_SEQUENCE_LABELS = ("3個月", "6個月", "12個月")
_DIRECTIONAL_RECOMMENDATIONS = {"買入", "避免", "放空"}


def _issue(issue_id: str, message: str, details: dict | None = None) -> dict:
    issue = {"id": issue_id, "message": message}
    if details:
        issue["details"] = details
    return issue


def _check(check_id: str, status: str, message: str, details: dict | None = None) -> dict:
    result = {"id": check_id, "status": status, "message": message}
    if details:
        result["details"] = details
    return result


def evaluate_horizon_target_sequence(parsed: dict[str, Any]) -> dict:
    """Project existing forward target-sequence warnings into credibility evidence."""
    parsed = safe_mapping_dict(parsed) or {}
    recommendation_map = safe_mapping_dict(parsed.get("recommendation")) or {}
    recommendation = normalize_recommendation_label(
        next((value for key, value in recommendation_map.items() if "建議" in safe_text(key)), None)
    )
    targets = {
        candidate["label"]: float(candidate["price"])
        for candidate in target_price_candidates(parsed)
        if candidate.get("label") in _SEQUENCE_LABELS and candidate.get("price") is not None
    }
    details = {"recommendation": recommendation, "targets": targets}
    if len(targets) < 2 or recommendation not in _DIRECTIONAL_RECOMMENDATIONS:
        return {
            "blocking_issues": [],
            "warnings": [],
            "checks": [_check(
                "horizon_target_sequence",
                "passed",
                "缺少足夠的方向性目標價，略過時序一致性檢查。",
                details,
            )],
        }

    messages = check_target_price_sequence(
        targets.get("3個月"),
        targets.get("6個月"),
        targets.get("12個月"),
        recommendation,
    )
    if not messages:
        return {
            "blocking_issues": [],
            "warnings": [],
            "checks": [_check(
                "horizon_target_sequence",
                "passed",
                "方向性目標價的 3/6/12 個月時序未見明顯矛盾。",
                details,
            )],
        }

    issue = _issue(
        "horizon_target_sequence_conflict",
        "方向性目標價的 3/6/12 個月時序與建議方向不一致，需要人工確認。",
        {**details, "rule_messages": messages},
    )
    return {
        "blocking_issues": [],
        "warnings": [issue],
        "checks": [_check("horizon_target_sequence", "warning", issue["message"], issue["details"])],
    }


__all__ = ["evaluate_horizon_target_sequence"]
