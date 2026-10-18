from datetime import datetime
import pytest
from two_week_market_eligibility import completed_session, observation_readiness


@pytest.mark.parametrize("moment, expected", [
    ("2026-10-01T08:30:00+08:00", "2026-09-30"),
    ("2026-10-01T18:00:00+08:00", "2026-10-01"),
    ("2026-10-03T18:00:00+08:00", "2026-10-02"),
    ("2026-09-28T18:00:00+08:00", "2026-09-24"),
    ("2026-10-09T18:00:00+08:00", "2026-10-08"),
    ("2027-10-01T18:00:00+08:00", None),
])
def test_completed_session_respects_clock_weekends_holidays_and_unknown_year(moment, expected):
    assert completed_session(datetime.fromisoformat(moment)) == expected


def test_recent_but_lagging_source_cannot_claim_latest_candidate():
    r = observation_readiness(price_date="2026-10-01", institutional_date="2026-09-30", moment=datetime.fromisoformat("2026-10-01T18:00:00+08:00"))
    assert not r["latest_source_dates_aligned"]
    assert r["research_only"] and not r["actionable"]
