"""Pure decision-backtest date, ROI, and hit/miss calculations."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from report_index import normalize_recommendation_label


BACKTEST_HORIZONS = (3, 6, 12)


def add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + int(months)
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def evaluate_prediction(
    *,
    recommendation: str,
    initial_price: float,
    actual_price: float,
    target_price: float | None = None,
) -> dict[str, Any]:
    initial = float(initial_price)
    actual = float(actual_price)
    if initial <= 0 or actual <= 0:
        raise ValueError("initial_price and actual_price must be positive")
    recommendation = normalize_recommendation_label(recommendation)
    market_return = (actual / initial - 1) * 100
    target = float(target_price) if target_price not in (None, "") else None
    target_error = ((actual / target - 1) * 100) if target and target > 0 else None

    if recommendation in {"買入", "買進"}:
        strategy_roi = market_return
        hit = market_return > 0 and (target is None or actual >= target * 0.9)
        reason = "direction_and_target_met" if hit else "buy_thesis_not_met"
    elif recommendation in {"避免", "強烈放空"}:
        strategy_roi = -market_return
        hit = market_return < 0 and (target is None or actual <= target * 1.1)
        reason = "short_direction_and_target_met" if hit else "short_thesis_not_met"
    elif recommendation == "持有":
        strategy_roi = 0.0
        hit = abs(market_return) <= 10
        reason = "hold_range_respected" if hit else "hold_range_broken"
    else:
        strategy_roi = market_return
        hit = False
        reason = "unsupported_recommendation"

    return {
        "recommendation": recommendation,
        "market_return_pct": round(market_return, 4),
        "strategy_roi_pct": round(strategy_roi, 4),
        "target_error_pct": round(target_error, 4) if target_error is not None else None,
        "outcome": "hit" if hit else "miss",
        "reason": reason,
    }
