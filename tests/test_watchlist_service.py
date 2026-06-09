import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import watchlist_service  # noqa: E402


def test_watchlist_due_items_enqueue_and_mark_run(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.upsert_watchlist_item({
        "ticker": "2308.TW",
        "pipeline": "v2",
        "schedule_slots": ["pre_market"],
        "enabled": True,
    })
    now = datetime(2026, 6, 8, 8, 31, tzinfo=watchlist_service.TAIPEI)
    due = watchlist_service.due_watchlist_items(now)
    queued_jobs = []

    class FakeQueue:
        def enqueue(self, key, func, job_id, ticker, pipeline):
            queued_jobs.append((key, job_id, ticker, pipeline))

    result = watchlist_service.enqueue_watchlist_items(
        due,
        create_job=lambda ticker, pipeline: f"job-{ticker}-{pipeline}",
        find_active_job=lambda ticker, pipeline: {},
        task_queue=FakeQueue(),
        run_stock_analysis_job=lambda job_id, ticker, pipeline: "ok",
    )

    assert result["queued"][0]["ticker"] == "2308.TW"
    assert queued_jobs[0][2:] == ("2308.TW", "v2")
    assert watchlist_service.due_watchlist_items(now) == []
    stored = watchlist_service.list_watchlist()["items"][0]
    assert stored["last_run_dates"]["pre_market"] == "2026-06-08"


def test_watchlist_api_upserts_and_lists_items(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    client = TestClient(api.app)

    response = client.post("/api/watchlist", json={
        "ticker": "2308.TW",
        "pipeline": "v1",
        "schedule_slots": ["post_market"],
        "enabled": True,
    })
    listed = client.get("/api/watchlist")

    assert response.status_code == 200
    assert listed.status_code == 200
    assert listed.json()["items"][0]["ticker"] == "2308.TW"
