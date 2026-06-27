import asyncio
import inspect
import sys
import threading
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_local_task_queue_awaits_coroutine_jobs():
    from task_queue import LocalAsyncQueue

    queue = LocalAsyncQueue(max_concurrent=1)
    seen = []

    async def job(value):
        seen.append(value)

    async def run_once():
        queue._running = True
        worker = asyncio.create_task(queue._worker())
        queue.enqueue("job-1", job, "awaited")
        await queue.queue.join()
        queue._running = False
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(run_once())

    assert seen == ["awaited"]


def test_run_stock_analysis_job_local_returns_awaitable(monkeypatch):
    import analysis_jobs
    import config

    monkeypatch.setattr(config, "TASK_QUEUE_BACKEND", "local")
    monkeypatch.setattr(analysis_jobs, "run_stock_analysis_job_async", lambda *args: asyncio.sleep(0, result="ok"))

    result = analysis_jobs.run_stock_analysis_job("job-1", "2308.TW", "v1")

    assert inspect.isawaitable(result)
    assert asyncio.run(result) == "ok"


def test_key_rotator_advances_index_once_per_selected_key(monkeypatch):
    import llm_rate_limits

    monkeypatch.setattr(llm_rate_limits, "emit_log", lambda message: None)
    rotator = llm_rate_limits.KeyRotator(["k1", "k2", "k3"])

    assert rotator.get_key("test-model") == "k1"
    assert rotator.index == 1
    assert rotator.get_key("test-model") == "k2"
    assert rotator.index == 2


def test_key_rotator_async_advances_index_once_per_selected_key(monkeypatch):
    import llm_rate_limits

    monkeypatch.setattr(llm_rate_limits, "emit_log", lambda message: None)
    rotator = llm_rate_limits.KeyRotator(["k1", "k2", "k3"])

    async def run():
        first = await rotator.async_get_key("test-model")
        second = await rotator.async_get_key("test-model")
        return first, second, rotator.index

    assert asyncio.run(run()) == ("k1", "k2", 2)


def test_analysis_done_fallback_handles_empty_pipeline_sequence():
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router

    router = create_analysis_router(AnalysisRouteDeps(
        active_analyses_lock=threading.Lock(),
        get_analysis_task_queue=lambda: None,
        run_stock_analysis_job=lambda job_id, ticker, pipeline: None,
        has_api_keys=lambda: True,
        api_key_setup_message=lambda: "",
        normalize_pipeline_run_id=lambda pipeline: pipeline,
        get_pipeline_run_sequence=lambda pipeline: (),
        get_pipeline_run_label=lambda pipeline: pipeline,
        get_pipeline_run_agent_total=lambda pipeline: 0,
        get_job=lambda job_id: {"job_id": job_id, "ticker": "2308.TW", "pipeline_id": "empty", "status": "done", "filename": "done.html"},
        find_active_job=lambda ticker, pipeline: {"job_id": "job-1"},
        create_job=lambda ticker, pipeline: "job-1",
        get_events_since=lambda job_id, after_id: [],
        update_job=lambda *args, **kwargs: None,
        append_event=lambda *args, **kwargs: None,
        request_job_cancel=lambda *args, **kwargs: False,
        print_streamed_event=lambda *args, **kwargs: None,
        require_mutation_authorized=lambda request: None,
    ))
    route = next(route for route in router.routes if getattr(route.endpoint, "__name__", "") == "analyze_stock")

    class Request:
        headers = {}

        async def is_disconnected(self):
            return False

    response = asyncio.run(
        route.endpoint(
            "2308.TW",
            Request(),
            job_id="job-1",
            last_event_id=0,
            pipeline="empty",
            cancel_on_disconnect=False,
        )
    )
    generator = response.body_iterator
    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert '"last_pipeline_id": "empty"' in second["data"]


def test_validate_runtime_settings_blocks_lan_without_mutation_token(monkeypatch):
    import settings.app_config as app_config

    monkeypatch.setattr(app_config, "DEPLOYMENT_MODE", "lan")
    monkeypatch.setattr(app_config, "MUTATION_API_TOKEN", "")

    with pytest.raises(RuntimeError, match="MUTATION_API_TOKEN"):
        app_config.validate_runtime_settings()


def test_list_reports_does_not_run_cleanup_on_read(monkeypatch, tmp_path):
    import report_history_service

    calls = []
    monkeypatch.setattr(report_history_service, "cleanup_expired_reports", lambda *args, **kwargs: calls.append("expired"))
    monkeypatch.setattr(report_history_service, "cleanup_orphan_markdown_reports", lambda *args, **kwargs: calls.append("orphan"))

    class EmptyRepository:
        def query(self, query):
            return [], 0

    report_history_service.list_reports(
        page=1,
        limit=10,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        output_dir=str(tmp_path),
        report_cache={},
        repository=EmptyRepository(),
    )

    assert calls == []


def test_create_app_warns_and_disables_credentials_for_wildcard_origin(monkeypatch):
    import api

    messages = []
    monkeypatch.setattr(api, "ALLOWED_ORIGINS", ["*"])
    monkeypatch.setattr(api, "emit_log", lambda message: messages.append(message))

    app = api.create_app()
    cors = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")

    assert cors.kwargs["allow_credentials"] is False
    assert any("已停用 credentials 支援" in message for message in messages)


class RecordingLock:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1

    def __exit__(self, exc_type, exc, tb):
        return False


class NoopRepository:
    def delete(self, *args, **kwargs):
        return None


def test_cleanup_expired_reports_uses_report_cache_lock(tmp_path):
    import os
    import time

    import report_history_service

    old_report = tmp_path / "2308_TW_report.html"
    old_report.write_text("<html></html>", encoding="utf-8")
    old_time = time.time() - 10 * 24 * 60 * 60
    os.utime(old_report, (old_time, old_time))
    report_cache = {"2308.TW": old_report.name}
    lock = RecordingLock()

    deleted = report_history_service.cleanup_expired_reports(
        str(tmp_path),
        report_cache,
        retention_days=1,
        repository=NoopRepository(),
        report_cache_lock=lock,
    )

    assert deleted == [old_report.name]
    assert report_cache == {}
    assert lock.entered == 1


def test_delete_report_files_uses_report_cache_lock(tmp_path):
    import report_history_service

    report = tmp_path / "2308_TW_report.html"
    report.write_text("<html></html>", encoding="utf-8")
    report_cache = {"2308.TW": report.name}
    lock = RecordingLock()

    result = report_history_service.delete_report_files(
        report.name,
        str(tmp_path),
        report_cache,
        repository=NoopRepository(),
        report_cache_lock=lock,
    )

    assert result["success"] is True
    assert report_cache == {}
    assert lock.entered == 1
