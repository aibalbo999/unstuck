import json
import sys
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import report_index  # noqa: E402
import watchlist_service  # noqa: E402
import watchlist_scheduler  # noqa: E402
from data_fetch import FetchRequest, FetchResult  # noqa: E402


def _write_report_pair(output_dir: Path, filename: str):
    (output_dir / filename).write_text('<div class="sidebar-name">台達電 / Delta Electronics</div>', encoding="utf-8")
    (output_dir / filename.replace(".html", ".md")).write_text(
        """# 2308.TW 台達電 - 報告

## 一頁式摘要
測試摘要。

## 📊 關鍵指標
- **股價:** NT$400

## 🎯 最終投資建議
- **綜合建議:** 持有
- **12個月目標:** NT$460
- **信心指數:** 7/10
""",
        encoding="utf-8",
    )


def _write_snapshot(output_dir: Path, filename: str, *, needs_rerun: bool):
    snapshot = {
        "ticker": "2308.TW",
        "pipeline": "v2",
        "generated_at": "2026-06-08T01:00:00+00:00",
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        "source_audit": [],
        "data": {"ticker": "2308.TW", "company_name": "台達電", "current_price": 410},
    }
    if needs_rerun:
        snapshot.update({
            "refreshed_without_analysis_rerun": True,
            "decision_validity_status": "needs_rerun",
            "snapshot_refreshed_at": "2026-06-09T01:00:00+00:00",
            "analysis_text_stale_message": "資料快照已刷新，但投資結論仍以原報告生成時間為準。",
        })
    (output_dir / filename.replace(".html", ".data.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )


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


def test_watchlist_claim_due_items_marks_slot_before_enqueue(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()
    watchlist_service.upsert_watchlist_item({
        "ticker": "2308.TW",
        "pipeline": "v2",
        "schedule_slots": ["pre_market"],
        "enabled": True,
    })
    now = datetime(2026, 6, 8, 8, 31, tzinfo=watchlist_service.TAIPEI)

    first_claim = watchlist_service.claim_due_watchlist_items(now)
    second_claim = watchlist_service.claim_due_watchlist_items(now)

    assert first_claim[0]["ticker"] == "2308.TW"
    assert first_claim[0]["due_slot"] == "pre_market"
    assert first_claim[0]["due_date"] == "2026-06-08"
    assert second_claim == []
    assert watchlist_service.due_watchlist_items(now) == []


def test_watchlist_store_uses_sqlite_and_preserves_run_dates(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()

    watchlist_service.upsert_watchlist_item({
        "ticker": "2308.TW",
        "pipeline": "v2",
        "schedule_slots": ["pre_market"],
        "enabled": True,
    })
    watchlist_service.mark_watchlist_run("2308.TW", "v2", "pre_market", run_date="2026-06-08")
    watchlist_service.upsert_watchlist_item({
        "ticker": "2308.TW",
        "pipeline": "v2",
        "schedule_slots": ["post_market"],
        "enabled": False,
    })

    assert (tmp_path / "watchlist.sqlite3").exists()
    assert not (tmp_path / "watchlist.json").exists()
    stored = watchlist_service.list_watchlist()["items"][0]
    assert stored["enabled"] is False
    assert stored["schedule_slots"] == ["post_market"]
    assert stored["last_run_dates"]["pre_market"] == "2026-06-08"


def test_watchlist_imports_legacy_json_once(monkeypatch, tmp_path):
    legacy_path = tmp_path / "watchlist.json"
    legacy_path.write_text(
        """{
  "items": [{
    "ticker": "2308.TW",
    "pipeline": "v2",
    "enabled": true,
    "schedule_slots": ["pre_market"],
    "last_run_dates": {"pre_market": "2026-06-08"},
    "created_at": "2026-06-08T08:00:00+08:00",
    "updated_at": "2026-06-08T08:00:00+08:00"
  }],
  "updated_at": "2026-06-08T08:00:00+08:00"
}""",
        encoding="utf-8",
    )
    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", legacy_path)
    watchlist_service.reset_watchlist_store_for_tests()

    first = watchlist_service.list_watchlist()
    watchlist_service.delete_watchlist_item("2308.TW", "v2")
    second = watchlist_service.list_watchlist()

    assert first["items"][0]["ticker"] == "2308.TW"
    assert second["items"] == []


def test_watchlist_api_upserts_and_lists_items(monkeypatch, tmp_path, mutation_headers):
    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path / "output"))
    client = TestClient(api.app)

    response = client.post("/api/watchlist", json={
        "ticker": "2308.TW",
        "pipeline": "v1",
        "schedule_slots": ["post_market"],
        "enabled": True,
    }, headers=mutation_headers)
    listed = client.get("/api/watchlist")

    assert response.status_code == 200
    assert listed.status_code == 200
    assert listed.json()["items"][0]["ticker"] == "2308.TW"
    assert "priority_counts" in listed.json()


def test_watchlist_listing_prioritizes_items_with_stale_decisions(monkeypatch, tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    watchlist_service.reset_watchlist_store_for_tests()
    watchlist_service.upsert_watchlist_item({
        "ticker": "2330.TW",
        "pipeline": "v1",
        "schedule_slots": ["post_market"],
        "enabled": True,
    })
    watchlist_service.upsert_watchlist_item({
        "ticker": "2308.TW",
        "pipeline": "v2",
        "schedule_slots": ["post_market"],
        "enabled": True,
    })
    report = "2308_v2_report_20260608_010000.html"
    _write_report_pair(output_dir, report)
    _write_snapshot(output_dir, report, needs_rerun=True)

    result = watchlist_service.list_watchlist_with_report_alerts(output_dir=str(output_dir))

    assert result["priority_counts"]["high"] == 1
    assert result["items"][0]["ticker"] == "2308.TW"
    assert result["items"][0]["decision_priority"] == "high"
    assert result["items"][0]["decision_alert"]["reason"] == "needs_rerun"
    assert result["items"][0]["latest_report"]["filename"] == report


def test_watchlist_trigger_monitor_queues_matched_event_once(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()
    watchlist_service.upsert_watchlist_item({
        "ticker": "2308.TW",
        "pipeline": "v1",
        "schedule_slots": ["post_market"],
        "enabled": True,
        "triggers": [{"type": "vix_above", "threshold": 30}],
    })
    queued_jobs = []

    class FakeQueue:
        def enqueue(self, key, func, job_id, ticker, pipeline):
            queued_jobs.append((key, job_id, ticker, pipeline))

    class FakeDataService:
        async def fetch_async(self, request):
            assert request.ticker == "2308.TW"
            return FetchResult(
                request=FetchRequest.from_ticker(request.ticker),
                data={"ticker": request.ticker, "macro_indicators": {"indicators": {"vix": {"value": 35}}}},
            )

    kwargs = {
        "data_service": FakeDataService(),
        "create_job": lambda ticker, pipeline: f"job-{ticker}-{pipeline}",
        "find_active_job": lambda ticker, pipeline: {},
        "task_queue": FakeQueue(),
        "run_stock_analysis_job": lambda job_id, ticker, pipeline: "ok",
        "now": datetime(2026, 6, 20, 16, 1, tzinfo=watchlist_service.TAIPEI),
    }

    first = asyncio.run(watchlist_service.monitor_watchlist_triggers(**kwargs))
    second = asyncio.run(watchlist_service.monitor_watchlist_triggers(**kwargs))

    assert first["queued"][0]["pipeline"] == "v3"
    assert second["queued"] == []
    assert queued_jobs == [("analysis:job-2308.TW-v3", "job-2308.TW-v3", "2308.TW", "v3")]
    latest = watchlist_service.list_watchlist()["items"][0]["latest_trigger_event"]
    assert latest["trigger_type"] == "vix_above"


def test_watchlist_scheduler_runs_trigger_monitor(monkeypatch):
    calls = []
    logs = []

    def fake_due_batch(**kwargs):
        calls.append(("due",))
        return {"success": True, "queued": [], "skipped": []}

    async def fake_monitor(**kwargs):
        calls.append(("monitor", kwargs["data_service"]))
        return {"success": True, "queued": [{"ticker": "2308.TW"}], "skipped": [], "errors": []}

    async def fake_sleep(seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr(watchlist_scheduler, "_run_due_watchlist_batch", fake_due_batch)
    monkeypatch.setattr(watchlist_service, "monitor_watchlist_triggers", fake_monitor)
    monkeypatch.setattr(watchlist_scheduler.asyncio, "sleep", fake_sleep)

    try:
        asyncio.run(watchlist_scheduler._watchlist_scheduler_forever(
            create_job=lambda ticker, pipeline: "job",
            find_active_job=lambda ticker, pipeline: {},
            task_queue=object(),
            run_stock_analysis_job=lambda job_id, ticker, pipeline: "ok",
            data_service="data-service",
            emit_log=logs.append,
            interval_seconds=1,
        ))
    except asyncio.CancelledError:
        pass

    assert calls == [("due",), ("monitor", "data-service")]
    assert any("triggered=1" in line for line in logs)
