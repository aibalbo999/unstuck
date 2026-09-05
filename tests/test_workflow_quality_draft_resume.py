"""Durable, unvalidated quality drafts across failed LangGraph node attempts."""

import asyncio
import copy
import sqlite3

import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from agent_runtime import quality_gates, quality_retry, step_cache
from agent_runtime.deferred import AgentDeferredError
from state_memory import initialize_agent_state
from workflow_checkpoints import execute_persistent_graph, open_sqlite_checkpointer
from workflow_services import create_default_workflow_services
from workflow_state import AgentGraphState, agent_state_to_graph


def initial_state():
    state = agent_state_to_graph(initialize_agent_state(
        {"ticker": "2330.TW", "company_name": "Draft fixture", "current_price": 100},
        run_id="quality-draft-run",
    ), pipeline_id="v1")
    state.update(analyses={}, structured_outputs={}, prompt_fingerprint="prompt-v1")
    return state


@pytest.fixture
def quality_runtime(monkeypatch):
    calls = {"initial": [], "rewrite": [], "validated": [], "parsed": [], "published": 0, "nodes_returned": []}
    control = {"deferred": True, "raw_size": 10, "parallel": False, "deferred_agents": {4, 14}, "wait_for_sibling": False}
    events = []

    async def context_digest(agent_num, context, *_args, **_kwargs):
        context.setdefault("context_digests", {}).setdefault(agent_num, f"digest-{agent_num}")

    async def rag(agent_num, context, *_args, **_kwargs):
        context.setdefault("rag_context", {}).setdefault(agent_num, f"retrieved-evidence-{agent_num}")

    async def status(*_args, **kwargs):
        events.append(kwargs)

    async def generate(agent_num, data, context, rotator):
        if context.get("_audit_retry_instruction"):
            calls["rewrite"].append((agent_num, context["analyses"][agent_num]))
            if control["parallel"]:
                while len(calls["rewrite"]) < 2:
                    await asyncio.sleep(0)
            if control["wait_for_sibling"] and agent_num == 4:
                while 14 not in calls["nodes_returned"]:
                    await asyncio.sleep(0)
            if control["deferred"] and agent_num in control["deferred_agents"]:
                raise AgentDeferredError(agent_num, [{"model_id": "offline-model", "retry_wait_seconds": 60}])
            context["structured_outputs"][agent_num] = {"approved": True}
            return f"validated-result-{agent_num}"
        calls["initial"].append(agent_num)
        context["structured_outputs"][agent_num] = {"unvalidated_value": agent_num}
        return f"unvalidated-draft-{agent_num}:" + "x" * control["raw_size"]

    def parse(agent_num, text, context):
        calls["parsed"].append((agent_num, text, copy.deepcopy(context["structured_outputs"].get(agent_num))))
        return True, text

    def validate(agent_num, text, data):
        calls["validated"].append((agent_num, text))
        return ["arithmetic must be checked"] if text.startswith("unvalidated-draft-") else []

    monkeypatch.setattr(quality_gates, "run_single_agent_async", generate)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", context_digest)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", rag)
    monkeypatch.setattr(quality_gates, "emit_status_async", status)
    monkeypatch.setattr(quality_gates, "emit_log", lambda *_args: None)
    monkeypatch.setattr(quality_retry, "emit_log", lambda *_args: None)
    monkeypatch.setattr(quality_gates, "get_runtime_model_sequence", lambda *_args: ["offline-model"])
    monkeypatch.setattr(quality_retry, "get_runtime_model_sequence", lambda *_args: ["offline-model"])
    monkeypatch.setattr(quality_gates, "validate_analysis_output", validate)
    monkeypatch.setattr(quality_gates, "validate_company_identity", lambda *_args: [])
    monkeypatch.setattr(quality_gates, "validate_prompt_leakage", lambda *_args: [])
    monkeypatch.setattr(quality_gates, "append_quality_warnings", lambda _agent, text, _data: text)
    monkeypatch.setattr(quality_gates, "_try_parse_structured_output", parse)
    return calls, control, events


