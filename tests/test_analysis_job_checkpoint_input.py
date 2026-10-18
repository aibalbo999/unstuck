"""Normal queued jobs resume one frozen input through real SQLite graphs."""
import asyncio
import json
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace

import pytest
import rq

import analysis_jobs
import job_store
from agent_runtime import AnalysisPipelineRunner
from agent_runtime import pipeline_runner as runner_module
from agent_runtime.deferred import AgentDeferredError
from data_fetch import FetchResult
from data_trust import unknown_data_trust
from pipeline_modes import get_pipeline_definition
from report_publication_gate import assert_report_publishable
from runtime_dependencies import RuntimeSettings
from workflow_context import input_data_from_state
from workflow_services import WorkflowServices, initialize_graph_state


@pytest.fixture
def harness(monkeypatch, tmp_path):
    counts, rendered, events = Counter(), [], []
    control = {"available": False, "price": 100, "blocked": False, "fail_pipeline": None}
    settings = RuntimeSettings.for_tests(tmp_path)
    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", settings.output_dir)
    monkeypatch.setattr(analysis_jobs, "runtime_settings_for_output_dir", lambda _: settings)
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    queue_job = [None]
    monkeypatch.setattr(rq, "get_current_job", lambda: queue_job[0])

    async def fetch(request):
        counts["fetch"] += 1
        return FetchResult(request=request, data={
            "ticker": request.ticker, "company_name": "Test", "current_price": control["price"],
            "fetch_date": "2026-10-12", "source_marker": f"original-{control['price']}",
        }, data_trust=unknown_data_trust())

    def quant(data):
        counts["quant"] += 1
        return {"input_price": data["current_price"], "metric_status": "test"}

    def temporal(*args, **kwargs):
        counts["temporal"] += 1
        return {"mode": kwargs["pipeline_id"], "generation": counts["temporal"]}

    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", SimpleNamespace(fetch_async=fetch))
    monkeypatch.setattr(analysis_jobs.QuantEngine, "compute_all", quant)
    monkeypatch.setattr(analysis_jobs, "build_temporal_memory", temporal)

    def services(**kwargs):
        async def noop(state):
            return {}

        async def agent(number, state):
            pipeline = state["pipeline_id"]
            counts[(pipeline, number)] += 1
            final = get_pipeline_definition(pipeline)["agents"][-1]
            selected = control["fail_pipeline"] in (None, pipeline)
            if number == final and selected and not control["available"]:
                raise AgentDeferredError(number, [{"model_id": "fixture", "retry_wait_seconds": 600}])
            return {"analyses": {str(number): f"price={input_data_from_state(state)['current_price']}"}}

        async def audit(state):
            return {"status": "blocked", "blocking_issues": ["fixture quality failure"]} if control["blocked"] else {}

        return WorkflowServices(
            initialize=lambda data, pipeline: initialize_graph_state(data, pipeline_id=pipeline),
            validate=lambda state: {}, repair=noop, prepare=noop, run_agent=agent,
            final_audit=audit, chief_editor=noop, tear_sheet=noop, persist_report=noop, **kwargs,
        )

    monkeypatch.setattr(runner_module, "create_default_workflow_services", services)
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", AnalysisPipelineRunner())

    async def render(**kwargs):
        assert_report_publishable(kwargs["context"])
        rendered.append(deepcopy(kwargs["context"]))
        return {"type": "report_done", "filename": kwargs["filename"],
                "pipeline_id": kwargs["current_pipeline_id"]}

    monkeypatch.setattr(analysis_jobs, "render_and_persist_report", render)
    original_append = analysis_jobs.append_event

    def append(job, event):
        events.append(deepcopy(event))
        original_append(job, event)

    monkeypatch.setattr(analysis_jobs, "append_event", append)

    def new_job(pipeline="v4"):
        job = job_store.create_job("TEST", pipeline)
        queue_job[0] = SimpleNamespace(id=f"analysis:{job}", retries_left=3,
                                      retry_intervals=[60, 300, 900], meta={}, save=lambda: None)
        return job

    def run(job, pipeline="v4", ticker="TEST", **kwargs):
        return asyncio.run(analysis_jobs.run_stock_analysis_job_async(job, ticker, pipeline, **kwargs))

    return SimpleNamespace(run=run, new_job=new_job, counts=counts, control=control,
                           rendered=rendered, events=events, settings=settings)


