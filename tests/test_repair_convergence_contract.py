"""A bounded audit resumes qualified work without publishing partial repairs."""

import asyncio
import copy
import json
from types import SimpleNamespace
from typing import get_type_hints

import pytest

from agent_runtime import audit_repair
from analysis_dependencies import stale_agent_numbers
from pipeline_modes import get_pipeline_definition


def context_for_repair():
    agents = get_pipeline_definition("v1")["agents"]
    return {
        "pipeline_id": "v1",
        "data": {"ticker": "TEST", "company_name": "Test", "frozen": {"cutoff": "2026-10-18", "value": -123}},
        "analyses": {agent: f"original {agent}" for agent in agents},
        "structured_outputs": {agent: {"value": f"original {agent}"} for agent in agents},
        "blocking_issues": ["external:keep", "Agent 4 incorrect original"],
        "audit_repair_log": ["prior failure must remain"],
    }


def finalize(context, asynchronous, passes=2):
    if asynchronous:
        return asyncio.run(audit_repair.finalize_final_audit_async(
            context, object(), max_repair_passes=passes))
    return audit_repair.finalize_final_audit(context, object(), max_repair_passes=passes)


def install_partial_repair(monkeypatch, accepted, *, always_fail=False):
    visits = []
    snapshots = []
    accepted_before = copy.deepcopy(accepted)

    def repair(agent, data, candidate, rotator, issues):
        # The caller must not see any intermediate accepted or rejected draft.
        assert accepted == accepted_before
        assert data == accepted_before["data"]
        visits.append(agent)
        if agent == 7:
            assert "full recommendation contract" in issues
        count = candidate.setdefault("repair_attempt_counts", {})
        count[agent] = count.get(agent, 0) + 1
        assert count[agent] <= 2
        if agent == 6:
            assert candidate["analyses"][4] == "repaired 4"
            assert candidate["structured_outputs"][4] == {"value": "repaired 4"}
            if always_fail or visits.count(6) == 1:
                candidate["analyses"][6] = "REJECTED candidate"
                candidate["structured_outputs"][6] = {"unvalidated": True}
                candidate.setdefault("repair_candidate_history", {}).setdefault("6", []).append("rejected")
                candidate["agent_quality_retry_counts"] = {6: count[6]}
                candidate["llm_token_usage"] = {6: {"total_tokens": count[6] * 100}}
                return False, "contract incomplete"
        candidate["analyses"][agent] = f"repaired {agent}"
        candidate["structured_outputs"][agent] = {"value": f"repaired {agent}"}
        candidate["blocking_issues"] = [issue for issue in candidate["blocking_issues"]
                                        if not issue.startswith(f"Agent {agent} ")]
        return True, "agent contract passed"

    async def repair_async(*args, **kwargs):
        return repair(*args, **kwargs)

    def audit(candidate, **kwargs):
        assert not stale_agent_numbers(candidate)
        snapshots.append(copy.deepcopy(candidate["analyses"]))
        issues = {4: ["valuation incorrect"], 7: ["full recommendation contract"]} if candidate["analyses"][4] == "original 4" else {}
        return {"critical": ["wrong valuation"] if issues else [], "repair_agent_issues": issues}

    monkeypatch.setattr(audit_repair, "_repair_agent_output", repair)
    monkeypatch.setattr(audit_repair, "_repair_agent_output_async", repair_async)
    monkeypatch.setattr(audit_repair, "run_final_report_audit", audit)
    return visits, snapshots


@pytest.mark.parametrize("asynchronous", [False, True])
def test_next_audit_pass_resumes_current_qualified_upstream(monkeypatch, asynchronous):
    context = context_for_repair()
    frozen = copy.deepcopy(context["data"])
    visits, snapshots = install_partial_repair(monkeypatch, context)
    result = finalize(context, asynchronous)
    assert visits == [4, 6, 6, 21, 7]
    assert not result["critical"]
    assert context["analyses"][4] == "repaired 4"
    assert context["analyses"][7] == "repaired 7"
    assert context["analyses"][5] == "original 5"
    assert not stale_agent_numbers(context)
    assert context["data"] == frozen
    assert context["repair_iteration_count"] == 2
    assert context["repair_attempt_counts"] == {4: 1, 6: 2, 21: 1, 7: 1}
    assert context["repair_candidate_history"]["6"] == ["rejected"]
    assert context["audit_repair_log"][0] == "prior failure must remain"
    assert any("contract incomplete" in entry for entry in context["audit_repair_log"])
    assert context["blocking_issues"] == ["external:keep"]
    assert all("REJECTED candidate" not in values.values() for values in snapshots)
    assert not any(key.startswith("_repair_pending") for key in context)


