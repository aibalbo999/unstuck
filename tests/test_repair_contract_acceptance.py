"""Production fallback drafts must satisfy the contracts before adoption."""

import asyncio
import copy

import pytest

from agent_runtime import audit_repair, repair_loop
from agent_runtime.structured_repair_contracts import structured_output_missing
from final_audit_mode_contracts import v2_position_plan_contract_issues, v3_short_setup_contract_issues
from trade_execution_contract import contains_trade_order


def context_for(agent):
    return {
        "pipeline_id": "v3" if agent == 19 else "v2",
        "data": {"ticker": "TEST", "company_name": "Test", "current_price": 100},
        "analyses": {agent: "ORIGINAL_ACCEPTED_TEXT"},
        "structured_outputs": {agent: {"analysis_markdown": "ORIGINAL_ACCEPTED_TEXT"}},
        "repair_attempt_counts": {agent: 2},
        "blocking_issues": [f"Agent {agent} 原問題", "external:keep"],
    }


def run(context, agent, asynchronous):
    args = agent, context["data"], context, object(), ["請修復交易契約"]
    if asynchronous:
        return asyncio.run(repair_loop._repair_agent_output_async(*args))
    return repair_loop._repair_agent_output(*args)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("agent", [16, 19])
@pytest.mark.parametrize("route", ["limit", "circuit", "provider_429", "quality"])
def test_real_fallback_passes_mode_contract(agent, asynchronous, route, monkeypatch):
    context = context_for(agent)
    calls = []

    def provider(*args, **kwargs):
        assert route in {"provider_429", "quality"}, "no provider call for limit or circuit"
        calls.append(agent)
        if route == "provider_429":
            return f"[Agent {agent} 執行失敗：429 RESOURCE_EXHAUSTED]"
        return "## 不完整修復候選\n資料待補。"

    async def provider_async(*args, **kwargs):
        return provider(*args, **kwargs)

    if route != "limit":
        context["repair_attempt_counts"] = {}
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _: {"open": route == "circuit"})
    monkeypatch.setattr(repair_loop, "record_repair_429_failure", lambda *_: {"open": True})
    monkeypatch.setattr(repair_loop, "run_single_agent", provider)
    monkeypatch.setattr(repair_loop, "run_single_agent_async", provider_async)
    if route == "quality":
        monkeypatch.setattr(repair_loop, "validate_analysis_output", lambda *_: ["候選缺少必要內容"])
    ok, message = run(context, agent, asynchronous)
    assert ok, message
    assert not structured_output_missing(context, agent)
    payload = context["structured_outputs"][agent]
    checker = v3_short_setup_contract_issues if agent == 19 else v2_position_plan_contract_issues
    field = "short_setup" if agent == 19 else "position_plan"
    assert checker(payload[field], recommendation=payload["recommendation"]) == []
    assert context["blocking_issues"] == ["external:keep"]
    assert len(calls) == {"limit": 0, "circuit": 0, "provider_429": 1, "quality": 2}[route]
    if route == "limit":
        assert context["repair_attempt_counts"][agent] == 2


@pytest.mark.parametrize("asynchronous", [False, True])
def test_invalid_fallback_cannot_replace_accepted_output_or_clear_blocker(asynchronous, monkeypatch):
    context = context_for(19)
    before = copy.deepcopy(context)

    def malformed(*args):
        context["analyses"][19] = "UNVERIFIED_DRAFT"
        context["structured_outputs"][19] = {"recommendation": {"建議": "避免"}, "short_setup": {}}
        context["blocking_issues"] = ["external:keep"]
        return True, "已套用備援"

    monkeypatch.setattr(repair_loop, "per_job_repair_limit_fallback", malformed)
    ok, message = run(context, 19, asynchronous)
    assert not ok
    assert "契約" in message
    for field in ("analyses", "structured_outputs", "blocking_issues"):
        assert context[field] == before[field]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_rewritten_recommendation_cannot_claim_acceptance_with_negative_hold_return(asynchronous, monkeypatch):
    context = context_for(16)
    context["repair_attempt_counts"] = {}
    before = copy.deepcopy(context)

    def complete(agent, data, candidate, rotator, **kwargs):
        candidate["structured_outputs"][16] = {
            "recommendation": {"建議": "持有", "長期目標（12個月）": "NT$50"},
            "position_plan": {"action": "等待", "entry_zone": "觀望", "position_size": "0%",
                              "invalidation_condition": "下次財報公布後重新評估"},
        }
        return "## 投資決策\n等待下次財報後重新評估。"

    async def complete_async(*args, **kwargs):
        return complete(*args, **kwargs)

    monkeypatch.setattr(repair_loop, "run_single_agent", complete)
    monkeypatch.setattr(repair_loop, "run_single_agent_async", complete_async)
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _: {"open": False})
    monkeypatch.setattr(repair_loop, "record_quality_fallback", lambda *_: (False, "無可用備援"))
    ok, message = run(context, 16, asynchronous)
    assert not ok
    assert "建議/報酬矛盾" in message
    assert context["analyses"] == before["analyses"]
    assert context["structured_outputs"] == before["structured_outputs"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_failed_contract_can_use_remaining_rewrite_attempt(asynchronous, monkeypatch):
    context = context_for(16)
    context["repair_attempt_counts"] = {}
    calls = []

    def complete(agent, data, candidate, rotator, **kwargs):
        calls.append(candidate.get("_audit_retry_instruction", ""))
        candidate["structured_outputs"][16] = {
            "recommendation": {"建議": "持有", "長期目標（12個月）": "NT$50" if len(calls) == 1 else "NT$110"},
            "position_plan": {"action": "等待", "entry_zone": "觀望", "position_size": "0%",
                              "invalidation_condition": "下次財報公布後重新評估"},
        }
        return "## 投資決策\n等待下次財報後重新評估。"

    async def complete_async(*args, **kwargs):
        return complete(*args, **kwargs)

    monkeypatch.setattr(repair_loop, "run_single_agent", complete)
    monkeypatch.setattr(repair_loop, "run_single_agent_async", complete_async)
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _: {"open": False})
    ok, message = run(context, 16, asynchronous)
    assert ok, message
    assert len(calls) == 2
    assert "建議/報酬矛盾" in calls[1]
    assert context["structured_outputs"][16]["recommendation"]["長期目標（12個月）"] == "NT$110"


def test_waiting_for_verifiable_entry_conditions_is_observation():
    assert not contains_trade_order("資料不足，等待可驗證進場條件")


@pytest.mark.parametrize("text", [
    "等待可驗證進場條件後買入 100 股", "等待突破 100 元進場",
    "等待可驗證進場條件，確認後建立空單", "明日開倉",
    "等待可驗證進場條件滿足後執行",
])
def test_actual_orders_remain_blocked(text):
    assert contains_trade_order(text)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_repair_event_distinguishes_candidate_acceptance_from_report_pass(asynchronous):
    context = context_for(19)
    events = []
    args = context, events.append, 19, "泡沫狙擊報告", True, "已套用備援"
    if asynchronous:
        asyncio.run(audit_repair._record_repair_result_async(*args))
    else:
        audit_repair._record_repair_result(*args)
    event = events[-1]
    assert "仍待整份報告稽核" in event["message"]
    assert "自動修復成功" not in event["message"]
    assert event["metadata"]["validation_scope"] == "agent_contract"
    assert event["metadata"]["final_report_passed"] is None
