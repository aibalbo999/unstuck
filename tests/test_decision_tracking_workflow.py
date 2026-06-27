import json
import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import decision_tracking_scheduler  # noqa: E402
import decision_tracking_service  # noqa: E402
import decision_tracking_store  # noqa: E402
import report_index  # noqa: E402
from data_fetch import FetchResult  # noqa: E402
from decision_tracking import build_decision_tracking  # noqa: E402


def _write_report(output_dir: Path, filename: str, ticker: str = "2449.TW", price: float = 100.0):
    name = ticker.split(".", 1)[0]
    (output_dir / filename).write_text(
        '<html><body><div class="sidebar-name">測試公司 / Test Co</div></body></html>',
        encoding="utf-8",
    )
    (output_dir / filename.replace(".html", ".md")).write_text(
        f"""# {ticker} 測試公司 - 報告

## 一頁式摘要
追蹤測試摘要。

## 📊 關鍵指標
- **股價:** NT${price}

---

## 🎯 最終投資建議
- **綜合建議:** 買入
- **3個月目標:** NT$90
- **6個月目標:** NT$105
- **12個月目標:** NT$130
- **信心指數:** 7/10
""",
        encoding="utf-8",
    )
    snapshot = {
        "ticker": ticker,
        "company_name": f"{name} 測試公司",
        "pipeline": "v3" if "_v3_" in filename else ("v2" if "_v2_" in filename else "v1"),
        "generated_at": "2026-06-09T00:00:00+00:00",
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "last_market_data_at": "2026-06-09T00:00:00+00:00", "notes": []},
        "source_audit": [],
        "data": {
            "ticker": ticker,
            "company_name": f"{name} 測試公司",
            "current_price": price,
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "last_market_data_at": "2026-06-09T00:00:00+00:00", "notes": []},
            "source_freshness": {"market_data": {"fetched_at": "2026-06-09T00:00:00+00:00"}},
            "source_audit": [],
        },
    }
    (output_dir / filename.replace(".html", ".data.json")).write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")


def _mark_snapshot_needs_rerun(output_dir: Path, filename: str):
    path = output_dir / filename.replace(".html", ".data.json")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot.update({
        "refreshed_without_analysis_rerun": True,
        "decision_validity_status": "needs_rerun",
        "snapshot_refreshed_at": "2026-06-10T12:00:00+00:00",
        "analysis_text_stale_message": "資料快照已刷新，但投資結論仍以原報告生成時間為準。",
    })
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")


def test_decision_tracking_compares_latest_price_to_all_targets(tmp_path):
    snapshot_path = tmp_path / "sample.data.json"
    snapshot_path.write_text(json.dumps({"data": {"current_price": 108.0}}, ensure_ascii=False), encoding="utf-8")
    tracking = build_decision_tracking(
        {
            "recommendation": "買入",
            "current_price": "NT$100",
            "target_3m": "NT$90",
            "target_6m": "NT$105",
            "target_12m": "NT$130",
        },
        str(snapshot_path),
    )

    comparisons = tracking["target_comparisons"]
    assert comparisons["target_3m"]["status"] == "above_target"
    assert comparisons["target_3m"]["label"] == "已高於目標"
    assert comparisons["target_6m"]["status"] == "near_target"
    assert comparisons["target_6m"]["label"] == "接近目標"
    assert comparisons["target_12m"]["status"] == "below_target"
    assert comparisons["target_12m"]["label"] == "低於目標"
    assert tracking["tracking_summary_status"] == "接近6月目標"

    above_all = build_decision_tracking(
        {
            "recommendation": "避免",
            "current_price": "NT$100",
            "target_3m": "NT$70",
            "target_6m": "NT$80",
            "target_12m": "NT$90",
        },
        str(snapshot_path),
    )
    assert above_all["tracking_summary_status"] == "高於12月目標"


def test_cached_decision_tracking_without_target_comparisons_is_rebuilt(tmp_path, monkeypatch):
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    filename = "2449_v2_report_20260610_090000.html"
    _write_report(tmp_path, filename, price=108.0)
    report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))
    old_tracking = {
        "status": "tracked",
        "recommendation": "買入",
        "initial_price": 108.0,
        "latest_price": 108.0,
        "target_12m": 130.0,
    }
    with sqlite3.connect(report_index.CACHE_DB_PATH) as conn:
        conn.execute(
            "UPDATE reports SET decision_tracking_json = ? WHERE filename = ?",
            (json.dumps(old_tracking, ensure_ascii=False), filename),
        )

    reports, _ = report_index.query_report_metadata(
        page=1,
        limit=10,
        q="2449",
        output_dir=str(tmp_path),
    )
    tracking = reports[0]["decision_tracking"]

    assert tracking["target_comparisons"]["target_6m"]["status"] == "near_target"
    assert tracking["target_comparisons"]["target_12m"]["status"] == "below_target"
    assert tracking["tracking_summary_status"] == "接近6月目標"


