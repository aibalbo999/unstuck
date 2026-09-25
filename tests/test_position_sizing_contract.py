"""Position percentages need external inputs and a deterministic loss budget."""

from copy import deepcopy

import pytest

from final_audit_mode_contracts import v2_position_plan_contract_issues
from position_sizing import (
    build_position_sizing_context,
    calculate_position_sizing,
    position_sizing_contract_issues,
)


def supplied(**updates):
    return {
        "capital_amount": 100_000, "risk_budget_amount": 1_000,
        "currency": "TWD", "scenario_type": "research",
        "position_state": "no_position", "existing_position_percent": 0,
        **updates,
    }


def context(**updates):
    return build_position_sizing_context(
        supplied(**updates), source_ref="research-request:case-1", quote_currency="TWD",
    )


def plan(**updates):
    return {
        "action": "進場", "entry_zone": "100", "stop_loss": "90",
        "target_price": "120", "transaction_cost": "0", "horizon_trading_days": 20,
        "risk_reward": "2:1", "position_size": "100%",
        "invalidation_condition": "下次營收公布後重新評估", **updates,
    }


def audited_plan(value, ctx):
    receipt = calculate_position_sizing(value, ctx)
    assert receipt["status"] == "calculated"
    return {
        **value, "position_size": f"{receipt['position_percent']:g}%",
        "planning_context": receipt["scenario_type"], "sizing_evidence": receipt,
    }


def test_arbitrary_full_position_is_rejected_without_external_basis():
    assert any("sizing" in issue for issue in v2_position_plan_contract_issues(plan()))


def test_valid_explicit_budget_calculates_ten_percent_not_model_full_position():
    result = audited_plan(plan(), context())
    assert result["position_size"] == "10%"
    assert result["planning_context"] == "research"
    assert result["sizing_evidence"]["capital_amount"] == 100_000
    assert result["sizing_evidence"]["risk_budget_amount"] == 1_000
    assert result["sizing_evidence"]["source_ref"] == "research-request:case-1"
    assert position_sizing_contract_issues(result, context()) == []
    assert v2_position_plan_contract_issues(result, sizing_context=context()) == []


def test_cost_and_worst_price_endpoints_limit_the_calculated_position():
    result = calculate_position_sizing(plan(entry_zone="100-110", stop_loss="85-90", transaction_cost="5"), context())
    assert result["risk_per_share"] == 30
    assert result["position_percent"] == pytest.approx(3.666666)


@pytest.mark.parametrize("field", ["capital_amount", "risk_budget_amount"])
@pytest.mark.parametrize("invalid", [None, True, False, -1, 0, float("nan"), float("inf"), "1000"])
def test_missing_negative_nonfinite_boolean_and_text_input_never_becomes_budget(field, invalid):
    ctx = context(**{field: invalid})
    assert ctx["status"] == "unavailable"
    assert calculate_position_sizing(plan(), ctx)["status"] == "unassessed"


@pytest.mark.parametrize("updates", [
    {"risk_budget_amount": 100_001}, {"position_state": "unknown"},
    {"position_state": "holding", "existing_position_percent": None},
    {"position_state": "holding", "existing_position_percent": 0},
    {"existing_position_percent": 10}, {"scenario_type": "inferred"},
    {"currency": "USD"},
])
def test_unverifiable_or_inconsistent_context_is_unavailable(updates):
    assert context(**updates)["status"] == "unavailable"


def test_source_identity_and_quote_currency_must_be_supplied_externally():
    assert build_position_sizing_context(supplied(), quote_currency="TWD")["status"] == "unavailable"
    assert build_position_sizing_context(supplied(), source_ref="request:1")["status"] == "unavailable"


def test_model_supplied_financial_inputs_cannot_authorize_a_position():
    fabricated = audited_plan(plan(), context())
    fabricated["sizing_context"] = context()
    before = deepcopy(fabricated)
    assert position_sizing_contract_issues(fabricated)
    assert fabricated == before
    result = calculate_position_sizing(fabricated)
    assert result["status"] == "unassessed"
    assert "實際持倉" in result["reason"]


def test_missing_budget_does_not_rewrite_unsupported_trade_into_passing_wait():
    original = plan()
    copied = deepcopy(original)
    receipt = calculate_position_sizing(original)
    assert receipt["status"] == "unassessed"
    assert original == copied
    assert v2_position_plan_contract_issues(original)


@pytest.mark.parametrize("action", ["續抱", "減碼"])
def test_hold_or_reduce_cannot_infer_existing_position(action):
    receipt = calculate_position_sizing(plan(action=action), context())
    assert receipt["status"] == "unassessed"


def test_holding_scenario_is_named_and_reduce_targets_budget_limited_exposure():
    ctx = context(position_state="holding", existing_position_percent=25)
    result = audited_plan(plan(action="減碼"), ctx)
    assert result["action"] == "減碼"
    assert result["planning_context"] == "research"
    assert result["position_size"] == "10%"
    assert result["sizing_evidence"]["position_state"] == "holding"
    assert result["sizing_evidence"]["existing_position_percent"] == 25


