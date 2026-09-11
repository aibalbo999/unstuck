"""Repairs rebuild only actual descendants, in pipeline order, atomically."""

import asyncio
import copy
from types import SimpleNamespace
from typing import get_type_hints

import pytest

from agent_runtime import audit_repair
from pipeline_modes import get_pipeline_definition
from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
from workflow_state import AgentGraphState


def _context(pipeline="v1"):
    agents = get_pipeline_definition(pipeline)["agents"]
    return {"pipeline_id": pipeline, "data": {},
            "analyses": {agent: f"original {agent}" for agent in agents},
            "structured_outputs": {agent: {"value": f"original {agent}"} for agent in agents},
            "blocking_issues": ["external:keep"]}


def _install_repair(monkeypatch, visits, *, unchanged=False, fail_agent=None):
    def repair(agent, data, context, rotator, issues):
        visits.append((agent, list(issues)))
        if agent == fail_agent:
            raise asyncio.CancelledError("cancel during downstream rebuild")
        if not unchanged:
            context["analyses"][agent] = f"repaired {agent}"
            context["structured_outputs"][agent] = {"value": f"repaired {agent}"}
        return True, "accepted"

    async def repair_async(*args, **kwargs):
        return repair(*args, **kwargs)

    monkeypatch.setattr(audit_repair, "_repair_agent_output", repair)
    monkeypatch.setattr(audit_repair, "_repair_agent_output_async", repair_async)


def _attempt(context, issues, asynchronous):
    audit = {"repair_agent_issues": issues}
    if asynchronous:
        return asyncio.run(audit_repair.attempt_final_audit_repair_async(context, audit, object()))
    return audit_repair.attempt_final_audit_repair(context, audit, object())


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("pipeline,requested,expected", [
    ("v1", {4: ["explicit valuation"]}, [4, 6, 21, 7]),
    ("v2", {14: ["explicit valuation"]}, [14, 21, 16]),
    ("v3", {18: ["explicit thesis"]}, [18, 21, 19]),
    ("v4", {22: ["explicit price"]}, [22, 24]),
    ("v1", {2: ["financial"], 4: ["explicit valuation"]}, [2, 3, 20, 4, 5, 6, 21, 7]),
])
def test_changed_upstream_rebuilds_descendants_once_in_group_order(
        pipeline, requested, expected, asynchronous, monkeypatch):
    context = _context(pipeline)
    visits = []
    _install_repair(monkeypatch, visits)
    _attempt(context, requested, asynchronous)
    assert [agent for agent, _ in visits] == expected
    for agent in expected:
        assert context["analyses"][agent] == f"repaired {agent}"
    for agent, issues in visits:
        if agent in requested:
            assert set(requested[agent]) <= set(issues)
    assert context["blocking_issues"] == ["external:keep"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_unchanged_repair_does_not_rebuild_descendants(asynchronous, monkeypatch):
    context = _context()
    visits = []
    _install_repair(monkeypatch, visits, unchanged=True)
    _attempt(context, {4: ["review"]}, asynchronous)
    assert [agent for agent, _ in visits] == [4]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_cancelled_rebuild_does_not_adopt_any_partial_result(asynchronous, monkeypatch):
    context = _context()
    before = copy.deepcopy(context)
    visits = []
    _install_repair(monkeypatch, visits, fail_agent=21)
    with pytest.raises(asyncio.CancelledError):
        _attempt(context, {4: ["review"]}, asynchronous)
    assert context == before


def test_explicit_replacement_delta_removes_old_keys_and_only_resolved_blockers():
    original = {"analyses": {"4": "old", "7": "stale"},
                "structured_outputs": {"4": {"old": True}, "7": {"old": True}},
                "parsed": {"obsolete_key": 1},
                "blocking_issues": ["Agent 4 resolved", "external:keep"]}
    context = {"analyses": {4: "new"}, "structured_outputs": {4: {"new": True}},
               "parsed": {"new_key": 2}, "blocking_issues": ["external:keep"],
               "_replace_analysis_state": True}
    hints = get_type_hints(AgentGraphState, include_extras=True)
    merged = copy.deepcopy(original)
    for key, value in graph_delta_from_legacy_context(context).items():
        metadata = getattr(hints[key], "__metadata__", ())
        merged[key] = metadata[0](merged.get(key), value) if metadata else value
    assert merged["analyses"] == {"4": "new"}
    assert merged["structured_outputs"] == {"4": {"new": True}}
    assert merged["parsed"] == {"new_key": 2}
    assert merged["blocking_issues"] == ["external:keep"]


def _finalize(context, asynchronous, passes=1):
    args = context, object()
    if asynchronous:
        return asyncio.run(audit_repair.finalize_final_audit_async(*args, max_repair_passes=passes))
    return audit_repair.finalize_final_audit(*args, max_repair_passes=passes)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_entire_final_audit_is_atomic_on_cancel(asynchronous, monkeypatch):
    context = _context()
    context["parsed"] = {"original": "accepted"}
    before = copy.deepcopy(context)
    _install_repair(monkeypatch, [], fail_agent=21)
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *args, **kwargs: {
        "critical": ["wrong valuation"], "repair_agent_issues": {4: ["valuation"]}})
    with pytest.raises(asyncio.CancelledError):
        _finalize(context, asynchronous)
    assert context == before


