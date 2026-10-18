"""Fail-closed completed-session dates for Taiwan research candidate readiness."""
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from market_calendar_store import load_market_calendar


def completed_session(moment):
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        return None
    moment = moment.astimezone(ZoneInfo("Asia/Taipei"))
    day = moment.date()
    for _ in range(32):
        calendar = load_market_calendar("tw", day.year)
        if calendar.get("coverage_status") != "available":
            return None
        close = time.fromisoformat(calendar.get("early_closes", {}).get(day.isoformat(), calendar["close"]))
        if day.weekday() < 5 and day.isoformat() not in calendar["holidays"]:
            if day < moment.date() or moment.time().replace(tzinfo=None) >= close:
                return day.isoformat()
        day -= timedelta(days=1)
    return None


def observation_readiness(*, price_date, institutional_date, moment):
    expected = completed_session(moment)
    aligned = bool(expected and price_date == expected and institutional_date == expected)
    return {"expected_completed_session": expected, "price_observation_date": price_date,
            "institutional_observation_date": institutional_date,
            "latest_source_dates_aligned": aligned,
            "calendar_basis": "market_calendar_store; weekday/holiday/session close; unknown-year fails closed",
            "actionable": False, "research_only": True,
            "reason": "日期符合最近已完成交易日；仍須獨立事實與觸發條件驗證" if aligned else "資料未達最近已完成交易日或日期未對齊；禁止當作最新完整候選"}
