"""Keep the 5314 live failures reproducible without contacting a provider."""

import json

import pytest

from final_audit_mode_contracts import v3_short_setup_contract_issues
from structured_output_runtime import process_agent_response
from trade_execution_contract import contains_trade_order, evaluate_trade_execution
from trade_price_inputs import parse_price_range
from test_google_recommendation_decode import _payload


# Relevant raw fields from the 5314.TWO 2026-09-20 canary's fourth STOP response.
OBSERVATION_SETUP = {
    "entry_trigger": "等待右側破線信號：收盤價確認跌破前波起漲頸線 NT$26.00，且伴隨單日法人賣超逾 8,000 張時重新評估進場；目前處於等待條件階段，不立即建立空單。",
    "downside_target": "NT$20.50（對應回歸本益比河流圖中低檔約 18.7x 區間及 P/B 實質修正）",
    "cover_stop": "NT$35.00（若反彈突破近週震盪平台高點則嚴格回補停損）",
    "squeeze_risk": "極高。公司股本結構帶有彈性面額特徵，流通籌碼曾受政策紅利煽動出現連續漲停與數萬張買單鎖死，散戶情緒波動劇烈，融券若遭集中鎖定易引發軋空。",
    "thesis_invalidation": "若月營收持續創歷史新高突破 NT$6.0 億元、TTM自由現金流轉正且單季營業利益率維持在 35% 以上，或股價有效站穩 NT$46.80，空方泡沫論點即告失效。",
    "transaction_cost": None, "horizon_trading_days": None,
}
MISSING_ENTRY = "股價跌破月線且單日法人賣超逾 5,000 千股，伴隨單月營收年增率放緩至 50% 以下確認時"


def test_real_candidate_system_observation_template_passes_its_own_contract():
    payload = _payload("中性觀察")
    payload["short_setup"] = OBSERVATION_SETUP
    context = {"pipeline_id": "v3", "data": {}}
    process_agent_response(19, json.dumps(payload), context, model_id="gemini-3.8-flash")
    output = context["structured_outputs"][19]
    setup = output["short_setup"]
    assert output["recommendation"]["建議"] == "持有"
    assert setup["downside_target"] == setup["cover_stop"] == "N/A"
    assert not contains_trade_order(setup["entry_trigger"])
    assert v3_short_setup_contract_issues(setup, recommendation=output["recommendation"]) == []


def test_real_candidate_missing_entry_price_does_not_use_stock_count_as_price():
    result = evaluate_trade_execution(direction="Short", entry_zone=MISSING_ENTRY,
        target_price="NT$ 25.25（回歸河流圖 18.7x 本益比中線位置）",
        stop_loss="收盤價突破並站穩 NT$ 46.8（52 週歷史高點）")
    assert result["details"]["entry_range"] is None
    assert [issue["id"] for issue in result["issues"]] == ["invalid_entry_zone"]


@pytest.mark.parametrize("quantity", ["5,000千股", "5,000 張", "3萬張", "8,000股", "5 million shares", "50 lots", "3,000至5,000張", "3-5 thousand shares", "3萬至5萬股", "3 million to 5 million shares", "3百萬至5百萬股"])
def test_explicit_stock_quantities_are_never_prices(quantity):
    assert parse_price_range("法人賣超逾 " + quantity) is None
    assert parse_price_range("股價 NT$32-34 元，法人賣超逾 " + quantity) == (32, 34)


@pytest.mark.parametrize("order", ["等待跌破26元後建立空單", "目前不建立空方部位；跌破26元即做空", "等待訊號確認後進場"])
def test_genuine_deferred_trade_orders_stay_rejected_for_observation(order):
    assert contains_trade_order(order)
    assert v3_short_setup_contract_issues({**OBSERVATION_SETUP, "entry_trigger": order}, recommendation="持有")


def test_multi_branch_entry_and_ambiguous_stop_remain_rejected():
    entry = "股價反彈至阻力區間NT$32.0至NT$34.0且法人單日賣超擴大超過5,000張，或跌破NT$29.0技術支撐確立"
    stop = "NT$37.50（嚴格高於完整進場區間上緣NT$34.0約10.3%，防範跳空軋空）"
    assert parse_price_range(entry) is None
    assert parse_price_range(stop) is None


def test_actual_wrong_short_stop_still_fails_after_count_exclusion():
    result = evaluate_trade_execution(direction="Short", entry_zone="NT$32-34，法人賣超5,000張",
                                     target_price="25.25", stop_loss="33")
    assert [issue["id"] for issue in result["issues"]] == ["short_stop_not_outside_entry"]
