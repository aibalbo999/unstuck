"""Execution checks must validate the intended entry, not a convenient spot price."""

import pytest

from final_audit_mode_contracts import (
    v2_position_plan_contract_issues,
    v3_short_setup_contract_issues,
    v4_trade_setup_contract_issues,
)
from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment


def position(**updates):
    return {
        "action": "進場", "entry_zone": "100", "position_size": "25%",
        "stop_loss": "90", "risk_reward": "2:1", "target_price": "120",
        "invalidation_condition": "下次營收公布後檢查是否轉為衰退", **updates,
    }


def short(**updates):
    return {
        "entry_trigger": "跌破 100", "downside_target": "80", "cover_stop": "110",
        "squeeze_risk": "借券回補可能推高股價",
        "thesis_invalidation": "下次法說若上修毛利率則重新評估", **updates,
    }


def swing(**updates):
    return {
        "trade_direction": "Long", "entry_zone": "100", "target_price": "120",
        "stop_loss": "90", "support_level": "90", "resistance_level": "120",
        "core_catalyst": "下週法說後重新檢查營收指引", "risk_level": "Medium", **updates,
    }


def test_b_rejects_stop_above_entry_and_overallocated_position():
    issues = v2_position_plan_contract_issues(position(stop_loss="120", position_size="150%"))
    assert any("stop_loss" in issue for issue in issues)
    assert any("position_size" in issue for issue in issues)


def test_c_rejects_short_target_above_entry_and_cover_stop_below_entry():
    issues = v3_short_setup_contract_issues(short(downside_target="120", cover_stop="90"))
    assert any("target" in issue for issue in issues)
    assert any("stop" in issue for issue in issues)


def test_d_rejects_target_below_entry_even_when_above_spot():
    setup = swing(entry_zone="115-116", target_price="110", stop_loss="95")
    assert v4_trade_setup_contract_issues(setup)
    result = evaluate_trade_setup_alignment(trade_setup=setup, current_price=100)
    assert result["blocking_issues"]


def test_d_accepts_pending_breakout_with_stop_above_current_spot():
    setup = swing(entry_zone="110-112", target_price="125", stop_loss="105")
    assert v4_trade_setup_contract_issues(setup) == []
    result = evaluate_trade_setup_alignment(trade_setup=setup, current_price=100)
    assert result["blocking_issues"] == []
    details = result["checks"][0]["details"]
    assert details["entry_range"] == [110.0, 112.0]
    assert details["worst_case_risk_reward"] == pytest.approx(13 / 7)
    assert details["transaction_cost"] is None


def test_b_wait_with_zero_position_and_recheck_condition_needs_no_prices():
    assert v2_position_plan_contract_issues(position(
        action="等待", position_size="0%", entry_zone=None, target_price=None,
        stop_loss=None, risk_reward=None,
    )) == []


@pytest.mark.parametrize("size", ["資料不足", "25%", None, "0-10%"])
def test_b_wait_does_not_invent_zero_position(size):
    assert v2_position_plan_contract_issues(position(action="等待", position_size=size))


def test_b_wait_requires_real_recheck_reason():
    assert v2_position_plan_contract_issues(position(
        action="等待", position_size="0%", invalidation_condition="資料不足",
    ))


def test_d_neutral_explicit_wait_accepts_nullable_prices():
    setup = swing(
        trade_direction="Neutral", entry_zone="暫不進場，等待法說公布營收指引",
        target_price=None, stop_loss=None, support_level=None, resistance_level=None,
    )
    assert v4_trade_setup_contract_issues(setup) == []
    result = evaluate_trade_setup_alignment(trade_setup=setup, current_price=None)
    assert result["blocking_issues"] == result["warnings"] == []
    assert result["checks"][0]["status"] == "passed"


@pytest.mark.parametrize("field", ["entry_zone", "core_catalyst"])
def test_d_neutral_requires_wait_and_recheck_explanation(field):
    setup = swing(trade_direction="Neutral", entry_zone="等待法說後重新檢查", target_price=None, stop_loss=None)
    setup[field] = "資料不足"
    assert v4_trade_setup_contract_issues(setup)


@pytest.mark.parametrize("field", ["entry_zone", "target_price", "stop_loss"])
@pytest.mark.parametrize("value", [None, "資料不足", "2026-09-05", "PE 20倍", "10%"])
def test_active_d_cannot_use_non_price_tokens(field, value):
    assert v4_trade_setup_contract_issues(swing(**{field: value}))


