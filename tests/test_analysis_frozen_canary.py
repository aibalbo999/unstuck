"""Offline source-boundary diagnostics, NOT qualified model/canary receipts."""

import asyncio
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import analysis_jobs
from analysis_frozen_canary import (
    FrozenCanaryError, check_frozen_canary, claim_frozen_canary, frozen_canary_inputs,
    frozen_workflow_services,
)
from agent_runtime import AnalysisPipelineRunner, AnalysisRequest, AnalysisResult
from agent_runtime import pipeline_runner
from agent_runtime.retry_policy import AgentRateLimitError, AgentTransientError
from workflow_services import WorkflowServices


def source(**changes):
    data = {"ticker": "2330.TW", "company_name": "Frozen fixture", "current_price": 100,
            "fetch_date": "2026-09-12", "data_trust": {"status": "unknown"},
            "analysis_input_cutoff": "2026-09-12T07:30:00+00:00",
            "price_history": {}, "temporal_memory": {"approved_fixture": "old"}}
    data['daily_market_data']={'source':'explicit offline fixture, not real market proof',
        'as_of':'2026-09-11','bars':[{'date':'2026-09-11','close':100,'volume':1}]}
    data.update(changes)
    return json.dumps(data, ensure_ascii=False).encode()


def options(raw=None, mode="v4", **changes):
    raw = source() if raw is None else raw
    values = dict(campaign_id="offline-fixture", job_id="frozen-job", ticker="2330.TW",
                  pipeline_id=mode, source_json=raw, source_sha256=hashlib.sha256(raw).hexdigest(),
                  manifest_sha256="a" * 64, boundary_check=lambda stage: True)
    values.update(changes)
    return values


@pytest.fixture
def job_boundary(monkeypatch, tmp_path):
    calls = SimpleNamespace(events=[], updates=[], requests=[], fetch=0, memory=0, render=0, retry=0)

    async def forbidden_fetch(request):
        calls.fetch += 1
        raise AssertionError("fresh market fetch attempted")

    def forbidden_memory(*args, **kwargs):
        calls.memory += 1
        raise AssertionError("fresh temporal memory attempted")

    async def run(request):
        calls.requests.append(request)
        return AnalysisResult(context={"ticker": request.data["ticker"], "data": request.data,
                                      "pipeline_id": request.pipeline_id, "analyses": {},
                                      "final_audit": {"status": "passed"}},
                              pipeline_id=request.pipeline_id)

    async def forbidden_render(request):
        calls.render += 1
        raise AssertionError("canary publication is not integrated")

    def forbidden_retry(*args):
        calls.retry += 1
        raise AssertionError("normal queue retry renewal attempted")

    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "is_job_cancel_requested", lambda job_id: False)
    monkeypatch.setattr(analysis_jobs, "append_event", lambda job, event: calls.events.append(event))
    monkeypatch.setattr(analysis_jobs, "get_events_since", lambda job: [])
    monkeypatch.setattr(analysis_jobs, "update_job", lambda job, state, **kw: calls.updates.append((state, kw)))
    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", SimpleNamespace(fetch_async=forbidden_fetch))
    monkeypatch.setattr(analysis_jobs, "build_temporal_memory", forbidden_memory)
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", SimpleNamespace(run_async=run))
    monkeypatch.setattr(analysis_jobs, "REPORT_RENDERER", SimpleNamespace(render_async=forbidden_render))
    monkeypatch.setattr(analysis_jobs, "prepare_analysis_retry", forbidden_retry)
    return calls


