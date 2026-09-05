"""Accepted repair output must survive State prompts and graph round trips."""

import asyncio
import copy
from types import SimpleNamespace
from typing import get_type_hints

import pytest

from agent_runtime import prompting, repair_loop
from agent_runtime.state_report_adapter import record_agent_state_report
from agent_state import AgentReport, RiskFlag
from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
from workflow_state import AgentGraphState, agent_state_from_graph, agent_state_to_graph
from state_memory import initialize_agent_state, merge_agent_report


def _payload(agent, marker):
    if agent == 21:
        return {"analysis_markdown": marker, "thesis_summary": marker, "downside_risks": [
            {"title": marker, "evidence": marker, "impact": marker, "severity": "warning", "confidence": 0.5},
        ]}
    return {"price_targets": {"熊市情境": 80, "基本情境": 100, "牛市情境": 120},
            "analysis_markdown": marker}


def _context(agent=14):
    data = {"ticker": "TEST", "company_name": "Test", "current_price": 100}
    state = initialize_agent_state(data, run_id="repair-state")
    old = _payload(agent, "OLD_ACCEPTED_SENTINEL")
    record_agent_state_report(state, agent, "OLD_ACCEPTED_SENTINEL", old)
    context = {"pipeline_id": "v2", "data": data, "agent_state": state,
               "analyses": {agent: "OLD_ACCEPTED_SENTINEL"}, "structured_outputs": {agent: old}}
    return data, context


def _install_provider(monkeypatch, agent, *, failed=False):
    def complete(_agent, _data, context, _rotator, **kwargs):
        context["structured_outputs"][agent] = _payload(agent, "NEW_ACCEPTED_SENTINEL")
        return "[Agent 14 執行失敗：fixture unavailable]" if failed else "## 分析\nNEW_ACCEPTED_SENTINEL"

    async def complete_async(*args, **kwargs):
        return complete(*args, **kwargs)

    monkeypatch.setattr(repair_loop, "run_single_agent", complete)
    monkeypatch.setattr(repair_loop, "run_single_agent_async", complete_async)
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _agent: {"open": False})


def _run(agent, data, context, asynchronous):
    args = agent, data, context, object(), ["重查估值來源"]
    if asynchronous:
        return asyncio.run(repair_loop._repair_agent_output_async(*args))
    return repair_loop._repair_agent_output(*args)


def _graph_roundtrip(context, initial):
    delta = graph_delta_from_legacy_context(context)
    hints = get_type_hints(AgentGraphState, include_extras=True)
    merged = copy.deepcopy(initial)
    for key, value in delta.items():
        metadata = getattr(hints[key], "__metadata__", ())
        merged[key] = metadata[0](merged.get(key), value) if metadata else value
    return legacy_context_from_graph(merged, SimpleNamespace(progress_callback=None, cancel_check=None))


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("agent", [14, 21])
def test_successful_repair_updates_downstream_prompt_and_graph(agent, asynchronous, monkeypatch):
    data, context = _context(agent)
    initial = agent_state_to_graph(context["agent_state"], pipeline_id="v2")
    _install_provider(monkeypatch, agent)
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda _agent: 1_000_000)

    ok, message = _run(agent, data, context, asynchronous)

    assert ok, message
    report = context["agent_state"].agent_reports[str(agent)]
    assert "NEW_ACCEPTED_SENTINEL" in report.markdown
    assert report.structured_output == context["structured_outputs"][agent]
    for current in (context, _graph_roundtrip(context, initial)):
        prompt = prompting.build_prompt(16, data, current)
        assert "NEW_ACCEPTED_SENTINEL" in prompt
        assert "OLD_ACCEPTED_SENTINEL" not in prompt


