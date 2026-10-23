"""Local fallback trigger receipts survive successful nodes and cold resumes."""
import asyncio
from copy import deepcopy

import pytest
from langgraph.graph import END, StateGraph

from agent_runtime.deferred import AgentDeferredError
from agent_runtime.deterministic_fallbacks import _apply_deterministic_fallback
from analysis_dependencies import record_result_provenance
from analysis_input_provenance import freeze_analysis_inputs
from data_trust_snapshot import build_data_snapshot
from report_analysis_completeness import assess_report_analysis_completeness
from workflow_checkpoints import execute_persistent_graph
from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
from workflow_services import create_default_workflow_services, initialize_graph_state
from workflow_state import AgentGraphState, append_unique


def fallback_context():
    data = {"ticker": "TEST", "company_name": "Test", "current_price": 20}
    freeze_analysis_inputs(data)
    context = {"pipeline_id": "v4", "ticker": "TEST", "data": data,
               "analyses": {22: "technical", 23: "risk", 24: "unvalidated draft"},
               "structured_outputs": {}}
    for agent in (22, 23):
        record_result_provenance(agent, context)
    assert _apply_deterministic_fallback(
        24, data, context, "unvalidated draft", ["source mismatch"],
        "quality_fallback_after_retries", raw_failure="fixture invalid source",
        metadata={"attempts": 2, "limit": 2})[0]
    record_result_provenance(24, context)
    return context


def test_trigger_receipt_deep_copy_survives_adapters_and_snapshot():
    context = fallback_context()
    original = deepcopy(context["deterministic_fallbacks"])
    state = initialize_graph_state(context["data"], pipeline_id="v4")
    delta = graph_delta_from_legacy_context(context)
    assert delta.get("deterministic_fallbacks") == original
    context["deterministic_fallbacks"][0]["metadata"]["attempts"] = 999
    assert delta["deterministic_fallbacks"] == original
    state.update(delta)
    restored = legacy_context_from_graph(state, create_default_workflow_services(rotator=object()))
    assert restored.get("deterministic_fallbacks") == original
    snapshot = build_data_snapshot(restored)
    assert snapshot["deterministic_fallbacks"] == original
    assert assess_report_analysis_completeness(restored)["status"] == "degraded"
    output = snapshot["rerun_context"]["structured_outputs"]["24"]
    assert output["source_assessment"]["output_completion"]["status"] == "local_fallback"
    assert output["source_assessment"]["output_completion"]["provider_finish_observed"] is False
    restored["deterministic_fallbacks"][0]["metadata"]["attempts"] = 777
    assert state["deterministic_fallbacks"] == original
    assert append_unique(original, original) == original


def test_cold_checkpoint_keeps_trigger_without_rerunning_successful_fallback(tmp_path):
    calls = {"fallback": 0, "pending": 0}
    control = {"available": False}
    context = fallback_context()
    original = deepcopy(context["deterministic_fallbacks"])
    state = initialize_graph_state(context["data"], pipeline_id="v4")

    async def fallback(_):
        calls["fallback"] += 1
        return graph_delta_from_legacy_context(context)

    async def pending(current):
        calls["pending"] += 1
        if not control["available"]:
            raise AgentDeferredError(24, [{"model_id": "fixture", "retry_wait_seconds": 60}])
        restored = legacy_context_from_graph(current, create_default_workflow_services(rotator=object()))
        assert build_data_snapshot(restored)["deterministic_fallbacks"] == original
        return {}

    graph = StateGraph(AgentGraphState)
    graph.add_node("fallback", fallback)
    graph.add_node("pending", pending)
    graph.set_entry_point("fallback")
    graph.add_edge("fallback", "pending")
    graph.add_edge("pending", END)

    def execute():
        return asyncio.run(execute_persistent_graph(graph_builder=graph, initial_state=state,
            thread_id="receipt-job", checkpoint_path=tmp_path / "receipt.sqlite3"))

    with pytest.raises(AgentDeferredError):
        execute()
    control["available"] = True
    result = execute()
    assert result["deterministic_fallbacks"] == original
    assert calls == {"fallback": 1, "pending": 2}


def test_successful_agent_adapter_exports_trigger_receipt(monkeypatch):
    import workflow_services

    original = fallback_context()
    state = initialize_graph_state(original["data"], pipeline_id="v4")
    state.update(graph_delta_from_legacy_context({**original, "deterministic_fallbacks": []}))
    monkeypatch.setattr(workflow_services, "preflight_remaining_critical_agents", lambda *a, **k: None)

    async def fallback(agent, data, context, *args):
        context["deterministic_fallbacks"] = deepcopy(original["deterministic_fallbacks"])
        return 24, original["analyses"][24]

    monkeypatch.setattr(workflow_services, "run_agent_with_quality_gates_async", fallback)
    delta = asyncio.run(workflow_services.run_agent_node_adapter(
        24, state, create_default_workflow_services(rotator=object()), object()))
    assert delta.get("deterministic_fallbacks") == original["deterministic_fallbacks"]