@pytest.mark.parametrize("mode", ["v1", "v2", "v3", "v4"])
def test_normal_job_uses_frozen_data_and_stops_before_publication(job_boundary, tmp_path, mode):
    raw = source()
    existing = tmp_path / "old-report.html"
    existing.write_text("keep existing report")

    async def run():
        with frozen_canary_inputs(**options(raw, mode)):
            return await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", mode)

    assert asyncio.run(run()) == ""
    assert job_boundary.fetch == job_boundary.memory == job_boundary.render == 0
    request, = job_boundary.requests
    assert request.data["fetch_date"] == "2026-09-12"
    assert request.data["analysis_input_cutoff"] == "2026-09-12T07:30:00+00:00"
    assert request.data["temporal_memory"] == {"approved_fixture": "old"}
    assert request.data["quant_metrics"]
    assert raw == source()
    receipt = next(e for e in job_boundary.events if e.get("phase") == "frozen_canary_input")
    assert receipt["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["publication_authorized"] is False
    assert receipt["production_ready"] is False
    assert len(receipt["workflow_data_sha256"]) == 64
    assert job_boundary.updates[-1][0] == "error"
    assert job_boundary.events[-1]["phase"] == "frozen_canary_publication_pending"
    assert not any(e["type"] in ("done", "report_done") for e in job_boundary.events)
    assert list(tmp_path.rglob("*.html")) == [existing]
    assert existing.read_text() == "keep existing report"


@pytest.mark.parametrize("arguments", [
    ("other-job", "2330.TW", "v4", False),
    ("frozen-job", "2412.TW", "v4", False),
    ("frozen-job", "2330.TW", "v1", False),
    ("frozen-job", "2330.TW", "both", False),
    ("frozen-job", "2330.TW", "invalid-mode", False),
    ("frozen-job", "2330.TW", "v4", True),
])
def test_job_binding_rejected_before_any_job_write(job_boundary, arguments):
    async def run():
        with frozen_canary_inputs(**options()):
            with pytest.raises(FrozenCanaryError):
                await analysis_jobs.run_stock_analysis_job_async(*arguments)
    asyncio.run(run())
    assert not job_boundary.updates and not job_boundary.events
    assert job_boundary.fetch == 0


@pytest.mark.parametrize("error", [AgentTransientError("fixture server failure"),
    AgentRateLimitError("fixture quota failure", 60, 60)])
def test_provider_failure_does_not_renew_queue_retry(job_boundary, monkeypatch, error):
    async def fail(request):
        raise error
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", SimpleNamespace(run_async=fail))

    async def run():
        with frozen_canary_inputs(**options()):
            with pytest.raises(type(error)) as caught:
                await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
            assert caught.value is error
    asyncio.run(run())
    assert job_boundary.retry == 0
    assert job_boundary.updates[-1][0] == "error"
    assert job_boundary.events[-1]["phase"] == "frozen_canary_provider_stop"
    assert job_boundary.events[-1]["queue_retry_state"] == "controller_must_verify_zero"
    assert job_boundary.render == 0


def test_frozen_data_trust_failure_keeps_normal_gate(job_boundary):
    async def run():
        with frozen_canary_inputs(**options(source(data_trust={"status": "error"}))):
            return await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
    assert asyncio.run(run()) == ""
    assert not job_boundary.requests
    assert job_boundary.events[-1]["phase"] == "data_trust"


@pytest.mark.parametrize("quality", [
    {"status": "blocked"}, {"final_audit": {"status": "blocked"}},
    {"content_credibility": {"status": "blocked"}},
    {"report_conformance": {"status": "blocked"}},
    {"evidence_exit_gate": {"verdict": "rejected"}}, {"report_lint": {"status": "blocked"}},
])
def test_frozen_report_quality_failure_keeps_normal_gate(job_boundary, monkeypatch, quality):
    async def fail_quality(request):
        return AnalysisResult(context={"ticker": "2330.TW", "pipeline_id": "v4",
            "data": request.data, "analyses": {}, **quality}, pipeline_id="v4")
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", SimpleNamespace(run_async=fail_quality))
    async def run():
        with frozen_canary_inputs(**options()):
            return await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
    assert asyncio.run(run()) == ""
    assert job_boundary.events[-1]["phase"] == "report_quality_blocked"
    assert job_boundary.render == 0


@pytest.mark.parametrize("mutations", [
    {"source_sha256": "b" * 64}, {"manifest_sha256": "no-digest"},
    {"pipeline_id": "both"}, {"job_id": "job:other"}, {"ticker": "2330.tw"},
    {"boundary_check": None}, {"source_json": bytearray(source())},
])
def test_invalid_binding_is_rejected(job_boundary, mutations):
    async def run():
        with pytest.raises(FrozenCanaryError):
            with frozen_canary_inputs(**options(**mutations)):
                pytest.fail("invalid binding admitted")
    asyncio.run(run())
    assert not job_boundary.updates and not job_boundary.events


def test_normal_pipeline_uses_controller_rotator_before_service_construction(monkeypatch, tmp_path):
    import inspect
    from workflow_services import create_default_workflow_services
    sentinel = object()
    seen = []
    async def graph(**kwargs):
        return {}
    def factory(**kwargs):
        seen.append(kwargs.get("rotator"))
        assert kwargs.get("rotator") is sentinel, "normal factory would create an unguarded rotator"
        return create_default_workflow_services(**kwargs)
    monkeypatch.setattr(pipeline_runner, "create_default_workflow_services", factory)
    monkeypatch.setattr(pipeline_runner, "execute_persistent_workflow", graph)
    monkeypatch.setattr(pipeline_runner, "legacy_context_from_graph", lambda *args: {})
    async def run():
        args = options()
        if "workflow_rotator" in inspect.signature(frozen_canary_inputs).parameters:
            args["workflow_rotator"] = sentinel
        with frozen_canary_inputs(**args):
            scope = claim_frozen_canary("frozen-job", "2330.TW", "v4", False)
            data = scope.data()
            scope.bind_workflow_data(data)
            await AnalysisPipelineRunner().run_async(AnalysisRequest(data=data, pipeline_id="v4",
                thread_id="frozen-job:v4", checkpoint_path=str(tmp_path / "checkpoint.sqlite3")))
    asyncio.run(run())
    assert seen == [sentinel]


@pytest.mark.parametrize("raw", [b"{}", b"[]", b'[{"a": 1}]', b"not JSON", b"\xff",
    b'{"a": 1, "a": 2}', b'{"a": NaN}', b'{"a": Infinity}', b'{"a": 1e999}',
    source(ticker="2412.TW"), source(fetch_date=None), source(data_trust=None),
    source(analysis_input_cutoff=None), source(analysis_input_cutoff="2026-09-12"),
])
def test_invalid_source_is_rejected_before_job_write(job_boundary, raw):
    async def run():
        with pytest.raises(FrozenCanaryError):
            with frozen_canary_inputs(**options(raw)):
                pytest.fail("invalid source admitted")
    asyncio.run(run())
    assert not job_boundary.updates and not job_boundary.events


@pytest.mark.parametrize("answer", [False, None, 1, "verified"])
def test_boundary_requires_explicit_true_before_job_write(job_boundary, answer):
    async def run():
        with frozen_canary_inputs(**options(boundary_check=lambda stage: answer)):
            with pytest.raises(FrozenCanaryError):
                await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
    asyncio.run(run())
    assert not job_boundary.updates and not job_boundary.events


def test_scope_cannot_be_nested_reused_or_claimed_by_child_task(job_boundary):
    async def run():
        with frozen_canary_inputs(**options()):
            with pytest.raises(FrozenCanaryError, match="non-nested"):
                with frozen_canary_inputs(**options()):
                    pytest.fail("nested scope admitted")
            with pytest.raises(FrozenCanaryError):
                await asyncio.create_task(
                    analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4"))
            assert not job_boundary.updates
            await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
            count = len(job_boundary.updates)
            with pytest.raises(FrozenCanaryError):
                await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
            assert len(job_boundary.updates) == count
    asyncio.run(run())


def test_late_inherited_context_is_not_treated_as_normal_job(job_boundary):
    async def run():
        ready = asyncio.Event()
        async def child():
            await ready.wait()
            check_frozen_canary("frozen-job")
        with frozen_canary_inputs(**options()):
            task = asyncio.create_task(child())
        ready.set()
        with pytest.raises(FrozenCanaryError, match="expired"):
            await task
    asyncio.run(run())
    assert not job_boundary.updates


def test_source_decode_is_independent_and_scope_checks_process_thread(monkeypatch):
    import analysis_frozen_canary as module
    async def run():
        with frozen_canary_inputs(**options()):
            scope = claim_frozen_canary("frozen-job", "2330.TW", "v4", False)
            first = scope.data()
            first["temporal_memory"]["approved_fixture"] = "changed"
            assert scope.data()["temporal_memory"]["approved_fixture"] == "old"
            with pytest.raises(FrozenCanaryError):
                await asyncio.to_thread(check_frozen_canary, "frozen-job")
            original_owner = module._owner
            owner = original_owner()
            monkeypatch.setattr(module, "_owner", lambda: (owner[0] + 1, owner[1], owner[2]))
            with pytest.raises(FrozenCanaryError, match="expired"):
                check_frozen_canary("frozen-job")
            monkeypatch.setattr(module, "_owner", original_owner)
    asyncio.run(run())


def service_fixture():
    def initialize(data, mode):
        return {"data": data, "pipeline_id": mode}
    def validate(state):
        return state
    async def forbidden(*args, **kwargs):
        raise AssertionError("original network/model service executed")
    return WorkflowServices(initialize=initialize, validate=validate, prepare=forbidden,
        repair=forbidden, run_agent=forbidden, final_audit=forbidden, chief_editor=forbidden,
        tear_sheet=forbidden, persist_report=forbidden)


@pytest.mark.parametrize("mode", ["v1", "v2", "v3", "v4"])
def test_real_job_and_pipeline_adapter_replace_only_fresh_services(job_boundary, monkeypatch, mode):
    original = service_fixture()
    seen = []
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", AnalysisPipelineRunner())
    monkeypatch.setattr(pipeline_runner, "create_default_workflow_services", lambda **kw: original)
    monkeypatch.setattr(pipeline_runner, "legacy_context_from_graph", lambda state, services: state)
    async def graph_probe(**kwargs):
        # Deliberately NOT a real model graph or a qualified report fixture.
        services = kwargs["services"]
        state = kwargs["initial_state"]
        seen.append(state["pipeline_id"])
        for field in ("initialize", "validate", "run_agent", "final_audit", "chief_editor",
                      "tear_sheet", "persist_report"):
            assert getattr(services, field) is getattr(original, field)
        assert services.prepare is not original.prepare
        assert services.repair is not original.repair
        prepared = await asyncio.create_task(services.prepare(state))
        repaired = await asyncio.create_task(services.repair(state))
        assert prepared["rag_status"]["status"] == "unavailable"
        assert prepared["rag_status"]["exact_original_prompt_replay"] is False
        assert repaired["tool_results"]["official_reconciliation"]["status"] == "unavailable"
        assert state["data"]["fetch_date"] == "2026-09-12"
        return {**state, "ticker": "2330.TW", "analyses": {}, "final_audit": {"status": "passed"}}
    monkeypatch.setattr(pipeline_runner, "execute_persistent_workflow", graph_probe)
    async def run():
        with frozen_canary_inputs(**options(mode=mode)):
            return await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", mode)
    assert asyncio.run(run()) == ""
    assert seen == [mode]
    assert job_boundary.fetch == job_boundary.memory == job_boundary.render == 0
    assert job_boundary.events[-1]["phase"] == "frozen_canary_publication_pending"


@pytest.mark.parametrize("change", ["data", "thread", "mode", "unbound"])
def test_workflow_request_cannot_substitute_frozen_job_binding(change):
    async def run():
        with frozen_canary_inputs(**options()):
            scope = claim_frozen_canary("frozen-job", "2330.TW", "v4", False)
            data = scope.data()
            if change != "unbound":
                scope.bind_workflow_data(data)
            if change == "data":
                data["current_price"] = 999
            request = AnalysisRequest(data=data, pipeline_id="v1" if change == "mode" else "v4",
                thread_id="other:v4" if change == "thread" else "frozen-job:v4")
            with pytest.raises(FrozenCanaryError, match="binding mismatch"):
                frozen_workflow_services(service_fixture(), request)
    asyncio.run(run())


def test_frozen_services_expire_and_workflow_is_single_use():
    async def run():
        with frozen_canary_inputs(**options()):
            scope = claim_frozen_canary("frozen-job", "2330.TW", "v4", False)
            data = scope.data()
            scope.bind_workflow_data(data)
            request = AnalysisRequest(data=data, pipeline_id="v4", thread_id="frozen-job:v4",
                                      checkpoint_path="/private/tmp/not-opened-by-service-test.sqlite3")
            services = frozen_workflow_services(service_fixture(), request)
            with pytest.raises(FrozenCanaryError):
                frozen_workflow_services(service_fixture(), request)
        with pytest.raises(FrozenCanaryError, match="expired"):
            await services.prepare({})
        with pytest.raises(FrozenCanaryError, match="expired"):
            await services.repair({})
    asyncio.run(run())


def test_no_scope_leaves_services_unchanged():
    services = service_fixture()
    request = AnalysisRequest(data={}, pipeline_id="v4")
    assert frozen_workflow_services(services, request) is services


@pytest.mark.parametrize("function", ["build_rag_index", "build_rag_index_async",
    "ensure_agent_rag_context", "ensure_agent_rag_context_async"])
@pytest.mark.parametrize("preloaded", [False, True])
def test_agent_rag_cannot_rebuild_or_read_unapproved_index(monkeypatch, function, preloaded):
    import rag_runtime.service as rag
    from rag_runtime.types import InMemoryRagIndex, RagChunk
    calls = []
    def forbidden(*args, **kwargs):
        calls.append("cache_or_embedding")
        raise AssertionError("unapproved RAG read or embedding")
    monkeypatch.setattr(rag, "RAG_ENABLED", True)
    for name in ("_get_cached_rag_index", "embed_index_chunks", "embed_index_chunks_async",
                 "embed_query", "embed_query_async"):
        monkeypatch.setattr(rag, name, forbidden)
    async def run():
        with frozen_canary_inputs(**options()):
            scope = claim_frozen_canary("frozen-job", "2330.TW", "v4", False)
            data = scope.data()
            context = {"data": data}
            if preloaded:
                context["rag_context"] = {24: "unapproved prior text"}
                context["rag_index"] = InMemoryRagIndex([RagChunk(
                    chunk_id="old", source="old", text="unapproved", metadata={}, embedding=[1.0])])
            args = (data,) if function.startswith("build") else (24, context)
            result = getattr(rag, function)(*args)
            if function.endswith("_async"):
                result = await result
            assert result is None if function.startswith("build") else result == ""
            if function.startswith("ensure"):
                assert context["rag_status"]["status"] == "unavailable"
                assert not context.get("rag_index") and not context.get("rag_context")
    asyncio.run(run())
    assert calls == []


@pytest.mark.parametrize("change", ["thread", "no_path", "relative_path", "backend", "custom_saver"])
def test_runner_rejects_invalid_binding_before_service_factory(monkeypatch, change):
    factories = []
    monkeypatch.setattr(pipeline_runner, "create_default_workflow_services",
                        lambda **kwargs: factories.append("factory"))
    async def run():
        with frozen_canary_inputs(**options()):
            scope = claim_frozen_canary("frozen-job", "2330.TW", "v4", False)
            data = scope.data()
            scope.bind_workflow_data(data)
            request = AnalysisRequest(data=data, pipeline_id="v4",
                thread_id="other:v4" if change == "thread" else "frozen-job:v4",
                checkpoint_path=None if change == "no_path" else
                    "relative.sqlite3" if change == "relative_path" else "/private/tmp/not-opened.sqlite3",
                checkpoint_backend="postgres" if change == "backend" else "sqlite",
                checkpointer=object() if change == "custom_saver" else None)
            with pytest.raises(FrozenCanaryError):
                await AnalysisPipelineRunner().run_async(request)
    asyncio.run(run())
    assert factories == []


@pytest.mark.parametrize("existing", ["completed", "pending", "other_namespace", "draft", "orphan_write"])
def test_real_sqlite_frozen_thread_rejects_all_existing_checkpoint_state(tmp_path, existing):
    from langgraph.checkpoint.base import empty_checkpoint
    from langgraph.graph import END, START, StateGraph
    from workflow_checkpoints import execute_persistent_graph, open_sqlite_checkpointer
    from workflow_state import AgentGraphState
    checkpoint_path = tmp_path / "canary.sqlite3"
    called = []
    def builder():
        graph = StateGraph(AgentGraphState)
        async def node(state):
            called.append(state)
            if existing == "pending":
                raise RuntimeError("fixture interrupted")
            return {"status": "done"}
        graph.add_node("step", node)
        graph.add_edge(START, "step")
        graph.add_edge("step", END)
        return graph
    async def execute():
        return await execute_persistent_graph(graph_builder=builder(),
            initial_state={"ticker": "2330.TW", "pipeline_id": "v4"},
            thread_id="frozen-job:v4", checkpoint_path=checkpoint_path)
    async def run():
        if existing in ("completed", "pending"):
            if existing == "pending":
                with pytest.raises(RuntimeError, match="fixture interrupted"):
                    await execute()
            else:
                await execute()
        else:
            async with open_sqlite_checkpointer(checkpoint_path) as saver:
                if existing == "orphan_write":
                    await saver.conn.execute("""INSERT INTO writes
                        (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value)
                        VALUES (?, '', 'orphan', 'task', 0, 'channel', 'bytes', ?)""",
                        ("frozen-job:v4", b"untrusted"))
                    await saver.conn.commit()
                else:
                    namespace = "quality_draft/24/old" if existing == "draft" else "other-namespace"
                    await saver.aput({"configurable": {"thread_id": "frozen-job:v4", "checkpoint_ns": namespace}},
                        empty_checkpoint(), {"source": "input", "step": -1, "parents": {}}, {})
        previous_calls = len(called)
        with frozen_canary_inputs(**options()):
            scope = claim_frozen_canary("frozen-job", "2330.TW", "v4", False)
            data = scope.data()
            scope.bind_workflow_data(data)
            frozen_workflow_services(service_fixture(), AnalysisRequest(data=data, pipeline_id="v4",
                thread_id="frozen-job:v4", checkpoint_path=checkpoint_path))
            with pytest.raises(FrozenCanaryError, match="existing checkpoint"):
                await execute()
        assert len(called) == previous_calls
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["v1", "v2", "v3", "v4"])
def test_fresh_normal_job_pipeline_and_sqlite_graph_stop_without_report(job_boundary, monkeypatch, mode):
    from dataclasses import replace
    from langgraph.graph import END, START, StateGraph
    from workflow_checkpoints import execute_persistent_graph
    from workflow_context import input_data_from_state
    from workflow_services import initialize_graph_state
    from workflow_state import AgentGraphState
    executed = []
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", AnalysisPipelineRunner())
    services = replace(service_fixture(), initialize=lambda data, pipeline_id:
                       initialize_graph_state(data, pipeline_id=pipeline_id))
    monkeypatch.setattr(pipeline_runner, "create_default_workflow_services", lambda **kw: services)
    async def diagnostic_graph(**kwargs):
        # Real graph execution and SQLite persistence, synthetic node only.
        # This cannot satisfy source qualification or live report acceptance.
        graph = StateGraph(AgentGraphState)
        async def diagnostic_node(state):
            executed.append(state)
            data = input_data_from_state(state)
            assert data["analysis_input_cutoff"] == "2026-09-12T07:30:00+00:00"
            assert data["temporal_memory"] == {"approved_fixture": "old"}
            prepared = await kwargs["services"].prepare(state)
            assert prepared["rag_status"]["status"] == "unavailable"
            return {"status": "done", "final_audit": {"status": "passed"}}
        graph.add_node("diagnostic", diagnostic_node)
        graph.add_edge(START, "diagnostic")
        graph.add_edge("diagnostic", END)
        return await execute_persistent_graph(graph_builder=graph, initial_state=kwargs["initial_state"],
            thread_id=kwargs["thread_id"], checkpoint_path=kwargs["checkpoint_path"],
            checkpoint_backend=kwargs["checkpoint_backend"])
    monkeypatch.setattr(pipeline_runner, "execute_persistent_workflow", diagnostic_graph)
    async def run():
        with frozen_canary_inputs(**options(mode=mode)):
            assert await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", mode) == ""
        with frozen_canary_inputs(**options(mode=mode)):
            with pytest.raises(FrozenCanaryError, match="existing checkpoint"):
                await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", mode)
    asyncio.run(run())
    assert len(executed) == 1
    assert job_boundary.fetch == job_boundary.memory == job_boundary.render == 0
    assert not any(event["type"] in ("done", "report_done") for event in job_boundary.events)


def test_checkpoint_binding_cannot_change_path_or_reenter():
    from analysis_frozen_canary import claim_frozen_checkpoint
    async def run():
        with frozen_canary_inputs(**options()):
            scope = claim_frozen_canary("frozen-job", "2330.TW", "v4", False)
            data = scope.data()
            scope.bind_workflow_data(data)
            path = "/private/tmp/not-opened-bound.sqlite3"
            frozen_workflow_services(service_fixture(), AnalysisRequest(data=data, pipeline_id="v4",
                thread_id="frozen-job:v4", checkpoint_path=path))
            with pytest.raises(FrozenCanaryError):
                claim_frozen_checkpoint("frozen-job:v4", "sqlite", path + ".other")
            assert claim_frozen_checkpoint("frozen-job:v4", "sqlite", path)
            with pytest.raises(FrozenCanaryError):
                claim_frozen_checkpoint("frozen-job:v4", "sqlite", path)
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["v1", "v2", "v3", "v4"])
def test_private_publication_uses_normal_job_renderer_and_index(job_boundary, monkeypatch, tmp_path, mode):
    """Legacy diagnostic contexts exercise plumbing, not qualified agent output."""
    import inspect
    import report_index
    import job_store
    from report_persistence import report_bundle_keys_for_filename
    from report_repository import ReportListQuery, ReportRepository
    from reporting import ReportRenderer
    original_run = analysis_jobs.PIPELINE_RUNNER.run_async
    async def diagnostic_context(request):
        result = await original_run(request)
        if mode == "v4":
            # Explicit synthetic no-trade legacy context, not a model receipt.
            result.context["analyses"][24] = "## 極短線交易計畫\n本測試不建立部位；待補齊來源後重新評估。"
            result.context["parsed"] = {"trade_setup": {"trade_direction": "Neutral",
                "entry_zone": "N/A", "target_price": "N/A", "stop_loss": "N/A",
                "core_catalyst": "本測試不建立部位；待補齊來源後重新評估。", "risk_level": "High"}}
        return result
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", SimpleNamespace(run_async=diagnostic_context))
    bundles = []
    async def render(request):
        from dataclasses import replace
        request = replace(request, generated_at='2026-09-12T07:30:00+00:00')
        bundle = await ReportRenderer().render_async(request)
        bundles.append(bundle)
        return bundle
    monkeypatch.setattr(analysis_jobs, "REPORT_RENDERER", SimpleNamespace(render_async=render))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "private-index.sqlite3"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "private-jobs.sqlite3"))
    job_store.create_or_attach_active_job("2330.TW", mode, job_id="frozen-job")
    def event(job_id, payload):
        job_boundary.events.append(payload)
        job_store.append_event(job_id, payload)
    def update(job_id, state, **kwargs):
        job_boundary.updates.append((state, kwargs))
        job_store.update_job(job_id, state, **kwargs)
    monkeypatch.setattr(analysis_jobs, "append_event", event)
    monkeypatch.setattr(analysis_jobs, "update_job", update)
    monkeypatch.setattr(analysis_jobs, "get_events_since", job_store.get_events_since)
    monkeypatch.setattr(analysis_jobs, "is_job_cancel_requested", job_store.is_job_cancel_requested)
    tmp_path.chmod(0o700)
    args = options(mode=mode)
    if "publication_output_dir" in inspect.signature(frozen_canary_inputs).parameters:
        args["publication_output_dir"] = str(tmp_path)

    async def run():
        with frozen_canary_inputs(**args):
            return await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", mode)
    filename = asyncio.run(run())
    assert filename, json.dumps(bundles[-1].data_snapshot["report_conformance"] if bundles else job_boundary.events[-1], ensure_ascii=False)
    assert job_boundary.updates[-1][0] == "done"
    assert [e["type"] for e in job_boundary.events][-2:] == ["report_done", "done"]
    keys = report_bundle_keys_for_filename(filename)
    snapshot = json.loads((tmp_path / keys.data_key).read_text())
    assert snapshot["pipeline"] == mode
    assert snapshot["data"]["analysis_input_cutoff"] == "2026-09-12T07:30:00+00:00"
    assert snapshot["data"]["fetch_date"] == "2026-09-12"
    assert snapshot["report_conformance"]["status"] != "blocked"
    # The renderer deliberately leaves unrecorded legacy contracts out of the
    # snapshot. Its actual metadata still classifies this diagnostic as unverified.
    assert not snapshot.get("generation_contract")
    assert not bundles[0].metadata.get("generation_contract")
    assert (tmp_path / keys.html_key).stat().st_size > 0
    assert (tmp_path / keys.md_key).stat().st_size > 0
    reports, count = ReportRepository().query(ReportListQuery(
        page=1, limit=10, output_dir=str(tmp_path), sync_metadata=False))
    assert count == 1 and reports[0]["filename"] == filename
    assert reports[0]["pipeline_id"] == mode
    durable_job = job_store.get_job("frozen-job")
    assert durable_job["status"] == "done" and durable_job["filename"] == filename
    durable_events = job_store.get_events_since("frozen-job")
    report_done = next(e["payload"] for e in durable_events if e["payload"]["type"] == "report_done")
    assert report_done["frozen_canary"]["private_publication_enabled"] is True
    assert report_done["frozen_canary"]["publication_authorized"] is False
    assert report_done["frozen_canary"]["production_ready"] is False
    _readback_private_report_consumers(tmp_path, filename, mode, job_store)
    assert job_boundary.fetch == job_boundary.memory == 0
    retained = {str(p): p.read_bytes() for p in tmp_path.rglob("*")
                if p.is_file() and not p.name.startswith(("private-index", "private-jobs"))}
    before_count = len([e for e in job_boundary.events if e["type"] == "report_done"])
    with pytest.raises(FileExistsError):
        asyncio.run(run())
    assert len([e for e in job_boundary.events if e["type"] == "report_done"]) == before_count
    assert {path: Path(path).read_bytes() for path in retained} == retained


