"""Per-security readiness must never borrow another exchange's closure evidence."""
from datetime import datetime
import json

import pytest
from test_candidate_source_market_identity import unverified_tpex_calendar


@pytest.mark.parametrize("moment,previous", [
    ("2026-10-23T18:00:00+08:00", "2026-10-22"),
    ("2026-07-10T18:00:00+08:00", "2026-07-09"),
])
def test_report_and_candidate_readiness_keep_unproven_tpex_session_unknown(moment, previous, unverified_tpex_calendar):
    from daily_candidate_review import evidence_context
    from reporting.content_credibility_observations import evaluate_observation_credibility
    moment = datetime.fromisoformat(moment)
    for ticker, aligned in (("1234.TWO", False), ("1234.TW", True)):
        data = {"ticker": ticker, "current_price": 60,
                "daily_market_data": {"as_of": previous, "source": "fixture", "bars": [
                    {"date": previous, "open": 60, "high": 60, "low": 60, "close": 60, "volume": 0}]},
                "institutional_trading": {"observation_dates": [previous]}}
        result = evaluate_observation_credibility({"candidate_evaluation_at": moment.isoformat()}, {}, data, "v4")
        readiness = result["checks"][0]["details"]
        assert readiness["latest_source_dates_aligned"] is aligned
        assert readiness["expected_completed_session"] == (previous if aligned else None)
        if not aligned:
            assert "v4_latest_completed_session_unconfirmed" in {x["id"] for x in result["warnings"]}
        item = {"ticker": ticker, "metrics": {"price_observation_date": previous, "flow_observation_date": previous}}
        assert evidence_context(item, moment=moment)["latest_source_dates_aligned"] is aligned


def test_snapshot_candidate_loader_preserves_tpex_unknown(tmp_path, unverified_tpex_calendar):
    from candidate_report_observations import load_candidate_report_observations
    filename = "1234_TWO_v4_report_job_fixture.html"
    value = {"data": {"ticker": "1234.TWO", "daily_market_data": {
        "as_of": "2026-10-22", "bars": [{"date": "2026-10-22", "close": 60, "volume": 0}]},
        "institutional_trading": {"observation_dates": ["2026-10-22"]}}}
    (tmp_path / filename.replace(".html", ".data.json")).write_text(json.dumps(value))
    results = load_candidate_report_observations([{"ticker": "1234.TWO"}],
        [{"ticker": "1234.TWO", "latest_report": {"filename": filename}}], str(tmp_path),
        moment=datetime.fromisoformat("2026-10-23T18:00:00+08:00"))
    assert results["1234.TWO"]["status"] == "available"
    assert results["1234.TWO"]["expected_completed_session"] is None
    assert not results["1234.TWO"]["latest_source_dates_aligned"]


def test_inner_yfinance_gate_uses_bound_exchange_before_source_admission(monkeypatch, unverified_tpex_calendar):
    import data_fetch.yfinance_cache_gate as gate
    import report_source_admission
    from market_price_reconciliation import CONTRACT
    monkeypatch.setattr(gate, "REQUIRED_DATA_SCHEMA_FIELDS", [])
    calls = []
    def admitted(*args):
        calls.append(args)
        return {"eligible": True}
    monkeypatch.setattr(report_source_admission, "institutional_admission", admitted)
    monkeypatch.setattr(report_source_admission, "price_admission", admitted)
    cached = {"ticker": "1234.TWO", "data_schema_version": gate.DATA_SCHEMA_VERSION,
        "daily_market_data": {"bars": [{"date": "2026-10-22"}], "as_of": "2026-10-22", "price_basis_contract": CONTRACT}}
    payload, stale, _ = gate.build_fresh_cache_payload("1234.TWO", cached,
        assess_cached=lambda *_: (True, {}), append_cache_audit=lambda *a, **k: None,
        now_epoch=datetime.fromisoformat("2026-10-23T18:00:00+08:00").timestamp())
    assert payload is None and stale == ["market_data"] and not calls


def test_missing_security_identity_does_not_default_to_twse_readiness():
    from two_week_market_eligibility import observation_readiness
    result = observation_readiness(price_date="2026-10-22", institutional_date="2026-10-22",
        moment=datetime.fromisoformat("2026-10-23T18:00:00+08:00"))
    assert result["expected_completed_session"] is None
    assert not result["latest_source_dates_aligned"]
