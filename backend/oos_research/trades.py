"""Pure B/C/D trade wrappers; no report stores, fetchers or runtime config."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from trade_path_backtest import evaluate_trade_path
from trade_execution_contract import evaluate_trade_execution


def validate_trade_inputs(*, direction: Any, horizon_trading_days: Any, plan: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if direction not in {"Long", "Short", "Neutral"}:
        issues.append("unknown_direction")
    if isinstance(horizon_trading_days, bool) or not isinstance(horizon_trading_days, int) or not 1 <= horizon_trading_days <= 252:
        issues.append("explicit_trade_horizon_required")
    if direction == "Neutral":
        if not plan.get("observation_reason"):
            issues.append("explicit_cash_observation_required")
        return issues
    contract = evaluate_trade_execution(direction=direction, entry_zone=plan.get("entry_zone"),
                                       target_price=plan.get("target_price"), stop_loss=plan.get("stop_loss"),
                                       transaction_cost=plan.get("transaction_cost"))
    if contract["issues"]:
        issues.extend(item["id"] for item in contract["issues"])
    return issues


def evaluate_trade_oos(*, bars: list[Mapping[str, Any]], generated_date: date, as_of: date,
                       direction: str, plan: Mapping[str, Any], horizon_trading_days: int) -> dict[str, Any]:
    issues = validate_trade_inputs(direction=direction, horizon_trading_days=horizon_trading_days, plan=plan)
    if issues:
        return {"status": "insufficient_data", "reason": ";".join(sorted(set(issues))),
                "outcome": None, "strategy_roi_pct": None, "net_strategy_roi_pct": None}
    return evaluate_trade_path(bars=bars, generated_date=generated_date, as_of=as_of, direction=direction,
                               entry_zone=plan.get("entry_zone"), target_price=plan.get("target_price"),
                               stop_loss=plan.get("stop_loss"), transaction_cost=plan.get("transaction_cost"),
                               horizon_trading_days=horizon_trading_days,
                               benchmark_return_pct=plan.get("benchmark_return_pct"))
