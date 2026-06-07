"""Market calendar/time helpers for stock-data freshness."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from market_calendar_store import load_market_calendar

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


def market_calendar(ticker: str, current: datetime | None = None) -> dict:
    now = current or market_now(ticker)
    market = "tw" if is_taiwan_ticker(ticker) else "us"
    calendar = load_market_calendar(market, now.year)
    return {
        "market": market,
        "timezone": calendar["timezone"],
        "open": _parse_hhmm(calendar["open"]),
        "close": _parse_hhmm(calendar["close"]),
        "holidays": {_parse_date(day) for day in calendar.get("holidays", [])},
        "early_closes": {
            _parse_date(day): _parse_hhmm(close_time)
            for day, close_time in (calendar.get("early_closes", {}) or {}).items()
        },
    }


def is_market_holiday(ticker: str, current: datetime | None = None) -> bool:
    now = current or market_now(ticker)
    calendar = market_calendar(ticker, current=now)
    return now.date() in calendar["holidays"]


def market_session_window(ticker: str, current: datetime | None = None) -> tuple[datetime, datetime] | None:
    now = current or market_now(ticker)
    calendar = market_calendar(ticker, current=now)
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


def _parse_date(value: str) -> date:
    return date.fromisoformat(str(value))


def _parse_hhmm(value: str) -> time:
    hour, minute = str(value or "00:00").split(":", 1)
    return time(int(hour), int(minute))
