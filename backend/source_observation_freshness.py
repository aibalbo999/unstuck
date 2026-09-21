"""Pure observation-date screening; a new fetch cannot renew an old observation."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from data_freshness_market import is_taiwan_ticker


def parse_observation_date(observed_at):
    """Parse a source's explicit date; never substitute fetch time."""
    if isinstance(observed_at, str):
        try:
            return (datetime.strptime(observed_at, "%Y%m%d").date()
                    if len(observed_at) == 8 and observed_at.isdigit()
                    else date.fromisoformat(observed_at[:10]))
        except ValueError:
            pass
    return None


def observation_recency(observed_at, *, ticker, now_epoch, max_age_days=7):
    """Conservative calendar-day bound, not an exchange-session completeness claim."""
    observed = parse_observation_date(observed_at)
    zone = ZoneInfo("Asia/Taipei" if is_taiwan_ticker(ticker) else "America/New_York")
    today = datetime.fromtimestamp(now_epoch, zone).date()
    age = (today - observed).days if observed else None
    status = ("unknown" if age is None else "future" if age < 0
              else "stale" if age > max_age_days else "recent")
    return {
        "observed_at": observed.isoformat() if observed else None,
        "observation_age_days": age,
        "observation_max_age_days": max_age_days,
        "observation_status": status,
        "observation_policy": "calendar_day_bound; not proof of latest trading session",
    }
