from datetime import datetime
import pytest
from two_week_market_eligibility import completed_session, observation_readiness
from daily_decision_dashboard import build_daily_decision_dashboard


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


@pytest.mark.parametrize("in_recent_sample", [False, True])
def test_current_withdrawal_outside_recent_sample_is_in_daily_summary(in_recent_sample):
    report = {"ticker": "1301.TW", "filename": "1301_TW_v4_report_old.html", "pipeline_id": "v4", "content_credibility": {"status": "blocked"}, "report_conformance": {"status": "passed"}, "evidence_exit_gate": {"verdict": "approved"}}
    dashboard = build_daily_decision_dashboard(reports={"reports": [{**report, "content_credibility": {"status": "passed"}}] if in_recent_sample else []}, watchlist={}, screener={"items": [{"ticker": "1301.TW", "score": 99}, {"ticker": "2327.TW", "score": 90}]}, performance={}, free_mode={}, quality_audit={"scope": "all_indexed_reports", "selection_basis": "latest_per_ticker_pipeline", "current_blocked_reports": [report]})
    assert dashboard["withdrawn_reports"][0]["ticker"] == "1301.TW"
    assert all(row["ticker"] != "1301.TW" for row in dashboard["top_candidates"])
    assert not dashboard["two_week_candidate_policy"]["actionable"]
    assert any(row.get("ticker") == "1301.TW" and row["type"] == "manual_review" for row in dashboard["actions"])
