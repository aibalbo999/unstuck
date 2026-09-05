"""The actual prompt shares one analysis budget across previous text and State."""

import copy
import json

import pytest

from agent_runtime import prompting
from agent_state import AgentReport, RiskFlag
from state_memory import initialize_agent_state, merge_agent_report


def _encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def _state_json(prompt):
    section = prompt.split("【AgentState view】\n", 1)[1].split("\n", 1)[1]
    return json.JSONDecoder().raw_decode(section)[0]


def _context():
    data = {"ticker": "TEST", "company_name": "Budget fixture", "revenue_history": [123.45]}
    state = initialize_agent_state(data, run_id="budget-fixture")
    state.quant_metrics = {"calculations": {"canonical_number": 987.654321}, "unit_contract": {"price": "TWD"}}
    analyses, structured = {}, {}
    for agent in (11, 12, 13, 14, 15, 17, 18, 20, 21, 22, 23):
        markdown = f"SOURCE_{agent} 財務營收\n\n" + "長報告原文" * 20_000
        output = {"analysis_markdown": markdown, "target": 123.456789,
                  "nested": {"unbounded_story": "巨大論述" * 20_000, "canonical_value": 234.567891}}
        flag = RiskFlag(id=f"risk-{agent}", severity="high", category="valuation", title=f"RISK_{agent}",
                        impact="需查證", source_agents=[str(agent)], confidence=0.5)
        merge_agent_report(state, AgentReport(agent_id=str(agent), role="test", markdown=markdown,
                           structured_output=output, risk_flags=[flag] * 30))
        analyses[agent], structured[agent] = markdown, output
    return data, {"agent_state": state, "analyses": analyses, "structured_outputs": structured}


@pytest.fixture
def configured_budget(monkeypatch):
    # Keep model-window clipping from hiding a violation of the separate analysis budget.
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda _agent: 1_000_000)
    monkeypatch.setattr(prompting, "get_agent_context_budgets", lambda _agent: (3000, 900), raising=False)
    monkeypatch.setattr(prompting, "PRIMARY_PROMPT_CONTEXT_TOTAL_CHAR_BUDGET", 900)
    for agent in (13, 16, 21, 24):
        monkeypatch.setitem(prompting.ANALYSIS_PROMPTS, agent, "BEGIN_PREV{{ prev }}END_PREV")


@pytest.mark.parametrize("agent,pipeline", [(16, "v2"), (21, "v3"), (24, "v4")])
@pytest.mark.parametrize("primary", [False, True])
def test_actual_prompt_shares_budget_and_keeps_raw_state(agent, pipeline, primary, configured_budget):
    data, context = _context()
    context.update(pipeline_id=pipeline, _primary_probe_prompt=primary)
    before = copy.deepcopy(context)

    prompt = prompting.build_prompt(agent, data, context)

    prev = prompt.split("BEGIN_PREV", 1)[1].split("END_PREV", 1)[0]
    view = _state_json(prompt)
    derived = {key: value for key, value in view.items()
               if key in {"agent_reports", "risk_flags", "_analysis_context_omitted"}}
    assert len(prev) + len(_encode(derived)) <= (900 if primary else 3000)
    assert view["normalized_financials"] == prompting.state_view_for(agent, context["agent_state"])["normalized_financials"]
    if agent != 24:
        assert view["quant_metrics"] == before["agent_state"].quant_metrics
    assert context == before


def test_state_projection_deduplicates_report_flags(configured_budget):
    data, context = _context()
    context["pipeline_id"] = "v3"
    view = _state_json(prompting.build_prompt(21, data, context))
    encoded = _encode(view)
    assert encoded.count('"id": "risk-17"') == 1
    assert "risk-21" not in encoded and "SOURCE_21" not in encoded


def test_overlong_fields_are_omitted_not_truncated_inside_state_json(configured_budget):
    data, context = _context()
    context["pipeline_id"] = "v3"
    view = _state_json(prompting.build_prompt(21, data, context))
    report = view["agent_reports"]["17"]
    assert "markdown" not in report
    assert "analysis_markdown" not in report["structured_output"]
    assert report["structured_output"]["target"] == 123.456789
    assert report["structured_output"]["nested"]["canonical_value"] == 234.567891
    assert view["_analysis_context_omitted"] is True


def test_no_state_does_not_reserve_unused_state_budget(configured_budget):
    data, context = _context()
    context.pop("agent_state")
    context["pipeline_id"] = "v2"
    prompt = prompting.build_prompt(16, data, context)
    prev = prompt.split("BEGIN_PREV", 1)[1].split("END_PREV", 1)[0]
    assert 1500 < len(prev) <= 3000


def test_blind_agent_gets_no_report_or_managed_flag(configured_budget):
    data, context = _context()
    context["pipeline_id"] = "v2"
    prompt = prompting.build_prompt(13, data, context)
    view = _state_json(prompt)
    assert not view.get("agent_reports") and not view.get("risk_flags")
    assert "SOURCE_" not in prompt and "RISK_" not in prompt
    assert view["quant_metrics"]["calculations"]["canonical_number"] == 987.654321


def test_production_template_growth_is_limited_by_one_analysis_budget(monkeypatch):
    data, context = _context()
    context["pipeline_id"] = "v3"
    empty = {**context, "analyses": {}, "structured_outputs": {},
             "agent_state": initialize_agent_state(data, run_id="budget-fixture")}
    empty["agent_state"].quant_metrics = copy.deepcopy(context["agent_state"].quant_metrics)
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda _agent: 1_000_000)
    monkeypatch.setattr(prompting, "get_agent_context_budgets", lambda _agent: (3000, 900))

    baseline = prompting.build_prompt(21, data, empty)
    prompt = prompting.build_prompt(21, data, context)

    assert len(prompt) - len(baseline) <= 3000
    assert _state_json(prompt)["quant_metrics"] == context["agent_state"].quant_metrics


@pytest.mark.parametrize("shape", [None, [], "malformed"])
def test_budget_boundary_ignores_malformed_report_containers(shape, monkeypatch):
    data, context = _context()
    context["pipeline_id"] = "v3"
    view = {"agent_reports": shape, "risk_flags": shape,
            "quant_metrics": {"canonical_number": 987.654321}}
    monkeypatch.setattr(prompting, "state_view_for", lambda *_args: view)
    before = copy.deepcopy(view)

    projected = _state_json(prompting.build_state_view_section(21, context, max_analysis_chars=100))

    assert not projected.get("agent_reports") and not projected.get("risk_flags")
    assert projected["quant_metrics"]["canonical_number"] == 987.654321
    assert view == before
