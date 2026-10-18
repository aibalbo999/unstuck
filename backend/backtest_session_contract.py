"""Verified session windows; never infer calendar coverage from bar count."""
from datetime import timedelta
from market_calendar_store import load_market_calendar


def session_window(generated, horizon, *, market="tw"):
    if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 252:
        return {"status": "invalid_horizon", "sessions": []}
    sessions = []
    day = generated
    for _ in range(horizon * 4 + 40):
        day += timedelta(days=1)
        calendar = load_market_calendar(market, day.year)
        if calendar.get("coverage_status") != "available":
            return {"status": "calendar_unavailable", "sessions": []}
        if day.weekday() < 5 and day.isoformat() not in calendar["holidays"]:
            sessions.append(day.isoformat())
        if len(sessions) == horizon:
            return {"status": "verified", "sessions": sessions, "maturity_date": sessions[-1]}
    return {"status": "calendar_unavailable", "sessions": []}
