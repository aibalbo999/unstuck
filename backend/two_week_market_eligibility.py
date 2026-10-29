"""Fail-closed completed-session dates for Taiwan research candidate readiness."""
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from market_calendar_store import load_market_calendar, session_day_status


def completed_session(moment, *, ticker=None):
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        return None
    moment = moment.astimezone(ZoneInfo("Asia/Taipei"))
    day = moment.date()
    for _ in range(32):
        calendar = load_market_calendar("tw", day.year)
        if calendar.get("coverage_status") != "available":
            return None
        close = time.fromisoformat(calendar.get("early_closes", {}).get(day.isoformat(), calendar["close"]))
        session = session_day_status(day, market="tw", calendar=calendar,
                                     exchange="TPEX" if str(ticker).upper().endswith(".TWO") else "TWSE")
        if session["state"] == "unknown":
            return None
        if session["state"] == "open":
            if day < moment.date() or moment.time().replace(tzinfo=None) >= close:
                return day.isoformat()
        day -= timedelta(days=1)
    return None


def observation_readiness(*, price_date, institutional_date, moment, ticker=None):
    # This is a per-security claim, unlike the exchange-wide completed-session
    # helper. An absent/ambiguous market identity must not borrow TWSE closures.
    identity = str(ticker or "").strip().upper()
    market = "TPEX" if identity.endswith(".TWO") else "TWSE" if identity.endswith(".TW") else None
    expected = completed_session(moment, ticker=identity) if market else None
    aligned = bool(expected and price_date == expected and institutional_date == expected)
    return {"expected_completed_session": expected, "price_observation_date": price_date,
            "institutional_observation_date": institutional_date,
            "ticker": identity or None, "calendar_market": market,
            "latest_source_dates_aligned": aligned,
            "calendar_basis": "market_calendar_store; weekday/holiday/session close; unknown-year fails closed",
            "actionable": False, "research_only": True,
            "reason": "日期符合最近已完成交易日；仍須獨立事實與觸發條件驗證" if aligned else "資料未達最近已完成交易日或日期未對齊；禁止當作最新完整候選"}
