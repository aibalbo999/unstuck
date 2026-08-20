"""Scenario-target consistency checks for content credibility."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text

from .content_credibility_target_prices import scenario_target_candidates


SCENARIO_ORDER = ("熊市情境", "基本情境", "牛市情境")


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


def evaluate_scenario_target_order(parsed: dict[str, Any]) -> dict:
    """Require parsed scenario targets to remain ordered from bear to bull."""
    candidates = scenario_target_candidates(parsed)
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if not candidates:
        checks.append(_check(
            "scenario_target_order",
            "passed",
            "未記錄長線情境目標價，略過情境順序檢查。",
        ))
        return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}

    targets = {
        candidate["label"]: float(candidate["price"])
        for candidate in candidates
        if candidate.get("price") is not None
    }
    for candidate in candidates:
        if candidate.get("price") is not None:
            continue
        label = candidate["label"]
        issue = _issue(
            "unparseable_scenario_target",
            "情境目標價存在但無法解析，無法完成完整順序檢查。",
            {"label": label, "raw": safe_text(candidate.get("raw"))},
        )
        warnings.append(issue)

    violations = []
    for index, left in enumerate(SCENARIO_ORDER):
        for right in SCENARIO_ORDER[index + 1:]:
            if left not in targets or right not in targets:
                continue
            if targets[left] > targets[right]:
                violations.append({
                    "from": left,
                    "from_price": targets[left],
                    "to": right,
                    "to_price": targets[right],
                })
    if violations:
        issue = _issue(
            "scenario_target_order_conflict",
            "熊市、基本與牛市場景目標價順序互相矛盾。",
            {"targets": targets, "violations": violations},
        )
        blocking.append(issue)
        checks.append(_check("scenario_target_order", "blocked", issue["message"], issue["details"]))
    elif warnings:
        checks.append(_check(
            "scenario_target_order",
            "warning",
            "情境目標價順序未見已解析的矛盾，但仍有欄位無法解析。",
            {"targets": targets},
        ))
    else:
        checks.append(_check(
            "scenario_target_order",
            "passed",
            "熊市、基本與牛市場景目標價順序未見矛盾。",
            {"targets": targets},
        ))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}


__all__ = ["evaluate_scenario_target_order"]
