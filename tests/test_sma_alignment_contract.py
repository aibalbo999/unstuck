"""Check explicit SMA ordering at both model and report quality boundaries."""
import pytest

from report_publication_gate import ReportPublicationBlockedError, assert_report_publishable
from reporting.content_credibility_observations import evaluate_observation_credibility
from trade_catalyst_semantics import trade_semantic_issues


def model_issues(text, technical, field="observed_signal"):
    return trade_semantic_issues({field: text}, {"data": {"technical_indicators": technical}})


@pytest.mark.parametrize("field", ["observed_signal", "core_catalyst", "catalyst"])
@pytest.mark.parametrize("text", [
    "目前 SMA5 > SMA10 > SMA20，技術面偏多",
    "目前 sma 5 ＞ sma 10 ＞ sma 20",
    "目前5日均線 > 10日均線 > 20日均線",
    "目前 SMA5 > SMA10 > SMA20 不是盈利的保證",
    "目前 SMA5 > SMA10 > SMA20；等待量能回升後再重新評估",
    "等待量能回升，但目前 SMA5 > SMA10 > SMA20 後再重新評估",
])
def test_explicit_strict_order_is_checked_without_bullish_label(text, field):
    technical = {"sma_5": 144.8, "sma_10": 144.95, "sma_20": 142.55}
    assert "bullish_sma_alignment_contradiction" in model_issues(text, technical, field)
    technical["sma_5"] = 145.8
    assert "bullish_sma_alignment_contradiction" not in model_issues(text, technical, field)


@pytest.mark.parametrize("technical", [
    {"sma_5": 3, "sma_10": 2, "sma_20": True},
    {"sma_5": 3, "sma_10": True, "sma_20": .5},
    {"sma_5": True, "sma_10": .5, "sma_20": .25},
])
def test_boolean_is_missing_evidence_even_when_float_conversion_is_ordered(technical):
    text = "5日、10日及20日均線呈多頭排列"
    assert "bullish_sma_alignment_unverified" in model_issues(text, technical)


@pytest.mark.parametrize("value", [None, "N/A", float("nan"), float("inf"), 0, -1, 10 ** 400])
def test_explicit_order_requires_three_finite_positive_values(value):
    technical = {"sma_5": 3, "sma_10": 2, "sma_20": value}
    assert "bullish_sma_alignment_unverified" in model_issues("目前 SMA5 > SMA10 > SMA20", technical)


@pytest.mark.parametrize("text", [
    "等待短期均線形成 SMA5 > SMA10 > SMA20 後再重新評估",
    "SMA5 > SMA10 > SMA20 尚未成立",
    "尚未形成 SMA5 > SMA10 > SMA20",
    "目前 SMA50 > SMA100 > SMA200",
    "15日、110日及120日均線呈多頭排列",
])
def test_future_negative_and_other_periods_are_not_asserted_5_10_20_order(text):
    assert not model_issues(text, {})


@pytest.mark.parametrize("text, technical, reason", [
    ("目前 SMA5 > SMA10 > SMA20", {"sma_5": 65.34, "sma_10": 64.85, "sma_20": 65.02},
     "v4_bullish_sma_alignment_contradiction"),
    ("5日、10日及20日均線呈多頭排列", {"sma_5": 3, "sma_10": 2, "sma_20": True},
     "v4_bullish_sma_alignment_unverified"),
])
def test_report_observation_gate_blocks_publication_for_same_defect(text, technical, reason):
    data = {"current_price": 87.9, "technical_indicators": technical,
            "daily_market_data": {"as_of": "2026-10-01", "source": "fixture",
                                  "price_adjustment_basis": "provider adjusted",
                                  "bars": [{"date": "2026-10-01", "close": 87.9}]},
            "institutional_trading": {"observation_dates": ["2026-10-01"]}}
    context = {"parsed": {"trade_setup": {"observed_signal": text}}}
    result = evaluate_observation_credibility(context, {"generated_at": "2026-10-01T13:30:00+00:00"}, data, "v4")
    assert reason in {issue["id"] for issue in result["blocking_issues"]}
    assert result["checks"][0]["status"] == "blocked"
    with pytest.raises(ReportPublicationBlockedError):
        assert_report_publishable({"content_credibility": {"status": "blocked", **result}})
