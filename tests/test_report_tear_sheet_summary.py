import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.sections import build_tear_sheet_summary as section_summary  # noqa: E402
from reporting.tear_sheet_summary import build_tear_sheet_summary  # noqa: E402


def test_tear_sheet_summary_keeps_sections_import_compatibility():
    context = {
        "pipeline_id": "v1",
        "tear_sheet_summary": "模型摘要：資料已交叉驗證，風險以估值回落為主。",
        "data": {},
        "parsed": {},
    }

    assert section_summary is build_tear_sheet_summary
    assert build_tear_sheet_summary(context) == "模型摘要：資料已交叉驗證，風險以估值回落為主。"


def test_tear_sheet_summary_drops_string_empty_model_summary_tokens():
    context = {
        "pipeline_id": "v1",
        "tear_sheet_summary": "NaN",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "industry": "半導體",
        },
        "parsed": {
            "recommendation": {"建議": "持有", "信心": "6/10", "12個月": "NT$120"},
            "price_targets": {},
        },
    }

    summary = build_tear_sheet_summary(context)

    assert summary.startswith("一頁式摘要：2330.TW 台積電")
    assert "NaN" not in summary


def test_tear_sheet_summary_builds_event_swing_trade_summary():
    context = {
        "pipeline_id": "v4",
        "data": {"ticker": "2330.TW", "company_name": "台積電"},
        "parsed": {
            "trade_setup": {
                "trade_direction": "Long",
                "entry_zone": "NT$900-920",
                "target_price": "NT$960",
                "stop_loss": "NT$880",
                "core_catalyst": "法說會上修展望",
                "risk_level": "Medium",
            }
        },
    }

    summary = build_tear_sheet_summary(context)

    assert summary.startswith("事件波段摘要：2330.TW 台積電")
    assert "1-2 週交易方向為「Long」" in summary
    assert "進場區間 NT$900-920" in summary
    assert "核心催化劑為「法說會上修展望」" in summary
    assert "短期波動風險為 Medium" in summary


def test_tear_sheet_summary_extracts_contrarian_risk_triggers():
    context = {
        "pipeline_id": "v3",
        "data": {"ticker": "9999.TW", "company_name": "測試股"},
        "parsed": {
            "recommendation": {
                "建議": "放空",
                "信心": "8/10",
                "3個月": "NT$70",
                "6個月": "NT$60",
            }
        },
        "analyses": {
            19: "## 做空觸發條件\n- 估值敘事破裂。後續文字不應進入摘要。\n## 防軋空停損點\n- 股價突破前高；需要回補。",
        },
    }

    summary = build_tear_sheet_summary(context)

    assert summary.startswith("逆勢風險摘要：9999.TW 測試股")
    assert "空方判斷為「放空」" in summary
    assert "短期壓力參考 NT$70" in summary
    assert "做空觸發為「估值敘事破裂」" in summary
    assert "防軋空或 thesis invalidation 條件為「股價突破前高」" in summary


def test_tear_sheet_summary_uses_fallbacks_for_decimal_non_finite_data_fields():
    context = {
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "industry": Decimal("NaN"),
            "recent_catalysts": [{"title": Decimal("NaN")}],
            "institutional_trading": {
                "trend": Decimal("Infinity"),
                "total_net_buy_thousand_shares": Decimal("-Infinity"),
            },
            "pe_river_chart": {"source": Decimal("NaN")},
        },
        "parsed": {
            "recommendation": {"建議": "持有", "信心": "6/10", "12個月": "NT$120"},
            "price_targets": {},
        },
    }

    summary = build_tear_sheet_summary(context)

    assert "基本面重點在於 N/A 景氣" in summary
    assert "近 30 日關鍵催化劑為「近期催化劑資料不足」" in summary
    assert "三大法人趨勢為 N/A" in summary
    assert "累計買賣超約 N/A 張" in summary
    assert "來源：N/A" in summary
    assert "nan" not in summary.lower()
    assert "infinity" not in summary.lower()


def test_target_price_text_formats_string_prices_and_rejects_non_finite_tokens():
    from reporting.structured_intro import target_price_text

    assert target_price_text("100") == "NT$100"
    assert target_price_text("NT$320") == "NT$320"
    assert target_price_text("1e3") == "NT$1,000"
    assert target_price_text("NaN") == "N/A"
    assert target_price_text("Infinity") == "N/A"
