"""Admission is independent of OHLC arithmetic, volume size, and input hashes."""
from datetime import date, datetime

import pandas as pd
import pytest


def _bar(day, volume=0.):
    return {"date": day, "open": 60., "high": 60., "low": 60., "close": 60., "volume": volume}


def _daily(*days, ticker="2356.TW"):
    return {"ticker": ticker, "as_of": days[-1] if days else None,
            "bars": [_bar(day) for day in days]}


def test_announced_emergency_closure_is_not_a_completed_session():
    from two_week_market_eligibility import completed_session
    assert completed_session(datetime.fromisoformat("2026-10-23T18:00:00+08:00")) == "2026-10-22"
    assert completed_session(datetime.fromisoformat("2026-10-27T08:00:00+08:00")) == "2026-10-22"


def test_july_typhoon_closure_is_sourced_and_not_a_missing_trading_day():
    from market_calendar_store import load_market_calendar
    from market_session_admission import assess_daily_session_integrity
    from two_week_market_eligibility import completed_session
    assert completed_session(datetime.fromisoformat("2026-07-10T18:00:00+08:00")) == "2026-07-09"
    result = assess_daily_session_integrity(_daily("2026-07-09", "2026-07-13"))
    assert result["eligible"] and result["missing_expected_dates"] == []
    exception = load_market_calendar("tw", 2026)["session_exceptions"]["2026-07-10"]
    assert exception["published_date"] == "2026-07-09"
    assert exception["exchanges"] == ["TWSE"]
    assert exception["source_url"].endswith("8a8216d69ef76943019f46cb86ae0110.pdf")


def test_yfinance_session_admission_removes_closed_bars_but_keeps_open_zero_volume(monkeypatch):
    from data_fetch.yfinance_enrichment_extractors import extract_market_history_bundle
    from data_fetch.market_sources import twse_session_observation
    monkeypatch.setattr(twse_session_observation, "official_observation", lambda *args: {"status": "unavailable"})

    class Stock:
        ticker = "2356.TW"

        def history(self, **kwargs):
            return pd.DataFrame({"Open": [60., 60., 63.], "High": [60., 60., 63.],
                                 "Low": [60., 60., 63.], "Close": [60., 60., 63.],
                                 "Adj Close": [60., 60., 63.], "Volume": [0., 0., 10.]},
                                index=pd.to_datetime(["2026-10-22", "2026-10-23", "2026-10-27"]))

    result = extract_market_history_bundle(Stock(), as_of=date(2026, 10, 27))
    assert [bar["date"] for bar in result["daily_market_data"]["bars"]] == ["2026-10-22", "2026-10-27"]
    assert result["daily_market_data"]["bars"][0]["volume"] == 0
    assert result["technical_indicators"]["sample_count"] == 2
    assert result["daily_market_data"]["history_query"]["calendar_verified"] is False
    assert result["daily_market_data"]["history_query"]["calendar_known"] is True
    assert result["daily_market_data"]["quarantined_session_rows"] == [
        {"date": "2026-10-23", "state": "closed", "reason": "official_emergency_closure"}]


def test_zero_volume_is_not_a_closure_and_calendar_consistency_does_not_verify_price():
    from market_session_admission import assess_daily_session_integrity
    result = assess_daily_session_integrity(_daily("2026-10-22", "2026-10-27"))
    assert result["eligible"] and result["status"] == "consistent"
    assert not result["official_price_verified"]
    assert not result["historical_point_in_time_verified"]
    assert result["verification_scope"] == "session_calendar_admission_only"


def test_missing_open_session_is_not_accepted_as_complete_or_imputed_zero():
    from market_session_admission import assess_daily_session_integrity
    daily = _daily("2026-10-20", "2026-10-22")
    # Legacy flags/unsupported issuer claims do not independently prove why a
    # security row is absent. A scoped official suspension validator is needed.
    daily["suspension_evidence"] = {"verified": True, "date": "2026-10-21"}
    result = assess_daily_session_integrity(daily)
    assert result["status"] == "unverifiable" and not result["eligible"]
    assert result["missing_expected_dates"] == ["2026-10-21"]
    assert "expected_session_bar_missing" in result["reason_codes"]
    assert [bar["date"] for bar in daily["bars"]] == ["2026-10-20", "2026-10-22"]


def test_known_closures_do_not_create_expected_missing_rows():
    from market_session_admission import assess_daily_session_integrity
    result = assess_daily_session_integrity(_daily("2026-10-22", "2026-10-27"))
    assert result["eligible"] and result["missing_expected_dates"] == []
    # TWSE closure cannot fill an evidence gap for another market.
    result = assess_daily_session_integrity(_daily("2026-10-22", "2026-10-27", ticker="1234.TWO"))
    assert not result["eligible"] and "2026-10-23" in result["unverified_dates"]


