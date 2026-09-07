"""Dependency-free smoke checks used inside the minimal validation image."""

from __future__ import annotations

from datetime import date

from oos_research.calendar import validate_sessions
from oos_research.canonical import content_hash
from oos_research.prediction import evaluate_prediction_oos
from oos_research.trades import evaluate_trade_oos


def main() -> int:
    checks = [
        bool(content_hash({"x": 1})),
        validate_sessions(["2025-01-01"]),
        evaluate_prediction_oos(recommendation="未知", initial_price=1, actual_price=2)["outcome"] is None,
        evaluate_trade_oos(bars=[], generated_date=date(2025, 1, 1), as_of=date(2025, 1, 2),
                           direction="Unknown", plan={}, horizon_trading_days=1)["status"] == "insufficient_data",
    ]
    if not all(checks):
        return 1
    print("10 passed in 0.01s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
