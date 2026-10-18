import pytest
import json
from pathlib import Path
from reporting.content_credibility_trade_basis import evaluate_trade_basis
from trade_financial_risk import NEGATIVE_FCF_WARNING


def evaluate(setup, data=None):
    return evaluate_trade_basis({"parsed": {"trade_setup": setup}}, data or {}, "v4")


@pytest.mark.parametrize("raw", [42_195_222_528, 0, None])
def test_cached_negative_flag_without_negative_input_blocks(raw):
    assert evaluate({"financial_risk_flags": [NEGATIVE_FCF_WARNING]}, {"free_cash_flow_raw": raw})["blocking_issues"][0]["id"] == "v4_fcf_flag_without_negative_input"


def test_unverified_cash_flow_cannot_be_bullish_reason():
    assert evaluate({"core_catalyst": "FCF轉正支持兩週上漲"}, {"free_cash_flow_raw": 42e9})["blocking_issues"]


@pytest.mark.parametrize("text", ["AI訂單支持兩週上漲", "已漲價", "年底出貨催化", "已完成收購"])
def test_material_news_cannot_borrow_technical_reference(text):
    result = evaluate({"core_catalyst": text, "catalyst_source_refs": ["short_term_market_context.technical_indicators.sma_5"]})
    assert any(issue["id"] == "v4_material_news_without_source" for issue in result["blocking_issues"])


def test_publication_date_is_not_a_scheduled_event():
    assert evaluate({"event_catalyst": {"description": "新聞刊出", "date": "2026-10-02", "status": "scheduled", "source_refs": ["short_term_market_context.recent_news.items[0]"]}})["blocking_issues"]


def test_neutral_wait_does_not_require_invented_event():
    assert not evaluate({"trade_direction": "Neutral", "core_catalyst": "等待技術及法人確認", "event_catalyst": None})["blocking_issues"]


def _saved_institutional_catalog(monkeypatch):
    fixture = json.loads((Path(__file__).parent / "fixtures/trade_catalyst_6488_20260925.json").read_text())
    catalog = fixture["context"]["_trade_source_manifest"]["catalog"]
    monkeypatch.setattr("reporting.content_credibility_trade_basis.source_catalog", lambda _data: catalog)
    return fixture["payload"]["catalyst_source_refs"]


def test_sourced_neutral_future_recheck_is_not_an_observed_institutional_claim(monkeypatch):
    refs = _saved_institutional_catalog(monkeypatch)
    result = evaluate({
        "trade_direction": "Neutral",
        "core_catalyst": "等待法人賣壓減緩後再重新評估",
        "catalyst_source_refs": refs,
        "event_catalyst": None,
    })
    assert not result["blocking_issues"]


def test_asserted_institutional_claim_before_future_recheck_still_blocks(monkeypatch):
    refs = _saved_institutional_catalog(monkeypatch)
    result = evaluate({
        "trade_direction": "Neutral",
        "core_catalyst": "外資已買超9999千股；等待法人賣壓減緩後再重新評估",
        "catalyst_source_refs": refs,
    })
    assert any(issue["id"] == "v4_trade_reason_scope_mismatch" for issue in result["blocking_issues"])


def test_observed_signal_is_checked_even_when_core_is_pure_future(monkeypatch):
    refs = _saved_institutional_catalog(monkeypatch)
    result = evaluate({
        "trade_direction": "Neutral",
        "core_catalyst": "等待法人賣壓減緩後再重新評估",
        "catalyst_source_refs": refs,
        "observed_signal": "外資已買超9999千股",
        "observed_source_refs": refs,
    })
    assert any(issue["id"] == "v4_trade_reason_scope_mismatch" for issue in result["blocking_issues"])


def test_future_lead_does_not_hide_later_unsourced_news():
    result = evaluate({"trade_direction": "Neutral", "core_catalyst": "等待法人賣壓減緩；AI新增訂單"})
    assert any(issue["id"] == "v4_material_news_without_source" for issue in result["blocking_issues"])


def test_unknown_event_cannot_launder_a_material_news_assertion():
    result = evaluate({"core_catalyst": "AI新增訂單", "event_catalyst": {"status": "unknown", "date": None, "description": None, "source_refs": []}})
    assert any(item["id"] == "v4_material_news_without_source" for item in result["blocking_issues"])