def test_missing_session_scan_is_bounded_for_untrusted_wide_ranges():
    from market_session_admission import assess_daily_session_integrity
    result = assess_daily_session_integrity(_daily("0001-01-01", "9999-12-31"))
    assert not result["eligible"]
    assert "session_window_exceeds_bounded_calendar_check" in result["reason_codes"]


@pytest.mark.parametrize("day, reason", [("2026-10-23", "official_emergency_closure"),
                                         ("2026-10-26", "scheduled_holiday"),
                                         ("2026-10-24", "weekend")])
def test_calendar_rejects_closed_day_even_with_positive_volume_and_forged_verified(day, reason):
    from market_session_admission import assess_daily_session_integrity
    daily = _daily(day)
    daily["bars"][0]["volume"] = 999999
    daily["session_integrity"] = {"eligible": True, "status": "consistent"}
    daily["history_query"] = {"calendar_verified": True}
    result = assess_daily_session_integrity(daily)
    assert not result["eligible"] and result["status"] == "invalid"
    assert result["closed_dates"] == [day] and reason in result["reason_codes"]


def test_unknown_year_and_unbound_market_fail_closed():
    from market_session_admission import assess_daily_session_integrity
    for daily, reason in [(_daily("2027-10-27"), "calendar_coverage_unknown"),
                          (_daily("2026-10-27", ticker=""), "session_market_unbound"),
                          (_daily("2026-10-27", ticker="XYZ.UNKNOWN"), "session_market_unbound")]:
        result = assess_daily_session_integrity(daily)
        assert result["status"] == "unverifiable" and not result["eligible"]
        assert reason in result["reason_codes"]


@pytest.mark.parametrize("days, as_of, reason", [
    (["2026-10-22"], "2026-10-27", "session_as_of_mismatch"),
    (["2026-10-22", "2026-10-22"], "2026-10-22", "session_dates_not_strictly_ordered"),
    (["2026-10-27", "2026-10-22"], "2026-10-22", "session_dates_not_strictly_ordered"),
])
def test_as_of_cannot_renew_old_bars_and_window_dates_must_be_strictly_ordered(days, as_of, reason):
    from market_session_admission import assess_daily_session_integrity
    daily = _daily(*days)
    daily["as_of"] = as_of
    result = assess_daily_session_integrity(daily)
    assert result["status"] == "invalid" and not result["eligible"]
    assert reason in result["reason_codes"]


def test_twse_exception_cannot_be_called_independent_tpex_proof():
    from market_session_admission import assess_daily_session_integrity
    result = assess_daily_session_integrity(_daily("2026-10-23", ticker="1234.TWO"))
    assert result["status"] == "unverifiable" and not result["eligible"]
    assert result["closed_dates"] == []
    assert result["unverified_dates"] == ["2026-10-23"]
    assert "closure_evidence_scope_unverified" in result["reason_codes"]


def test_unknown_removed_date_remains_a_hole_until_reacquired():
    from market_session_admission import assess_daily_session_integrity
    from short_term_market_data import normalize_daily_market_data, build_short_term_market_context
    rows = [_bar("2026-10-22"), _bar("2026-10-23"), _bar("2026-10-27")]
    daily = normalize_daily_market_data(rows, ticker="1234.TWO", as_of=date(2026, 10, 27))
    assert [row["date"] for row in daily["bars"]] == ["2026-10-22", "2026-10-27"]
    assert daily["availability"] == "partial"
    assert not assess_daily_session_integrity(daily)["eligible"]
    context = build_short_term_market_context({"ticker": "1234.TWO", "daily_market_data": daily}, as_of=date(2026, 10, 27))
    assert not context["daily_market_data"]["session_integrity"]["eligible"]
    assert context["technical_indicators"]["sample_count"] == 0
    # If a previously unknown excluded day becomes scheduled-open, its missing
    # bar cannot be recovered by merely changing the calendar label.
    daily = _daily("2026-10-21", "2026-10-27")
    daily["quarantined_session_rows"] = [{"date": "2026-10-22", "state": "unknown", "reason": "prior_missing_calendar"}]
    assert "excluded_session_requires_reacquisition" in assess_daily_session_integrity(daily)["reason_codes"]


