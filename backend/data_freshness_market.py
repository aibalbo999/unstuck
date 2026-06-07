"""Market calendar/time helpers for stock-data freshness."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None


def is_taiwan_ticker(ticker: str) -> bool:
    stock_id = str(ticker).replace(".TW", "").replace(".TWO", "")
    return str(ticker).endswith(".TW") or str(ticker).endswith(".TWO") or (stock_id.isdigit() and len(stock_id) == 4)


US_MARKET_HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
}
US_EARLY_CLOSES_2026 = {
    date(2026, 11, 27): time(13, 0),
    date(2026, 12, 24): time(13, 0),
}
TW_MARKET_HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 2, 12),
    date(2026, 2, 13),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 27),
    date(2026, 4, 3),
    date(2026, 4, 6),
    date(2026, 5, 1),
    date(2026, 6, 19),
    date(2026, 9, 25),
    date(2026, 9, 28),
    date(2026, 10, 9),
    date(2026, 10, 26),
    date(2026, 12, 25),
}


def market_now(ticker: str) -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    zone_name = "Asia/Taipei" if is_taiwan_ticker(ticker) else "America/New_York"
    return datetime.now(ZoneInfo(zone_name))


def market_calendar(ticker: str) -> dict:
    if is_taiwan_ticker(ticker):
        return {
            "market": "tw",
            "timezone": "Asia/Taipei",
            "open": time(9, 0),
            "close": time(13, 30),
            "holidays": TW_MARKET_HOLIDAYS_2026,
            "early_closes": {},
        }
    return {
        "market": "us",
        "timezone": "America/New_York",
        "open": time(9, 30),
        "close": time(16, 0),
        "holidays": US_MARKET_HOLIDAYS_2026,
        "early_closes": US_EARLY_CLOSES_2026,
    }


def is_market_holiday(ticker: str, current: datetime | None = None) -> bool:
    now = current or market_now(ticker)
    calendar = market_calendar(ticker)
    return now.date() in calendar["holidays"]


def market_session_window(ticker: str, current: datetime | None = None) -> tuple[datetime, datetime] | None:
    now = current or market_now(ticker)
    calendar = market_calendar(ticker)
    if now.weekday() >= 5 or now.date() in calendar["holidays"]:
        return None
    close_time = calendar["early_closes"].get(now.date(), calendar["close"])
    return (
        now.replace(hour=calendar["open"].hour, minute=calendar["open"].minute, second=0, microsecond=0),
        now.replace(hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0),
    )


def is_likely_market_session(ticker: str, current: datetime | None = None, grace_minutes: int = 15) -> bool:
    window = market_session_window(ticker, current=current)
    if window is None:
        return False
    now = current or market_now(ticker)
    opens_at, closes_at = window
    closes_with_grace = closes_at + timedelta(minutes=max(0, int(grace_minutes)))
    return opens_at <= now <= closes_with_grace