@pytest.mark.parametrize("asynchronous", [False, True])
def test_coverage_only_repairs_run_bounded_without_becoming_critical(asynchronous, monkeypatch):
    context = _context()
    visits = []
    _install_repair(monkeypatch, visits, unchanged=True)
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *args, **kwargs: {
        "critical": [], "warnings": ["news not assessed"],
        "coverage_repair_agent_issues": {7: ["assess news"]}})
    result = _finalize(context, asynchronous, passes=2)
    assert [agent for agent, _ in visits] == [7, 7]
    assert not result["critical"]
    assert "final_audit:repair_iteration_limit" not in context["blocking_issues"]
    assert context.get("status") != "blocked"


def test_draft_namespace_includes_current_upstream_even_with_same_graph_state():
    from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node
    namespaces = []

    class Saver:
        async def aget_tuple(self, config):
            namespaces.append(config["configurable"]["checkpoint_ns"])
            return None

    async def run():
        context = _context()
        graph_state = {"analyses": {"4": "old graph version"}}
        with checkpoint_draft_scope(Saver(), "test-thread"):
            async with quality_draft_node(7, graph_state, context):
                pass
            context["analyses"][4] = "new accepted valuation"
            async with quality_draft_node(7, graph_state, context):
                pass

    asyncio.run(run())
    assert len(set(namespaces)) == 2


def test_prompt_context_excludes_results_with_stale_upstream_provenance():
    from analysis_dependencies import initialize_result_provenance
    from context_dependencies import upstream_context_inputs
    context = _context()
    initialize_result_provenance(context)
    context["analyses"][4] = "changed upstream"
    current = upstream_context_inputs(7, context)
    assert 6 not in current["analyses"]
    assert 21 not in current["structured_outputs"]
    assert current["analyses"][5] == "original 5"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_failed_direct_repair_restores_accepted_structured_output(asynchronous, monkeypatch):
    from agent_runtime import repair_loop
    context = _context()
    before = copy.deepcopy(context)

    def provider(agent, data, candidate, rotator, **kwargs):
        candidate["structured_outputs"][agent] = {"unvalidated": True}
        return f"[Agent {agent} 執行失敗：fixture unavailable]"

    async def provider_async(*args, **kwargs):
        return provider(*args, **kwargs)

    monkeypatch.setattr(repair_loop, "run_single_agent", provider)
    monkeypatch.setattr(repair_loop, "run_single_agent_async", provider_async)
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _: {"open": False})
    args = 4, {}, context, object(), ["repair valuation"]
    result = (asyncio.run(repair_loop._repair_agent_output_async(*args)) if asynchronous
              else repair_loop._repair_agent_output(*args))
    assert not result[0]
    assert context["structured_outputs"] == before["structured_outputs"]
    assert context["analyses"] == before["analyses"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_stale_dependencies_block_even_when_audit_claims_no_critical(asynchronous, monkeypatch):
    context = _context()
    context["invalidated_agents"] = [7]
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *args, **kwargs: {"critical": [], "warnings": []})
    _finalize(context, asynchronous, passes=0)
    assert context["status"] == "blocked"
    assert "final_audit:stale_dependencies" in context["blocking_issues"]


