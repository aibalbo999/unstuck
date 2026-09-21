"""Offline source audit to usage joins and per-fetch attribution."""
import asyncio
import json
import sqlite3

from data_fetch.service import StockDataService
from data_fetch.types import FetchRequest
from data_trust import build_source_audit_entry
import api_usage_recorders


def test_fetch_identity_is_attached_before_work_and_survives_source_audit():
    async def fetch(request):
        audit = await asyncio.to_thread(build_source_audit_entry, "market_data", "fixture", "success")
        return {"ticker": request.ticker, "source_audit": [audit]}

    result = asyncio.run(StockDataService(fetcher=fetch).fetch_async(
        FetchRequest.from_ticker("2330.TW", record_provider_sla=False)))
    entry = result.source_audit[0]
    assert entry.get("ticker") == "2330.TW"
    assert entry.get("fetch_id")
    assert entry.get("event_kind") == "aggregate"
    assert "job_id" not in entry  # A standalone fetch must not invent a job.


def test_usage_preserves_explicit_join_fields_without_recording_unrelated_metadata(tmp_path):
    path = tmp_path / "usage.sqlite3"
    api_usage_recorders.record_provider_audit_usage({
        "source": "market_data", "provider": "fixture", "status": "success",
        "job_id": "job-a", "ticker": "2330.TW", "fetch_id": "fetch-a",
        "event_kind": "aggregate", "operation_id": "operation-a",
        "data_fingerprint": "a" * 64, "api_key": "SECRET_SENTINEL",
    }, db_path=path)
    with sqlite3.connect(path) as conn:
        raw = conn.execute("select metadata_json from api_usage_events").fetchone()[0]
    metadata = json.loads(raw)
    assert metadata.get("job_id") == "job-a"
    assert metadata.get("ticker") == "2330.TW"
    assert metadata.get("fetch_id") == "fetch-a"
    assert metadata.get("event_kind") == "aggregate"
    assert metadata.get("data_fingerprint") == "a" * 64
    assert "SECRET_SENTINEL" not in raw


def test_concurrent_jobs_keep_fetch_and_thread_pool_audits_separate(monkeypatch):
    from provider_correlation import correlate_job, current_correlation
    from data_fetch.market_sources.common import _run_named_fetches
    import provider_resilience

    monkeypatch.setattr(provider_resilience, "_check_provider_state", lambda *_: None)
    monkeypatch.setattr(provider_resilience, "enforce_provider_throttle", lambda *_: None)
    monkeypatch.setattr(provider_resilience, "_record_provider_success", lambda *_: None)

    async def fetch(request):
        def threaded():
            return _run_named_fetches({"news": (lambda: [{"title": "fixture"}], (), [], "",
                                                   "recent_catalysts", "fixture")}, include_audit=True)
        result = await asyncio.to_thread(threaded)
        return {"source_audit": result["audit"]}

    service = StockDataService(fetcher=fetch)

    @correlate_job
    async def job(job_id, ticker):
        return await service.fetch_async(FetchRequest.from_ticker(ticker, record_provider_sla=False))

    async def run():
        results = await asyncio.gather(job("job-a", "2330.TW"), job("job-b", "3324.TWO"))
        assert current_correlation() == {}
        return results

    first, second = asyncio.run(run())
    audits = [result.source_audit[0] for result in (first, second)]
    assert [(entry["job_id"], entry["ticker"]) for entry in audits] == [
        ("job-a", "2330.TW"), ("job-b", "3324.TWO")]
    assert audits[0]["fetch_id"] != audits[1]["fetch_id"]
    for entry in audits:
        assert len(entry["provider_attempts"]) == 1
        assert entry["provider_attempts"][0]["source"] == "recent_catalysts"
        assert entry["provider_attempts"][0]["status"] == "success"


