"""Publication must not turn a blocked workflow or snapshot into success."""
import asyncio
from types import SimpleNamespace

import pytest

import analysis_jobs
from agent_runtime import AnalysisResult
from data_fetch import FetchResult
from report_persistence import persist_report_bundle, report_bundle_keys_for_filename
from report_publication_gate import ReportPublicationBlockedError
from reporting import ReportBundle
from storage.report_storage import InMemoryStorage


@pytest.mark.parametrize("quality", [
    {"final_audit": {"status": "needs_attention", "critical": ["unverifiable DCF source"]}},
    {"final_audit": {"status": "blocked"}},
    {"content_credibility": {"status": "blocked"}},
    {"report_conformance": {"status": "blocked"}},
    {"evidence_exit_gate": {"verdict": "rejected"}},
    {"report_lint": {"status": "blocked"}},
])
def test_blocked_bundle_never_overwrites_existing_report_or_index(quality):
    filename = "TEST_v1_report_job_existing.html"
    key = report_bundle_keys_for_filename(filename).html_key
    storage = InMemoryStorage()
    storage.save_report(key, b"previous accepted report", content_type="text/html")
    indexed = []
    repository = SimpleNamespace(upsert=lambda *a, **kw: indexed.append(kw))
    with pytest.raises(ReportPublicationBlockedError, match="品質檢查未通過"):
        persist_report_bundle(filename=filename, html_content="blocked new report", markdown_content="draft",
                              data_snapshot=quality, storage=storage, repository=repository)
    assert storage.get_report(key).content == b"previous accepted report"
    assert len(storage.list_reports()) == 1
    assert indexed == []


def test_warning_bundle_remains_publishable():
    storage = InMemoryStorage()
    result = persist_report_bundle(
        filename="TEST_v1_report_job_warning.html", html_content="warning disclosed", markdown_content="warning",
        data_snapshot={"final_audit": {"status": "passed", "warnings": ["optional source stale"]},
                       "content_credibility": {"status": "warning"}, "evidence_exit_gate": {"verdict": "caution"}},
        storage=storage, repository=SimpleNamespace(upsert=lambda *a, **kw: {}))
    assert result["filename"].endswith("warning.html")
    assert len(storage.list_reports()) == 3


@pytest.mark.parametrize("blocked_at", ["workflow", "rendered_snapshot", "lint"])
def test_combined_job_stops_at_blocked_mode_without_false_done(monkeypatch, tmp_path, blocked_at):
    events, updates, calls, rendered = [], [], [], []

    async def fetch(request):
        return FetchResult(request=request, data={"ticker": "TEST", "current_price": 100}, data_trust={"status": "fresh"})

    async def run(request):
        calls.append(request.pipeline_id)
        context = {"ticker": "TEST", "pipeline_id": request.pipeline_id,
                   "final_audit": {"status": "passed", "critical": []}}
        if request.pipeline_id == "v2" and blocked_at == "workflow":
            context.update(status="blocked", blocking_issues=["unverifiable DCF source"])
            context["final_audit"] = {"status": "needs_attention", "critical": ["unverifiable DCF source"]}
        return AnalysisResult(context=context, pipeline_id=request.pipeline_id)

    async def render(request):
        rendered.append(request.pipeline_id)
        if request.pipeline_id == "v2" and blocked_at == "lint":
            from reporting.lint import assert_report_lint_passed
            assert_report_lint_passed("<p>Senior Analyst at Goldman Sachs</p>", "draft")
        snapshot = {"ticker": "TEST", "final_audit": request.context["final_audit"]}
        if request.pipeline_id == "v2" and blocked_at == "rendered_snapshot":
            snapshot["content_credibility"] = {"status": "blocked", "blocking_issues": [{"message": "contradictory trade direction"}]}
        return ReportBundle(html="accepted", markdown="accepted", data_snapshot=snapshot)

    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "is_job_cancel_requested", lambda _: False)
    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", SimpleNamespace(fetch_async=fetch))
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", SimpleNamespace(run_async=run))
    monkeypatch.setattr(analysis_jobs, "REPORT_RENDERER", SimpleNamespace(render_async=render))
    monkeypatch.setattr(analysis_jobs, "build_temporal_memory", lambda *a, **kw: {})
    monkeypatch.setattr(analysis_jobs, "append_event", lambda _, p: events.append(p))
    monkeypatch.setattr(analysis_jobs, "update_job", lambda _, status, **kw: updates.append(status))
    result = asyncio.run(analysis_jobs.run_stock_analysis_job_async("publication-test", "TEST", "both"))
    assert result == ""
    assert updates[-1] == "error" and "done" not in updates
    assert calls == ["v1", "v2"]
    assert rendered == (["v1"] if blocked_at == "workflow" else ["v1", "v2"])
    assert [e["pipeline_id"] for e in events if e["type"] == "report_done"] == ["v1"]
    assert not any(e["type"] == "done" for e in events)
    assert events[-1]["phase"] == "report_quality_blocked"
    assert events[-1]["pipeline_id"] == "v2"
    assert len(list(tmp_path.rglob("*.html"))) == 1


@pytest.mark.parametrize("from_audit", [True, False, "lint"])
def test_partial_rerun_quality_failures_have_quality_phase(monkeypatch, tmp_path, from_audit):
    import report_rerun_jobs as jobs
    from report_rerun_audit import FinalRerunQualityBlockedError
    events, updates = [], []

    async def rerun(*a, **kw):
        if from_audit == "lint":
            from reporting.lint import assert_report_lint_passed
            assert_report_lint_passed("<p>Senior Analyst at Goldman Sachs</p>", "draft")
        if from_audit is True:
            raise FinalRerunQualityBlockedError("稽核未通過，請完整重跑。")
        raise ReportPublicationBlockedError(["內容可信度未通過"])

    monkeypatch.setattr(jobs.report_rerun_service, "rerun_report_analysis", rerun)
    monkeypatch.setattr(jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(jobs, "is_job_cancel_requested", lambda _: False)
    monkeypatch.setattr(jobs, "append_event", lambda _, p: events.append(p))
    monkeypatch.setattr(jobs, "update_job", lambda _, status, **kw: updates.append(status))
    result = asyncio.run(jobs.run_report_rerun_job_async(
        "partial-quality", "TEST_v1_report_job_existing.html", scope="final_recommendation", output_dir=str(tmp_path)))
    assert result == "" and updates == ["running", "error"]
    assert events[-1]["phase"] == "report_quality_blocked"
    assert events[-1]["retry_scheduled"] is False
    assert not any(e["type"] in {"done", "report_done"} for e in events)
