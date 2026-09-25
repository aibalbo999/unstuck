"""Last-resort output must preserve unknowns instead of manufacturing evidence."""

import pytest

from agent_runtime.deterministic_fallbacks import _deterministic_structured_fallback
from structured_output_parser import parse_structured_data


def context(agent, **data):
    return {
        "pipeline_id": "v2" if agent in {12, 14, 16} else "v1",
        "data": {"current_price": 100, **data}, "analyses": {}, "structured_outputs": {},
    }


@pytest.mark.parametrize("agent", [3, 12])
def test_missing_moat_evidence_fallback_has_no_invented_scores(agent):
    ctx = context(agent)
    assert _deterministic_structured_fallback(agent, ctx["data"], ctx, "")[0]
    result = ctx["structured_outputs"][agent]
    assert len(result["moat_scores"]) == 6
    assert all(value is None for value in result["moat_scores"].values())
    assert result["moat_trend"] == "unassessed"
    assert all(not item["source_refs"] for item in result["moat_evidence"].values())
    assert "未評估" in ctx["analyses"][agent]


@pytest.mark.parametrize("agent", [4, 14])
@pytest.mark.parametrize("spot", [None, 100, 5000, True, float("nan"), float("inf")])
def test_missing_valuation_fallback_does_not_derive_targets_from_spot(agent, spot):
    from final_audit_price_targets import price_target_audit_issues
    ctx = context(agent, current_price=spot)
    assert _deterministic_structured_fallback(agent, ctx["data"], ctx, "")[0]
    result = ctx["structured_outputs"][agent]
    assert result["price_targets"] == {}
    assert result["valuation_assessment"]["status"] == "unassessed"
    assert "未重算" in ctx["analyses"][agent]
    parsed = parse_structured_data(ctx)
    assert parsed["price_targets"] == {}
    assert price_target_audit_issues(parsed["price_targets"], current_price=spot, valuation_agent=agent)


@pytest.mark.parametrize("agent", [4, 14])
def test_partial_existing_valuation_stays_partial_and_not_recalculated(agent):
    from final_audit_price_targets import price_target_audit_issues
    ctx = context(agent)
    text = "原分析採用相對估值，但缺兩個情境。\n[目標股價]\n基本情境: NT$120\n[/目標股價]"
    assert _deterministic_structured_fallback(agent, ctx["data"], ctx, text)[0]
    result = ctx["structured_outputs"][agent]
    assert result["price_targets"] == {"基本情境": 120}
    assert result["valuation_assessment"]["missing_scenarios"] == ["熊市情境", "牛市情境"]
    assert price_target_audit_issues(result["price_targets"], current_price=100, valuation_agent=agent)


@pytest.mark.parametrize("agent", [4, 14])
@pytest.mark.parametrize("value", [True, False, float("inf"), float("nan"), -1, 0])
def test_valuation_fallback_rejects_nonfinite_boolean_and_nonpositive_parsed_values(monkeypatch, agent, value):
    monkeypatch.setattr("agent_runtime.deterministic_fallbacks.parse_structured_data", lambda _: {
        "price_targets": {"熊市情境": value, "基本情境": value, "牛市情境": value},
    })
    ctx = context(agent)
    assert _deterministic_structured_fallback(agent, ctx["data"], ctx, "先前估值分析")[0]
    assert ctx["structured_outputs"][agent]["price_targets"] == {}


@pytest.mark.parametrize("agent", [7, 16])
def test_missing_decision_has_no_spot_or_cross_horizon_target_defaults(agent):
    ctx = context(agent)
    ctx["parsed"] = {"price_targets": {"基本情境": 123, "牛市情境": 456}}
    assert _deterministic_structured_fallback(agent, ctx["data"], ctx, "")[0]
    result = ctx["structured_outputs"][agent]
    assert result["recommendation"]["建議"] == "避免"
    for key, value in result["recommendation"].items():
        if "目標" in key or "潛力" in key:
            assert value.startswith("N/A") and "123" not in value and "456" not in value
    assert result["recommendation"]["信心指數"].startswith("N/A")