def test_retry_attempts_share_operation_but_have_unique_ids(monkeypatch):
    import provider_resilience
    from source_audit import audited_fetch
    from provider_correlation import correlation_scope, current_correlation

    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("PROVIDER_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("PROVIDER_RETRY_JITTER_SECONDS", "0")
    monkeypatch.setattr(provider_resilience, "_check_provider_state", lambda *_: None)
    monkeypatch.setattr(provider_resilience, "enforce_provider_throttle", lambda *_: None)
    monkeypatch.setattr(provider_resilience, "_record_provider_success", lambda *_: None)
    seen = []

    def callback():
        seen.append(current_correlation())
        if len(seen) == 1:
            raise RuntimeError("fixture retry")
        return [1]

    with correlation_scope(job_id="job-r", ticker="2330.TW", fetch_id="fetch-r"):
        entry = audited_fetch("market_data", "fixture", callback)["audit"]
        assert "attempt_id" not in current_correlation()
    assert current_correlation() == {}
    assert [a["status"] for a in entry["provider_attempts"]] == ["error", "success"]
    assert len({a["attempt_id"] for a in entry["provider_attempts"]}) == 2
    assert {item["operation_id"] for item in seen} == {entry["operation_id"]}
    assert {item["fetch_id"] for item in seen} == {"fetch-r"}


def test_cancelled_fetch_and_late_thread_do_not_leak_into_next_job():
    import threading
    from provider_correlation import correlate_job, current_correlation

    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    late_context = []

    async def fetch(request):
        if request.ticker == "2330.TW":
            def blocked():
                started.set()
                assert release.wait(3)
                late_context.append(current_correlation())
                finished.set()
            await asyncio.to_thread(blocked)
        return {"source_audit": [build_source_audit_entry("market_data", "fixture", "success")]}

    @correlate_job
    async def job(job_id, ticker):
        return await StockDataService(fetcher=fetch).fetch_async(
            FetchRequest.from_ticker(ticker, record_provider_sla=False))

    async def run():
        task = asyncio.create_task(job("cancelled-job", "2330.TW"))
        assert await asyncio.to_thread(started.wait, 3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert current_correlation() == {}
        second = await job("next-job", "3324.TWO")
        release.set()
        assert await asyncio.to_thread(finished.wait, 3)
        return second

    result = asyncio.run(run())
    assert result.source_audit[0]["job_id"] == "next-job"
    assert late_context[0]["job_id"] == "cancelled-job"
    assert late_context[0]["fetch_id"] != result.source_audit[0]["fetch_id"]
    assert current_correlation() == {}


def test_sla_usage_join_uses_existing_event_id_without_inventing_legacy_job(monkeypatch, tmp_path):
    import provider_sla
    from provider_correlation import correlation_scope

    path = tmp_path / "sla.sqlite3"
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(path))
    with correlation_scope(job_id="current-job", ticker="2330.TW", fetch_id="current-fetch"):
        provider_sla.record_source_audit_entries([
            {"source": "market_data", "provider": "fixture", "status": "success", "record_count": 1,
             "job_id": "explicit-job", "ticker": "3324.TWO", "fetch_id": "explicit-fetch"},
            {"source": "market_data", "provider": "legacy", "status": "success"},
        ])
    with sqlite3.connect(path) as conn:
        rows = conn.execute("select provider,metadata_json from api_usage_events order by id").fetchall()
        event_ids = {row[0] for row in conn.execute("select id from provider_sla_events")}
    metadata = [json.loads(row[1]) for row in rows]
    assert {item["provider_sla_event_id"] for item in metadata} == event_ids
    assert metadata[0]["job_id"] == "explicit-job"
    assert metadata[0]["fetch_id"] == "explicit-fetch"
    assert "job_id" not in metadata[1]
    assert "fetch_id" not in metadata[1]


def test_fetch_result_does_not_mix_new_identity_into_retained_entry():
    async def fetch(request):
        return {"source_audit": [{"source": "market_data", "provider": "legacy",
                                  "job_id": "old-job", "status": "success"}]}
    result = asyncio.run(StockDataService(fetcher=fetch).fetch_async(
        FetchRequest.from_ticker("2330.TW", record_provider_sla=False)))
    assert result.source_audit[0]["job_id"] == "old-job"
    assert "fetch_id" not in result.source_audit[0]


def test_real_job_entrypoints_bind_and_reset_job_identity_on_early_exit(monkeypatch):
    import analysis_jobs
    import report_rerun_jobs
    from provider_correlation import current_correlation

    observed = []
    for module in (analysis_jobs, report_rerun_jobs):
        monkeypatch.setattr(module, "has_api_keys", lambda: False)
        monkeypatch.setattr(module, "update_job", lambda *a, **k: observed.append(current_correlation()))
        monkeypatch.setattr(module, "append_event", lambda *a, **k: None)
    asyncio.run(analysis_jobs.run_stock_analysis_job_async("analysis-job", "2330.TW"))
    assert observed and all(value["job_id"] == "analysis-job" for value in observed)
    assert current_correlation() == {}
    observed.clear()
    asyncio.run(report_rerun_jobs.run_report_rerun_job_async("rerun-job", "not-a-ticker.html"))
    assert observed and all(value["job_id"] == "rerun-job" for value in observed)
    assert all("ticker" not in value for value in observed)
    assert current_correlation() == {}


def test_new_fetch_does_not_inherit_an_enclosing_operations_attempt_list():
    from provider_correlation import source_operation, provider_attempt

    async def fetch(request):
        return {"source_audit": [build_source_audit_entry("news", "new-provider", "success")]}

    with source_operation("old-source", "old-provider"):
        with provider_attempt("old-provider", 1):
            pass
        result = asyncio.run(StockDataService(fetcher=fetch).fetch_async(
            FetchRequest.from_ticker("2330.TW", record_provider_sla=False)))
    assert "provider_attempts" not in result.source_audit[0]