def test_typed_checkpoint_restore_rejects_stale_reports_and_managed_risks():
    from analysis_dependencies import initialize_result_provenance
    from agent_runtime.state_report_adapter import record_agent_state_report
    from agent_state import RiskFlag
    from state_memory import initialize_agent_state
    from workflow_state import agent_state_from_graph, agent_state_to_graph
    context = _context()
    state = initialize_agent_state({"ticker": "TEST"}, run_id="dependency-test")
    for agent in (4, 6, 7):
        record_agent_state_report(state, agent, context["analyses"][agent], context["structured_outputs"][agent])
    state.risk_flags = [RiskFlag(id="external", severity="warning", category="data_quality",
                                 title="keep", impact="external", confidence=0.5)]
    initialize_result_provenance(context)
    graph = {**agent_state_to_graph(state, pipeline_id="v1"), **context}
    graph["analyses"][4] = "changed valuation"
    restored = agent_state_from_graph(graph)
    assert not restored.agent_reports
    assert [flag.id for flag in restored.risk_flags] == ["external"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_repair_invalidates_analysis_rag_including_changed_root_but_keeps_external(asynchronous, monkeypatch):
    from rag_runtime import InMemoryRagIndex, RagChunk
    context = _context()
    context["rag_index"] = InMemoryRagIndex([
        RagChunk("old4", "analysis:4", "old valuation", {}),
        RagChunk("old7", "analysis:7", "old recommendation", {}),
        RagChunk("peer5", "analysis:5", "keep same group", {}),
        RagChunk("filing", "filing", "keep raw evidence", {"agent_num": 7}),
    ])
    _install_repair(monkeypatch, [])
    _attempt(context, {4: ["review"]}, asynchronous)
    assert [chunk.chunk_id for chunk in context["rag_index"].chunks] == ["peer5", "filing"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_audit_appendix_and_telemetry_do_not_invalidate_descendants(asynchronous, monkeypatch):
    context = _context()
    visits = []

    def complete(agent, data, candidate, rotator, issues):
        visits.append(agent)
        candidate["analyses"][agent] += "\n## 系統最終稽核\n附錄修訂"
        candidate["llm_token_usage"] = {agent: {"total_tokens": 987}}
        return True, "unchanged analysis"

    async def complete_async(*args):
        return complete(*args)

    monkeypatch.setattr(audit_repair, "_repair_agent_output", complete)
    monkeypatch.setattr(audit_repair, "_repair_agent_output_async", complete_async)
    _attempt(context, {4: ["review"]}, asynchronous)
    assert visits == [4]


def test_transaction_copies_analysis_state_but_preserves_opaque_clients():
    from agent_runtime.repair_transaction import clone_repair_context
    from state_memory import initialize_agent_state
    from rag_runtime import InMemoryRagIndex, RagChunk

    class Client:
        def __deepcopy__(self, memo):
            raise AssertionError("process-local client must retain identity")

    context = _context()
    client = context["provider_client"] = Client()
    context["agent_state"] = initialize_agent_state({"ticker": "TEST"})
    context["rag_index"] = InMemoryRagIndex([RagChunk("filing", "filing", "original", {})])
    candidate = clone_repair_context(context)
    assert candidate["provider_client"] is client
    candidate["analyses"][4] = "candidate"
    candidate["agent_state"].executive_thesis = "candidate"
    candidate["rag_index"].chunks[0].text = "candidate"
    assert context["analyses"][4] == "original 4"
    assert context["agent_state"].executive_thesis is None
    assert context["rag_index"].chunks[0].text == "original"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_rejected_final_audit_identifies_uncommitted_candidate(asynchronous, monkeypatch):
    context = _context()
    before = copy.deepcopy(context["analyses"])
    _install_repair(monkeypatch, [])
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *args, **kwargs: {
        "critical": ["still invalid"], "repair_agent_issues": {4: ["valuation"]}})
    audit = _finalize(context, asynchronous)
    assert context["analyses"] == before
    assert context["status"] == "blocked"
    assert audit["repair_transaction"]["accepted"] is False
    assert audit["repair_transaction"]["audited_output_hashes"] != audit["repair_transaction"]["accepted_output_hashes"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_stale_result_rebuilds_without_new_audit_issue(asynchronous, monkeypatch):
    context = _context()
    context["invalidated_agents"] = [7]
    visits = []
    _install_repair(monkeypatch, visits)
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *args, **kwargs: {"critical": []})
    _finalize(context, asynchronous)
    assert [agent for agent, _ in visits] == [7]
    assert context["invalidated_agents"] == []
    assert context.get("status") != "blocked"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_success_removes_resolved_round_blockers_and_keeps_other_blockers(asynchronous, monkeypatch):
    context = _context()
    context["blocking_issues"].append("final_audit:repair_iteration_limit")
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *args, **kwargs: {"critical": []})
    _finalize(context, asynchronous)
    assert context["blocking_issues"] == ["external:keep"]


