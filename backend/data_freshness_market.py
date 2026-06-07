"""Market calendar/time helpers for stock-data freshness."""

from __future__ import annotations

from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None


def is_taiwan_ticker(ticker: str) -> bool:
    stock_id = str(ticker).replace(".TW", "").replace(".TWO", "")
    return str(ticker).endswith(".TW") or str(ticker).endswith(".TWO") or (stock_id.isdigit() and len(stock_id) == 4)


def market_now(ticker: str) -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    zone_name = "Asia/Taipei" if is_taiwan_ticker(ticker) else "America/New_York"
    return datetime.now(ZoneInfo(zone_name))


def is_likely_market_session(ticker: str) -> bool:
    now = market_now(ticker)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    if is_taiwan_ticker(ticker):
        return 9 * 60 <= minutes <= 13 * 60 + 30
    return 9 * 60 + 30 <= minutes <= 16 * 60