def builder_for(calls, agents=(4,)):
    services = create_default_workflow_services(rotator=object())
    builder = StateGraph(AgentGraphState)
    names = []
    for agent_num in agents:
        name = f"agent_{agent_num}"
        names.append(name)

        async def agent_node(state, agent_num=agent_num):
            result = await services.run_agent(agent_num, state)
            calls["nodes_returned"].append(agent_num)
            return result

        builder.add_node(name, agent_node)
        builder.add_edge(START, name)

    async def publish(state):
        calls["published"] += 1
        return {"status": "done"}

    builder.add_node("publish", publish)
    builder.add_edge(names, "publish")
    builder.add_edge("publish", END)
    return builder


def execute(path, state, calls, *, thread_id="draft-job", agents=(4,)):
    return asyncio.run(execute_persistent_graph(
        graph_builder=builder_for(calls, agents), initial_state=state,
        thread_id=thread_id, checkpoint_path=path,
    ))


def draft_records(path):
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT thread_id, checkpoint_ns, type, checkpoint FROM checkpoints WHERE checkpoint_ns LIKE 'quality_draft/%' ORDER BY checkpoint_id").fetchall()
    return [(thread, namespace, JsonPlusSerializer().loads_typed((kind, blob))["channel_values"]["quality_draft"])
            for thread, namespace, kind, blob in rows]


def main_snapshot(path, calls, thread_id="draft-job", agents=(4,)):
    async def read():
        async with open_sqlite_checkpointer(path) as saver:
            return await builder_for(calls, agents).compile(checkpointer=saver).aget_state({"configurable": {"thread_id": thread_id}})
    return asyncio.run(read())


@pytest.mark.parametrize("cache_enabled,ttl", [(False, 3600), (True, 0), (False, 0)])
def test_deferred_quality_retry_persists_unvalidated_full_draft_and_resumes_gate(
    tmp_path, monkeypatch, quality_runtime, cache_enabled, ttl,
):
    calls, control, events = quality_runtime
    control["raw_size"] = 110_000
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_ENABLED", cache_enabled)
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_SECONDS", ttl)
    path = tmp_path / "checkpoints.sqlite3"
    state = initial_state()
    before = copy.deepcopy(state)

    with pytest.raises(AgentDeferredError):
        execute(path, state, calls)

    assert state == before
    assert calls["published"] == 0
    snapshot = main_snapshot(path, calls)
    assert snapshot.next == ("agent_4",)
    assert not snapshot.values.get("analyses") and not snapshot.values.get("agent_reports")
    records = draft_records(path)
    assert len(records) == 1
    record = records[0][2]
    assert record["status"] == "unvalidated"
    assert record["text"] == "unvalidated-draft-4:" + "x" * 110_000
    assert record["structured_output"] == {"unvalidated_value": 4}
    assert record["rag_context"] == "retrieved-evidence-4"
    assert record["context_digest"] == "digest-4"

    control["deferred"] = False
    result = execute(path, state, calls)

    assert calls["initial"] == [4]
    assert [text for agent, text in calls["validated"]].count(record["text"]) == 2
    assert len(calls["rewrite"]) == 2
    assert calls["parsed"][-2][2] == {"unvalidated_value": 4}
    assert result["analyses"]["4"] == "validated-result-4"
    assert result["agent_reports"]["4"]["markdown"] == "validated-result-4"
    assert result["status"] == "done" and calls["published"] == 1


def test_repeated_deferrals_keep_node_pending_and_never_regenerate_initial(tmp_path, quality_runtime):
    calls, control, events = quality_runtime
    path, state = tmp_path / "checkpoints.sqlite3", initial_state()

    for _ in range(3):
        with pytest.raises(AgentDeferredError):
            execute(path, state, calls)

    assert calls["initial"] == [4]
    assert len(calls["rewrite"]) == 3 and calls["published"] == 0
    assert len(draft_records(path)) == 1
    assert main_snapshot(path, calls).next == ("agent_4",)