@pytest.mark.parametrize("managed_blocker", [
    "final_audit:repair_iteration_limit", "final_audit:dependency_rebuild_failed",
    "final_audit:stale_dependencies", "final_audit:unresolved_critical",
])
@pytest.mark.parametrize("other_blockers,expected_status,expected_route", [
    ([], "running", "chief_editor"),
    (["external:keep"], "blocked", "blocked_finalize"),
])
def test_final_audit_adapter_round_trips_resolved_blocked_status(
        managed_blocker, other_blockers, expected_status, expected_route, monkeypatch):
    from state_memory import initialize_agent_state
    from workflow_graph import route_after_final_audit
    from workflow_services import create_default_workflow_services
    from workflow_state import agent_state_to_graph

    state = {**agent_state_to_graph(initialize_agent_state({"ticker": "TEST"}), pipeline_id="v1"),
             **_context(), "status": "blocked",
             "blocking_issues": [managed_blocker, *other_blockers]}
    before = copy.deepcopy(state)
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *args, **kwargs: {
        "status": "passed", "critical": [], "warnings": [], "repair_agent_issues": {}})
    services = create_default_workflow_services(rotator=object())
    delta = asyncio.run(services.final_audit(state))
    hints = get_type_hints(AgentGraphState, include_extras=True)
    merged = copy.deepcopy(state)
    for key, value in delta.items():
        metadata = getattr(hints[key], "__metadata__", ())
        merged[key] = metadata[0](merged.get(key), value) if metadata else value

    assert state == before
    assert merged["blocking_issues"] == other_blockers
    assert delta.get("status") == expected_status
    assert merged["status"] == expected_status
    assert route_after_final_audit(merged) == expected_route


def test_removed_report_risks_without_source_agents_do_not_become_external():
    from analysis_dependencies import invalidate_analysis_results
    from agent_state import AgentReport, RiskFlag
    from state_memory import initialize_agent_state
    from workflow_state import agent_state_from_graph, agent_state_to_graph
    state = initialize_agent_state({"ticker": "TEST"})
    owned = RiskFlag(id="owned-no-agents", severity="warning", category="valuation", title="old", impact="old", confidence=0.5)
    external = owned.model_copy(update={"id": "external", "title": "provider"})
    mixed = owned.model_copy(update={"id": "mixed", "source_agents": ["4", "6"]})
    state.agent_reports["6"] = AgentReport(agent_id="6", role="debate", markdown="old", risk_flags=[owned])
    state.risk_flags = [owned, external, mixed]
    context = {**_context(), "agent_state": state}
    graph = {**agent_state_to_graph(state, pipeline_id="v1"), "invalidated_agents": [6]}
    invalidate_analysis_results(context, [6])
    assert [flag.id for flag in state.risk_flags] == ["external"]
    assert [flag.id for flag in agent_state_from_graph(graph).risk_flags] == ["external"]