@pytest.mark.parametrize("field", ["entry_zone", "target_price", "stop_loss"])
def test_active_d_rejects_ambiguous_or_nonpositive_price_ranges(field):
    for value in ("100 或 120", "0-100", "-10", "NaN 或 100", "100-110 或 120"):
        assert v4_trade_setup_contract_issues(swing(**{field: value}))


@pytest.mark.parametrize("action", ["進場", "續抱", "減碼"])
def test_active_b_requires_positive_position_and_valid_long_stop(action):
    assert v2_position_plan_contract_issues(position(action=action, position_size="0%"))
    assert v2_position_plan_contract_issues(position(action=action, stop_loss="120"))


def test_b_rejects_claimed_ratio_that_does_not_match_prices():
    assert v2_position_plan_contract_issues(position(risk_reward="4:1"))


def test_b_keeps_unavailable_target_explicit_instead_of_inventing_one():
    assert v2_position_plan_contract_issues(position(target_price=None)) == []


def test_d_all_entry_and_target_range_endpoints_must_be_consistent():
    assert v4_trade_setup_contract_issues(swing(entry_zone="100-110", target_price="105-120"))
    assert v4_trade_setup_contract_issues(swing(entry_zone="100-110", stop_loss="95-105"))
    assert v4_trade_setup_contract_issues(swing(trade_direction="Short", entry_zone="100-110", target_price="90-105", stop_loss="120"))


@pytest.mark.parametrize("recommendation", ["避免", "持有", "買入"])
def test_c_non_short_recommendation_needs_no_short_target_or_cover_stop(recommendation):
    assert v3_short_setup_contract_issues(short(
        entry_trigger="暫不放空，等待下次財報驗證應收帳款", downside_target=None, cover_stop=None,
    ), recommendation={"建議": recommendation}) == []


def test_c_active_short_still_requires_prices():
    assert v3_short_setup_contract_issues(short(downside_target=None, cover_stop=None), recommendation="放空")


def test_c_mode_execution_uses_actual_recommendation():
    from final_audit_mode_contracts import mode_execution_contract_issues

    result = mode_execution_contract_issues({
        "recommendation": {"建議": "避免"},
        "short_setup": short(entry_trigger="等待下次財報", downside_target=None, cover_stop=None),
    }, position_plan_agent=None, short_setup_agent=19, trade_setup_agent=None)
    assert result == []


def test_neutral_d_cannot_turn_fallback_strings_into_verified_no_trade():
    assert v4_trade_setup_contract_issues(swing(
        trade_direction="Neutral", entry_zone="等待突破確認", core_catalyst="等待近期事件",
        target_price=None, stop_loss=None,
    ))


def test_explicit_prices_ignore_dates_periods_percentages_and_multiples():
    from trade_price_inputs import parse_price_range

    assert parse_price_range("2026-09-05 確認後進場 NT$100-110，部位 20%，PE 25倍") == (100, 110)
    assert parse_price_range("8/18 後 1-2 週內在 NT$100 至 NT$110 進場") == (100, 110)
    assert parse_price_range("2026年9月5日") is None


def test_execution_preserves_unknown_target_and_cost_in_diagnostics():
    from trade_execution_contract import evaluate_trade_execution

    result = evaluate_trade_execution(direction="Long", entry_zone="100", target_price=None,
                                      stop_loss="90", risk_reward="2:1", require_target=False)
    assert result["issues"] == []
    assert result["details"]["risk_reward_status"] == "unverifiable"
    assert result["details"]["worst_case_risk_reward"] is None
    assert result["details"]["transaction_cost"] is None


def test_execution_recomputes_worst_endpoint_ratio_after_explicit_cost():
    from trade_execution_contract import evaluate_trade_execution

    result = evaluate_trade_execution(direction="Long", entry_zone="100-110", target_price="130-140",
                                      stop_loss="90-95", transaction_cost=2, risk_reward="0.818:1")
    assert result["issues"] == []
    assert result["details"]["worst_case_risk_reward"] == 1
    assert result["details"]["net_risk_reward"] == pytest.approx(18 / 22)


@pytest.mark.parametrize("cost", [-1, float("nan"), float("inf"), "2%", "-2元"])
def test_execution_rejects_invalid_cost_instead_of_assuming_free_trading(cost):
    assert v4_trade_setup_contract_issues(swing(transaction_cost=cost))


def test_cost_must_not_consume_expected_reward():
    assert v4_trade_setup_contract_issues(swing(transaction_cost=21))


