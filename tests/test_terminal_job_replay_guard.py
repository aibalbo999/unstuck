"""A stale Redis snapshot must not replay an already terminal report job."""

import asyncio

import pytest

import analysis_jobs
import job_store
import report_rerun_jobs


@pytest.mark.parametrize("terminal_status", ["done", "error", "cancelled"])
def test_terminal_analysis_job_replay_does_not_fetch_or_change_history(monkeypatch, terminal_status):
    job_id = job_store.create_job("6505.TW", "v4")
    filename = "6505_TW_v4_report_job_original.html" if terminal_status == "done" else None
    job_store.update_job(job_id, terminal_status, filename=filename, error="original error")
    before = job_store.get_job(job_id)
    events_before = job_store.get_events_since(job_id)

    async def unexpected_fetch(_request):
        pytest.fail("terminal replay fetched data")

    monkeypatch.setattr(analysis_jobs.STOCK_DATA_SERVICE, "fetch_async", unexpected_fetch)
    result = asyncio.run(analysis_jobs.run_stock_analysis_job_async(job_id, "6505.TW", "v4"))

    assert result == (filename or "")
    assert job_store.get_job(job_id) == before
    assert job_store.get_events_since(job_id) == events_before


@pytest.mark.parametrize("terminal_status", ["done", "error", "cancelled"])
def test_terminal_report_rerun_replay_does_not_publish_or_change_history(monkeypatch, terminal_status):
    job_id = job_store.create_job("original.html", "rerun:full")
    filename = "rerun.html" if terminal_status == "done" else None
    job_store.update_job(job_id, terminal_status, filename=filename, error="original error")
    before = job_store.get_job(job_id)
    events_before = job_store.get_events_since(job_id)

    async def unexpected_rerun(*_args, **_kwargs):
        pytest.fail("terminal replay regenerated a report")

    monkeypatch.setattr(report_rerun_jobs.report_rerun_service, "rerun_report_analysis", unexpected_rerun)
    result = asyncio.run(report_rerun_jobs.run_report_rerun_job_async(job_id, "original.html", "full"))

    assert result == (filename or "")
    assert job_store.get_job(job_id) == before
    assert job_store.get_events_since(job_id) == events_before
