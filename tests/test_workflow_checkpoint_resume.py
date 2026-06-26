import asyncio
import sys
from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agent_runtime.retry_policy import AgentRateLimitError
from agent_runtime import AnalysisResult
from data_fetch import FetchResult
from data_trust import unknown_data_trust
import analysis_jobs
from workflow_graph import execute_persistent_graph, open_sqlite_checkpointer
from workflow_state import AgentGraphState


async def _sqlite_pragmas(path):
    async with open_sqlite_checkpointer(path) as saver:
        journal_cursor = await saver.conn.execute("PRAGMA journal_mode")
        journal_mode = (await journal_cursor.fetchone())[0]
        timeout_cursor = await saver.conn.execute("PRAGMA busy_timeout")
        busy_timeout = (await timeout_cursor.fetchone())[0]
        return journal_mode, busy_timeout


def _resume_fixture_builder(calls, *, allow_b):
    builder = StateGraph(AgentGraphState)

    async def node_a(state):
        calls["a"] += 1
        return {"execution_trace": [{"id": "a"}]}

    async def node_b(state):
        calls["b"] += 1
        if not allow_b:
            raise AgentRateLimitError("429", 0, 60)
        return {"status": "done"}

    builder.add_node("node_a", node_a)
    builder.add_node("node_b", node_b)
    builder.add_edge(START, "node_a")
    builder.add_edge("node_a", "node_b")
    builder.add_edge("node_b", END)
    return builder


async def run_resume_fixture(checkpoint, thread_id, calls, *, allow_b):
    return await execute_persistent_graph(
        graph_builder=_resume_fixture_builder(calls, allow_b=allow_b),
        initial_state={
            "run_id": "run-429",
            "ticker": "2330.TW",
            "company_name": "台積電",
            "pipeline_id": "v4",
        },
        thread_id=thread_id,
        checkpoint_path=checkpoint,
    )


def test_sqlite_checkpointer_sets_wal_and_busy_timeout(tmp_path):
    checkpoint = tmp_path / "checkpoints.sqlite3"

    journal_mode, busy_timeout = asyncio.run(_sqlite_pragmas(checkpoint))

    assert journal_mode == "wal"
    assert busy_timeout == 30000


def test_sqlite_resume_does_not_repeat_successful_nodes(tmp_path):
    calls = {"a": 0, "b": 0}
    checkpoint = tmp_path / "checkpoints.sqlite3"
    thread_id = "job-429"

    with pytest.raises(AgentRateLimitError):
        asyncio.run(run_resume_fixture(checkpoint, thread_id, calls, allow_b=False))

    result = asyncio.run(run_resume_fixture(checkpoint, thread_id, calls, allow_b=True))

    assert result["status"] == "done"
    assert calls == {"a": 1, "b": 2}


def test_analysis_job_passes_stable_thread_id_and_checkpoint_path(monkeypatch, tmp_path):
    requests = []
    rendered_filenames = []

    class FakeStockDataService:
        async def fetch_async(self, request):
            data = {
                "ticker": request.ticker,
                "company_name": "測試公司",
                "current_price": 100,
                "fetch_date": "2026年06月27日",
                "price_history": {},
            }
            return FetchResult(request=request, data=data, data_trust=unknown_data_trust())

    class FakePipelineRunner:
        async def run_async(self, request):
            requests.append(request)
            return AnalysisResult(
                context={
                    "ticker": request.data["ticker"],
                    "company_name": request.data["company_name"],
                    "data": request.data,
                    "pipeline_id": request.pipeline_id,
                    "analyses": {},
                    "structured_outputs": {},
                    "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
                },
                pipeline_id=request.pipeline_id,
            )

    async def fake_render_and_persist_report(**kwargs):
        rendered_filenames.append(kwargs["filename"])
        return {
            "type": "report_done",
            "filename": f"{kwargs['ticker_upper']}_{kwargs['current_pipeline_id']}.html",
            "pipeline_id": kwargs["current_pipeline_id"],
            "pipeline_label": kwargs["pipeline_def"]["label"],
            "audit": kwargs["audit_notice"],
        }

    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", FakeStockDataService())
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", FakePipelineRunner())
    monkeypatch.setattr(analysis_jobs, "render_and_persist_report", fake_render_and_persist_report)
    monkeypatch.setattr(analysis_jobs, "append_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_jobs, "update_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        analysis_jobs,
        "runtime_settings_for_output_dir",
        lambda _output_dir: type("Settings", (), {"checkpoint_path": str(tmp_path / "checkpoints.sqlite3")})(),
        raising=False,
    )

    asyncio.run(analysis_jobs.run_stock_analysis_job_async("job-thread", "2330.TW", "v4"))

    assert requests[0].thread_id == "job-thread:v4"
    assert requests[0].checkpoint_path == str(tmp_path / "checkpoints.sqlite3")
    assert requests[0].report_filename == analysis_jobs.stable_report_filename(
        "job-thread",
        "2330.TW",
        "v4",
    )
    assert rendered_filenames == [requests[0].report_filename]


def test_analysis_job_marks_rate_limited_workflow_waiting_retry(monkeypatch, tmp_path):
    updates = []
    events = []

    class FakeStockDataService:
        async def fetch_async(self, request):
            data = {
                "ticker": request.ticker,
                "company_name": "測試公司",
                "current_price": 100,
                "fetch_date": "2026年06月27日",
                "price_history": {},
            }
            return FetchResult(request=request, data=data, data_trust=unknown_data_trust())

    class RateLimitedPipelineRunner:
        async def run_async(self, request):
            raise AgentRateLimitError("429", 0, 60)

    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", FakeStockDataService())
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", RateLimitedPipelineRunner())
    monkeypatch.setattr(analysis_jobs, "append_event", lambda job_id, payload: events.append(payload))
    monkeypatch.setattr(
        analysis_jobs,
        "update_job",
        lambda job_id, status, filename=None, error=None, **kwargs: updates.append((status, error)),
    )
    monkeypatch.setattr(
        analysis_jobs,
        "runtime_settings_for_output_dir",
        lambda _output_dir: type("Settings", (), {"checkpoint_path": str(tmp_path / "checkpoints.sqlite3")})(),
        raising=False,
    )

    with pytest.raises(AgentRateLimitError):
        asyncio.run(analysis_jobs.run_stock_analysis_job_async("job-429", "2330.TW", "v4"))

    assert updates[-1][0] == "waiting_retry"
    retry_event = events[-1]
    assert retry_event["phase"] == "workflow_retry"
    assert retry_event["thread_id"] == "job-429:v4"
