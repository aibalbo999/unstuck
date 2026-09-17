"""All-mode admission uses existing defer semantics without speculative prompts."""

import asyncio
import copy
import time

import config
import pytest
from langgraph.graph import END, START, StateGraph

from agent_runtime import routing
from agent_runtime.deferred import AgentDeferredError
from agent_runtime.report_preflight import preflight_remaining_critical_agents
from analysis_dependencies import record_result_provenance
from workflow_checkpoints import execute_persistent_graph
from workflow_state import AgentGraphState


BASE = ("gemini-3.8-flash", "gemini-3.6-flash")
LITE = "gemini-3.5-flash-lite"


class Availability:
    def __init__(self, blocked=BASE, *, quota=True):
        self.blocked = set(blocked)
        self.quota = quota
        self.seen = []

    def eligible_key_slots(self, model):
        self.seen.append(model)
        return set() if model in self.blocked else {1}

    def model_retry_wait(self, model):
        return 123.0 if model in self.blocked else 0.0

    def provider_quota_exhausted(self, model):
        return self.quota and model in self.blocked


@pytest.fixture(autouse=True)
def routes(monkeypatch):
    monkeypatch.setattr(routing, "AGENT_MODELS", {agent: BASE[0] for agent in (4, 7, 14, 16, 19, 24)})
    monkeypatch.setattr(routing, "AGENT_FALLBACK_MODELS", {agent: list(BASE[1:]) for agent in (4, 7, 14, 16, 19, 24)})
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {})


@pytest.mark.parametrize("pipeline,agent", [("v1", 4), ("v2", 14), ("v3", 19), ("v4", 24)])
def test_each_mode_defers_on_essential_routes_and_preserves_context(pipeline, agent):
    context = {"pipeline_id": pipeline, "analyses": {}, "source_audit": [{"source": "kept"}]}
    before = copy.deepcopy(context)
    with pytest.raises(AgentDeferredError) as raised:
        preflight_remaining_critical_agents(context, Availability())
    assert raised.value.agent_num == agent
    assert raised.value.retry_wait_seconds == 123
    assert raised.value.provider_quota_confirmed is True
    assert context == before


def test_completed_current_role_does_not_block_or_mutate_checkpoint():
    context = {"pipeline_id": "v4", "analyses": {22: "technical", 23: "position", 24: "accepted result"}}
    record_result_provenance(24, context)
    before = copy.deepcopy(context)
    availability = Availability()
    preflight_remaining_critical_agents(context, availability)
    assert availability.seen == []
    assert context == before


@pytest.mark.parametrize("cause", ["invalidated", "upstream_changed", "current", "upstream_rerun"])
def test_stale_or_soon_invalidated_result_still_requires_route(cause):
    context = {"pipeline_id": "v4", "analyses": {22: "technical", 23: "position", 24: "accepted result"}}
    record_result_provenance(24, context)
    current_agent = None
    if cause == "invalidated":
        context["invalidated_agents"] = [24]
    elif cause == "upstream_changed":
        context["analyses"][22] = "changed technical"
    elif cause == "current":
        current_agent = 24
    else:
        current_agent = 22
    with pytest.raises(AgentDeferredError):
        preflight_remaining_critical_agents(context, Availability(), current_agent=current_agent)


def test_unvalidated_draft_is_not_a_completed_agent():
    context = {"pipeline_id": "v4", "structured_outputs": {24: {"draft": True}}}
    with pytest.raises(AgentDeferredError):
        preflight_remaining_critical_agents(context, Availability())


def test_recheck_after_reset_allows_same_input_without_sticky_block():
    availability = Availability()
    context = {"pipeline_id": "v4"}
    with pytest.raises(AgentDeferredError):
        preflight_remaining_critical_agents(context, availability)
    availability.blocked.clear()
    preflight_remaining_critical_agents(context, availability)


def test_explicit_role_candidate_is_considered_without_assuming_it_fits(monkeypatch):
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {24: True})
    availability = Availability()
    preflight_remaining_critical_agents({"pipeline_id": "v4"}, availability)
    assert LITE in availability.seen


def test_unknown_rotator_availability_never_defers():
    preflight_remaining_critical_agents({"pipeline_id": "v4"}, object())


def test_one_unknown_route_prevents_false_all_unavailable_result():
    class PartiallyUnknown(Availability):
        def eligible_key_slots(self, model):
            return None if model == BASE[1] else super().eligible_key_slots(model)

    preflight_remaining_critical_agents({"pipeline_id": "v4"}, PartiallyUnknown())


