"""Verified research waiting state is policy metadata, never market evidence."""

from copy import deepcopy

import pytest

from evidence_exit_gate import evaluate_report_evidence
from position_sizing_runtime import assess_position_plan


def snapshot():
    plan = {
        "action": "等待", "entry_zone": "N/A", "position_size": "0%",
        "stop_loss": "N/A", "risk_reward": "N/A", "target_price": None,
        "transaction_cost": None, "horizon_trading_days": None,
        "planning_context": "unassessed", "invalidation_condition": "等待財報與風險預算後重新評估。",
        "sizing_evidence": {"status": "unassessed", "reason": "缺少外部預算，不代表使用者實際持倉為零。"},
    }
    output = {"position_plan": deepcopy(plan), "recommendation": {"建議": "買入"}, "analysis_markdown": "本研究等待風險預算後重新評估，不新增部位。"}
    output["position_sizing_assessment"] = assess_position_plan(plan, {}, output["recommendation"], output["analysis_markdown"])
    return {"pipeline": "v2", "data": {"current_price": 100}, "rerun_context": {
        "pipeline_id": "v2", "parsed": {"position_plan": plan}, "structured_outputs": {"16": output},
    }}


def markdown(size="0%", action="等待", label="部位大小"):
    return f"- 股價: 100\n## 實戰交易決策\n- **操作動作:** {action}\n- **進場條件:** N/A\n- **{label}:** {size}"


def gate(snap=None, **text):
    return evaluate_report_evidence(markdown(**text), snapshot() if snap is None else snap, sample_ratio=1.0)


def test_verified_wait_zero_is_checked_as_policy_and_not_financial_evidence():
    result = gate()
    assert result["verdict"] == "approved"
    assert result["claim_count"] == result["verified_count"] == 1
    assert result["policy_claim_count"] == result["policy_checked_count"] == 1
    assert result["metadata_claim_count"] == 0
    claim = result["policy_claims"][0]
    assert claim["claim_type"] == "execution_policy"
    assert claim["financial_evidence"] is False
    assert claim["status"] == "valid"
    assert claim["verification_reason_code"] == "verified_waiting_position_policy"
    assert claim["matched_path"] == "rerun_context.structured_outputs.16.position_sizing_assessment"


@pytest.mark.parametrize("size", ["10%", "100%", "-1%", "0元", "0%（實際持股比例）"])
def test_nonzero_or_other_semantics_never_receive_waiting_policy_exemption(size):
    result = gate(size=size)
    assert result.get("policy_claim_count", 0) == 0
    assert result["verdict"] != "approved"


@pytest.mark.parametrize("kind", ["missing_receipt", "failed_receipt", "wrong_version", "contradictory_plan", "parsed_mismatch", "invented_capital", "wrong_mode", "model_order", "receipt_calculated", "inferred_holdings", "actual_scenario"])
def test_snapshot_requires_consistent_real_waiting_receipt(kind):
    snap = snapshot()
    output = snap["rerun_context"]["structured_outputs"]["16"]
    if kind == "missing_receipt":
        output.pop("position_sizing_assessment")
    elif kind == "failed_receipt":
        output["position_sizing_assessment"]["issues"] = ["raw 100% did not pass"]
    elif kind == "wrong_version":
        output["position_sizing_assessment"]["contract_version"] = "invented:v0"
    elif kind == "contradictory_plan":
        output["position_plan"]["action"] = "進場"
    elif kind == "parsed_mismatch":
        snap["rerun_context"]["parsed"]["position_plan"]["position_size"] = "10%"
    elif kind == "invented_capital":
        output["position_plan"]["sizing_evidence"]["capital_amount"] = 100_000
        snap["rerun_context"]["parsed"]["position_plan"] = deepcopy(output["position_plan"])
    elif kind == "wrong_mode":
        snap["pipeline"] = "v3"
    elif kind == "model_order":
        output["analysis_markdown"] = "請立即買入建立部位。"
    elif kind == "receipt_calculated":
        output["position_sizing_assessment"]["calculation"]["status"] = "calculated"
    elif kind == "inferred_holdings":
        output["position_plan"]["sizing_evidence"]["position_state"] = "holding"
        snap["rerun_context"]["parsed"]["position_plan"] = deepcopy(output["position_plan"])
    elif kind == "actual_scenario":
        output["position_sizing_assessment"]["calculation"]["scenario_type"] = "actual"
    result = gate(snap)
    assert result.get("policy_claim_count", 0) == 0
    assert result["unverifiable_count"] >= 1
    assert result["verdict"] == "caution"