@pytest.mark.parametrize("agent", [7, 16])
@pytest.mark.parametrize("label", ["買入", "持有", "避免", "放空"])
def test_fallback_preserves_existing_research_classification_without_executable_plan(agent, label):
    ctx = context(agent)
    ctx["structured_outputs"][agent] = {"recommendation": {"建議": label}}
    assert _deterministic_structured_fallback(agent, ctx["data"], ctx, "")[0]
    result = ctx["structured_outputs"][agent]
    assert result["recommendation"]["建議"] == label
    assert "研究分類" in result["analysis_markdown"]
    if agent == 16:
        assert result["position_plan"]["action"] == "等待"
        assert result["position_plan"]["position_size"] == "0%"


def test_a_fallback_has_honest_unassessed_reconciliation_and_runtime_receipt():
    from research_assumption_contract import assess_reconciliation, TOPICS
    ctx = context(7)
    assert _deterministic_structured_fallback(7, ctx["data"], ctx, "")[0]
    result = ctx["structured_outputs"][7]
    value = result["assumption_reconciliation"]
    assert value["status"] == "unassessed"
    assert {row["topic"] for row in value["checks"]} == set(TOPICS)
    assert all(row["status"] == "unassessed" and not row["valuation_quote"] and not row["growth_quote"] for row in value["checks"])
    assert result["assumption_reconciliation_assessment"] == assess_reconciliation(value, ctx)


def test_b_fallback_has_unassessed_sizing_with_system_receipt_and_no_holdings_inference():
    from position_sizing_runtime import assess_position_plan
    ctx = context(16)
    assert _deterministic_structured_fallback(16, ctx["data"], ctx, "")[0]
    result = ctx["structured_outputs"][16]
    plan = result["position_plan"]
    assert plan["planning_context"] == "unassessed"
    assert plan["sizing_evidence"]["status"] == "unassessed"
    assert plan["sizing_evidence"]["existing_position_percent"] is None
    assert result["position_sizing_assessment"] == assess_position_plan(plan, ctx, result["recommendation"], result["analysis_markdown"])
    assert result["position_sizing_assessment"]["issues"] == []


@pytest.mark.parametrize("agent", [3, 12, 7, 16])
def test_fallback_new_role_contracts_survive_normalization_roundtrip(agent):
    from structured_output_normalizer import normalize_structured_output
    ctx = context(agent)
    assert _deterministic_structured_fallback(agent, ctx["data"], ctx, "")[0]
    original = ctx["structured_outputs"][agent]
    normalized = normalize_structured_output(agent, original)
    assert normalized
    if agent in {3, 12}:
        assert all(value is None for value in normalized["moat_scores"].values())
        assert normalized["moat_trend"] == "unassessed"
    elif agent == 7:
        assert normalized["assumption_reconciliation"] == original["assumption_reconciliation"]
        assert normalized["assumption_reconciliation_assessment"] == original["assumption_reconciliation_assessment"]
    else:
        assert normalized["position_plan"]["sizing_evidence"] == original["position_plan"]["sizing_evidence"]
        assert normalized["position_sizing_assessment"] == original["position_sizing_assessment"]


@pytest.mark.parametrize("agent", [4, 14])
def test_missing_valuation_remains_critical_in_complete_final_audit(agent):
    from final_audit import run_final_report_audit
    ctx = context(agent)
    ctx["agent_sequence"] = [agent]
    assert _deterministic_structured_fallback(agent, ctx["data"], ctx, "")[0]
    ctx["parsed"] = parse_structured_data(ctx)
    audit = run_final_report_audit(ctx, append_section=False)
    assert any(f"Agent {agent} 缺少目標價情境" in issue for issue in audit["critical"])