def test_filtering_precedes_120_bar_cap_and_does_not_mutate_raw_rows():
    from short_term_market_data import normalize_daily_market_data
    from market_calendar_store import session_day_status
    dates = [day.date().isoformat() for day in pd.date_range("2026-01-01", "2026-10-27")
             if session_day_status(day.date())["state"] == "open"][-120:]
    rows = [_bar(day) for day in dates] + [_bar("2026-10-23", 777.)]
    before = [dict(row) for row in rows]
    daily = normalize_daily_market_data(rows, ticker="2356.TW", as_of=date(2026, 10, 27))
    assert len(daily["bars"]) == 120
    assert daily["bars"][0]["date"] == dates[0]
    assert daily["session_integrity"]["eligible"]
    assert rows == before


def test_calendar_file_cannot_erase_emergency_exception_and_versions_change(tmp_path):
    from market_calendar_store import BUILTIN_MARKET_CALENDARS, load_market_calendar, write_market_calendar
    annual = dict(BUILTIN_MARKET_CALENDARS[("tw", 2026)])
    assert "2026-10-23" not in annual["holidays"]
    write_market_calendar(annual, calendar_dir=str(tmp_path))
    loaded = load_market_calendar("tw", 2026, calendar_dir=str(tmp_path))
    assert loaded["source"] == "local_file"
    assert "2026-10-23" in loaded["holidays"]
    assert loaded["session_exceptions"]["2026-10-23"]["published_date"] == "2026-10-22"
    assert loaded["session_exceptions"]["2026-10-23"]["source_url"].endswith(".pdf")


def test_temporary_open_or_close_requires_dated_official_scope():
    from market_calendar_store import load_market_calendar, session_day_status
    calendar = load_market_calendar("tw", 2026)
    calendar["session_exceptions"] = {"2026-10-24": {"state": "open", "reason": "special_session"}}
    assert session_day_status("2026-10-24", calendar=calendar)["state"] == "unknown"
    calendar["session_exceptions"]["2026-10-24"].update(
        source_url="https://www.twse.com.tw/fixture-not-a-live-announcement", published_date="2026-10-22", exchanges=["TWSE"])
    assert session_day_status("2026-10-24", calendar=calendar)["state"] == "open"
    calendar["session_exceptions"]["2026-10-24"]["source_url"] = "https://untrusted.example/announcement"
    assert session_day_status("2026-10-24", calendar=calendar)["state"] == "unknown"


def test_absent_quote_is_not_inferred_as_closure_and_malformed_dates_do_not_crash():
    from market_calendar_store import session_day_status
    from market_session_admission import assess_daily_session_integrity
    assert session_day_status("2026-10-22")["state"] == "open"
    result = assess_daily_session_integrity({"ticker": "2356.TW", "as_of": "2026-10-27", "bars": [None]})
    assert result["status"] == "invalid" and result["closed_dates"] == []
    assert not assess_daily_session_integrity({"ticker": "2356.TW", "bars": [_bar("2026-10-27")]})["eligible"]


@pytest.mark.parametrize("bad_bar", [None, [], {"date": []}, {"date": {}}, {"date": 20261027}, {"date": True}])
def test_arbitrary_json_bar_values_are_diagnostic_not_projection_exceptions(bad_bar):
    from market_session_admission import assess_daily_session_integrity
    result = assess_daily_session_integrity({"ticker": "2356.TW", "as_of": {}, "bars": [bad_bar]})
    assert result["status"] == "invalid" and not result["eligible"]
    assert "invalid_session_date" in result["reason_codes"]


@pytest.mark.parametrize("daily", [None, [], {}, {"ticker": "2356.TW", "bars": None}])
def test_absent_daily_or_bars_remains_unverifiable(daily):
    from market_session_admission import assess_daily_session_integrity
    result = assess_daily_session_integrity(daily)
    assert result["status"] == "unverifiable" and not result["eligible"]


def test_malformed_quarantine_date_does_not_hide_unresolved_gap():
    from market_session_admission import assess_daily_session_integrity
    daily = _daily("2026-10-27")
    daily["quarantined_session_rows"] = [{"date": {}, "state": "unknown"}]
    result = assess_daily_session_integrity(daily)
    assert not result["eligible"] and "invalid_session_date" in result["reason_codes"]


@pytest.mark.parametrize("bad_entry", [{"state": []}, {"state": "open", "source_url": {}},
                                       {"state": "open", "source_url": "https://www.twse.com.tw/fixture", "exchanges": None}])
def test_malformed_exception_metadata_is_unknown_not_a_calendar_failure(bad_entry):
    from market_calendar_store import load_market_calendar, session_day_status
    calendar = load_market_calendar("tw", 2026)
    calendar["session_exceptions"] = {"2026-10-22": bad_entry}
    assert session_day_status("2026-10-22", calendar=calendar)["state"] == "unknown"
