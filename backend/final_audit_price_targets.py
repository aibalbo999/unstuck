"""Deterministic price-target checks used by final report audit."""

from __future__ import annotations

from typing import Any


REQUIRED_PRICE_TARGETS = ("熊市情境", "基本情境", "牛市情境")


def price_target_audit_issues(
    price_targets: dict[str, Any],
    *,
    current_price: Any,
    valuation_agent: int | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    missing_targets = [key for key in REQUIRED_PRICE_TARGETS if key not in price_targets]
    if valuation_agent is not None and missing_targets:
        message = f"缺少目標價情境：{', '.join(missing_targets)}"
        issues.append({
            "critical": f"Agent {valuation_agent} {message}",
            "repair_agent": valuation_agent,
            "repair_issue": message,
        })

    numeric_targets = {key: value for key, value in price_targets.items() if isinstance(value, (int, float))}
    if isinstance(current_price, (int, float)) and current_price > 100:
        tiny_targets = [
            f"{key}=NT${value:g}"
            for key, value in numeric_targets.items()
            if value < current_price * 0.05
        ]
        if tiny_targets:
            issue = f"目標價疑似單位縮小錯誤：{', '.join(tiny_targets)}"
            issues.append({
                "critical": issue,
                "repair_agent": valuation_agent,
                "repair_issue": issue,
            })

    if all(key in numeric_targets for key in REQUIRED_PRICE_TARGETS):
        bear = numeric_targets["熊市情境"]
        base = numeric_targets["基本情境"]
        bull = numeric_targets["牛市情境"]
        if not (bear <= base <= bull):
            issue = f"三情境目標價順序不合理：熊市 {bear:g}、基本 {base:g}、牛市 {bull:g}。"
            issues.append({
                "critical": issue,
                "repair_agent": valuation_agent,
                "repair_issue": issue,
            })

    return issues