def test_deferred_final_audit_resumes_only_uncommitted_round_in_real_graph(monkeypatch):
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import START, END, StateGraph
    from agent_runtime.deferred import AgentDeferredError
    from state_memory import initialize_agent_state
    from workflow_services import create_default_workflow_services
    from workflow_state import agent_state_to_graph
    visits, prior = [], []
    allow_finish = False

    async def complete(agent, data, candidate, rotator, issues):
        visits.append(agent)
        if agent == 21 and not allow_finish:
            raise AgentDeferredError(agent, [{"model_id": "test-model", "retry_wait_seconds": 1}])
        candidate["analyses"][agent] = f"repaired {agent}"
        candidate["structured_outputs"][agent] = {"value": f"repaired {agent}"}
        return True, "accepted"

    def audit(context, **kwargs):
        issues = {4: ["valuation"]} if context["analyses"].get(4) == "original 4" else {}
        return {"critical": ["old valuation"] if issues else [], "repair_agent_issues": issues}

    monkeypatch.setattr(audit_repair, "_repair_agent_output_async", complete)
    monkeypatch.setattr(audit_repair, "run_final_report_audit", audit)

    async def execute():
        nonlocal allow_finish
        services = create_default_workflow_services(rotator=object())
        builder = StateGraph(AgentGraphState)

        async def previous_node(state):
            prior.append("already successful")
            return {}

        builder.add_node("previous", previous_node)
        builder.add_node("final_audit", services.final_audit)
        builder.add_edge(START, "previous")
        builder.add_edge("previous", "final_audit")
        builder.add_edge("final_audit", END)
        graph = builder.compile(checkpointer=MemorySaver())
        state = {**agent_state_to_graph(initialize_agent_state({"ticker": "TEST"}), pipeline_id="v1"), **_context()}
        config = {"configurable": {"thread_id": "repair-deferred"}}
        with pytest.raises(AgentDeferredError):
            await graph.ainvoke(state, config)
        snapshot = await graph.aget_state(config)
        assert snapshot.next == ("final_audit",)
        assert snapshot.values["analyses"][4] == "original 4"
        assert snapshot.values["analyses"][7] == "original 7"
        allow_finish = True
        result = await graph.ainvoke(None, config)
        assert result["analyses"]["4"] == "repaired 4"
        assert result["analyses"]["7"] == "repaired 7"
        assert result["invalidated_agents"] == []

    asyncio.run(execute())
    assert prior == ["already successful"]
    assert visits == [4, 6, 21, 4, 6, 21, 7]


@pytest.mark.parametrize("pipeline,expected", [("v1", "market_context.v1"), ("v2", "market_context.v1"),
                                               ("v3", "market_context.v1"), ("v4", None)])
def test_new_workflow_market_contract_is_enabled_for_only_longer_horizon_modes(pipeline, expected):
    from workflow_services import initialize_graph_state
    state = initialize_graph_state({"ticker": "TEST"}, pipeline_id=pipeline)
    assert state.get("market_context_contract_version") == expected


def test_market_manifest_roundtrip_and_replacement_do_not_restore_invalidated_manifest():
    from state_memory import initialize_agent_state
    from workflow_state import agent_state_to_graph, merge_dicts
    state = agent_state_to_graph(initialize_agent_state({"ticker": "TEST"}), pipeline_id="v1")
    services = SimpleNamespace(progress_callback=None, cancel_check=None)
    assert not legacy_context_from_graph(state, services).get("market_context_contract_version")
    state.update(market_context_contract_version="market_context.v1", market_context_manifests={"7": {"old": True}})
    context = legacy_context_from_graph(state, services)
    assert context["market_context_contract_version"] == "market_context.v1"
    assert context["market_context_manifests"] == {7: {"old": True}}
    context["market_context_manifests"] = {}
    context["_replace_analysis_state"] = True
    delta = graph_delta_from_legacy_context(context)
    assert merge_dicts(state["market_context_manifests"], delta["market_context_manifests"]) == {}


@pytest.mark.parametrize("stored_manifest", [None, {"saved": "successful attempt"}])
def test_restored_draft_uses_only_its_saved_successful_manifest(stored_manifest):
    from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node, initial_or_checkpointed_draft

    class Saver:
        async def aget_tuple(self, config):
            fingerprint = config["configurable"]["checkpoint_ns"].rsplit("/", 1)[-1]
            record = {"status": "unvalidated", "agent_num": 7, "input_fingerprint": fingerprint,
                      "text": "saved draft", "structured_output": {"assessment": "saved"}}
            if stored_manifest is not None:
                record["market_context_manifest"] = stored_manifest
            return SimpleNamespace(config=config, checkpoint={"channel_values": {"quality_draft": record}, "channel_versions": {}})

    async def execute():
        context = _context()
        context["market_context_manifests"] = {7: {"current": "wrong version"}}
        context["_market_context_attempt_manifests"] = {7: {"attempt": "also wrong"}}
        with checkpoint_draft_scope(Saver(), "draft-manifest"):
            async with quality_draft_node(7, {}, context):
                async def never_generate(*args):
                    raise AssertionError("saved draft should be revalidated")
                text = await initial_or_checkpointed_draft(7, {}, context, object(), never_generate)
                assert text == "saved draft"
                assert context["market_context_manifests"].get(7) == stored_manifest
                if stored_manifest is not None:
                    assert context["market_context_manifests"][7] is not stored_manifest

    asyncio.run(execute())