def test_parallel_agents_recover_their_own_drafts(tmp_path, quality_runtime):
    calls, control, events = quality_runtime
    control["parallel"] = True
    path, state = tmp_path / "checkpoints.sqlite3", initial_state()

    with pytest.raises(AgentDeferredError):
        execute(path, state, calls, agents=(4, 14))

    assert len(draft_records(path)) == 2
    control["deferred"] = False
    result = execute(path, state, calls, agents=(4, 14))

    assert sorted(calls["initial"]) == [4, 14]
    assert result["analyses"] == {"4": "validated-result-4", "14": "validated-result-14"}
    assert calls["published"] == 1


def test_drafts_do_not_cross_workflow_threads(tmp_path, quality_runtime):
    calls, control, events = quality_runtime
    path, state = tmp_path / "checkpoints.sqlite3", initial_state()

    for thread_id in ("first-job", "second-job"):
        with pytest.raises(AgentDeferredError):
            execute(path, state, calls, thread_id=thread_id)

    assert calls["initial"] == [4, 4]
    assert {thread for thread, namespace, payload in draft_records(path)} == {"first-job", "second-job"}


def test_successful_parallel_sibling_does_not_invalidate_pending_draft(tmp_path, quality_runtime):
    calls, control, events = quality_runtime
    control.update(deferred_agents={4}, wait_for_sibling=True)
    path, state = tmp_path / "checkpoints.sqlite3", initial_state()

    with pytest.raises(AgentDeferredError):
        execute(path, state, calls, agents=(4, 14))

    assert calls["nodes_returned"] == [14]
    control["deferred"] = False
    result = execute(path, state, calls, agents=(4, 14))

    assert sorted(calls["initial"]) == [4, 14]
    assert calls["nodes_returned"] == [14, 4]
    assert result["analyses"] == {"4": "validated-result-4", "14": "validated-result-14"}


def test_checkpoint_write_failure_stops_before_validation_or_publication(tmp_path, monkeypatch, quality_runtime):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    calls, control, events = quality_runtime
    original_put = AsyncSqliteSaver.aput

    async def fail_draft_write(self, config, *args, **kwargs):
        if config["configurable"].get("checkpoint_ns", "").startswith("quality_draft/"):
            raise OSError("test checkpoint storage unavailable")
        return await original_put(self, config, *args, **kwargs)

    monkeypatch.setattr(AsyncSqliteSaver, "aput", fail_draft_write)

    with pytest.raises(OSError, match="checkpoint storage unavailable"):
        execute(tmp_path / "checkpoints.sqlite3", initial_state(), calls)

    assert calls["initial"] == [4]
    assert not calls["validated"] and not calls["rewrite"] and calls["published"] == 0


def test_changed_node_input_never_reuses_another_inputs_draft(tmp_path):
    from workflow_quality_drafts import checkpoint_draft_scope, initial_or_checkpointed_draft, quality_draft_node

    generated = []

    async def generate(agent_num, data, context, rotator):
        generated.append(data["current_price"])
        return f"draft with current price {data['current_price']}"

    async def run():
        async with open_sqlite_checkpointer(tmp_path / "checkpoints.sqlite3") as saver:
            with checkpoint_draft_scope(saver, "same-job"):
                for price in (100, 200, 100):
                    state = initial_state()
                    state["normalized_financials"]["current_price"] = price
                    context = {"structured_outputs": {}}
                    async with quality_draft_node(4, state, context):
                        text = await initial_or_checkpointed_draft(4, {"current_price": price}, context, object(), generate)
                    assert text == f"draft with current price {price}"

    asyncio.run(run())
    assert generated == [100, 200]


def test_resume_does_not_refresh_or_overwrite_draft_evidence_inputs(tmp_path, monkeypatch, quality_runtime):
    calls, control, events = quality_runtime
    path, state = tmp_path / "checkpoints.sqlite3", initial_state()
    with pytest.raises(AgentDeferredError):
        execute(path, state, calls)

    async def forbidden_refresh(*args, **kwargs):
        pytest.fail("A resumed draft must not refresh its evidence before quality validation")

    generate = quality_gates.run_single_agent_async

    async def check_rewrite_inputs(agent_num, data, context, rotator):
        assert context.get("_audit_retry_instruction")
        assert context["rag_context"][agent_num] == "retrieved-evidence-4"
        assert context["context_digests"][agent_num] == "digest-4"
        return await generate(agent_num, data, context, rotator)

    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", forbidden_refresh)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", forbidden_refresh)
    monkeypatch.setattr(quality_gates, "run_single_agent_async", check_rewrite_inputs)
    control["deferred"] = False

    assert execute(path, state, calls)["status"] == "done"
    assert calls["initial"] == [4]
    assert any(event.get("phase") == "quality_draft_restored" for event in events)


