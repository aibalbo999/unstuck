"""Exercise queued reruns through the real runner, graph and SQLite saver."""
import asyncio
from collections import Counter
from types import SimpleNamespace

import pytest
import rq

import job_store
import report_rerun_jobs
import report_rerun_service
import report_rerun_checkpoint
from agent_runtime import AnalysisPipelineRunner
from agent_runtime.deferred import AgentDeferredError
from agent_runtime import pipeline_runner as runner_module
from pipeline_modes import get_pipeline_definition
from report_publication_gate import assert_report_publishable
from runtime_dependencies import RuntimeSettings
from storage.report_storage import InMemoryStorage
from workflow_context import input_data_from_state
from workflow_services import WorkflowServices, initialize_graph_state
from report_analysis_evidence import capture_analysis_evidence


@pytest.fixture
def rerun_harness(monkeypatch, tmp_path):
    counts, rendered, events = Counter(), [], []
    control = {"available": False, "blocked": False, "price": 100, "pipeline": "v4"}
    settings = RuntimeSettings.for_tests(tmp_path)
    monkeypatch.setattr(report_rerun_checkpoint, "runtime_settings_for_output_dir", lambda _: settings)
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(rq, "get_current_job", lambda: None)

    def services(**kwargs):
        async def noop(state):
            return {}

        async def agent(number, state):
            counts[number] += 1
            final = get_pipeline_definition(state["pipeline_id"])["agents"][-1]
            if number == final and not control["available"]:
                raise AgentDeferredError(number, [{"model_id": "test-model", "retry_wait_seconds": 600}])
            return {"analyses": {str(number): f"price={input_data_from_state(state)['current_price']}"}}

        async def audit(state):
            counts["audit"] += 1
            return {"status": "blocked", "blocking_issues": ["test quality failure"]} if control["blocked"] else {}

        return WorkflowServices(
            initialize=lambda data, pipeline: initialize_graph_state(data, pipeline_id=pipeline),
            validate=lambda state: {}, repair=noop, prepare=noop, run_agent=agent,
            final_audit=audit, chief_editor=noop, tear_sheet=noop, persist_report=noop, **kwargs,
        )

    monkeypatch.setattr(runner_module, "create_default_workflow_services", services)

    async def fetch(request):
        counts["fetch"] += 1
        return SimpleNamespace(data={"ticker": request.ticker, "company_name": "Test", "current_price": control["price"], "fetch_date": "2026-09-17"})

    async def render(**kwargs):
        assert_report_publishable(kwargs["context"])
        rendered.append(kwargs["context"])
        return {"filename": "new-report.html"}

    monkeypatch.setattr(report_rerun_service, "render_and_save_rerun_report", render)
    original_append = report_rerun_jobs.append_event
    def append(job, event):
        events.append(event)
        original_append(job, event)
    monkeypatch.setattr(report_rerun_jobs, "append_event", append)
    storage = InMemoryStorage()
    filename = "TEST_v4_report_20260917_010000.html"
    storage.save_report(filename, b"<html>source</html>", content_type="text/html")
    monkeypatch.setattr(report_rerun_service, "read_report_snapshot", lambda *a, **kw: {
        "pipeline": control["pipeline"], "ticker": "TEST", "data": {"ticker": "TEST", "company_name": "Test", "current_price": 80},
    })

    def new_job(scope="full_report"):
        return job_store.create_job(filename, f"rerun:{scope}")

    def run(job, scope="full_report"):
        return asyncio.run(report_rerun_jobs.run_report_rerun_job_async(
            job, filename, scope, output_dir=settings.output_dir, storage=storage,
            pipeline_runner=AnalysisPipelineRunner(), refresh_service=SimpleNamespace(fetch_async=fetch),
        ))

    return SimpleNamespace(run=run, new_job=new_job, counts=counts, control=control,
                           rendered=rendered, events=events, settings=settings)


