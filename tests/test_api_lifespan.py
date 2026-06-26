import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import api


ROOT = Path(__file__).resolve().parents[1]


class FakeProducer:
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start_workers(self):
        self.started += 1

    async def stop_workers(self):
        self.stopped += 1


def _sleeping_task():
    return asyncio.create_task(asyncio.sleep(3600))


def test_api_lifespan_never_starts_workers_or_schedulers(monkeypatch):
    forbidden: list[str] = []
    producer = FakeProducer()

    async def cleanup_forever():
        forbidden.append("cleanup")
        await asyncio.sleep(3600)

    def watchlist_scheduler_factory(**_kwargs):
        forbidden.append("watchlist")
        return _sleeping_task()

    def decision_tracking_scheduler_factory(**_kwargs):
        forbidden.append("decision")
        return _sleeping_task()

    monkeypatch.setattr(api, "validate_runtime_settings", lambda: [])
    monkeypatch.setattr(api, "analysis_task_queue", producer)
    monkeypatch.setattr(api, "_cleanup_reports_forever", cleanup_forever, raising=False)
    monkeypatch.setattr(api, "create_watchlist_scheduler_task", watchlist_scheduler_factory, raising=False)
    monkeypatch.setattr(api, "create_decision_tracking_scheduler_task", decision_tracking_scheduler_factory, raising=False)

    with TestClient(api.create_app()) as client:
        assert client.get("/api/client-config").status_code == 200

    assert forbidden == []
    assert producer.started == 0
    assert producer.stopped == 0


def test_api_lifespan_does_not_close_job_store(monkeypatch):
    import job_store

    closed = []
    runtime = SimpleNamespace(close=lambda: None)

    async def close_cached_clients_async():
        return None

    monkeypatch.setattr(api, "validate_runtime_settings", lambda: [])
    monkeypatch.setattr(api, "create_api_runtime", lambda *_args, **_kwargs: runtime)
    monkeypatch.setattr(job_store, "close_job_store", lambda: closed.append("job"))
    monkeypatch.setattr("llm_transport.close_cached_clients_async", close_cached_clients_async)

    with TestClient(api.create_app()) as client:
        assert client.get("/api/client-config").status_code == 200

    assert closed == []


def test_api_lifespan_closes_preexisting_lazy_runtime_before_replacing(monkeypatch):
    closed = []
    old_runtime = SimpleNamespace(close=lambda: closed.append("old"))
    new_runtime = SimpleNamespace(close=lambda: closed.append("new"))

    async def close_cached_clients_async():
        return None

    monkeypatch.setattr(api, "validate_runtime_settings", lambda: [])
    monkeypatch.setattr(api, "create_api_runtime", lambda *_args, **_kwargs: new_runtime)
    monkeypatch.setattr("llm_transport.close_cached_clients_async", close_cached_clients_async)

    app = api.create_app()
    app.state.runtime = old_runtime

    with TestClient(app) as client:
        assert client.get("/api/client-config").status_code == 200

    assert closed == ["old", "new"]


def test_api_source_excludes_background_runtime_startup():
    source = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")

    for forbidden in [
        "_cleanup_reports_forever",
        "_mark_abandoned_local_jobs",
        "start_workers",
        "stop_workers",
        "create_watchlist_scheduler_task",
        "create_decision_tracking_scheduler_task",
        "acquire_local_runtime_instance_lock",
        "close_job_store",
        "StockDataService",
        "data_refresh_service =",
    ]:
        assert forbidden not in source
