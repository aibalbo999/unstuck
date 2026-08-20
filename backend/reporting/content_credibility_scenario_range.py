"""Check whether the 12-month target stays near the scenario range."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict

from .content_credibility_target_prices import scenario_target_candidates, target_price_candidates


SCENARIO_LABELS = ("熊市情境", "基本情境", "牛市情境")


def _check(check_id: str, status: str, message: str, details: dict) -> dict:
    return {"id": check_id, "status": status, "message": message, "details": details}


def _issue(issue_id: str, message: str, details: dict) -> dict:
    return {"id": issue_id, "message": message, "details": details}


def evaluate_recommendation_target_scenario_range(parsed: dict[str, Any]) -> dict:
    """Project the existing final-audit scenario-range warning into credibility evidence."""
    parsed = safe_mapping_dict(parsed) or {}
    target_12m = next(
        (candidate for candidate in target_price_candidates(parsed) if candidate.get("label") == "12個月"),
        None,
    )
    scenarios = scenario_target_candidates(parsed)
    targets = {
        candidate["label"]: float(candidate["price"])
        for candidate in scenarios
        if candidate.get("label") in SCENARIO_LABELS and candidate.get("price") is not None
    }
    details = {
        "target_12m": target_12m.get("price") if target_12m else None,
        "target_source": target_12m.get("source") if target_12m else None,
        "scenario_targets": targets,
    }
    if target_12m is None or any(label not in targets for label in SCENARIO_LABELS):
        return {
            "blocking_issues": [],
            "warnings": [],
            "checks": [_check(
                "recommendation_target_scenario_range",
                "passed",
                "缺少完整 12 個月與三情境目標價，略過情境區間檢查。",
                details,
            )],
        }

    lower = targets["熊市情境"] * 0.7
    upper = targets["牛市情境"] * 1.3
    details = {
        **details,
        "allowed_lower_bound": lower,
        "allowed_upper_bound": upper,
    }
    target_price = float(target_12m["price"])
    if lower <= target_price <= upper:
        return {
            "blocking_issues": [],
            "warnings": [],
            "checks": [_check(
                "recommendation_target_scenario_range",
                "passed",
                "12 個月目標價仍落在三情境區間的可解釋範圍內。",
                details,
            )],
        }

    issue = _issue(
        "recommendation_target_outside_scenario_range",
        "12 個月目標價超出三情境區間的可解釋範圍，需要人工確認。",
        details,
    )
    return {
        "blocking_issues": [],
        "warnings": [issue],
        "checks": [_check(
            "recommendation_target_scenario_range",
            "warning",
            issue["message"],
            details,
        )],
    }


__all__ = ["evaluate_recommendation_target_scenario_range"]