@pytest.mark.parametrize("pipeline", ["v1", "v2", "v3", "v4"])
def test_same_job_resume_keeps_actual_checkpoint_input_without_unused_source_refetch(harness, pipeline):
    h = harness
    job = h.new_job(pipeline)
    with pytest.raises(AgentDeferredError):
        h.run(job, pipeline)
    h.control.update(available=True, price=200)
    assert h.run(job, pipeline)
    assert h.counts["fetch"] == 1
    assert h.counts["quant"] == 1
    assert h.counts["temporal"] == 1
    agents = get_pipeline_definition(pipeline)["agents"]
    assert {a: h.counts[(pipeline, a)] for a in agents} == {
        a: 2 if a == agents[-1] else 1 for a in agents}
    assert h.rendered[-1]["data"]["current_price"] == 100
    assert json.loads(job_store.get_job(job)["data_snapshot"]) == h.rendered[-1]["data"]
    receipts = [e for e in h.events if e.get("phase") == "analysis_input_frozen"]
    assert len(receipts) == 1
    assert receipts[0]["analysis_input_hash"] == h.rendered[-1]["data"]["analysis_input_hash"]
    assert any(e.get("phase") == "analysis_resume" for e in h.events)


def test_new_job_fetches_new_data_and_has_a_distinct_input(harness):
    h = harness
    previous = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(previous)
    job_store.update_job(previous, "error", error="operator started a new analysis")
    h.control.update(available=True, price=200)
    fresh = h.new_job()
    assert h.run(fresh)
    assert h.counts["fetch"] == 2
    assert h.rendered[-1]["data"]["current_price"] == 200
    assert job_store.get_job(previous)["status"] == "error"


def test_same_job_force_refresh_does_not_mix_fresh_data_into_committed_outputs(harness):
    h = harness
    job = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(job, force_refresh=True)
    h.control.update(available=True, price=200)
    assert h.run(job, force_refresh=True)
    assert h.counts["fetch"] == 1
    assert h.rendered[-1]["data"]["current_price"] == 100


def test_cancelled_job_spends_no_new_fetch_or_agent_work(harness):
    h = harness
    job = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(job)
    job_store.request_job_cancel(job)
    before = h.counts.copy()
    assert h.run(job) == ""
    assert h.counts == before


def test_quality_failure_remains_blocked_on_resume(harness):
    h = harness
    job = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(job)
    h.control.update(available=True, blocked=True, price=200)
    assert h.run(job) == ""
    assert h.counts["fetch"] == 1
    assert not h.rendered
    assert job_store.get_job(job)["status"] == "error"
    assert h.events[-1]["phase"] == "report_quality_blocked"


def test_joint_mode_resume_preserves_existing_modes_and_uses_frozen_sources_for_unstarted_mode(harness):
    h = harness
    h.control["fail_pipeline"] = "v2"
    job = h.new_job("both")
    with pytest.raises(AgentDeferredError):
        h.run(job, "both")
    assert [c["pipeline_id"] for c in h.rendered] == ["v1"]
    h.control.update(available=True, price=200)
    assert h.run(job, "both")
    assert h.counts["fetch"] == 1
    assert h.counts["quant"] == 1
    assert h.counts["temporal"] == 3
    for pipeline in ("v1", "v2", "v3"):
        assert {c["data"]["current_price"] for c in h.rendered if c["pipeline_id"] == pipeline} == {100}
    assert json.loads(job_store.get_job(job)["data_snapshot"]) == h.rendered[-1]["data"]
    receipts = [e for e in h.events if e.get("phase") == "analysis_input_frozen"]
    assert [e["pipeline_id"] for e in receipts] == ["v1", "v2", "v3"]