def test_zero_cost_is_explicitly_distinct_from_unknown_cost():
    from trade_execution_contract import evaluate_trade_execution

    result = evaluate_trade_execution(direction="Long", entry_zone="100", target_price="120",
                                      stop_loss="90", transaction_cost=0)
    assert result["issues"] == []
    assert result["details"]["transaction_cost"] == 0
    assert result["details"]["net_risk_reward"] == 2


@pytest.mark.parametrize("value", ["-10-20", "NT$-10 至 20", "-10元-20元", "-10 至 -5"])
def test_price_range_does_not_hide_negative_first_endpoint(value):
    from trade_price_inputs import parse_price_range

    assert parse_price_range(value) is None


def test_cost_string_zero_keeps_explicit_units():
    from trade_execution_contract import evaluate_trade_execution

    result = evaluate_trade_execution(direction="Long", entry_zone="100", target_price="120",
                                      stop_loss="90", transaction_cost="0元")
    assert result["issues"] == []
    assert result["details"]["transaction_cost"] == 0


def test_short_worst_entry_ratio_uses_lower_entry_and_upper_target_stop():
    from trade_execution_contract import evaluate_trade_execution

    result = evaluate_trade_execution(direction="Short", entry_zone="100-110", target_price="70-80", stop_loss="120-125")
    assert result["issues"] == []
    assert result["details"]["worst_case_risk_reward"] == pytest.approx(20 / 25)


def test_b_native_schema_preserves_same_plan_target_and_explicit_zero_cost():
    from structured_output_recommendation_outputs import PositionPlan

    result = PositionPlan.model_validate(position(target_price=120, transaction_cost=0)).model_dump()
    assert result["target_price"] == "120"
    assert result["transaction_cost"] == "0"


def test_b_native_schema_keeps_absent_target_and_cost_null():
    from structured_output_recommendation_outputs import PositionPlan

    plan = position()
    plan.pop("target_price")
    result = PositionPlan.model_validate(plan).model_dump()
    assert result["target_price"] is None
    assert result["transaction_cost"] is None


def test_b_optional_fields_survive_all_normalization_passes():
    from structured_output_normalizer import normalize_structured_output

    payload = {
        "recommendation": {"建議": "買入", "短期目標（3個月）": "150", "中期目標（6個月）": "160",
                           "長期目標（12個月）": "180", "長期潛力（5年）": "200", "信心指數": "7/10"},
        "position_plan": position(target_price=120, transaction_cost=0),
        "reasoning_steps": ["進場有價格依據", "停損在進場下方", "目標與持倉期間一致"],
        "analysis_markdown": "有明確條件才進場。",
    }
    normalized = normalize_structured_output(16, payload)
    twice = normalize_structured_output(16, normalized)
    assert twice["position_plan"]["target_price"] == "120"
    assert twice["position_plan"]["transaction_cost"] == "0"
    assert v2_position_plan_contract_issues(twice["position_plan"]) == []


def test_b_normalization_does_not_copy_recommendation_target_into_trade_plan():
    from structured_output_normalizer_payloads import _coerce_position_plan_payload

    plan = position()
    plan.pop("target_price")
    result = _coerce_position_plan_payload(plan)
    assert result["target_price"] is None
    assert result["transaction_cost"] is None


def test_b_provider_schema_describes_optional_target_horizon_and_cost_units():
    from structured_output_recommendation_outputs import PositionPlan

    properties = PositionPlan.model_json_schema()["properties"]
    assert "同一" in properties["target_price"]["description"]
    assert "每股" in properties["transaction_cost"]["description"]
    assert {"type": "null"} in properties["target_price"]["anyOf"]


def test_no_trade_recheck_reason_can_honestly_state_missing_data():
    assert v2_position_plan_contract_issues(position(
        action="等待", position_size="0%", entry_zone=None, stop_loss=None, risk_reward=None,
        invalidation_condition="資料不足，待下次財報確認營收與毛利率後重新評估",
    )) == []
    setup = swing(
        trade_direction="Neutral", entry_zone="資料不足，暫不進場，等待法說",
        core_catalyst="資料不足，法說後重新確認營收指引", target_price=None, stop_loss=None,
    )
    assert v4_trade_setup_contract_issues(setup) == []
    assert evaluate_trade_setup_alignment(trade_setup=setup, current_price=None)["warnings"] == []