def install_deferred_provider(monkeypatch):
    from agent_runtime import repair_loop
    from agent_runtime.deferred import failed_route_result

    calls = []

    def provider(agent, data, candidate, rotator, **kwargs):
        calls.append(agent)
        assert kwargs["max_retries"] == 1
        usage = candidate.setdefault("llm_token_usage", {}).setdefault(agent, {"total_tokens": 0})
        usage["total_tokens"] += 17
        candidate.setdefault("audit_repair_log", []).append("provider 503 deferred")
        candidate["analyses"][agent] = "UNACCEPTED partial response"
        candidate["structured_outputs"][agent] = {"unvalidated": True}
        return failed_route_result(agent, "503 UNAVAILABLE", [{
            "model_id": "offline", "retry_wait_seconds": 300,
            "reason_code": "temporary_provider_failure", "provider_quota_confirmed": False,
        }])

    async def provider_async(*args, **kwargs):
        return provider(*args, **kwargs)

    monkeypatch.setattr(audit_repair, "run_single_agent", provider)
    monkeypatch.setattr(audit_repair, "run_single_agent_async", provider_async)
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _: {"open": False})
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *_args, **_kwargs: {
        "critical": ["industry requires repair"], "warnings": [],
        "repair_agent_issues": {11: ["industry requires repair"]}})
    return calls