def test_cooldown_is_not_reported_as_provider_daily_quota():
    with pytest.raises(AgentDeferredError) as raised:
        preflight_remaining_critical_agents({"pipeline_id": "v4"}, Availability(quota=False))
    assert raised.value.provider_quota_confirmed is False
    assert {route["reason_code"] for route in raised.value.routes} == {"model_cooldown"}


@pytest.mark.parametrize("pipeline", ["", "not-a-mode", None])
def test_unknown_pipeline_does_not_silently_assume_v1(pipeline):
    availability = Availability()
    preflight_remaining_critical_agents({"pipeline_id": pipeline}, availability)
    assert availability.seen == []


def test_explicit_empty_route_is_not_misreported_as_provider_exhaustion():
    preflight_remaining_critical_agents({"pipeline_id": "v4", "_model_sequence_override": {24: []}}, Availability())


def test_cold_checkpoint_resume_keeps_completed_valuation_when_only_its_route_is_blocked(monkeypatch, tmp_path):
    monkeypatch.setitem(routing.AGENT_MODELS, 4, "valuation-route")
    monkeypatch.setitem(routing.AGENT_MODELS, 7, "decision-route")
    monkeypatch.setitem(routing.AGENT_FALLBACK_MODELS, 4, [])
    monkeypatch.setitem(routing.AGENT_FALLBACK_MODELS, 7, [])
    availability = Availability(blocked=[])
    calls = {4: 0, 5: 0, 7: 0}

    def builder():
        graph = StateGraph(AgentGraphState)

        async def valuation(state):
            preflight_remaining_critical_agents(state, availability, current_agent=4)
            calls[4] += 1
            context = {**state, "analyses": {4: "validated valuation"}}
            record_result_provenance(4, context)
            availability.blocked = {"decision-route"}
            return {"analyses": {"4": "validated valuation"},
                    "analysis_provenance": {"4": context["analysis_provenance"][4]}}

        async def growth(state):
            preflight_remaining_critical_agents(state, availability, current_agent=5)
            calls[5] += 1
            return {"analyses": {"5": "validated growth"}}

        async def decision(state):
            preflight_remaining_critical_agents(state, availability, current_agent=7)
            calls[7] += 1
            return {"analyses": {"7": "validated decision"}, "status": "done"}

        graph.add_node("agent_4", valuation)
        graph.add_node("agent_5", growth)
        graph.add_node("agent_7", decision)
        graph.add_edge(START, "agent_4")
        graph.add_edge("agent_4", "agent_5")
        graph.add_edge("agent_5", "agent_7")
        graph.add_edge("agent_7", END)
        return graph

    def invoke():
        return asyncio.run(execute_persistent_graph(
            graph_builder=builder(), initial_state={"pipeline_id": "v1", "analyses": {}},
            thread_id="fallback-preflight-cold-resume", checkpoint_path=tmp_path / "checkpoint.sqlite3",
        ))

    with pytest.raises(AgentDeferredError) as raised:
        invoke()
    assert raised.value.agent_num == 7
    assert calls == {4: 1, 5: 0, 7: 0}
    # A new graph/saver reads the valid valuation, despite its route now being
    # unavailable. Only unfinished nodes resume after the decision route recovers.
    availability.blocked = {"valuation-route"}
    result = invoke()
    assert result["status"] == "done"
    assert result["analyses"]["4"] == "validated valuation"
    assert calls == {4: 1, 5: 1, 7: 1}


def test_unknown_configuration_is_left_to_per_agent_admission():
    class MissingConfiguration(Availability):
        def eligible_key_slots(self, model):
            raise RuntimeError("offline provider configuration unavailable")

    preflight_remaining_critical_agents({"pipeline_id": "v4"}, MissingConfiguration())


@pytest.mark.parametrize("expired", [False, True])
def test_job_circuit_expiry_is_observed_without_rewriting_checkpoint(expired):
    context = {"pipeline_id": "v4", "_llm_model_circuits": {
        model: {"opened_until": time.time() + (-100 if expired else 100), "failures": 3}
        for model in BASE
    }}
    before = copy.deepcopy(context)
    availability = Availability(blocked=[])
    if expired:
        preflight_remaining_critical_agents(context, availability)
    else:
        with pytest.raises(AgentDeferredError) as raised:
            preflight_remaining_critical_agents(context, availability)
        assert raised.value.provider_quota_confirmed is False
    assert context == before
