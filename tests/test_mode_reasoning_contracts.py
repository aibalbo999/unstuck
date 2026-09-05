"""Research stance, no-trade semantics and prompt/state boundary contracts."""

import json

import pytest

from agent_runtime.prompting import build_prompt, build_state_view_section, data_for_agent_prompt
from agent_runtime.structured_repair_contracts import structured_output_missing
from agent_state import AgentReport, RiskFlag
from forward_consistency_checker import run_forward_consistency_checks
from prompt_loader import load_agent_prompt_config
from recommendation_calibration import calibrate_recommendation_summary
from reporting.content_credibility_alignment import evaluate_recommendation_target_alignment
from state_memory import initialize_agent_state, merge_agent_report, state_view_for


def test_avoid_is_no_new_position_not_a_negative_price_forecast():
    assert run_forward_consistency_checks("避免", 100, 110, 120, 135) == {"critical": [], "warnings": []}
    calibrated = calibrate_recommendation_summary(
        {"recommendation": "避免", "current_price": "100", "target_12m": "135", "confidence": "8/10"},
        data_trust={"status": "fresh"},
    )
    assert calibrated["recommendation"] == "避免"
    result = evaluate_recommendation_target_alignment(
        recommendation_present=True, recommendation_label="避免", current_price=100,
        main_target={"price": 135, "source": "target_12m"},
    )
    assert result["blocking_issues"] == []


@pytest.mark.parametrize("label,target", [("買入", 80), ("放空", 135)])
def test_directional_trades_still_reject_opposite_targets(label, target):
    assert run_forward_consistency_checks(label, 100, None, None, target)["critical"]


def test_mode_a_has_one_consistent_final_recommendation_contract():
    config = load_agent_prompt_config()
    combined = config["system_prompts"]["7"] + config["analysis_prompts"]["7"]
    assert "不可提供「買入」" not in combined
    assert "不可給出「買入/持有/避免」" not in combined
    assert "recommendation" in combined


def test_mode_c_challenger_tests_short_thesis_without_forced_short_bias():
    data = {"ticker": "TEST", "company_name": "Test"}
    short_review = build_prompt(21, data, {"pipeline_id": "v3"})
    long_review = build_prompt(21, data, {"pipeline_id": "v1"})
    assert "挑戰空方論點" in short_review
    assert "挑戰空方論點" not in long_review
    config = load_agent_prompt_config()
    system = config["system_prompts"]["19"]
    assert "Your default bias" not in system
    assert "絕大多數情況應傾向" not in system
    assert "未發現泡沫" in system
    final_prompt = build_prompt(19, data, {"pipeline_id": "v3"})
    assert "否則應傾向" not in final_prompt
    assert "downside_risks 必須 3 至 5 項" not in short_review


@pytest.mark.parametrize("risks", [[], [{"title": "營收反證", "evidence": "已提供季度营收改善",
                                        "impact": "降低空方勝算", "severity": "warning", "confidence": 0.6}]])
def test_challenger_schema_does_not_pad_unprovided_risks(risks):
    from structured_output_risk_models import BearAdvocateStructuredOutput
    from structured_output_normalizer import normalize_structured_output
    payload = {"thesis_summary": "僅列出有證據的反證", "downside_risks": risks,
               "analysis_markdown": "其餘風險資料不足，不湊數。"}
    validated = BearAdvocateStructuredOutput.model_validate(payload)
    assert len(validated.downside_risks) == len(risks)
    output = normalize_structured_output(21, payload)
    assert output is not None
    assert len(output["downside_risks"]) == len(risks)


def test_mode_d_neutral_prompt_does_not_force_fabricated_execution_prices():
    config = load_agent_prompt_config()
    combined = config["system_prompts"]["24"] + config["analysis_prompts"]["24"]
    assert "即使方向為 Neutral，仍需提供" not in combined
    assert "Neutral" in combined and "不交易" in combined


def test_c_non_short_is_complete_without_short_prices_in_repair_loop():
    context = {"pipeline_id": "v3", "structured_outputs": {19: {
        "recommendation": {"建議": "避免"},
        "short_setup": {"entry_trigger": "等待財報證據", "downside_target": None,
                        "cover_stop": None, "squeeze_risk": "借券資料不足",
                        "thesis_invalidation": "營收恢復成長時重審"},
    }}}
    assert not structured_output_missing(context, 19)


