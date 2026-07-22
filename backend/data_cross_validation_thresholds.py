"""Dynamic threshold policy for cross-source financial validation."""

from __future__ import annotations

from typing import Any

from data_validation_values import safe_float


DEFAULT_DIVERGENCE_THRESHOLD_PCT = 5.0
DEFAULT_CONFLICT_THRESHOLD_PCT = 20.0


def is_taiwan_ticker_for_threshold(ticker: str) -> bool:
    text = str(ticker or "").strip().upper()
    if text.endswith(".TWO"):
        stock_id = text[:-4]
        return stock_id.isdigit() and len(stock_id) == 4
    if text.endswith(".TW"):
        stock_id = text[:-3]
        return stock_id.isdigit() and len(stock_id) == 4
    return text.isdigit() and len(text) == 4


def dynamic_cross_validation_thresholds(primary_data: dict[str, Any]) -> tuple[float, float]:
    ticker = str(primary_data.get("ticker") or "").strip().upper() if isinstance(primary_data, dict) else ""
    if not is_taiwan_ticker_for_threshold(ticker):
        return DEFAULT_DIVERGENCE_THRESHOLD_PCT, DEFAULT_CONFLICT_THRESHOLD_PCT
    market_cap = safe_float(primary_data.get("market_cap_raw")) if isinstance(primary_data, dict) else None
    if market_cap is None:
        return DEFAULT_DIVERGENCE_THRESHOLD_PCT, DEFAULT_CONFLICT_THRESHOLD_PCT
    market_cap_twd_billion = market_cap / 100_000_000
    if market_cap_twd_billion > 500:
        return DEFAULT_DIVERGENCE_THRESHOLD_PCT, DEFAULT_CONFLICT_THRESHOLD_PCT
    if market_cap_twd_billion > 100:
        return 8.0, 28.0
    return 12.0, 40.0