@pytest.mark.parametrize("target,cost,expected_target,expected_cost", [(120, 0, "120", "0"), (None, None, "未驗證", "未估計")])
def test_b_text_and_html_focus_show_the_actual_execution_target_and_cost(target, cost, expected_target, expected_cost):
    from structured_output_report_text import structured_output_to_report_text
    from reporting.mode_focus_context import build_mode_focus_context

    plan = position(target_price=target, transaction_cost=cost)
    text = structured_output_to_report_text(16, {"position_plan": plan, "recommendation": {}, "analysis_markdown": "條件確認後進場"})
    rows = build_mode_focus_context({}, {"position_plan": plan}, pipeline_id="v2")["rows"]
    values = {row["label"]: row["value"] for row in rows}
    assert f"同期間目標：{expected_target}" in text
    assert f"每股來回成本：{expected_cost}" in text
    assert values["同期間目標"] == expected_target
    assert values["每股來回成本"] == expected_cost


def test_c_observation_can_disclose_unknown_borrow_availability():
    assert v3_short_setup_contract_issues(short(
        entry_trigger="暫不放空，等待財報與借券確認", downside_target=None, cover_stop=None,
        squeeze_risk="借券資料不足",
    ), recommendation="避免") == []


def test_d_neutral_can_put_waiting_and_recheck_in_catalyst_with_no_entry_price():
    setup = swing(trade_direction="Neutral", entry_zone="N/A", target_price=None, stop_loss=None,
                  core_catalyst="等待財報後重新評估營收指引，暫不交易")
    assert v4_trade_setup_contract_issues(setup) == []
    result = evaluate_trade_setup_alignment(trade_setup=setup, current_price=None)
    assert result["warnings"] == result["blocking_issues"] == []


@pytest.mark.parametrize("entry", ["跌破 100 立即建立空單", "等待跌破 100 後立即建立空單"])
def test_c_non_short_label_does_not_hide_active_short_instructions(entry):
    assert v3_short_setup_contract_issues(short(entry_trigger=entry, downside_target=None, cover_stop=None), recommendation="避免")


@pytest.mark.parametrize("cost", [0, 21, None])
def test_c_and_d_native_schemas_preserve_explicit_execution_cost(cost):
    from structured_output_recommendation_outputs import ShortSetup
    from structured_output_risk_models import SwingTradeSetup

    expected = None if cost is None else str(cost)
    assert ShortSetup.model_validate(short(transaction_cost=cost)).model_dump().get("transaction_cost", "missing") == expected
    assert SwingTradeSetup.model_validate(swing(transaction_cost=cost)).model_dump().get("transaction_cost", "missing") == expected


def test_d_cost_survives_normalization_and_parser_and_blocks_unprofitable_trade():
    from structured_output_normalizer import normalize_structured_output
    from structured_output_parser import parse_structured_data

    normalized = normalize_structured_output(24, swing(transaction_cost=21))
    parsed = parse_structured_data({"pipeline_id": "v4", "structured_outputs": {24: normalized}, "analyses": {}})
    assert parsed["trade_setup"].get("transaction_cost") == "21"
    assert v4_trade_setup_contract_issues(parsed["trade_setup"])


def test_c_cost_survives_coercion_and_blocks_unprofitable_short():
    from structured_output_normalizer_payloads import _coerce_short_setup_payload
    from structured_output_recommendation_outputs import ShortSetup

    payload = _coerce_short_setup_payload(short(transaction_cost=21))
    normalized = ShortSetup.model_validate(payload).model_dump()
    twice = _coerce_short_setup_payload(normalized)
    assert twice.get("transaction_cost") == "21"
    assert v3_short_setup_contract_issues(twice, recommendation="放空")


@pytest.mark.parametrize("days", [1, 10, 252, None])
def test_b_c_keep_explicit_trading_horizon_through_native_and_coercion(days):
    from structured_output_recommendation_outputs import PositionPlan, ShortSetup
    from structured_output_normalizer_payloads import _coerce_position_plan_payload, _coerce_short_setup_payload

    for schema, coercer, fixture in ((PositionPlan, _coerce_position_plan_payload, position), (ShortSetup, _coerce_short_setup_payload, short)):
        value = schema.model_validate(fixture(horizon_trading_days=days)).model_dump()
        assert value.get("horizon_trading_days", "missing") == days
        assert coercer(value).get("horizon_trading_days", "missing") == days


@pytest.mark.parametrize("days", [True, False, 0, -1, 253, 1.5, "10"])
def test_b_c_native_horizon_rejects_non_integer_or_out_of_range_values(days):
    from pydantic import ValidationError
    from structured_output_recommendation_outputs import PositionPlan, ShortSetup

    for schema, fixture in ((PositionPlan, position), (ShortSetup, short)):
        with pytest.raises(ValidationError):
            schema.model_validate(fixture(horizon_trading_days=days))
