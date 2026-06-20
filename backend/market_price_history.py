"""Historical close lookup used by deterministic decision backtests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable


def fetch_backtest_prices(
    ticker: str,
    generated_date: date,
    evaluation_date: date,
    *,
    ticker_factory: Callable[[str], Any] | None = None,
) -> dict:
    if ticker_factory is None:
        import yfinance as yf

        ticker_factory = yf.Ticker
    history = ticker_factory(str(ticker)).history(
        start=(generated_date - timedelta(days=10)).isoformat(),
        end=(evaluation_date + timedelta(days=3)).isoformat(),
        auto_adjust=False,
    )
    if history is None or history.empty or "Close" not in history:
        raise ValueError(f"{ticker} 無可用歷史收盤價")
    closes = []
    for index, value in history["Close"].items():
        trading_date = index.date() if hasattr(index, "date") else date.fromisoformat(str(index)[:10])
        if value is not None:
            closes.append((trading_date, float(value)))
    initial = _nearest_close(closes, generated_date)
    actual = _nearest_close(closes, evaluation_date)
    if initial is None or actual is None:
        raise ValueError(f"{ticker} 歷史收盤價期間不完整")
    return {
        "initial_price": round(initial[1], 4),
        "initial_price_date": initial[0].isoformat(),
        "actual_price": round(actual[1], 4),
        "actual_price_date": actual[0].isoformat(),
        "source": "yfinance historical close",
    }


def _nearest_close(closes: list[tuple[date, float]], target: date) -> tuple[date, float] | None:
    before = [item for item in closes if item[0] <= target]
    if before:
        return max(before, key=lambda item: item[0])
    after = [item for item in closes if item[0] > target]
    return min(after, key=lambda item: item[0]) if after else None