def _readback_private_report_consumers(root, filename, mode, job_store):
    from dataclasses import fields, MISSING
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.reports import ReportRouteDeps, create_reports_router
    from api_routes.analysis_sse import analysis_event_generator
    from storage.report_storage import LocalFileStorage
    def forbidden(*args, **kwargs):
        raise AssertionError("readback called a mutation/queue dependency")
    args = {field.name: forbidden for field in fields(ReportRouteDeps) if field.default is MISSING}
    args.update(get_output_dir=lambda: str(root), get_report_storage=lambda: LocalFileStorage(root))
    app = FastAPI()
    app.include_router(create_reports_router(ReportRouteDeps(**args)))
    before = {str(p): p.read_bytes() for p in root.rglob("*")
              if p.is_file() and not p.name.startswith(("private-index", "private-jobs"))}
    with TestClient(app) as client:
        listing = client.get("/api/reports", params={"pipeline": mode})
        assert listing.status_code == 200
        assert listing.json()["reports"][0]["filename"] == filename
        for suffix in ("", "/download/html", "/download/md", "/download/data"):
            response = client.get(f"/api/report/{filename}{suffix}")
            assert response.status_code == 200 and response.content
            if suffix == "/download/data":
                assert response.json()["pipeline"] == mode
                assert response.json()["data"]["fetch_date"] == "2026-09-12"
    assert {path: Path(path).read_bytes() for path in before} == before

    async def connected():
        return False
    deps = SimpleNamespace(get_job=job_store.get_job, get_events_since=job_store.get_events_since,
        append_event=job_store.append_event, request_job_cancel=forbidden, print_streamed_event=lambda *args: None)
    async def read_events():
        return [event async for event in analysis_event_generator(deps,
            SimpleNamespace(is_disconnected=connected), job_id="frozen-job", resume_after_id=0,
            cancel_on_disconnect=False, intro_payload={"type": "intro"})]
    replay = [json.loads(event["data"]) for event in asyncio.run(read_events())]
    assert [event["type"] for event in replay][-2:] == ["report_done", "done"]
    assert replay[-1]["filename"] == filename