@pytest.mark.parametrize("asynchronous", [False, True])
def test_failed_provider_draft_does_not_replace_state(asynchronous, monkeypatch):
    data, context = _context()
    before = context["agent_state"].model_dump(mode="json")
    _install_provider(monkeypatch, 14, failed=True)
    ok, _ = _run(14, data, context, asynchronous)
    assert not ok
    assert context["agent_state"].model_dump(mode="json") == before


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("route", ["limit", "circuit", "quality"])
def test_accepted_fallback_also_updates_state(route, asynchronous, monkeypatch):
    data, context = _context()
    context["context_digests"] = {16: "STALE_DOWNSTREAM_DIGEST", 14: "STALE_REPAIR_DIGEST"}
    _install_provider(monkeypatch, 14)

    def fallback(*args, **kwargs):
        context["analyses"][14] = "NEW_FALLBACK_SENTINEL"
        context["structured_outputs"][14] = _payload(14, "NEW_FALLBACK_SENTINEL")
        return True, "accepted fallback"

    if route == "limit":
        monkeypatch.setattr(repair_loop, "per_job_repair_limit_fallback", fallback)
    elif route == "circuit":
        monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _agent: {"open": True})
        monkeypatch.setattr(repair_loop, "apply_429_fallback", fallback)
    else:
        monkeypatch.setattr(repair_loop, "validate_analysis_output", lambda *_args: ["quality fixture rejection"])
        monkeypatch.setattr(repair_loop, "record_quality_fallback", fallback)

    ok, message = _run(14, data, context, asynchronous)
    assert ok, message
    report = context["agent_state"].agent_reports["14"]
    assert report.markdown == "NEW_FALLBACK_SENTINEL"
    assert report.structured_output == context["structured_outputs"][14]
    assert context["context_digests"] == {}


def _external_flag():
    return RiskFlag(id="provider-warning", severity="warning", category="data_quality",
                    title="EXTERNAL_KEEP", impact="provider gap", source_agents=[], confidence=0.5)


def test_graph_rebuild_removes_deleted_managed_risks_but_preserves_external():
    _, context = _context(21)
    context["agent_state"].risk_flags.append(_external_flag())
    initial = agent_state_to_graph(context["agent_state"], pipeline_id="v2")
    output = {**_payload(21, "NO_RISKS_AFTER_REPAIR"), "downside_risks": []}
    record_agent_state_report(context["agent_state"], 21, "NO_RISKS_AFTER_REPAIR", output)

    restored = _graph_roundtrip(context, initial)["agent_state"]

    assert [flag.title for flag in restored.risk_flags] == ["EXTERNAL_KEEP"]
    assert restored.agent_reports["21"].risk_flags == []


def test_parallel_report_merge_keeps_both_new_risk_sets_and_external():
    _, context = _context(21)
    initial = agent_state_to_graph(context["agent_state"], pipeline_id="v2")
    initial["risk_flags"].append(_external_flag().model_dump(mode="json"))
    left = context["agent_state"].model_copy(deep=True)
    right = context["agent_state"].model_copy(deep=True)
    record_agent_state_report(left, 21, "NEW_21", _payload(21, "NEW_21"))
    flag20 = RiskFlag(id="sentiment-20", severity="high", category="sentiment", title="NEW_20",
                      impact="需關注", source_agents=["20"], confidence=0.6)
    merge_agent_report(right, AgentReport(agent_id="20", role="sentiment", markdown="NEW_20", risk_flags=[flag20]))
    hints = get_type_hints(AgentGraphState, include_extras=True)
    for agent, state in [("20", right), ("21", left)]:
        report = state.agent_reports[agent]
        for key, delta in {
            "agent_reports": {agent: report.model_dump(mode="json")},
            "risk_flags": [flag.model_dump(mode="json") for flag in report.risk_flags],
        }.items():
            initial[key] = hints[key].__metadata__[0](initial.get(key), delta)

    restored = agent_state_from_graph(initial)

    assert {flag.title for flag in restored.risk_flags} == {"NEW_20", "NEW_21", "EXTERNAL_KEEP"}
    assert set(restored.agent_reports) == {"20", "21"}
