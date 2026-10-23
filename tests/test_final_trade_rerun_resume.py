"""Mode-D final-only reruns preserve upstream reports and existing safety gates."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
import rq
from fastapi import HTTPException

import job_store
import report_rerun_jobs
import report_rerun_service as service
from agent_runtime import audit_repair
from agent_runtime.deferred import AgentDeferredError
from agent_runtime.accepted_output_provenance import (
    final_rerun_provenance_scope, seal_returned_output, attach_accepted_final_model,
)
from storage.report_storage import InMemoryStorage
from agent_runtime.attempt_telemetry import record_node_model_response


FILENAME = "TEST_v4_report_20261023_010000.html"


def snapshot():
    return {"ticker": "TEST", "pipeline": "v4", "data": {
        "ticker": "TEST", "company_name": "Test", "current_price": 100,
        "analysis_input_cutoff": "2026-10-23T01:00:00Z"},
        "rerun_context": {"pipeline_id": "v4", "analyses": {
            "22": "original technical", "23": "original institutional", "24": "old final"},
            "structured_outputs": {"22": {"technical": 1}, "23": {"institutional": 2}, "24": {"old": True}}}}


def test_final_trade_context_reuses_only_matching_original_upstream(tmp_path):
    source = snapshot()
    before = deepcopy(source)
    context, definition, final = service._build_final_rerun_context(FILENAME, source, str(tmp_path))
    assert final == 24 and definition["id"] == "v4"
    assert context["analyses"] == {22: "original technical", 23: "original institutional"}
    assert context["structured_outputs"] == {22: {"technical": 1}, 23: {"institutional": 2}}
    assert context["data"]["analysis_input_cutoff"] == "2026-10-23T01:00:00Z"
    context["structured_outputs"][22]["technical"] = 999
    assert source == before


@pytest.mark.parametrize("change", ["refreshed", "needs_rerun", "missing_upstream", "ticker", "pipeline"])
def test_final_trade_rejects_stale_or_mismatched_source_before_model(tmp_path, monkeypatch, change):
    source = snapshot()
    if change == "refreshed": source["refreshed_without_analysis_rerun"] = True
    elif change == "needs_rerun": source["decision_validity_status"] = "needs_rerun"
    elif change == "missing_upstream": source["rerun_context"]["analyses"].pop("23")
    elif change == "ticker": source["data"]["ticker"] = "OTHER"
    else: source["rerun_context"]["pipeline_id"] = "v3"
    monkeypatch.setattr(service, "read_report_markdown", lambda *a, **k: "")
    with pytest.raises(HTTPException) as raised:
        service._build_final_rerun_context(FILENAME, source, str(tmp_path))
    assert raised.value.status_code == 409


def test_final_trade_model_is_bound_to_current_output_and_fallback_cannot_borrow_it():
    context = {"pipeline_id": "v4", "analyses": {24: "new final"},
               "structured_outputs": {24: {"trade_direction": "Neutral"}}}
    with final_rerun_provenance_scope(context, 24):
        record_node_model_response(context, 24, "fixture-model", {})
        seal_returned_output(context, 24, "new final")
        attach_accepted_final_model(context, 24)
        assert context["model_id"] == "fixture-model"
        context["deterministic_fallbacks"] = [{"agent_num": 24, "trigger": "fixture"}]
        attach_accepted_final_model(context, 24)
        assert context["model_id"] == "unknown"


@pytest.mark.parametrize("raw", ["", '{"trade_direction":"Long"}', '{"trade_direction":"Long","core_catalyst":"cut'])
def test_final_trade_incomplete_raw_response_is_rejected_by_actual_auditor(tmp_path, monkeypatch, raw):
    from structured_output_runtime import process_agent_response

    rendered, audited = [], []
    actual_audit = service.run_final_report_audit

    def audit(context, **kwargs):
        audited.append(True)
        return actual_audit(context, **kwargs)

    monkeypatch.setattr(service, "run_final_report_audit", audit)
    monkeypatch.setattr(service, "KeyRotator", lambda *a: object())
    monkeypatch.setattr(audit_repair, "MAX_REPAIR_ITERATIONS", 0)

    async def generate(agent, data, context, rotator, **kwargs):
        assert agent == 24
        context["analyses"][24] = process_agent_response(24, raw, context)
        return 24, context["analyses"][24]

    async def render(**kwargs):
        rendered.append(kwargs)

    monkeypatch.setattr(service, "run_agent_with_quality_gates_async", generate)
    monkeypatch.setattr(service, "render_and_save_rerun_report", render)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(service._run_final_recommendation_rerun(filename=FILENAME, snapshot=snapshot(),
            output_dir=str(tmp_path), report_renderer=object()))
    assert raised.value.status_code == 409
    assert not rendered
    if raw:
        assert audited


@pytest.mark.parametrize("outcome", ["success", "deferred", "incomplete", "quality", "cancelled"])
def test_queued_final_trade_runs_only_24_and_preserves_terminal_gates(tmp_path, monkeypatch, outcome):
    source = snapshot()
    original = deepcopy(source)
    calls, renders = [], []
    monkeypatch.setattr(service, "read_report_snapshot", lambda *a, **k: deepcopy(source))
    monkeypatch.setattr(service, "KeyRotator", lambda *a: object())
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(rq, "get_current_job", lambda: SimpleNamespace(
        id=f"report-rerun:{job}", retries_left=3, retry_intervals=[60, 300, 900], meta={}, save=lambda: None))
    monkeypatch.setattr(audit_repair, "MAX_REPAIR_ITERATIONS", 0)

    async def generate(agent, data, context, rotator, **kwargs):
        calls.append(agent)
        assert context["analyses"] == {22: "original technical", 23: "original institutional"}
        if outcome == "deferred":
            raise AgentDeferredError(24, [{"model_id": "fixture", "retry_wait_seconds": 60}])
        context["analyses"][24] = "new final"
        if outcome != "incomplete": context["structured_outputs"][24] = {"trade_direction": "Neutral"}
        else: context.setdefault("blocking_issues", []).append("Agent 24 provider output incomplete")
        return 24, "new final"

    def audit(context, **kwargs):
        return {"status": "needs_attention" if outcome == "quality" else "passed",
                "critical": ["Agent 24 source unsupported"] if outcome == "quality" else [],
                "repair_agent_issues": {24: ["source unsupported"]} if outcome == "quality" else {}}

    async def render(**kwargs):
        renders.append(deepcopy(kwargs["context"]))
        return {"filename": "new_v4_report.html"}

    monkeypatch.setattr(service, "run_agent_with_quality_gates_async", generate)
    monkeypatch.setattr(service, "run_final_report_audit", audit)
    monkeypatch.setattr(service, "parse_structured_data", lambda context: {})
    monkeypatch.setattr(service, "render_and_save_rerun_report", render)
    storage = InMemoryStorage()
    storage.save_report(FILENAME, b"source", content_type="text/html")
    job = job_store.create_job("TEST", "rerun:final_recommendation")
    if outcome == "cancelled": job_store.request_job_cancel(job)

    def run():
        return asyncio.run(report_rerun_jobs.run_report_rerun_job_async(
            job, FILENAME, "final_recommendation", output_dir=str(tmp_path), storage=storage))

    if outcome == "deferred":
        with pytest.raises(AgentDeferredError): run()
        assert job_store.get_job(job)["status"] == "waiting_retry"
    else:
        result = run()
        assert result == ("new_v4_report.html" if outcome == "success" else "")
        assert job_store.get_job(job)["status"] == (
            "done" if outcome == "success" else "cancelled" if outcome == "cancelled" else "error")
    assert calls == ([] if outcome == "cancelled" else [24])
    assert len(renders) == (1 if outcome == "success" else 0)
    assert source == original
    if outcome in {"quality", "incomplete", "cancelled"}:
        before = list(calls)
        assert run() == ""
        assert calls == before  # Failed jobs cannot be resurrected by retrying the entrypoint.
