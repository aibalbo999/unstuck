from copy import deepcopy
import pytest
from reporting.content_credibility_observations import evaluate_observation_credibility
from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError


def data():
    return {"ticker": "2356.TW", "current_price": 87.9, "daily_market_data": {"as_of": "2026-10-01", "source": "test provider", "price_adjustment_basis": "provider adjusted", "bars": [{"date": "2026-10-01", "close": 87.9}]}, "institutional_trading": {"observation_dates": ["2026-10-01"]}}


def evaluate(value):
    return evaluate_observation_credibility({}, {"generated_at": "2026-10-01T13:30:00+00:00"}, value, "v4")


@pytest.mark.parametrize("failure", ["missing_source", "provider_error", "future", "stale", "wrong_bar_date", "invented_price"])
def test_bad_market_data_cannot_be_published(failure):
    value = data()
    if failure == "missing_source": value["daily_market_data"]["source"] = ""
    if failure == "provider_error": value["daily_market_data"] = {}
    if failure == "future": value["daily_market_data"]["as_of"] = "2026-10-02"
    if failure == "stale": value["daily_market_data"]["as_of"] = "2026-09-20"
    if failure == "wrong_bar_date": value["daily_market_data"]["bars"][0]["date"] = "2026-09-30"
    if failure == "invented_price": value["current_price"] = 602
    result = evaluate(value)
    assert result["blocking_issues"]
    with pytest.raises(ReportPublicationBlockedError):
        assert_report_publishable({"content_credibility": {"status": "blocked", **result}})


def test_aligned_data_passes_and_lagging_institution_is_downgraded():
    value = data()
    assert evaluate(value)["checks"][0]["status"] == "passed"
    value["institutional_trading"]["observation_dates"] = ["2026-09-30"]
    assert evaluate(value)["checks"][0]["status"] == "warning"
    assert not evaluate(value)["blocking_issues"]


def test_old_missing_adjustment_basis_is_not_rewritten_as_verified():
    value = data(); del value["daily_market_data"]["price_adjustment_basis"]
    assert evaluate(value)["checks"][0]["status"] == "warning"


def test_false_bullish_alignment_is_blocked():
    value = data(); value["technical_indicators"] = {"sma_5": 65.34, "sma_10": 64.85, "sma_20": 65.02}
    context = {"parsed": {"trade_setup": {"observed_signal": "5日、10日及20日均線呈多頭排列"}}}
    result = evaluate_observation_credibility(context, {"generated_at": "2026-10-01T13:30:00+00:00"}, value, "v4")
    assert any(x["id"] == "v4_bullish_sma_alignment_contradiction" for x in result["blocking_issues"])
    context["parsed"]["trade_setup"]["observed_signal"] = "5日、10日及20日均線尚未多頭排列"
    assert not evaluate_observation_credibility(context, {}, value, "v4")["blocking_issues"]


def test_future_institutional_record_is_not_observed_evidence():
    value = data(); value["institutional_trading"]["observation_dates"] = ["2026-10-02"]
    assert any(item["id"] == "v4_institutional_observation_future" for item in evaluate(value)["blocking_issues"])


def test_cash_flow_claim_is_downgraded_in_shared_report_focus():
    from reporting.mode_focus_context import build_mode_focus_context
    parsed = {"trade_setup": {"trade_direction": "Long", "financial_risk_flags": ["自由現金流為負，短線財務壓力升高"]}}
    rows = build_mode_focus_context({"data": data()}, parsed, pipeline_id="v4")["rows"]
    financial = next(row for row in rows if row["label"] == "財務風險")
    assert financial["value"].startswith("待查主張：")
    assert "不能視為已確認" in financial["value"]