@pytest.mark.parametrize("action", ["進場", "續抱", "減碼", "未評估"])
def test_rendered_action_must_agree_with_waiting_snapshot(action):
    result = gate(action=action)
    assert result.get("policy_claim_count", 0) == 0
    assert result["verdict"] == "caution"


def test_an_isolated_model_position_claim_is_not_trusted_from_zero_alone():
    result = evaluate_report_evidence("- 股價: 100\n- 部位大小: 0%", snapshot(), sample_ratio=1.0)
    assert result.get("policy_claim_count", 0) == 0
    assert result["verdict"] == "caution"


def test_verified_policy_only_report_does_not_count_as_financial_evidence_approved():
    result = evaluate_report_evidence(markdown().split("\n", 1)[1], snapshot(), sample_ratio=1.0)
    assert result["claim_count"] == result["verified_count"] == 0
    assert result["policy_claim_count"] == 1
    assert result["verdict"] == "caution"


def test_policy_projection_does_not_mutate_snapshot():
    original = snapshot()
    before = deepcopy(original)
    gate(original)
    assert original == before


@pytest.mark.parametrize("rendered", [
    markdown().replace("實戰交易決策", "使用者實際持倉"),
    markdown() + "\n以上部位大小就是使用者目前實際持股比例。",
    markdown() + "\n請立即買入建立部位。",
    markdown() + "\n## 後續行動\n請立即買入建立部位。",
])
def test_rendered_holdings_or_immediate_order_cannot_borrow_clean_saved_receipt(rendered):
    result = evaluate_report_evidence(rendered, snapshot(), sample_ratio=1.0)
    assert result.get("policy_claim_count", 0) == 0
    assert result["verdict"] == "caution"


@pytest.mark.parametrize("body", [
    "以上部位大小就是使用者目前實際持股比例。",
    "## 使用者實際持倉\n部位大小為零。",
])
def test_saved_body_cannot_claim_actual_holdings_under_an_unassessed_receipt(body):
    snap = snapshot()
    snap["rerun_context"]["structured_outputs"]["16"]["analysis_markdown"] = body
    result = gate(snap)
    assert result.get("policy_claim_count", 0) == 0
    assert result["verdict"] == "caution"


@pytest.mark.parametrize("field,value", [
    ("horizon_trading_days", 10), ("currency", "USD"), ("trade_direction", "Short"),
])
def test_model_evidence_unknown_fields_must_agree_with_system_receipt(field, value):
    snap = snapshot()
    output = snap["rerun_context"]["structured_outputs"]["16"]
    output["position_plan"]["sizing_evidence"][field] = value
    snap["rerun_context"]["parsed"]["position_plan"] = deepcopy(output["position_plan"])
    result = gate(snap)
    assert result.get("policy_claim_count", 0) == 0
    assert result["verdict"] == "caution"


@pytest.mark.parametrize("body", [
    "0% 僅指本研究不新增部位，不代表使用者實際持倉為零。",
    "若使用者實際持倉為零，待取得資金與風險預算後再重新評估。",
    "若取得資金與風險預算後，才可立即買入。",
    "請不要立即買入建立部位。",
])
def test_explicit_disclaimers_and_future_conditions_keep_the_policy_scope(body):
    snap = snapshot()
    snap["rerun_context"]["structured_outputs"]["16"]["analysis_markdown"] = body
    result = evaluate_report_evidence(markdown() + "\n" + body, snap, sample_ratio=1.0)
    assert result["policy_claim_count"] == 1
    assert result["verdict"] == "approved"