def test_wrong_stock_checkpoint_is_rejected_before_external_fetch(harness):
    from analysis_job_checkpoint import AnalysisCheckpointInputError
    h = harness
    job = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(job)
    before = h.counts.copy()
    with pytest.raises(AnalysisCheckpointInputError):
        h.run(job, ticker="OTHER")
    assert h.counts == before


def test_legacy_checkpoint_receipt_stays_unknown_without_refreezing(harness, monkeypatch):
    h = harness
    job = h.new_job()
    monkeypatch.setattr("analysis_job_provenance.freeze_analysis_inputs", lambda data: {})
    with pytest.raises(AgentDeferredError):
        h.run(job)
    monkeypatch.setattr("analysis_job_provenance.freeze_analysis_inputs", lambda data: pytest.fail("legacy refrozen"))
    h.control["available"] = True
    assert h.run(job)
    assert h.counts["fetch"] == 1
    assert "analysis_input_hash" not in h.rendered[-1]["data"]


def test_persisted_empty_checkpoint_is_unverifiable_before_any_external_fetch(harness):
    from analysis_job_checkpoint import AnalysisCheckpointInputError
    from langgraph.checkpoint.base import empty_checkpoint
    from workflow_checkpoints import open_sqlite_checkpointer
    h = harness
    job = h.new_job()

    async def seed_empty():
        async with open_sqlite_checkpointer(h.settings.checkpoint_path) as saver:
            await saver.aput({"configurable": {"thread_id": f"{job}:v4", "checkpoint_ns": ""}},
                             empty_checkpoint(), {"source": "input", "step": -1, "parents": {}}, {})

    asyncio.run(seed_empty())
    h.control["available"] = True
    with pytest.raises(AnalysisCheckpointInputError):
        h.run(job)
    assert h.counts["fetch"] == 0
    assert not h.rendered


@pytest.mark.parametrize("fault", ["pipeline", "state_ticker", "input_ticker", "job_id", "missing_input"])
def test_malformed_checkpoint_identity_cannot_spend_calls_or_publish(harness, fault):
    from analysis_job_checkpoint import AnalysisCheckpointInputError
    from workflow_checkpoints import open_sqlite_checkpointer
    h = harness
    job = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(job)

    async def corrupt_isolated_checkpoint():
        async with open_sqlite_checkpointer(h.settings.checkpoint_path) as saver:
            saved = await saver.aget_tuple({"configurable": {"thread_id": f"{job}:v4", "checkpoint_ns": ""}})
            checkpoint = deepcopy(saved.checkpoint)
            state = checkpoint["channel_values"]
            if fault == "pipeline":
                state["pipeline_id"] = "v1"
            elif fault == "state_ticker":
                state["ticker"] = "OTHER"
            elif fault == "input_ticker":
                state["raw_financial_data"]["input"]["ticker"] = "OTHER"
            elif fault == "job_id":
                state["job_id"] = "another-job"
            else:
                state["raw_financial_data"] = {}
            await saver.aput(saved.config, checkpoint, saved.metadata, {})

    asyncio.run(corrupt_isolated_checkpoint())
    h.control["available"] = True
    before = h.counts.copy()
    with pytest.raises(AnalysisCheckpointInputError):
        h.run(job)
    assert h.counts == before
    assert not h.rendered