def test_main_checkpoint_lookup_and_maintenance_respect_draft_namespace(tmp_path, quality_runtime):
    from checkpoint_maintenance import cleanup_terminal_checkpoints

    calls, control, events = quality_runtime
    checkpoint_path, state = tmp_path / "checkpoints.sqlite3", initial_state()
    with pytest.raises(AgentDeferredError):
        execute(checkpoint_path, state, calls, thread_id="draft-job:v1")
    snapshot = main_snapshot(checkpoint_path, calls, thread_id="draft-job:v1")
    assert snapshot.values["run_id"] == state["run_id"]
    assert "quality_draft" not in snapshot.values
    assert snapshot.next == ("agent_4",)

    task_path = tmp_path / "maintenance-operational.sqlite3"
    with sqlite3.connect(task_path) as db:
        db.execute("CREATE TABLE analysis_jobs (job_id TEXT, status TEXT)")
        db.execute("INSERT INTO analysis_jobs VALUES ('draft-job', 'waiting_retry')")
    options = {"checkpoint_db_path": str(checkpoint_path), "task_db_path": str(task_path), "write": True}

    active = cleanup_terminal_checkpoints(**options)
    assert active["active_thread_count"] == 1 and active["deleted_checkpoint_rows"] == 0
    assert len(draft_records(checkpoint_path)) == 1

    with sqlite3.connect(task_path) as db:
        db.execute("UPDATE analysis_jobs SET status = 'done'")
    terminal = cleanup_terminal_checkpoints(**options)
    assert terminal["candidate_thread_count"] == 1
    assert terminal["deleted_checkpoint_rows"] > 1
    assert draft_records(checkpoint_path) == []


@pytest.fixture(params=["structured", "identity"])
def intermediate_quality_runtime(request, monkeypatch, quality_runtime):
    calls, control, events = quality_runtime
    generated = []

    async def generate(agent_num, data, context, rotator):
        if context.get("_audit_retry_instruction"):
            calls["rewrite"].append((agent_num, context["analyses"][agent_num]))
            if control.get("audit_failure"):
                return "[Agent 4 \u57f7\u884c\u5931\u6557: empty response]"
            if control["deferred"]:
                raise AgentDeferredError(agent_num, [{"model_id": "offline-model", "retry_wait_seconds": 60}])
            context["structured_outputs"][agent_num] = {"approved": True}
            return "validated-result-4"
        text = "bad-json" if not generated else f"repaired-draft-{len(generated)}"
        generated.append(text)
        context["structured_outputs"][agent_num] = {"draft": text}
        return text

    def parse(agent_num, text, context):
        calls["parsed"].append((agent_num, text, copy.deepcopy(context["structured_outputs"].get(agent_num))))
        return request.param != "structured" or text != "bad-json", text

    def validate(agent_num, text, data):
        calls["validated"].append((agent_num, text))
        return [] if text == "validated-result-4" else ["arithmetic must be checked"]

    monkeypatch.setattr(quality_gates, "run_single_agent_async", generate)
    monkeypatch.setattr(quality_gates, "_try_parse_structured_output", parse)
    monkeypatch.setattr(quality_gates, "validate_analysis_output", validate)
    monkeypatch.setattr(quality_gates, "validate_company_identity", lambda text, _data:
                        ["wrong company"] if request.param == "identity" and text == "bad-json" else [])
    return calls, control, generated