def test_draft_checkpoint_saves_manifest_from_successful_output():
    from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node, checkpoint_unvalidated_draft
    records = []

    class Saver:
        async def aget_tuple(self, config):
            return None

        def get_next_version(self, *args):
            return 1

        async def aput(self, config, checkpoint, *args):
            records.append(checkpoint["channel_values"]["quality_draft"])
            return config

    async def execute():
        context = _context()
        context["market_context_manifests"] = {7: {"successful": True}}
        context["_market_context_attempt_manifests"] = {7: {"failed": True}}
        with checkpoint_draft_scope(Saver(), "draft-manifest"):
            async with quality_draft_node(7, {}, context):
                await checkpoint_unvalidated_draft(7, "unvalidated text", context)

    asyncio.run(execute())
    assert records[0]["market_context_manifest"] == {"successful": True}


def test_successful_agent_node_checkpoints_its_output_manifest(monkeypatch):
    import workflow_services
    from state_memory import initialize_agent_state
    from workflow_state import agent_state_to_graph

    async def complete(agent, data, context, *args):
        context["market_context_manifests"] = {agent: {"successful": "this output"}}
        return agent, "accepted recommendation"

    monkeypatch.setattr(workflow_services, "run_agent_with_quality_gates_async", complete)
    state = agent_state_to_graph(initialize_agent_state({"ticker": "TEST"}), pipeline_id="v1")
    state["market_context_contract_version"] = "market_context.v1"
    services = SimpleNamespace(progress_callback=None, cancel_check=None)
    result = asyncio.run(workflow_services.run_agent_node_adapter(7, state, services, object()))
    assert result["market_context_manifests"] == {"7": {"successful": "this output"}}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_parsed_and_real_audit_only_see_current_dependency_versions(asynchronous, monkeypatch):
    from analysis_dependencies import stale_agent_numbers
    context = _context()
    context["invalidated_agents"] = [7]
    _install_repair(monkeypatch, [])

    def parse(candidate):
        assert not stale_agent_numbers(candidate), "parsed consumed stale analysis"
        return {}

    def audit(candidate, **kwargs):
        assert not stale_agent_numbers(candidate), "audit consumed stale analysis"
        return {"critical": []}

    monkeypatch.setattr(audit_repair, "parse_structured_data", parse)
    monkeypatch.setattr(audit_repair, "run_final_report_audit", audit)
    _finalize(context, asynchronous)


@pytest.mark.parametrize("operation", ["attempt", "finalize"])
def test_public_legacy_sync_entry_uses_same_dependency_plan(operation, monkeypatch):
    import agent_runner as public
    context = _context()
    visits = []

    def complete(agent, data, candidate, rotator, issues):
        visits.append(agent)
        candidate["analyses"][agent] = f"repaired {agent}"
        candidate["structured_outputs"][agent] = {"value": f"repaired {agent}"}
        return True, "accepted"

    def audit(candidate, **kwargs):
        issues = {4: ["valuation"]} if candidate["analyses"][4] == "original 4" else {}
        return {"critical": ["wrong valuation"] if issues else [], "repair_agent_issues": issues}

    monkeypatch.setattr(public, "_repair_agent_output", complete)
    monkeypatch.setattr(public, "run_final_report_audit", audit)
    if operation == "attempt":
        public.attempt_final_audit_repair(context, audit(context), object())
    else:
        public.finalize_final_audit(context, object(), max_repair_passes=1)
    assert visits == [4, 6, 21, 7]
    assert context["analyses"][7] == "repaired 7"