def test_hold_preserves_supplied_exposure_and_does_not_invent_addition():
    ctx = context(position_state="holding", existing_position_percent=5, scenario_type="actual")
    result = audited_plan(plan(action="續抱"), ctx)
    assert result["position_size"] == "5%"
    assert result["planning_context"] == "actual"
    assert calculate_position_sizing(plan(action="減碼"), ctx)["status"] == "unassessed"


@pytest.mark.parametrize("updates", [
    {"transaction_cost": None}, {"transaction_cost": True}, {"transaction_cost": "1%"},
    {"horizon_trading_days": None}, {"horizon_trading_days": True},
    {"stop_loss": "110"}, {"entry_zone": "NaN"},
])
def test_unknown_or_invalid_execution_inputs_cannot_generate_numeric_position(updates):
    assert calculate_position_sizing(plan(**updates), context())["status"] == "unassessed"


def test_validator_recomputes_and_rejects_forged_context_or_calculation_receipt():
    ctx = context()
    valid = audited_plan(plan(), ctx)
    for field, value in (("position_percent", 100), ("capital_amount", 1), ("source_ref", "invented"), ("context_sha256", "fake")):
        forged = deepcopy(valid)
        forged["sizing_evidence"][field] = value
        assert position_sizing_contract_issues(forged, ctx)
    forged_context = deepcopy(ctx)
    forged_context["inputs"]["risk_budget_amount"] = 10_000
    assert position_sizing_contract_issues(valid, forged_context)


def test_old_position_snapshot_remains_readable_without_sizing_evidence():
    from structured_output_recommendation_outputs import PositionPlan
    legacy = PositionPlan.model_validate(plan()).model_dump()
    assert legacy["position_size"] == "100%"
    assert legacy["sizing_evidence"] is None
    assert v2_position_plan_contract_issues(legacy)


@pytest.mark.parametrize("field,value", [
    ("capital_amount", 10 ** 500), ("scenario_type", {}),
    ("position_state", []), ("existing_position_percent", True),
])
def test_malformed_external_context_fails_closed_without_exception(field, value):
    assert context(**{field: value})["status"] == "unavailable"


def test_short_risk_uses_highest_cover_stop_and_lowest_entry():
    result = calculate_position_sizing(
        plan(entry_zone="100-110", stop_loss="120-125", transaction_cost="5"),
        context(), recommendation={"建議": "放空"},
    )
    assert result["risk_per_share"] == 30
    assert result["entry_reference"] == 100
    assert result["position_percent"] == pytest.approx(3.333333)


def test_full_percentage_only_passes_with_explicit_budget_and_recomputed_receipt():
    ctx = context(risk_budget_amount=20_000)
    result = audited_plan(plan(), ctx)
    assert result["position_size"] == "100%"
    assert position_sizing_contract_issues(result, ctx) == []


def test_wait_receipt_cannot_smuggle_fabricated_capital():
    value = plan(action="等待", position_size="0%", sizing_evidence={
        "status": "unassessed", "reason": "預算未知", "capital_amount": 1_000_000,
    })
    assert position_sizing_contract_issues(value)


def test_schema_rejects_boolean_and_nonfinite_receipt_money():
    from pydantic import ValidationError
    from structured_output_recommendation_outputs import PositionPlan
    for value in (True, float("inf"), float("nan")):
        source = audited_plan(plan(), context())
        source["sizing_evidence"]["capital_amount"] = value
        with pytest.raises(ValidationError):
            PositionPlan.model_validate(source)


def test_valid_receipt_survives_schema_roundtrip_without_coercing_unknown_values():
    from structured_output_recommendation_outputs import PositionPlan
    ctx = context()
    value = PositionPlan.model_validate(audited_plan(plan(), ctx)).model_dump()
    assert position_sizing_contract_issues(value, ctx) == []


def test_unassessed_wait_is_explicit_without_invented_holdings():
    value = plan(action="等待", position_size="0%", planning_context="unassessed")
    value["sizing_evidence"] = calculate_position_sizing(value)
    assert value["sizing_evidence"]["position_state"] == "unknown"
    assert value["sizing_evidence"]["existing_position_percent"] is None
    assert position_sizing_contract_issues(value) == []


def test_unassessed_wait_rejects_model_fabricated_source_identity():
    value = plan(action="等待", position_size="0%", sizing_evidence={
        "status": "unassessed", "reason": "預算未知", "source_ref": "made-up-account:7",
    })
    assert position_sizing_contract_issues(value)


def test_repair_receipt_is_emitted_once_and_does_not_accept_or_rewrite_plan():
    original = plan()
    issues = position_sizing_contract_issues(original, context())
    assert issues
    assert sum("context_sha256" in issue for issue in issues) == 1
    assert "不是已接受" in issues[-1]
    assert "正文" in issues[-1]
    assert '"position_percent":10.0' in issues[-1]
    assert len(issues[-1]) < 2500
    assert original["position_size"] == "100%"


def test_context_source_identity_is_bounded_for_repair_feedback():
    assert build_position_sizing_context(supplied(), source_ref="x" * 257, quote_currency="TWD")["status"] == "unavailable"