@pytest.mark.parametrize("change", ["ticker", "pipeline_id", "data", "report_filename", "output", "root_replaced"])
def test_private_publication_rejects_changed_binding_before_renderer(job_boundary, monkeypatch, tmp_path, change):
    original_run = analysis_jobs.PIPELINE_RUNNER.run_async
    root = tmp_path / "private-output"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(root))

    async def changed(request):
        result = await original_run(request)
        if change == "data":
            result.context["data"]["fetch_date"] = "2026-09-15"
        elif change == "output":
            monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path))
        elif change == "root_replaced":
            root.rename(tmp_path / "original-output")
            root.mkdir(mode=0o700)
        else:
            result.context[change] = "other"
        return result
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", SimpleNamespace(run_async=changed))

    async def run():
        with frozen_canary_inputs(**options(publication_output_dir=str(root))):
            with pytest.raises(FrozenCanaryError):
                await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
    asyncio.run(run())
    assert job_boundary.render == 0
    assert not list(root.rglob("*.html"))
    assert not any(e["type"] in ("done", "report_done") for e in job_boundary.events)


@pytest.mark.parametrize("blocked_at", ["workflow", "snapshot", "renderer_cancel", "controller_boundary"])
def test_private_publication_keeps_quality_and_cancellation_veto(job_boundary, monkeypatch, tmp_path, blocked_at):
    from reporting import ReportBundle
    original_run = analysis_jobs.PIPELINE_RUNNER.run_async
    tmp_path.chmod(0o700)
    async def run_context(request):
        result = await original_run(request)
        if blocked_at == "workflow":
            result.context["blocking_issues"] = ["fixture quality rejection"]
        return result
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", SimpleNamespace(run_async=run_context))
    async def render(request):
        job_boundary.render += 1
        if blocked_at == "renderer_cancel":
            monkeypatch.setattr(analysis_jobs, "is_job_cancel_requested", lambda _: True)
        return ReportBundle(html="diagnostic", markdown="diagnostic", data_snapshot={
            "ticker": "2330.TW", "content_credibility": {"status": "blocked" if blocked_at == "snapshot" else "warning"}})
    monkeypatch.setattr(analysis_jobs, "REPORT_RENDERER", SimpleNamespace(render_async=render))
    async def run():
        with frozen_canary_inputs(**options(publication_output_dir=str(tmp_path),
            boundary_check=lambda stage: not (blocked_at == "controller_boundary" and stage == "before_private_publication"))):
            return await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
    if blocked_at == "controller_boundary":
        with pytest.raises(FrozenCanaryError):
            asyncio.run(run())
    else:
        assert asyncio.run(run()) == ""
    assert not list(tmp_path.rglob("*.html"))
    assert not any(e["type"] in ("done", "report_done") for e in job_boundary.events)
    assert job_boundary.render == int(blocked_at in ("snapshot", "renderer_cancel"))


@pytest.mark.parametrize("kind", ["missing", "relative", "symlink", "file", "public"])
def test_private_publication_requires_existing_private_root_before_job_writes(job_boundary, tmp_path, kind):
    path = tmp_path / "output"
    if kind == "relative":
        path = Path("relative-output")
    elif kind == "symlink":
        path.symlink_to(tmp_path, target_is_directory=True)
    elif kind == "file":
        path.write_text("not a directory")
    elif kind == "public":
        path.mkdir(mode=0o755)
    async def run():
        with pytest.raises(FrozenCanaryError):
            with frozen_canary_inputs(**options(publication_output_dir=str(path))):
                await analysis_jobs.run_stock_analysis_job_async("frozen-job", "2330.TW", "v4")
    asyncio.run(run())
    assert not job_boundary.events and not job_boundary.updates
