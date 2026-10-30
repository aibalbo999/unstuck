"""Calendar identity must survive nested candidate explanation and price lookup."""
from copy import deepcopy
from datetime import date, datetime
import json

import pandas as pd
import pytest


DATES = [("2026-10-23", "2026-10-22"), ("2026-07-10", "2026-07-09")]


@pytest.fixture
def unverified_tpex_calendar(monkeypatch):
    """Exercise missing exchange proof independently of maintained calendars."""
    import market_session_admission
    import two_week_market_eligibility
    for module in (market_session_admission, two_week_market_eligibility):
        original = module.session_day_status
        def status(*args, _original=original, **kwargs):
            result = _original(*args, **kwargs)
            if kwargs.get('exchange') == 'TPEX':
                return {**result, 'state': 'unknown', 'reason': 'synthetic_tpex_proof_missing'}
            return result
        monkeypatch.setattr(module, 'session_day_status', status)


def snapshot(ticker, previous):
    return {"ticker": ticker, "pipeline": "v4", "data": {"ticker": ticker,
        "daily_market_data": {"ticker": ticker, "as_of": previous,
            "bars": [{"date": previous, "close": 60, "volume": 0}]},
        "institutional_trading": {"latest_date": previous, "observation_dates": [previous]}}}


def load(tmp_path, value, moment, metadata=None):
    from candidate_report_observations import load_candidate_report_observations
    ticker = "1234.TWO"
    filename = "1234_TWO_v4_report_job_identity.html"
    (tmp_path / filename.replace(".html", ".data.json")).write_text(json.dumps(value))
    return load_candidate_report_observations([{"ticker": ticker}],
        [{"ticker": ticker, "latest_report": {"filename": filename, **(metadata or {})}}], str(tmp_path), moment=moment)[ticker]


@pytest.mark.parametrize("day,previous", DATES)
def test_nested_candidate_and_direct_explanation_share_unproven_market_scope(tmp_path, day, previous, unverified_tpex_calendar):
    from candidate_decision_explanation import explain_report_decision
    moment = datetime.fromisoformat(day + "T23:00:00+08:00")
    value = snapshot("1234.TWO", previous)
    original = deepcopy(value)
    result = load(tmp_path, value, moment)
    nested = result["decision_explanation"]["source_evidence_state"]
    assert result["status"] == "available" and not result["latest_source_dates_aligned"]
    assert result["expected_completed_session"] is nested["expected_completed_session"] is None
    assert nested["institutional_snapshot_state"] == nested["evaluation_phase"] == "unknown"
    assert explain_report_decision(value, moment=moment)["source_evidence_state"] == nested
    assert value == original


@pytest.mark.parametrize("ticker,day,expected", [
    ("1234.TW", "2026-10-23", "2026-10-22"),
    ("1234.TW", "2026-07-10", "2026-07-09"),
    ("1234.TWO", "2026-10-27", "2026-10-27"),
])
def test_bound_market_positive_dates_still_work_without_optional_snapshot_header(ticker, day, expected):
    from candidate_decision_explanation import explain_report_decision
    value = snapshot(ticker, expected)
    value.pop("ticker")
    state = explain_report_decision(value, moment=datetime.fromisoformat(day + "T23:00:00+08:00"))["source_evidence_state"]
    assert state["expected_completed_session"] == expected
    assert state["institutional_snapshot_state"] == "latest_session_in_snapshot"


def unbound(kind):
    value = snapshot("1234.TWO", "2026-10-27")
    if kind == "missing": value["data"].pop("ticker")
    if kind == "ambiguous": value["data"]["ticker"] = "1234"
    if kind == "malformed": value["data"]["ticker"] = {"ticker": "1234.TWO"}
    if kind == "header": value["ticker"] = "1234.TW"
    if kind == "daily": value["data"]["daily_market_data"]["ticker"] = "1234.TW"
    if kind == "institution": value["data"]["institutional_trading"]["ticker"] = "5678.TWO"
    if kind == "official": value["data"]["institutional_trading"]["latest_official_observation"] = {"ticker": "5678.TWO"}
    return value


@pytest.mark.parametrize("kind", ["missing", "ambiguous", "malformed", "header", "daily", "institution", "official"])
def test_missing_or_conflicting_identity_cannot_make_nested_dates_current(tmp_path, kind):
    from candidate_decision_explanation import explain_report_decision
    value = unbound(kind)
    before = deepcopy(value)
    moment = datetime.fromisoformat("2026-10-27T23:00:00+08:00")
    state = explain_report_decision(value, moment=moment)["source_evidence_state"]
    assert state["expected_completed_session"] is None
    assert state["institutional_snapshot_state"] == "unknown"
    result = load(tmp_path, value, moment)
    assert result["status"] == "unavailable" and not result["actionable"]
    assert value == before


@pytest.mark.parametrize("other", ["1234.TW", "5678.TWO", None])
def test_metadata_identity_conflict_cannot_diverge_outer_and_inner_states(tmp_path, other):
    from candidate_decision_explanation import explain_report_decision
    value = snapshot("1234.TWO", "2026-10-27")
    moment = datetime.fromisoformat("2026-10-27T23:00:00+08:00")
    metadata = {"ticker": other}
    state = explain_report_decision(value, metadata, moment=moment)["source_evidence_state"]
    assert state["expected_completed_session"] is None
    assert state["institutional_snapshot_state"] == "unknown"
    assert load(tmp_path, value, moment, metadata)["status"] == "unavailable"


@pytest.mark.parametrize("day,previous", DATES)
@pytest.mark.parametrize("ticker,may_fetch", [("1234.TWO", False), ("1234.TW", True)])
def test_price_lookup_uses_security_market_before_provider_access(day, previous, ticker, may_fetch, unverified_tpex_calendar):
    from market_price_history import fetch_backtest_bars
    calls = []
    class Stock:
        def history(self, **kwargs):
            calls.append(kwargs)
            return pd.DataFrame()
    result = fetch_backtest_bars(ticker, date(2026, 7, 1), date.fromisoformat(day),
        ticker_factory=lambda _: Stock(), moment=datetime.fromisoformat(day + "T23:00:00+08:00"))
    assert result == [] and bool(calls) is may_fetch
    if may_fetch:
        assert calls[0]["end"] == day
