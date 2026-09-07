"""Strict A prediction wrapper around the existing pure evaluator."""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Mapping

from decision_backtest import add_calendar_months, evaluate_prediction
from recommendation_labels import normalize_recommendation_label


LABELS = {"買入", "放空", "避免", "持有"}


def _positive(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value)) and float(value) > 0


def evaluate_prediction_oos(*, recommendation: Any, initial_price: Any, actual_price: Any,
                           target_price: Any = None, direction_only: bool = False) -> dict[str, Any]:
    label = normalize_recommendation_label(recommendation) if isinstance(recommendation, str) else "N/A"
    result = {"metric_basis": "direction_only" if direction_only else "target_calibration", "outcome": None,
              "reason": None, "strategy_roi_pct": None, "target_error_pct": None}
    if label not in LABELS:
        result.update(reason="unsupported_recommendation", status="unscored")
        return result
    if not _positive(initial_price) or not _positive(actual_price):
        result.update(reason="invalid_price_input", status="unscored")
        return result
    if not direction_only and label in {"買入", "放空"} and not _positive(target_price):
        result.update(reason="invalid_target_price", status="unscored")
        return result
    evaluated = evaluate_prediction(recommendation=label, initial_price=initial_price, actual_price=actual_price,
                                     target_price=target_price)
    if direction_only and label in {"買入", "放空"}:
        market_return = evaluated["market_return_pct"]
        hit = market_return > 0 if label == "買入" else market_return < 0
        evaluated.update(outcome="hit" if hit else "miss", reason="direction_only")
    result.update(evaluated, status="scored")
    return result


def evaluate_a_horizon(*, report_available_date: date, sessions: list[date], closes: Mapping[str, Any],
                       recommendation: Any, target_price: Any, horizon_months: int) -> dict[str, Any]:
    if horizon_months not in {3, 6, 12}:
        raise ValueError("A horizon must be 3, 6 or 12 months")
    baseline = next((s for s in sessions if s > report_available_date), None)
    endpoint = add_calendar_months(report_available_date, horizon_months)
    endpoint = next((s for s in sessions if s >= endpoint), None)
    result = {"horizon_months": horizon_months, "baseline_session": baseline.isoformat() if baseline else None,
              "endpoint_session": endpoint.isoformat() if endpoint else None, "status": "pending", "outcome": None}
    if baseline is None or endpoint is None or endpoint <= baseline:
        result["reason"] = "pending_horizon" if endpoint is None else "invalid_evaluation_window"
        return result
    initial = closes.get(baseline.isoformat())
    actual = closes.get(endpoint.isoformat())
    evaluated = evaluate_prediction_oos(recommendation=recommendation, initial_price=initial, actual_price=actual,
                                        target_price=target_price)
    result.update(evaluated)
    return result