def test_decision_tracking_api_tracks_selected_tickers_and_refreshes_latest_price(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(tmp_path / "decision_tracking.sqlite3"))
    decision_tracking_store.reset_decision_tracking_store_for_tests()
    _write_report(tmp_path, "2449_report_20260609_090000.html", price=100.0)
    _write_report(tmp_path, "2449_v2_report_20260610_090000.html", price=108.0)
    _write_report(tmp_path, "2449_v3_report_20260611_090000.html", price=112.0)
    _write_report(tmp_path, "2330_v2_report_20260610_090000.html", ticker="2330.TW", price=500.0)
    refresh_requests = []

    class FakeRefreshService:
        async def fetch_async(self, request):
            refresh_requests.append(request.ticker)
            return FetchResult(
                request=request,
                data={
                    "ticker": request.ticker,
                    "company_name": "測試公司",
                    "current_price": 132.0,
                    "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "last_market_data_at": "2026-06-10T00:00:00+00:00", "notes": []},
                    "source_freshness": {"market_data": {"fetched_at": "2026-06-10T00:00:00+00:00"}},
                    "source_audit": [{"source": "market_data", "provider": "fake", "status": "success", "record_count": 1}],
                },
            )

    monkeypatch.setattr(api, "get_data_refresh_service", lambda _app: FakeRefreshService())
    client = TestClient(api.app)

    empty = client.get("/api/decision-tracking")
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    added = client.post("/api/decision-tracking", json={"ticker": "2449.TW"}, headers=mutation_headers)
    assert added.status_code == 200
    item = added.json()["items"][0]
    assert item["ticker"] == "2449.TW"
    assert item["company_name"] == "測試公司 / Test Co"
    assert item["latest_report"]["filename"] == "2449_v3_report_20260611_090000.html"
    assert [report["pipeline_id"] for report in item["latest_reports"]] == ["v1", "v2", "v3"]
    assert [report["filename"] for report in item["latest_reports"]] == [
        "2449_report_20260609_090000.html",
        "2449_v2_report_20260610_090000.html",
        "2449_v3_report_20260611_090000.html",
    ]

    refreshed = client.post("/api/decision-tracking/refresh", headers=mutation_headers)
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["success"] is True
    assert body["updated_count"] == 1
    assert body["updated_reports_count"] == 3
    assert refresh_requests == ["2449.TW", "2449.TW", "2449.TW"]
    row = body["items"][0]
    assert row["ticker"] == "2449.TW"
    assert row["company_name"] == "測試公司 / Test Co"
    assert row["latest_report"]["decision_tracking"]["latest_price"] == 132.0
    assert [report["decision_tracking"]["latest_price"] for report in row["latest_reports"]] == [132.0, 132.0, 132.0]
    assert row["latest_report"]["decision_tracking"]["target_comparisons"]["target_12m"]["status"] == "near_target"
    assert {item["ticker"] for item in body["items"]} == {"2449.TW"}


def test_decision_tracking_refresh_skips_reports_that_already_need_full_rerun(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(tmp_path / "decision_tracking.sqlite3"))
    decision_tracking_store.reset_decision_tracking_store_for_tests()
    _write_report(tmp_path, "2449_report_20260609_090000.html", price=100.0)
    _write_report(tmp_path, "2449_v2_report_20260610_090000.html", price=108.0)
    _mark_snapshot_needs_rerun(tmp_path, "2449_report_20260609_090000.html")
    refresh_requests = []

    class FakeRefreshService:
        async def fetch_async(self, request):
            refresh_requests.append(request.ticker)
            return FetchResult(
                request=request,
                data={
                    "ticker": request.ticker,
                    "company_name": "測試公司",
                    "current_price": 132.0,
                    "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "last_market_data_at": "2026-06-10T00:00:00+00:00", "notes": []},
                    "source_freshness": {"market_data": {"fetched_at": "2026-06-10T00:00:00+00:00"}},
                    "source_audit": [{"source": "market_data", "provider": "fake", "status": "success", "record_count": 1}],
                },
            )

    monkeypatch.setattr(api, "get_data_refresh_service", lambda _app: FakeRefreshService())
    client = TestClient(api.app)
    client.post("/api/decision-tracking", json={"ticker": "2449.TW"}, headers=mutation_headers)

    refreshed = client.post("/api/decision-tracking/refresh", headers=mutation_headers)

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["updated_count"] == 1
    assert body["updated_reports_count"] == 1
    assert refresh_requests == ["2449.TW"]
    assert body["skipped"] == [
        {
            "ticker": "2449.TW",
            "filename": "2449_report_20260609_090000.html",
            "reason": "needs_full_rerun",
        }
    ]


def test_scheduler_runs_due_backtests_after_daily_refresh(monkeypatch):
    calls = []
    logs = []

    async def fake_refresh_tracking_items(**kwargs):
        calls.append(("refresh", kwargs["output_dir"], kwargs["due_only"]))
        return {"updated_count": 1, "errors": []}

    def fake_run_due_backtests(**kwargs):
        calls.append(("backtest", kwargs["output_dir"]))
        return {"evaluated_count": 2, "skipped": [], "errors": []}

    async def fake_sleep(seconds):
        raise asyncio.CancelledError()

    import asyncio

    monkeypatch.setattr(decision_tracking_service, "refresh_tracking_items", fake_refresh_tracking_items)
    monkeypatch.setattr(decision_tracking_service, "run_due_backtests", fake_run_due_backtests)
    monkeypatch.setattr(decision_tracking_scheduler.asyncio, "sleep", fake_sleep)

    try:
        asyncio.run(decision_tracking_scheduler._decision_tracking_scheduler_forever(
            get_output_dir=lambda: "/tmp/reports",
            get_refresh_service=lambda: object(),
            emit_log=logs.append,
            interval_seconds=1,
        ))
    except asyncio.CancelledError:
        pass

    assert calls == [("refresh", "/tmp/reports", True), ("backtest", "/tmp/reports")]
    assert any("backtests=2" in line for line in logs)
