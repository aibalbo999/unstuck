import asyncio
import json
from types import SimpleNamespace

import pytest
import rq

import analysis_jobs
import report_rerun_jobs
import task_queue_arq
from analysis_job_retry import prepare_analysis_retry
from agent_runtime.deferred import AgentDeferredError
from workflow_graph import is_retryable_workflow_error


@pytest.fixture
def retry_job(monkeypatch, tmp_path):
    events, updates, saved = [], [], []
    job = SimpleNamespace(id="analysis:job-deferred", retries_left=3, retry_intervals=[60, 300, 900], save=lambda: saved.append(True))

    async def fetch(_request):
        return SimpleNamespace(data={"ticker": "TEST", "company_name": "Test", "current_price": 100})

    async def run(_request):
        raise AgentDeferredError(2, [{"model_id": "test-model", "reason_code": "daily_quota_disabled", "retry_wait_seconds": 18000}])

    monkeypatch.setattr(rq, "get_current_job", lambda: job)
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "_raise_if_cancelled", lambda *_: None)
    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", SimpleNamespace(fetch_async=fetch))
    monkeypatch.setattr(analysis_jobs, "build_data_fetch_blocking_notice", lambda *_: None)
    monkeypatch.setattr(analysis_jobs, "build_temporal_memory", lambda *a, **kw: {})
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", SimpleNamespace(run_async=run))
    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(analysis_jobs, "runtime_settings_for_output_dir", lambda *_: SimpleNamespace(checkpoint_path=str(tmp_path / "checkpoint.sqlite3")))
    monkeypatch.setattr(analysis_jobs, "append_event", lambda _job, event: events.append(event))
    monkeypatch.setattr(analysis_jobs, "update_job", lambda _job, status, **kw: updates.append((status, kw)))
    monkeypatch.setattr(analysis_jobs, "render_and_persist_report", lambda **kw: pytest.fail("deferred job must not publish a report"))
    return job, events, updates, saved


def test_rq_retry_respects_model_recovery_time(retry_job):
    job, events, updates, saved = retry_job
    with pytest.raises(AgentDeferredError):
        asyncio.run(analysis_jobs.run_stock_analysis_job_async("job-deferred", "TEST", "v4"))
    assert min(job.retry_intervals) >= 18000
    assert saved
    assert updates[-1][0] == "waiting_retry"
    assert events[-1]["retry_after_seconds"] >= 18000
    assert events[-1]["retry_scheduled"] is True
    assert events[-1]["retry_at"] is not None
    assert events[-1]["routes"][0]["reason_code"] == "daily_quota_disabled"


def test_exhausted_rq_retry_budget_does_not_leave_waiting_job(retry_job):
    job, events, updates, _ = retry_job
    job.retries_left = 0
    with pytest.raises(AgentDeferredError):
        asyncio.run(analysis_jobs.run_stock_analysis_job_async("job-deferred", "TEST", "v4"))
    assert updates[-1][0] == "error"
    assert events[-1]["type"] == "error"
    assert events[-1]["retry_scheduled"] is False
    assert events[-1]["retry_at"] is None


def test_deferred_routes_do_not_trigger_immediate_graph_retries():
    error = AgentDeferredError(2, [{"model_id": "test", "retry_wait_seconds": 600}])
    assert is_retryable_workflow_error(error) is False


def test_retry_metadata_matches_longer_queue_interval(monkeypatch):
    job = SimpleNamespace(id="analysis:later", retries_left=1, retry_intervals=[60, 300, 900], save=lambda: None)
    monkeypatch.setattr(rq, "get_current_job", lambda: job)
    job.get_retry_interval = lambda: job.retry_intervals[-1]
    result = prepare_analysis_retry("later", Exception("unavailable"))
    assert result["retry_after_seconds"] == 900


@pytest.fixture
def rerun_retry_job(monkeypatch, tmp_path):
    events, updates = [], []
    job = SimpleNamespace(id="report-rerun:rerun-deferred", retries_left=2, retry_intervals=[60, 300], save=lambda: None)
    monkeypatch.setattr(rq, "get_current_job", lambda: job)
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(report_rerun_jobs, "_raise_if_cancelled", lambda *_: None)
    monkeypatch.setattr(report_rerun_jobs, "append_event", lambda _job, event: events.append(event))
    monkeypatch.setattr(report_rerun_jobs, "update_job", lambda _job, status, **kw: updates.append((status, kw)))

    async def rerun(*args, **kwargs):
        raise AgentDeferredError(16, [{"model_id": "test", "retry_wait_seconds": 1800}])

    monkeypatch.setattr(report_rerun_jobs.report_rerun_service, "rerun_report_analysis", rerun)
    monkeypatch.setattr(report_rerun_jobs, "OUTPUT_DIR", str(tmp_path))
    return job, events, updates


def test_report_rerun_defers_without_publishing(rerun_retry_job, tmp_path):
    job, events, updates = rerun_retry_job
    with pytest.raises(AgentDeferredError):
        asyncio.run(report_rerun_jobs.run_report_rerun_job_async("rerun-deferred", "sample.html", output_dir=str(tmp_path), storage=object()))
    assert updates[-1][0] == "waiting_retry"
    assert min(job.retry_intervals) >= 1800
    assert events[-1]["retry_after_seconds"] >= 1800
    assert events[-1]["retry_scheduled"] is True
    assert events[-1]["retry_at"] is not None
    assert not any(event["type"] in {"done", "report_done"} for event in events)


