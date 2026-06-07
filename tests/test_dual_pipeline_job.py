import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import analysis_jobs  # noqa: E402
import pipeline_modes  # noqa: E402
from agent_runtime import AnalysisResult  # noqa: E402
from data_fetch import FetchResult  # noqa: E402
from data_trust import DATA_SNAPSHOT_SCHEMA_VERSION, unknown_data_trust  # noqa: E402
from reporting import ReportBundle  # noqa: E402


def test_dual_pipeline_job_runs_v1_then_v2(monkeypatch, tmp_path):
    events = []
    updates = []
    pipeline_calls = []

    class FakeStockDataService:
        async def fetch_async(self, request):
            data = {
                "ticker": request.ticker,
                "company_name": "測試公司",
                "current_price": 100,
                "fetch_date": "2026年06月06日",
                "price_history": {},
            }
            return FetchResult(request=request, data=data, data_trust=unknown_data_trust())

    class FakePipelineRunner:
        async def run_async(self, request):
            pipeline_id = request.pipeline_id
            data = request.data
            pipeline_calls.append(pipeline_id)
            pipeline_def = pipeline_modes.get_pipeline_definition(pipeline_id)
            if request.progress_callback:
                request.progress_callback(1, len(pipeline_def["agents"]), "Fake Agent")
            context = {
                "ticker": data["ticker"],
                "company_name": data["company_name"],
                "data": data,
                "pipeline_id": pipeline_id,
                "analyses": {},
                "structured_outputs": {},
                "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
            }
            return AnalysisResult(context=context, pipeline_id=pipeline_id)

    class FakeReportRenderer:
        async def render_async(self, request):
            trust = unknown_data_trust()
            snapshot = {
                "snapshot_schema_version": DATA_SNAPSHOT_SCHEMA_VERSION,
                "snapshot_truncated": False,
                "snapshot_size_bytes": 0,
                "snapshot_omitted_sections": [],
                "ticker": request.context["ticker"],
                "pipeline": request.pipeline_id,
                "generated_at": "2026-06-07T00:00:00+00:00",
                "data_schema_version": None,
                "source_freshness": {},
                "source_audit": [],
                "data_trust": trust,
                "data": request.context["data"],
            }
            return ReportBundle(
                html=f"<html>{request.context['pipeline_id']}</html>",
                markdown=f"# {request.context['pipeline_id']}",
                data_snapshot=snapshot,
            )

    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", FakeStockDataService())
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", FakePipelineRunner())
    monkeypatch.setattr(analysis_jobs, "REPORT_RENDERER", FakeReportRenderer())
    monkeypatch.setattr(analysis_jobs, "append_event", lambda job_id, payload: events.append(payload))
    monkeypatch.setattr(analysis_jobs, "update_job", lambda job_id, status, filename=None, error=None: updates.append((status, filename, error)))

    filename = asyncio.run(analysis_jobs.run_stock_analysis_job_async("job-test", "2449.TW", "both"))

    assert pipeline_calls == ["v1", "v2"]
    assert filename.startswith("2449_TW_v2_report_")
    assert (tmp_path / filename).exists()
    assert len(list(tmp_path.glob("2449_TW_*_report_*.html"))) == 2
    assert len(list(tmp_path.glob("2449_TW_*_report_*.data.json"))) == 2

    report_done_events = [event for event in events if event["type"] == "report_done"]
    assert [event["pipeline_id"] for event in report_done_events] == ["v1", "v2"]
    assert all(event["data_filename"].endswith(".data.json") for event in report_done_events)
    assert all(event["data_trust"]["status"] == "unknown" for event in report_done_events)

    done_event = next(event for event in events if event["type"] == "done")
    assert done_event["pipeline_id"] == "both"
    assert done_event["last_pipeline_id"] == "v2"
    assert len(done_event["filenames"]) == 2

    progress_events = [event for event in events if event["type"] == "progress"]
    assert progress_events[0]["current"] == 1
    assert progress_events[0]["total"] == 13
    assert progress_events[1]["current"] == 8
    assert progress_events[1]["total"] == 13
    assert updates[-1][0] == "done"
