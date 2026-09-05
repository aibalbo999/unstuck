"""Credibility checks for the mode-D short-term trade plan."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_text
from trade_execution_contract import evaluate_trade_execution, neutral_observation_is_explicit
from trade_price_inputs import parse_price_range

from .content_credibility_inputs import first_price, has_explicit_price_range, price_candidates


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
    """Check mode-D execution against the full intended entry range."""
    setup = safe_mapping_dict(trade_setup) or {}
    direction = safe_text(setup.get("trade_direction")).strip() or "Neutral"
    target_price_candidates = price_candidates(setup.get("target_price"))
    stop_loss_candidates = price_candidates(setup.get("stop_loss"))
    target_price = first_price(setup.get("target_price"))
    stop_loss = first_price(setup.get("stop_loss"))
    details = {
        "trade_direction": direction,
        "current_price": current_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
    }
    ambiguous_fields = []
    if len(target_price_candidates) > 1 and not has_explicit_price_range(setup.get("target_price")):
        details["target_price_candidates"] = target_price_candidates
        ambiguous_fields.append("target_price")
    if len(stop_loss_candidates) > 1 and not has_explicit_price_range(setup.get("stop_loss")):
        details["stop_loss_candidates"] = stop_loss_candidates
        ambiguous_fields.append("stop_loss")
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if direction not in _VALID_DIRECTIONS:
        issue = _issue("invalid_trade_direction", "交易方向不在允許的 Long、Short 或 Neutral 範圍內。", details)
        blocking.append(issue)
        checks.append(_check("trade_setup_alignment", "blocked", issue["message"], details))
        return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}

    if neutral_observation_is_explicit(setup):
        details["execution_status"] = "no_trade"
        checks.append(_check("trade_setup_alignment", "passed", "明確觀望且附重新檢查條件，本次不建立交易部位。", details))
        return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}

    entry = parse_price_range(setup.get("entry_zone"))
    if target_price is None or stop_loss is None or (direction == "Neutral" and current_price is None) or (direction != "Neutral" and entry is None):
        issue = _issue(
            "missing_trade_setup_price_inputs",
            "交易計畫缺少可解析的進場、目標或停損，無法完成方向一致性檢查。",
            details,
        )
        warnings.append(issue)
        checks.append(_check("trade_setup_alignment", "warning", issue["message"], details))
        return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}

    if ambiguous_fields:
        issue = _issue(
            "ambiguous_trade_setup_price_inputs",
            "交易計畫的目標或停損包含多個情境價格，無法用單一數值代表，需人工核對。",
            {**details, "ambiguous_fields": ambiguous_fields},
        )
        warnings.append(issue)

    if direction in {"Long", "Short"} and not ambiguous_fields:
        execution = evaluate_trade_execution(
            direction=direction, entry_zone=setup.get("entry_zone"),
            target_price=setup.get("target_price"), stop_loss=setup.get("stop_loss"),
            risk_reward=setup.get("risk_reward"), transaction_cost=setup.get("transaction_cost"),
        )
        details.update(execution["details"])
        # Preserve historical issue IDs used by quality UI filters; evidence and
        # messages now explicitly identify the intended entry rather than spot.
        aliases = {
            "long_target_not_outside_entry": "long_target_not_above_current_price",
            "long_stop_not_outside_entry": "long_stop_not_below_current_price",
            "short_target_not_outside_entry": "short_target_not_below_current_price",
            "short_stop_not_outside_entry": "short_stop_not_above_current_price",
        }
        for failure in execution["issues"]:
            issue = _issue(aliases.get(failure["id"], failure["id"]), failure["message"], details)
            blocking.append(issue)
            checks.append(_check("trade_setup_alignment", "blocked", issue["message"], details))

    if not blocking:
        status = "warning" if warnings else "passed"
        message = (
            "交易方向未見阻斷矛盾，但目標或停損包含多個情境價格，需人工核對。"
            if warnings
            else "交易方向、目標與停損未見明顯矛盾。"
        )
        checks.append(_check("trade_setup_alignment", status, message, details))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}


__all__ = ["evaluate_trade_setup_alignment"]