@pytest.mark.parametrize("current_id", [None, "analysis:unrelated"])
def test_missing_matching_rq_job_cannot_claim_a_scheduled_retry(monkeypatch, current_id):
    saved = []
    job = None if current_id is None else SimpleNamespace(
        id=current_id, retries_left=3, retry_intervals=[60], save=lambda: saved.append(True),
    )
    monkeypatch.setattr(rq, "get_current_job", lambda: job)
    error = AgentDeferredError(2, [{"model_id": "test", "retry_wait_seconds": 1800}])

    result = prepare_analysis_retry("job-deferred", error)

    assert result["retry_scheduled"] is False
    assert result["retry_at"] is None
    assert result["queue_retries_left"] is None
    assert result["retry_budget_exhausted"] is False
    assert result["retry_after_seconds"] == 1800
    assert saved == []


@pytest.mark.parametrize("entrypoint,current_id", [
    ("direct", None), ("direct", "analysis:unrelated"), ("local", None), ("arq", None),
])
def test_analysis_without_retry_scheduler_is_terminal(monkeypatch, retry_job, entrypoint, current_id):
    job, events, updates, saved = retry_job
    if current_id is not None:
        job.id = current_id
    monkeypatch.setattr(rq, "get_current_job", lambda: job if current_id is not None else None)

    async def invoke():
        if entrypoint == "local":
            monkeypatch.setattr("config.TASK_QUEUE_BACKEND", "local")
            return await analysis_jobs.run_stock_analysis_job("job-deferred", "TEST", "v4")
        if entrypoint == "arq":
            return await task_queue_arq.arq_run_stock_analysis_job({}, "job-deferred", "TEST", "v4")
        return await analysis_jobs.run_stock_analysis_job_async("job-deferred", "TEST", "v4")

    with pytest.raises(AgentDeferredError):
        asyncio.run(invoke())

    assert updates[-1][0] == "error"
    assert events[-1]["type"] == "error"
    assert events[-1]["retry_scheduled"] is False
    assert events[-1]["retry_at"] is None
    assert "手動" in events[-1]["message"]
    assert "秒後重試" not in events[-1]["message"]
    assert updates[-1][1]["error"] == events[-1]["message"]
    assert events[-1]["error"] == events[-1]["message"]
    assert not any(event["type"] in {"done", "report_done"} for event in events)
    assert saved == []


@pytest.mark.parametrize("entrypoint,current_id", [
    ("direct", None), ("direct", "report-rerun:unrelated"), ("local", None), ("arq", None),
])
def test_rerun_without_retry_scheduler_is_terminal(monkeypatch, rerun_retry_job, entrypoint, current_id):
    job, events, updates = rerun_retry_job
    if current_id is not None:
        job.id = current_id
    monkeypatch.setattr(rq, "get_current_job", lambda: job if current_id is not None else None)

    async def invoke():
        if entrypoint == "local":
            monkeypatch.setattr("config.TASK_QUEUE_BACKEND", "local")
            return await report_rerun_jobs.run_report_rerun_job("rerun-deferred", "sample.html")
        if entrypoint == "arq":
            return await task_queue_arq.arq_run_report_rerun_job({}, "rerun-deferred", "sample.html")
        return await report_rerun_jobs.run_report_rerun_job_async("rerun-deferred", "sample.html")

    with pytest.raises(AgentDeferredError):
        asyncio.run(invoke())

    assert updates[-1][0] == "error"
    assert events[-1]["type"] == "error"
    assert events[-1]["retry_scheduled"] is False
    assert events[-1]["retry_at"] is None
    assert "手動" in events[-1]["message"]
    assert "秒後重試" not in events[-1]["message"]
    assert updates[-1][1]["error"] == events[-1]["message"]
    assert events[-1]["error"] == events[-1]["message"]
    assert not any(event["type"] in {"done", "report_done"} for event in events)


@pytest.mark.parametrize("caller", ["analysis", "rerun"])
@pytest.mark.parametrize("failure", ["get_current_job", "save"])
def test_retry_preparation_failure_keeps_callers_terminal_and_redacts_detail(monkeypatch, request, caller, failure):
    from redis.exceptions import ConnectionError

    fixture = request.getfixturevalue("retry_job" if caller == "analysis" else "rerun_retry_job")
    job, events, updates = fixture[:3]

    def unavailable():
        raise ConnectionError("redis://fixture-user:secret-fixture-token@localhost/0")

    if failure == "get_current_job":
        monkeypatch.setattr(rq, "get_current_job", unavailable)
    else:
        job.save = unavailable

    with pytest.raises(AgentDeferredError):
        if caller == "analysis":
            asyncio.run(analysis_jobs.run_stock_analysis_job_async("job-deferred", "TEST", "v4"))
        else:
            asyncio.run(report_rerun_jobs.run_report_rerun_job_async("rerun-deferred", "sample.html"))

    assert updates[-1][0] == "error"
    assert events[-1]["type"] == "error"
    assert events[-1]["retry_scheduled"] is False
    assert events[-1]["retry_at"] is None
    assert events[-1]["retry_budget_exhausted"] is False
    assert events[-1]["retry_preparation_error"] == "ConnectionError"
    assert "無法確認自動重試排程" in events[-1]["message"]
    assert updates[-1][1]["error"] == events[-1]["error"] == events[-1]["message"]
    assert "secret-fixture-token" not in json.dumps([events[-1], updates[-1]])
    assert "redis://" not in json.dumps([events[-1], updates[-1]])
    assert not any(event["type"] in {"done", "report_done"} for event in events)
