import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import report_index  # noqa: E402
from data_fetch import FetchResult  # noqa: E402


def test_parse_recommendation_summary_from_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    (tmp_path / "2449_v2_report_20260606_010000.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "2449_v2_report_20260606_010000.md").write_text(
        """# 2449.TW 京元電子 - 實戰交易決策報告

## 一頁式摘要
京元電子目前建議採取「持有」策略，等待回檔後再分批布局。

## 📊 關鍵指標
- **股價:** NT$309.50

---

## 🎯 最終投資建議
- **綜合建議:** 持有
- **3個月目標:** NT$273
- **6個月目標:** NT$310
- **12個月目標:** NT$350
- **信心指數:** 7/10
""",
        encoding="utf-8",
    )

    summary = api.parse_recommendation_summary("2449_v2_report_20260606_010000.html")

    assert summary["recommendation"] == "持有"
    assert summary["current_price"] == "NT$309.50"
    assert summary["target_3m"] == "NT$273"
    assert summary["target_6m"] == "NT$310"
    assert summary["target_12m"] == "NT$350"
    assert summary["confidence"] == "7/10"
    assert "等待回檔" in summary["summary"]


def write_report_pair(output_dir: Path, filename: str, recommendation: str):
    (output_dir / filename).write_text(
        '<div class="sidebar-name">京元電子 / King Yuan Electronics Co., Ltd.</div>',
        encoding="utf-8",
    )
    (output_dir / filename.replace(".html", ".md")).write_text(
        f"""# 2449.TW 京元電子 - 報告

## 一頁式摘要
測試摘要。

## 📊 關鍵指標
- **股價:** NT$309.50

---

## 🎯 最終投資建議
- **綜合建議:** {recommendation}
- **3個月目標:** NT$273
- **6個月目標:** NT$310
- **12個月目標:** NT$350
- **信心指數:** 7/10
""",
        encoding="utf-8",
    )


def write_data_snapshot(output_dir: Path, filename: str, status: str = "fresh"):
    (output_dir / filename.replace(".html", ".data.json")).write_text(
        f"""{{
  "ticker": "2449.TW",
  "pipeline": "v2",
  "data_trust": {{
    "status": "{status}",
    "critical_failures": [],
    "stale_sources": [],
    "last_market_data_at": "2026-06-06T01:00:00+00:00",
    "notes": ["測試資料可信度"]
  }},
  "source_audit": []
}}""",
        encoding="utf-8",
    )


def test_get_reports_filters_pipeline_and_recommendation(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    write_report_pair(tmp_path, "2449_v2_report_20260606_010000.html", "持有")
    write_data_snapshot(tmp_path, "2449_v2_report_20260606_010000.html", "fresh")
    write_report_pair(tmp_path, "2449_report_20260606_005900.html", "買入")

    result = api.get_reports(page=1, limit=20, q="", pipeline="v2", recommendation="持有")

    assert result["pagination"]["pipeline"] == "v2"
    assert result["pagination"]["recommendation"] == "持有"
    assert result["pagination"]["total"] == 1
    assert result["reports"][0]["filename"] == "2449_v2_report_20260606_010000.html"
    assert result["reports"][0]["recommendation"]["current_price"] == "NT$309.50"
    assert result["reports"][0]["data_trust"]["status"] == "fresh"


def test_get_reports_marks_old_reports_without_snapshot_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    write_report_pair(tmp_path, "2449_v2_report_20260606_010000.html", "持有")

    result = api.get_reports(page=1, limit=20, q="", pipeline="v2", recommendation="持有")

    assert result["reports"][0]["data_trust"]["status"] == "unknown"


def test_get_reports_filters_data_trust_status(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    write_report_pair(tmp_path, "2449_v2_report_20260606_010000.html", "持有")
    write_data_snapshot(tmp_path, "2449_v2_report_20260606_010000.html", "stale")
    write_report_pair(tmp_path, "2330_v2_report_20260606_020000.html", "持有")
    write_data_snapshot(tmp_path, "2330_v2_report_20260606_020000.html", "fresh")

    client = TestClient(api.app)
    response = client.get("/api/reports", params={"data_trust": "stale", "pipeline": "v2", "limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["data_trust"] == "stale"
    assert body["pagination"]["total"] == 1
    assert body["reports"][0]["filename"] == "2449_v2_report_20260606_010000.html"
    assert body["reports"][0]["data_trust"]["status"] == "stale"


def test_download_data_snapshot_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "partial")

    client = TestClient(api.app)
    response = client.get(f"/api/report/{filename}/download/data")

    assert response.status_code == 200
    assert response.json()["data_trust"]["status"] == "partial"

    missing = client.get("/api/report/2449_v2_report_20260606_020000.html/download/data")
    assert missing.status_code == 404


def test_refresh_data_snapshot_endpoint_updates_trust(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "stale")

    class FakeRefreshService:
        async def fetch_async(self, request):
            return FetchResult(
                request=request,
                data={
                    "data_schema_version": 4,
                    "ticker": request.ticker,
                    "company_name": "京元電子",
                    "source_freshness": {
                        "market_data": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
                        "financial_statements": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
                    },
                    "source_audit": [
                        {"source": "market_data", "provider": "fake", "status": "success", "record_count": 1},
                        {"source": "financial_statements", "provider": "fake", "status": "success", "record_count": 1},
                    ],
                    "data_trust": {
                        "status": "fresh",
                        "critical_failures": [],
                        "stale_sources": [],
                        "last_market_data_at": "2026-06-07T00:00:00+00:00",
                        "notes": ["刷新後資料新鮮"],
                    },
                },
            )

    monkeypatch.setattr(api, "data_refresh_service", FakeRefreshService())
    client = TestClient(api.app)
    response = client.post(f"/api/report/{filename}/refresh/data")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data_trust"]["status"] == "fresh"
    assert body["refresh_diff"]["data_trust_status"] == {"before": "stale", "after": "fresh", "changed": True}
    assert "可信度 stale → fresh" in body["refresh_diff"]["summary"]
    saved = json.loads((tmp_path / filename.replace(".html", ".data.json")).read_text(encoding="utf-8"))
    assert saved["data_trust"]["status"] == "fresh"
    assert saved["refreshed_from_report"] == filename


def test_refresh_data_snapshot_endpoint_rejects_legacy_without_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")

    client = TestClient(api.app)
    response = client.post(f"/api/report/{filename}/refresh/data")

    assert response.status_code == 404
