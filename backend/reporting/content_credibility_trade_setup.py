"""Credibility checks for the mode-D short-term trade plan."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_text

from .content_credibility_inputs import first_price


_VALID_DIRECTIONS = {"Long", "Short", "Neutral"}


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


def evaluate_trade_setup_alignment(
    *,
    trade_setup: dict[str, Any],
    current_price: float | None,
) -> dict:
    """Check that a mode-D target and stop-loss agree with its trade direction."""
    setup = safe_mapping_dict(trade_setup) or {}
    direction = safe_text(setup.get("trade_direction")).strip() or "Neutral"
    target_price = first_price(setup.get("target_price"))
    stop_loss = first_price(setup.get("stop_loss"))
    details = {
        "trade_direction": direction,
        "current_price": current_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
    }
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if direction not in _VALID_DIRECTIONS:
        issue = _issue("invalid_trade_direction", "交易方向不在允許的 Long、Short 或 Neutral 範圍內。", details)
        blocking.append(issue)
        checks.append(_check("trade_setup_alignment", "blocked", issue["message"], details))
        return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}

    if current_price is None or target_price is None or stop_loss is None:
        issue = _issue(
            "missing_trade_setup_price_inputs",
            "交易計畫缺少可解析的現價、目標或停損，無法完成方向一致性檢查。",
            details,
        )
        warnings.append(issue)
        checks.append(_check("trade_setup_alignment", "warning", issue["message"], details))
        return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}

    if direction == "Long":
        rules = (
            (target_price <= current_price, "long_target_not_above_current_price", "偏多交易的目標價未高於目前股價。"),
            (stop_loss >= current_price, "long_stop_not_below_current_price", "偏多交易的停損未低於目前股價。"),
        )
    elif direction == "Short":
        rules = (
            (target_price >= current_price, "short_target_not_below_current_price", "偏空交易的目標價未低於目前股價。"),
            (stop_loss <= current_price, "short_stop_not_above_current_price", "偏空交易的停損未高於目前股價。"),
        )
    else:
        rules = ()

    for violated, issue_id, message in rules:
        if not violated:
            continue
        issue = _issue(issue_id, message, details)
        blocking.append(issue)
        checks.append(_check("trade_setup_alignment", "blocked", message, details))

    if not blocking:
        checks.append(_check("trade_setup_alignment", "passed", "交易方向、目標與停損未見明顯矛盾。", details))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}


__all__ = ["evaluate_trade_setup_alignment"]