@pytest.mark.parametrize("scope,pipeline", [
    ("full_report", "v1"), ("full_report", "v2"), ("full_report", "v3"),
    ("full_report", "v4"), ("mode_b", "v2"),
])
def test_rerun_cold_resume_reuses_completed_agents_and_frozen_data(rerun_harness, scope, pipeline):
    h = rerun_harness
    h.control["pipeline"] = pipeline
    job = h.new_job(scope)
    agents = get_pipeline_definition(pipeline)["agents"]
    with pytest.raises(AgentDeferredError):
        h.run(job, scope)
    from pathlib import Path
    assert Path(h.settings.checkpoint_path).is_file()
    assert not h.rendered
    h.control.update(available=True, price=200)
    assert h.run(job, scope) == "new-report.html"
    assert {a: h.counts[a] for a in agents} == {a: (2 if a == agents[-1] else 1) for a in agents}
    assert h.counts["fetch"] == (1 if scope == "full_report" else 0)
    assert h.rendered[-1]["data"]["current_price"] == (100 if scope == "full_report" else 80)
    assert any(e.get("phase") == "rerun_resume" for e in h.events)


def test_new_job_refreshes_and_does_not_reuse_another_jobs_checkpoint(rerun_harness):
    h = rerun_harness
    with pytest.raises(AgentDeferredError):
        h.run(h.new_job())
    h.control.update(available=True, price=200)
    h.run(h.new_job())
    assert h.counts[22] == 2
    assert h.counts["fetch"] == 2
    assert h.rendered[-1]["data"]["current_price"] == 200


def test_resumed_rerun_still_blocks_quality_failure(rerun_harness):
    h = rerun_harness
    job = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(job)
    h.control.update(available=True, blocked=True)
    assert h.run(job) == ""
    assert not h.rendered
    assert job_store.get_job(job)["status"] == "error"
    assert h.events[-1]["phase"] == "report_quality_blocked"


def test_cancelled_rerun_does_not_resume_or_refresh(rerun_harness):
    h = rerun_harness
    job = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(job)
    job_store.request_job_cancel(job)
    before = h.counts.copy()
    h.control["available"] = True
    assert h.run(job) == ""
    assert h.counts == before
    assert not h.rendered


def test_changed_source_pipeline_does_not_mix_checkpoint_or_spend_calls(rerun_harness):
    h = rerun_harness
    job = h.new_job()
    with pytest.raises(AgentDeferredError):
        h.run(job)
    before = h.counts.copy()
    h.control.update(available=True, pipeline="v1")
    assert h.run(job) == ""
    assert h.counts == before
    assert h.events[-1]["status_code"] == 409
    assert not h.rendered


@pytest.mark.parametrize("scope,pipeline", [
    ("full_report", "v1"), ("full_report", "v2"), ("full_report", "v3"),
    ("full_report", "v4"), ("mode_b", "v2"),
])
def test_real_full_rerun_freezes_quant_and_input_before_first_agent_and_keeps_on_resume(rerun_harness, scope, pipeline):
    h = rerun_harness
    h.control["pipeline"] = pipeline
    job = h.new_job(scope)
    with pytest.raises(AgentDeferredError):
        h.run(job, scope)
    # Changes outside this job must not replace its checkpoint input or cutoff.
    h.control.update(available=True, price=200)
    h.run(job, scope)
    data = h.rendered[-1]["data"]
    assert data.get("analysis_input_hash")
    assert data.get("analysis_input_cutoff")
    assert data.get("quant_metrics")
    assert isinstance(data.get("_analysis_input_evidence"), str)
    packet = capture_analysis_evidence(h.rendered[-1])
    assert packet["input_verification"] == "hash_verified"
    assert packet["sections"]["analysis_input"]["data"]["current_price"] == (100 if scope == "full_report" else 80)
    assert packet["sections"]["quant_metrics"]["status"] == "preserved"
    receipts = [e for e in h.events if e.get("phase") == "analysis_input_frozen"]
    assert len(receipts) == 1
    assert receipts[0]["analysis_input_hash"] == data["analysis_input_hash"]
    assert receipts[0]["analysis_input_cutoff"] == data["analysis_input_cutoff"]


def test_legacy_checkpoint_without_receipt_is_not_retroactively_frozen(rerun_harness, monkeypatch):
    h = rerun_harness
    job = h.new_job()
    # Simulate the pre-fix job boundary creating an old checkpoint without a receipt.
    monkeypatch.setattr("analysis_input_provenance.freeze_analysis_inputs", lambda data: {})
    with pytest.raises(AgentDeferredError):
        h.run(job)
    monkeypatch.setattr("analysis_input_provenance.freeze_analysis_inputs", lambda data: pytest.fail("legacy input refrozen"))
    h.control["available"] = True
    h.run(job)
    packet = capture_analysis_evidence(h.rendered[-1])
    assert packet["input_verification"] == "unknown"
    assert packet["sections"]["analysis_input"]["status"] == "unknown"