@pytest.mark.parametrize("asynchronous", [False, True])
def test_native_deferred_reentry_preserves_metadata_without_extra_budget(monkeypatch, asynchronous):
    from agent_runtime.deferred import AgentDeferredError

    context = context_for_repair()
    context["final_audit"] = {"warnings": ["accepted version warning"]}
    before = copy.deepcopy(context)
    calls = install_deferred_provider(monkeypatch)
    for spent in (1, 2):
        with pytest.raises(AgentDeferredError) as caught:
            finalize(context, asynchronous)
        assert caught.value.retry_wait_seconds == 300
        assert caught.value.provider_quota_confirmed is False
        assert context.get("repair_attempt_counts") == {11: spent}
        assert context.get("repair_iteration_count") == spent
        assert context["repair_candidate_history"]["11"]["calls"] == spent
        assert context["repair_candidate_history"]["11"]["call_failures"] == spent
        assert context["llm_token_usage"] == {11: {"total_tokens": 17 * spent}}
        assert context["audit_repair_log"].count("provider 503 deferred") == spent
        for field in ("analyses", "structured_outputs", "data", "blocking_issues", "final_audit"):
            assert context[field] == before[field]
    result = finalize(context, asynchronous)
    assert calls == [11, 11]
    assert result["repair_transaction"]["accepted"] is False
    assert context["repair_attempt_counts"] == {11: 2}
    assert context["repair_iteration_count"] == 2
    assert "accepted version warning" in result["warnings"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_standalone_deferred_round_preserves_spent_metadata(monkeypatch, asynchronous):
    from agent_runtime.deferred import AgentDeferredError

    context = context_for_repair()
    before = copy.deepcopy(context)
    install_deferred_provider(monkeypatch)
    audit = {"repair_agent_issues": {11: ["repair industry"]}}
    with pytest.raises(AgentDeferredError):
        if asynchronous:
            asyncio.run(audit_repair.attempt_final_audit_repair_async(context, audit, object()))
        else:
            audit_repair.attempt_final_audit_repair(context, audit, object())
    assert context.get("repair_attempt_counts") == {11: 1}
    assert context["repair_candidate_history"]["11"]["call_failures"] == 1
    assert context["llm_token_usage"] == {11: {"total_tokens": 17}}
    for field in ("analyses", "structured_outputs", "data", "blocking_issues"):
        assert context[field] == before[field]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_downstream_defer_keeps_all_spent_counts_but_no_partial_analysis(monkeypatch, asynchronous):
    from agent_runtime.deferred import AgentDeferredError

    context = context_for_repair()
    before = copy.deepcopy(context)
    visits, _ = install_partial_repair(monkeypatch, context)
    original = audit_repair._repair_agent_output
    deferred = AgentDeferredError(6, [{"model_id": "offline", "retry_wait_seconds": 300}])

    def repair(agent, *args, **kwargs):
        result = original(agent, *args, **kwargs)
        if agent == 6:
            raise deferred
        return result

    async def repair_async(*args, **kwargs):
        return repair(*args, **kwargs)

    monkeypatch.setattr(audit_repair, "_repair_agent_output", repair)
    monkeypatch.setattr(audit_repair, "_repair_agent_output_async", repair_async)
    with pytest.raises(AgentDeferredError) as caught:
        finalize(context, asynchronous)
    assert caught.value is deferred
    assert visits == [4, 6]
    assert context["repair_attempt_counts"] == {4: 1, 6: 1}
    assert context["repair_iteration_count"] == 1
    assert context["repair_candidate_history"]["6"] == ["rejected"]
    assert context["llm_token_usage"] == {6: {"total_tokens": 100}}
    for field in ("analyses", "structured_outputs", "data", "blocking_issues"):
        assert context[field] == before[field]
    assert not any(key.startswith("_repair_") for key in context)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_rejected_atomic_audit_keeps_original_warnings_and_blockers(monkeypatch, asynchronous):
    context = context_for_repair()
    context["final_audit"] = {"critical": ["accepted version critical"], "warnings": ["accepted version warning"]}
    before = copy.deepcopy(context)
    install_partial_repair(monkeypatch, context, always_fail=True)
    result = finalize(context, asynchronous)
    assert set(before["blocking_issues"]) <= set(context["blocking_issues"])
    assert "accepted version warning" in result["warnings"]
    assert "accepted version critical" in result["critical"]
    assert context["analyses"] == before["analyses"]


@pytest.mark.parametrize("failed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_original_version_warning_survives_only_when_transaction_rolls_back(monkeypatch, asynchronous, failed):
    context = context_for_repair()
    install_partial_repair(monkeypatch, context, always_fail=failed)
    original_audit = audit_repair.run_final_report_audit

    def audit(candidate, **kwargs):
        result = original_audit(candidate, **kwargs)
        result["warnings"] = ["original-only warning"] if candidate["analyses"][4] == "original 4" else []
        return result

    monkeypatch.setattr(audit_repair, "run_final_report_audit", audit)
    result = finalize(context, asynchronous)
    assert ("original-only warning" in result["warnings"]) is failed


@pytest.mark.parametrize("asynchronous", [False, True])
def test_preserved_deferred_metadata_can_roundtrip_existing_graph_delta(monkeypatch, asynchronous):
    from agent_runtime.deferred import AgentDeferredError
    from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
    from workflow_services import initialize_graph_state
    from workflow_state import AgentGraphState

    services = SimpleNamespace(progress_callback=None, cancel_check=None)
    state = initialize_graph_state(context_for_repair()["data"], pipeline_id="v1")
    source = context_for_repair()
    for field in ("analyses", "structured_outputs", "blocking_issues", "audit_repair_log"):
        state[field] = source[field]
    original = copy.deepcopy(state)
    context = legacy_context_from_graph(state, services)
    install_deferred_provider(monkeypatch)
    with pytest.raises(AgentDeferredError):
        finalize(context, asynchronous)
    delta = graph_delta_from_legacy_context(context)
    hints = get_type_hints(AgentGraphState, include_extras=True)
    for key, value in delta.items():
        metadata = getattr(hints[key], "__metadata__", ())
        state[key] = metadata[0](state.get(key), value) if metadata else value
    restored = legacy_context_from_graph(json.loads(json.dumps(state)), services)
    assert restored["repair_attempt_counts"] == {"11": 1}
    assert restored["repair_iteration_count"] == 1
    assert restored["repair_candidate_history"]["11"]["call_failures"] == 1
    assert restored["llm_token_usage"] == {11: {"total_tokens": 17}}
    assert restored["analyses"] == original["analyses"]
    assert restored["structured_outputs"] == original["structured_outputs"]
    assert restored["blocking_issues"] == original["blocking_issues"]


def graph_state_for_repair():
    from workflow_services import initialize_graph_state

    source = context_for_repair()
    state = initialize_graph_state(source["data"], pipeline_id="v1")
    for field in ("analyses", "structured_outputs", "blocking_issues", "audit_repair_log"):
        state[field] = {str(key): value for key, value in source[field].items()} if isinstance(source[field], dict) else source[field]
    state["final_audit"] = {"warnings": ["accepted version warning"]}
    return state


async def audit_sidecars(saver, thread_id):
    return [item async for item in saver.alist({"configurable": {"thread_id": thread_id}})
            if item.config["configurable"]["checkpoint_ns"] == "final_audit_metadata"]


def test_deferred_graph_resume_cannot_reset_repair_budget(tmp_path, monkeypatch):
    from agent_runtime.deferred import AgentDeferredError
    from langgraph.graph import END, START, StateGraph
    from workflow_checkpoints import open_sqlite_checkpointer
    from workflow_quality_drafts import checkpoint_draft_scope
    from workflow_services import create_default_workflow_services
    from workflow_state import AgentGraphState

    state = graph_state_for_repair()
    before = copy.deepcopy(state)
    calls = install_deferred_provider(monkeypatch)
    services = create_default_workflow_services(rotator=object())
    builder = StateGraph(AgentGraphState)
    builder.add_node("final_audit", services.final_audit)
    builder.add_edge(START, "final_audit")
    builder.add_edge("final_audit", END)

    async def run():
        config = {"configurable": {"thread_id": "deferred-final-audit-budget"}}
        for attempt in range(3):
            async with open_sqlite_checkpointer(tmp_path / "deferred-budget.sqlite3") as saver:
                graph = builder.compile(checkpointer=saver)
                with checkpoint_draft_scope(saver, config["configurable"]["thread_id"]):
                    try:
                        await graph.ainvoke(state if attempt == 0 else None, config)
                    except AgentDeferredError as exc:
                        assert exc.retry_wait_seconds == 300
                        assert exc.provider_quota_confirmed is False
                snapshot = await graph.aget_state(config)
                assert snapshot.values["analyses"] == before["analyses"]
                assert snapshot.values["structured_outputs"] == before["structured_outputs"]
                assert snapshot.values["raw_financial_data"] == before["raw_financial_data"]
                if attempt < 2:
                    assert snapshot.next == ("final_audit",)
                    assert snapshot.values["final_audit"] == before["final_audit"]
                    assert snapshot.values["blocking_issues"] == before["blocking_issues"]
                    records = await audit_sidecars(saver, config["configurable"]["thread_id"])
                    record = records[0].checkpoint["channel_values"]["final_audit_metadata"]
                    assert record["status"] == "ready"
                    assert record["metadata"]["repair_iteration_count"] == attempt + 1
                    assert record["metadata"]["llm_token_usage"] == {11: {"total_tokens": 17 * (attempt + 1)}}
                    for item in records:
                        payload = item.checkpoint["channel_values"]["final_audit_metadata"]
                        assert set(payload["metadata"]) <= {
                            "repair_attempt_counts", "repair_iteration_count", "repair_candidate_history",
                            "audit_repair_log", "agent_quality_retry_counts", "_llm_model_circuits",
                            "llm_token_usage", "_runtime_events", "execution_trace", "deterministic_fallbacks",
                        }
                        serialized = json.dumps(payload)
                        assert "UNACCEPTED partial response" not in serialized
                        assert "original 11" not in serialized and "cutoff" not in serialized
        assert len(calls) <= 2, "failed node discarded metadata; third provider call exceeds the original budget"
        assert calls == [11, 11]
        assert snapshot.values["status"] == "blocked"
        assert snapshot.values["repair_attempt_counts"] == {"11": 2}
        assert snapshot.values["repair_iteration_count"] == 2
        assert snapshot.values["repair_candidate_history"]["11"]["call_failures"] == 2
        assert snapshot.values["llm_token_usage"] == {"11": {"total_tokens": 34}}
        assert "accepted version warning" in snapshot.values["final_audit"]["warnings"]
        assert set(before["blocking_issues"]) <= set(snapshot.values["blocking_issues"])

    asyncio.run(run())


@pytest.mark.parametrize("changed_identity", ["thread", "run", "input", "accepted", "prompt"])
def test_same_job_identity_drift_is_rejected_but_new_job_is_independent(tmp_path, monkeypatch, changed_identity):
    from agent_runtime.deferred import AgentDeferredError
    from workflow_checkpoints import open_sqlite_checkpointer
    from workflow_quality_drafts import checkpoint_draft_scope
    from workflow_services import create_default_workflow_services

    state = graph_state_for_repair()
    changed = copy.deepcopy(state)
    if changed_identity == "run":
        changed["run_id"] = "different-run"
    elif changed_identity == "input":
        changed["raw_financial_data"]["input"]["frozen"]["value"] = -456
    elif changed_identity == "accepted":
        changed["analyses"]["11"] = "another accepted version"
    elif changed_identity == "prompt":
        changed["prompt_fingerprint"] = "different-contract"
    before = copy.deepcopy(state)
    calls = install_deferred_provider(monkeypatch)
    services = create_default_workflow_services(rotator=object())
    observed = []
    audit = audit_repair.run_final_report_audit

    def inspect(candidate, **kwargs):
        observed.append((copy.deepcopy(candidate["repair_attempt_counts"]),
                         candidate["repair_iteration_count"], copy.deepcopy(candidate["llm_token_usage"])))
        return audit(candidate, **kwargs)

    monkeypatch.setattr(audit_repair, "run_final_report_audit", inspect)

    async def invoke(selected, thread="job"):
        async with open_sqlite_checkpointer(tmp_path / "identity.sqlite3") as saver:
            with checkpoint_draft_scope(saver, thread):
                return await services.final_audit(selected)

    async def run():
        for _ in range(2):
            with pytest.raises(AgentDeferredError):
                await invoke(state)
        assert calls == [11, 11]
        if changed_identity == "thread":
            with pytest.raises(AgentDeferredError):
                await invoke(changed, "other-job")
            assert calls == [11, 11, 11]
        else:
            with pytest.raises(RuntimeError, match="refusing to reset budget"):
                await invoke(changed)
            assert calls == [11, 11]
        result = await invoke(state)
        assert result["status"] == "blocked"
        assert result["repair_attempt_counts"] == {"11": 2}
        assert result["repair_iteration_count"] == 2
        assert result["llm_token_usage"] == {"11": {"total_tokens": 34}}
        assert state == before

    asyncio.run(run())
    expected = [({}, 0, {}), ({11: 1}, 1, {11: {"total_tokens": 17}})]
    if changed_identity == "thread":
        expected.append(({}, 0, {}))
    assert observed[:len(expected)] == expected
    final_checks = observed[len(expected):]
    assert final_checks
    assert all(item == ({11: 2}, 2, {11: {"total_tokens": 34}}) for item in final_checks)


@pytest.mark.parametrize("write_status", ["running", "ready"])
def test_audit_metadata_write_failure_cannot_reopen_uncertain_budget(tmp_path, monkeypatch, write_status):
    from agent_runtime.deferred import AgentDeferredError
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from workflow_checkpoints import open_sqlite_checkpointer
    from workflow_quality_drafts import checkpoint_draft_scope
    from workflow_services import create_default_workflow_services

    state = graph_state_for_repair()
    before = copy.deepcopy(state)
    calls = install_deferred_provider(monkeypatch)
    services = create_default_workflow_services(rotator=object())
    original_put = AsyncSqliteSaver.aput

    async def fail_write(self, config, checkpoint, *args, **kwargs):
        record = checkpoint["channel_values"].get("final_audit_metadata", {})
        if record.get("status") == write_status:
            raise OSError("test audit metadata write failure")
        return await original_put(self, config, checkpoint, *args, **kwargs)

    monkeypatch.setattr(AsyncSqliteSaver, "aput", fail_write)

    async def run():
        async with open_sqlite_checkpointer(tmp_path / "failed-write.sqlite3") as saver:
            with checkpoint_draft_scope(saver, "job"):
                with pytest.raises(OSError, match="audit metadata write failure") as caught:
                    await services.final_audit(state)
                if write_status == "ready":
                    assert isinstance(caught.value.__context__, AgentDeferredError)
        monkeypatch.setattr(AsyncSqliteSaver, "aput", original_put)
        async with open_sqlite_checkpointer(tmp_path / "failed-write.sqlite3") as saver:
            with checkpoint_draft_scope(saver, "job"):
                if write_status == "ready":
                    with pytest.raises(RuntimeError, match="refusing to reset budget"):
                        await services.final_audit(state)
                else:
                    assert not calls
                    with pytest.raises(AgentDeferredError):
                        await services.final_audit(state)
        assert state == before

    asyncio.run(run())
    assert calls == [11]


def test_audit_metadata_read_failure_stops_before_provider(tmp_path, monkeypatch):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from workflow_checkpoints import open_sqlite_checkpointer
    from workflow_quality_drafts import checkpoint_draft_scope
    from workflow_services import create_default_workflow_services

    state = graph_state_for_repair()
    calls = install_deferred_provider(monkeypatch)
    services = create_default_workflow_services(rotator=object())

    async def unavailable(*args, **kwargs):
        raise OSError("test audit metadata read failure")

    monkeypatch.setattr(AsyncSqliteSaver, "aget_tuple", unavailable)

    async def run():
        async with open_sqlite_checkpointer(tmp_path / "failed-read.sqlite3") as saver:
            with checkpoint_draft_scope(saver, "job"):
                with pytest.raises(OSError, match="audit metadata read failure"):
                    await services.final_audit(state)

    asyncio.run(run())
    assert not calls


@pytest.mark.parametrize("asynchronous", [False, True])
def test_exhausted_partial_repair_preserves_accepted_views_and_failure_costs(monkeypatch, asynchronous):
    context = context_for_repair()
    before = copy.deepcopy(context)
    visits, _ = install_partial_repair(monkeypatch, context, always_fail=True)
    result = finalize(context, asynchronous)
    assert visits == [4, 6, 6]
    assert result["repair_transaction"]["accepted"] is False
    assert result["repair_transaction"]["audited_output_hashes"]["4"] != result["repair_transaction"]["accepted_output_hashes"]["4"]
    for field in ("analyses", "structured_outputs", "data"):
        assert context[field] == before[field]
    assert context["status"] == "blocked"
    assert set(before["blocking_issues"]) <= set(context["blocking_issues"])
    assert context["repair_attempt_counts"] == {4: 1, 6: 2}
    assert context["repair_candidate_history"]["6"] == ["rejected", "rejected"]
    assert context["agent_quality_retry_counts"] == {6: 2}
    assert context["llm_token_usage"] == {6: {"total_tokens": 200}}
    assert context["audit_repair_log"][0] == "prior failure must remain"


@pytest.mark.parametrize("used_passes", [2, 3])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_reentering_final_audit_does_not_grant_more_passes(monkeypatch, asynchronous, used_passes):
    context = context_for_repair()
    context["repair_iteration_count"] = used_passes
    context["repair_attempt_counts"] = {4: 2}
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *_args, **_kwargs: {
        "critical": ["unresolved"], "repair_agent_issues": {4: ["unresolved"]}})

    def forbidden(*args, **kwargs):
        pytest.fail("the per-job final-audit pass budget was already consumed")

    monkeypatch.setattr(audit_repair, "attempt_final_audit_repair", forbidden)
    monkeypatch.setattr(audit_repair, "attempt_final_audit_repair_async", forbidden)
    result = finalize(context, asynchronous)
    assert result["critical"] == ["unresolved"]
    assert context["repair_iteration_count"] == used_passes
    assert context["repair_attempt_counts"] == {4: 2}
    assert context["status"] == "blocked"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_standalone_failed_round_still_rolls_back_all_analysis(monkeypatch, asynchronous):
    context = context_for_repair()
    before = copy.deepcopy(context)
    visits, _ = install_partial_repair(monkeypatch, context)
    audit = {"repair_agent_issues": {4: ["valuation incorrect"]}}
    if asynchronous:
        result = asyncio.run(audit_repair.attempt_final_audit_repair_async(context, audit, object()))
    else:
        result = audit_repair.attempt_final_audit_repair(context, audit, object())
    assert result is False
    assert visits == [4, 6]
    for field in ("analyses", "structured_outputs", "data"):
        assert context[field] == before[field]
    assert context["repair_attempt_counts"] == {4: 1, 6: 1}
    assert context["repair_candidate_history"]["6"] == ["rejected"]
    assert "_repair_pending_audit" not in context


@pytest.mark.parametrize("asynchronous", [False, True])
def test_cancellation_after_retained_progress_cannot_publish_it(monkeypatch, asynchronous):
    context = context_for_repair()
    before = copy.deepcopy(context)
    install_partial_repair(monkeypatch, context)
    repair = audit_repair._repair_agent_output
    visits = []

    def cancel_second_pass(agent, *args, **kwargs):
        visits.append(agent)
        if agent == 6 and visits.count(6) == 2:
            raise asyncio.CancelledError("cancel retained transaction")
        return repair(agent, *args, **kwargs)

    async def cancel_async(*args, **kwargs):
        return cancel_second_pass(*args, **kwargs)

    monkeypatch.setattr(audit_repair, "_repair_agent_output", cancel_second_pass)
    monkeypatch.setattr(audit_repair, "_repair_agent_output_async", cancel_async)
    with pytest.raises(asyncio.CancelledError):
        finalize(context, asynchronous)
    assert visits == [4, 6, 6]
    assert context == before


@pytest.mark.parametrize("asynchronous", [False, True])
def test_actual_agent_contract_rejects_truncated_candidate_within_existing_budget(monkeypatch, asynchronous):
    from agent_runtime import repair_loop
    from config import MAX_PER_JOB_REPAIR_ATTEMPTS
    from industry_output_completion import industry_output_issues
    from structured_output_runtime import process_agent_response

    context = context_for_repair()
    context["data"].update(financial_currency="TWD", net_income_ttm_raw=984595972.65,
                           free_cash_flow_raw=-168490256)
    original = json.dumps({
        "as_of_date": "2026-10-18", "confidence": "medium",
        "evidence_items": [{"finding": "訂單實現仍須核對。", "source_refs": ["data.net_income_ttm_raw"],
                            "freshness_note": "財務期間尚未確認。", "counterevidence": "融資成本可能增加。"}],
        "analysis_markdown": (
            "## 總體經濟\n利率及匯率變動仍可能影響融資成本。\n"
            "## 產業供需\n需求須由正式訂單與出貨支持，不以新聞推定已實現。\n"
            "## 宏觀定調結論\n產業具有成長機會，但尚須核對訂單及現金流；"
            "若需求未落實或融資成本增加，投資風險仍高，不應僅以題材推定改善。"
        ),
    }, ensure_ascii=False)
    context["analyses"][11] = process_agent_response(
        11, original, context, completion_diagnostics={"finish_reasons": ["STOP"]})
    assert not industry_output_issues(context["analyses"][11], context["data"], context["structured_outputs"][11])
    assert context["structured_outputs"][11]["financial_basis"]["facts"]["net_income_ttm_raw"]["period_status"] == "unverified"
    before = copy.deepcopy(context)
    calls = []

    def provider(agent, data, candidate, rotator, **kwargs):
        calls.append(agent)
        assert kwargs["max_retries"] == 1
        return process_agent_response(agent, json.dumps({
            "as_of_date": "2026-10-18", "confidence": "medium", "evidence_items": [],
            "analysis_markdown": "## Industry\nUNVERIFIED TRUNCATED CANDIDATE",
        }), candidate, completion_diagnostics={"finish_reasons": ["MAX_TOKENS"]})

    async def provider_async(*args, **kwargs):
        return provider(*args, **kwargs)

    monkeypatch.setattr(audit_repair, "run_single_agent", provider)
    monkeypatch.setattr(audit_repair, "run_single_agent_async", provider_async)
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _: {"open": False})
    monkeypatch.setattr(repair_loop, "record_quality_fallback", lambda *_: (False, "no fallback"))
    monkeypatch.setattr(audit_repair, "run_final_report_audit", lambda *_args, **_kwargs: {
        "critical": ["invalid industry"], "repair_agent_issues": {11: ["repair original issue"]}})
    result = finalize(context, asynchronous)
    assert result["repair_transaction"]["accepted"] is False
    assert len(calls) == MAX_PER_JOB_REPAIR_ATTEMPTS == 2
    assert context["repair_attempt_counts"][11] == 2
    assert context["repair_iteration_count"] == 2
    assert any("provider_output_incomplete" in issue
               for issue in context["repair_candidate_history"]["11"]["issue_checklist"])
    for field in ("analyses", "structured_outputs", "data"):
        assert context[field] == before[field]
    assert context["audit_repair_log"][0] == "prior failure must remain"