def test_intermediate_repaired_draft_is_checkpointed_and_reused(tmp_path, intermediate_quality_runtime):
    calls, control, generated = intermediate_quality_runtime
    path, state = tmp_path / "checkpoints.sqlite3", initial_state()

    for _ in range(2):
        with pytest.raises(AgentDeferredError):
            execute(path, state, calls)

    assert generated == ["bad-json", "repaired-draft-1"]
    assert calls["rewrite"] == [(4, "repaired-draft-1"), (4, "repaired-draft-1")]
    latest = draft_records(path)[-1][2]
    assert latest["status"] == "unvalidated" and latest["text"] == "repaired-draft-1"
    assert latest["structured_output"] == {"draft": "repaired-draft-1"}
    assert latest["rag_context"] == "retrieved-evidence-4" and latest["context_digest"] == "digest-4"
    assert calls["parsed"][-1][2] == {"draft": "repaired-draft-1"}
    snapshot = main_snapshot(path, calls)
    assert snapshot.next == ("agent_4",) and calls["published"] == 0
    assert not snapshot.values.get("analyses") and not snapshot.values.get("agent_reports")
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT type, checkpoint FROM checkpoints WHERE checkpoint_ns LIKE 'quality_draft/%' ORDER BY checkpoint_id").fetchall()
    versions = [JsonPlusSerializer().loads_typed(row)["channel_versions"]["quality_draft"] for row in rows]
    assert len(versions) == 2 and versions[1] > versions[0]


def test_intermediate_checkpoint_failure_is_not_swallowed(tmp_path, monkeypatch, intermediate_quality_runtime):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    calls, control, generated = intermediate_quality_runtime
    control["deferred"] = False
    original_put = AsyncSqliteSaver.aput

    async def fail_repaired_write(self, config, checkpoint, *args, **kwargs):
        draft = checkpoint["channel_values"].get("quality_draft", {})
        if draft.get("text", "").startswith("repaired-draft-"):
            raise OSError("intermediate draft write failed")
        return await original_put(self, config, checkpoint, *args, **kwargs)

    monkeypatch.setattr(AsyncSqliteSaver, "aput", fail_repaired_write)
    path, state = tmp_path / "checkpoints.sqlite3", initial_state()
    with pytest.raises(OSError, match="intermediate draft write failed"):
        execute(path, state, calls)

    assert generated == ["bad-json", "repaired-draft-1"]
    assert calls["rewrite"] == [] and calls["published"] == 0
    assert draft_records(path)[-1][2]["text"] == "bad-json"
    assert main_snapshot(path, calls).next == ("agent_4",)


def test_failed_quality_placeholder_cannot_replace_repaired_checkpoint(tmp_path, intermediate_quality_runtime):
    calls, control, generated = intermediate_quality_runtime
    control["audit_failure"] = True
    path, state = tmp_path / "checkpoints.sqlite3", initial_state()
    with pytest.raises(quality_retry.AgentQualityDraftError):
        execute(path, state, calls)

    latest = draft_records(path)[-1][2]
    assert latest["text"] == "repaired-draft-1" and latest["status"] == "unvalidated"
    assert latest["structured_output"] == {"draft": "repaired-draft-1"}
    assert calls["published"] == 0
    control.update(audit_failure=False, deferred=False)
    assert execute(path, state, calls)["analyses"]["4"] == "validated-result-4"
    assert generated == ["bad-json", "repaired-draft-1"]


@pytest.mark.parametrize("invalid", [None, "", "  ", "[Agent 4 \u57f7\u884c\u5931\u6557: empty response]"])
def test_checkpoint_update_rejects_empty_and_failure_outputs(tmp_path, invalid):
    from workflow_quality_drafts import checkpoint_draft_scope, checkpoint_unvalidated_draft, quality_draft_node

    path = tmp_path / "checkpoints.sqlite3"

    async def run():
        async with open_sqlite_checkpointer(path) as saver:
            with checkpoint_draft_scope(saver, "draft-job"):
                context = {"structured_outputs": {4: {"draft": "original"}}}
                async with quality_draft_node(4, initial_state(), context):
                    await checkpoint_unvalidated_draft(4, "original", context)
                    context["structured_outputs"][4] = {"failure": True}
                    await checkpoint_unvalidated_draft(4, invalid, context)

    asyncio.run(run())
    records = draft_records(path)
    assert len(records) == 1
    assert records[0][2]["text"] == "original" and records[0][2]["structured_output"] == {"draft": "original"}