def _flag(agent, title, *, source=True):
    return RiskFlag(id=title, severity="warning", category="valuation", title=title,
                    source_agents=[str(agent)] if source else [], impact="待查", confidence=0.5)


def test_state_view_excludes_self_peers_and_downstream_reports_and_flags():
    state = initialize_agent_state({"ticker": "TEST"})
    for agent, title in [(17, "UPSTREAM"), (18, "FORENSIC"), (20, "GUIDANCE"), (21, "SELF_LEAK"), (19, "FINAL_LEAK")]:
        merge_agent_report(state, AgentReport(agent_id=str(agent), role="test", markdown=title,
                           risk_flags=[_flag(agent, title, source=agent != 19)]))
    section = build_state_view_section(21, {"pipeline_id": "v3", "agent_state": state})
    assert all(title in section for title in ["UPSTREAM", "FORENSIC", "GUIDANCE"])
    assert "SELF_LEAK" not in section
    assert "FINAL_LEAK" not in section
    assert "FINAL_LEAK" in state.agent_reports["19"].markdown  # projection must not mutate state


def test_prompt_and_state_route_projected_daily_context_to_d():
    data = {"ticker": "TEST", "company_name": "Test", "price_history": [{"month": "2026-01", "price": 100}],
            "event_calendar": {"events": [{"date": "2000-01-01", "title": "OLD_EVENT_DO_NOT_USE"}]}}
    assert data_for_agent_prompt(22, data).get("_prompt_agent_num") == 22
    view = state_view_for(24, initialize_agent_state(data))
    assert "short_term_market_context" in view
    assert "price_history" not in view["normalized_financials"]
    assert "OLD_EVENT_DO_NOT_USE" not in json.dumps(view, ensure_ascii=False)


def test_no_trade_does_not_hide_conditional_or_immediate_orders():
    from final_audit_mode_contracts import (v2_position_plan_contract_issues,
        v3_short_setup_contract_issues, v4_trade_setup_contract_issues)
    assert v2_position_plan_contract_issues({"action": "等待", "position_size": "0%",
        "entry_zone": "立即100買入", "stop_loss": "N/A", "risk_reward": "N/A",
        "invalidation_condition": "等待下週財報後重新評估"})
    assert v3_short_setup_contract_issues({"entry_trigger": "等待跌破100後放空",
        "downside_target": "N/A", "cover_stop": "N/A", "squeeze_risk": "借券資料不足",
        "thesis_invalidation": "營收恢復成長後重審"}, recommendation="避免")
    assert v4_trade_setup_contract_issues({"trade_direction": "Neutral", "entry_zone": "立即100買入",
        "target_price": "N/A", "stop_loss": "N/A", "support_level": "N/A", "resistance_level": "N/A",
        "core_catalyst": "等待下週財報後重新評估", "risk_level": "High"})


def test_oversized_snapshot_preserves_short_term_sources_used_by_mode_d():
    from data_trust_snapshot_integrity import apply_snapshot_size_governance
    data = {"ticker": "TEST", "daily_market_data": {"bars": [{"date": "2026-08-31", "close": 100}]},
            "technical_indicators": {"sma_5": None}, "event_calendar": {"events": []},
            "discardable_debug_text": "x" * 100000}
    snapshot = apply_snapshot_size_governance({"data": data}, max_bytes=3000)
    assert snapshot["snapshot_truncated"]
    for key in ("daily_market_data", "technical_indicators", "event_calendar"):
        assert snapshot["data"][key] == data[key]


def test_b_short_recommendation_uses_short_price_order_through_repair_contract():
    from final_audit_mode_contracts import mode_execution_contract_issues
    plan = {"action": "進場", "entry_zone": "100", "target_price": "80", "stop_loss": "110",
            "position_size": "10%", "risk_reward": "2:1", "invalidation_condition": "營收轉強時重審"}
    structured = {"recommendation": {"建議": "放空"}, "position_plan": plan}
    context = {"pipeline_id": "v2", "structured_outputs": {16: structured}}
    assert not structured_output_missing(context, 16)
    assert mode_execution_contract_issues(structured, position_plan_agent=16,
                                          short_setup_agent=None, trade_setup_agent=None) == []