@pytest.mark.parametrize("requested,resolved", [
    ("2330", "2330.TW"), ("8069.TW", "8069.TWO"), ("2330.TW", "2330.TW"),
])
def test_saved_original_request_and_real_resolved_stock_can_resume(harness, monkeypatch, requested, resolved):
    from data_fetch.market_sources.ticker_resolver import TaiwanStockProvider
    from data_fetch.yfinance_fetch_runtime import resolve_core_stock
    h = harness
    provider = TaiwanStockProvider()
    monkeypatch.setattr(provider, "get_valid_info", lambda ticker: (object(), {"currentPrice": 100}, ticker == resolved))
    resolution = resolve_core_stock(requested, market_data_provider=provider,
                                    get_market_data_provider=lambda _: provider, emit=lambda _: None)
    assert resolution.ticker == resolved
    original_fetch = analysis_jobs.STOCK_DATA_SERVICE.fetch_async

    async def fetch(request):
        result = await original_fetch(request)
        result.data["ticker"] = resolution.ticker
        return result

    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", SimpleNamespace(fetch_async=fetch))
    job = job_store.create_job(requested, "v4")
    queued = SimpleNamespace(id=f"analysis:{job}", retries_left=3, retry_intervals=[60, 300, 900],
                             meta={}, save=lambda: None)
    monkeypatch.setattr(rq, "get_current_job", lambda: queued)
    with pytest.raises(AgentDeferredError):
        h.run(job, ticker=requested)
    h.control.update(available=True, price=200)
    assert h.run(job, ticker=requested)
    assert h.counts["fetch"] == 1
    assert h.rendered[-1]["data"]["ticker"] == resolved
    assert h.rendered[-1]["data"]["current_price"] == 100
    assert job_store.get_job(job)["ticker"] == requested


def test_changed_checkpoint_venue_does_not_override_the_saved_resolver_result(harness, monkeypatch):
    from analysis_job_checkpoint import AnalysisCheckpointInputError
    from data_fetch.market_sources.ticker_resolver import TaiwanStockProvider
    from data_fetch.yfinance_fetch_runtime import resolve_core_stock
    from workflow_checkpoints import open_sqlite_checkpointer
    h = harness
    provider = TaiwanStockProvider()
    monkeypatch.setattr(provider, "get_valid_info", lambda ticker: (object(), {"currentPrice": 100}, ticker == "8069.TWO"))
    resolution = resolve_core_stock("8069.TW", market_data_provider=provider,
                                    get_market_data_provider=lambda _: provider, emit=lambda _: None)
    original_fetch = analysis_jobs.STOCK_DATA_SERVICE.fetch_async

    async def fetch(request):
        result = await original_fetch(request)
        result.data["ticker"] = resolution.ticker
        return result

    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", SimpleNamespace(fetch_async=fetch))
    job = job_store.create_job("8069.TW", "v4")
    queued = SimpleNamespace(id=f"analysis:{job}", retries_left=3, retry_intervals=[60, 300, 900],
                             meta={}, save=lambda: None)
    monkeypatch.setattr(rq, "get_current_job", lambda: queued)
    with pytest.raises(AgentDeferredError):
        h.run(job, ticker="8069.TW")

    async def change_both_checkpoint_tickers():
        async with open_sqlite_checkpointer(h.settings.checkpoint_path) as saver:
            saved = await saver.aget_tuple({"configurable": {"thread_id": f"{job}:v4", "checkpoint_ns": ""}})
            checkpoint = deepcopy(saved.checkpoint)
            checkpoint["channel_values"]["ticker"] = "8069.TW"
            checkpoint["channel_values"]["raw_financial_data"]["input"]["ticker"] = "8069.TW"
            await saver.aput(saved.config, checkpoint, saved.metadata, {})

    asyncio.run(change_both_checkpoint_tickers())
    assert json.loads(job_store.get_job(job)["data_snapshot"])["ticker"] == "8069.TWO"
    before = h.counts.copy()
    h.control["available"] = True
    with pytest.raises(AnalysisCheckpointInputError):
        h.run(job, ticker="8069.TW")
    assert h.counts == before
    assert not h.rendered
