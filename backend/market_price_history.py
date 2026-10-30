"""Historical close lookup used by deterministic decision backtests."""

from __future__ import annotations

from datetime import date, timedelta, datetime, timezone
from typing import Any, Callable


def fetch_backtest_bars(
    ticker: str, generated_date: date, evaluation_date: date,
    *, ticker_factory: Callable[[str], Any] | None = None, moment: datetime | None = None,
) -> list[dict]:
    """Read unadjusted daily OHLC after the report; absent columns stay absent."""
    captured_at=moment or datetime.now(timezone.utc)
    if str(ticker).endswith((".TW",".TWO")):
        from market_evidence_policy import completed_evidence_session
        completed=completed_evidence_session(captured_at, ticker=ticker)
        if completed is None:return []
        evaluation_date=min(evaluation_date,date.fromisoformat(completed))
        if evaluation_date<=generated_date:return []
    if ticker_factory is None:
        import yfinance as yf

        ticker_factory = yf.Ticker
    history = ticker_factory(str(ticker)).history(
        start=(generated_date + timedelta(days=1)).isoformat(),
        end=(evaluation_date + timedelta(days=1)).isoformat(), auto_adjust=False, actions=True,
    )
    if history is None or history.empty:
        return []
    observation = {"provider": "yfinance", "ticker": str(ticker),
                   "retrieved_at": datetime.now(timezone.utc).isoformat(),
                   "query_start": (generated_date + timedelta(days=1)).isoformat(),
                   "query_end_exclusive": (evaluation_date + timedelta(days=1)).isoformat(),
                   "auto_adjust": False, "actions_requested": True,
                   "finality_verified": False, "raw_http_retained": False,
                   "price_basis": "provider_ohlc_auto_adjust_false",
                   "limitation": "SDK settings do not establish exchange-raw split history or historical availability; retrieved_at is acquisition time."}
    rows = []
    for index, values in history.iterrows():
        trading_date = index.date() if hasattr(index, "date") else date.fromisoformat(str(index)[:10])
        if not generated_date < trading_date <= evaluation_date:
            continue
        row = {"date": trading_date.isoformat(), "observation_provenance": dict(observation)}
        for column in ("Open", "High", "Low", "Close"):
            if column in history:
                row[column.lower()] = float(values[column]) if values[column] is not None else None
        for column, key in (("Stock Splits", "stock_splits"), ("Dividends", "dividends")):
            if column in history:
                row[key] = float(values[column])
        rows.append(row)
    if rows and str(ticker).endswith(".TW"):
        from data_fetch.market_sources.twse_session_observation import official_observation
        rows[-1]["observation_provenance"]["official_observation"]=official_observation(str(ticker),rows[-1]["date"])
    if rows and str(ticker).endswith(".TWO"):
        from data_fetch.market_sources.tpex_session_observation import official_observation
        rows[-1]["observation_provenance"]["official_observation"]=official_observation(str(ticker),rows[-1]["date"])
    return rows


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
    later = [item for item in closes if generated_date < item[0] <= evaluation_date]
    initial = min(later, key=lambda item: item[0]) if later else None
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
    return None  # Missing prior price cannot be repaired with future information.
