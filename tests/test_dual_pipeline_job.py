import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import analysis_jobs  # noqa: E402
import pipeline_modes  # noqa: E402


def test_dual_pipeline_job_runs_v1_then_v2(monkeypatch, tmp_path):
    events = []
    updates = []
    pipeline_calls = []

    async def fake_fetch_stock_data(ticker):
        return {
            "ticker": ticker,
            "company_name": "測試公司",
            "current_price": 100,
            "fetch_date": "2026年06月06日",
            "price_history": {},
        }

    async def fake_run_pipeline(data, progress_callback=None, pipeline_id="v1"):
        pipeline_calls.append(pipeline_id)
        pipeline_def = pipeline_modes.get_pipeline_definition(pipeline_id)
        if progress_callback:
            progress_callback(1, len(pipeline_def["agents"]), "Fake Agent")
        return {
            "ticker": data["ticker"],
            "company_name": data["company_name"],
            "data": data,
            "pipeline_id": pipeline_id,
            "analyses": {},
            "structured_outputs": {},
            "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
        }

    async def fake_generate_html_report(context):
        return f"<html>{context['pipeline_id']}</html>"

    def fake_generate_markdown_report(context):
        return f"# {context['pipeline_id']}"

    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "async_fetch_stock_data", fake_fetch_stock_data)
    monkeypatch.setattr(analysis_jobs, "run_analysis_pipeline_async", fake_run_pipeline)
    monkeypatch.setattr(analysis_jobs, "generate_html_report_async", fake_generate_html_report)
    monkeypatch.setattr(analysis_jobs, "generate_markdown_report", fake_generate_markdown_report)
    monkeypatch.setattr(analysis_jobs, "append_event", lambda job_id, payload: events.append(payload))
    monkeypatch.setattr(analysis_jobs, "update_job", lambda job_id, status, filename=None, error=None: updates.append((status, filename, error)))

    filename = asyncio.run(analysis_jobs.run_stock_analysis_job_async("job-test", "2449.TW", "both"))

    assert pipeline_calls == ["v1", "v2"]
    assert filename.startswith("2449_TW_v2_report_")
    assert (tmp_path / filename).exists()
    assert len(list(tmp_path.glob("2449_TW_*_report_*.html"))) == 2

    report_done_events = [event for event in events if event["type"] == "report_done"]
    assert [event["pipeline_id"] for event in report_done_events] == ["v1", "v2"]

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
