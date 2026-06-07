import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import report_index  # noqa: E402


STATIC_DIR = ROOT / "backend" / "static"


def _write_report_pair(output_dir: Path, filename: str, recommendation: str = "持有"):
    (output_dir / filename).write_text(
        '<html><body><div class="sidebar-name">京元電子 / King Yuan Electronics</div></body></html>',
        encoding="utf-8",
    )
    (output_dir / filename.replace(".html", ".md")).write_text(
        f"""# 2449.TW 京元電子 - 報告

## 一頁式摘要
端到端測試摘要。

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


def _write_snapshot(output_dir: Path, filename: str, status: str):
    snapshot = {
        "snapshot_schema_version": 3,
        "snapshot_truncated": False,
        "snapshot_size_bytes": 0,
        "snapshot_omitted_sections": [],
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline": "v2",
        "generated_at": "2026-06-07T00:00:00+00:00",
        "data_schema_version": 4,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": {
            "status": status,
            "critical_failures": [],
            "stale_sources": ["market_data"] if status == "stale" else [],
            "last_market_data_at": "2026-06-06T01:00:00+00:00",
            "notes": ["E2E fixture"],
        },
        "data": {
            "data_schema_version": 4,
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "source_audit": [],
            "data_trust": {
                "status": status,
                "critical_failures": [],
                "stale_sources": [],
                "last_market_data_at": "2026-06-06T01:00:00+00:00",
                "notes": ["E2E fixture"],
            },
        },
    }
    (output_dir / filename.replace(".html", ".data.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )


def test_frontend_shell_static_assets_and_report_history_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    stale_filename = "2449_v2_report_20260606_010000.html"
    fresh_filename = "2330_v2_report_20260606_020000.html"
    _write_report_pair(tmp_path, stale_filename, "持有")
    _write_snapshot(tmp_path, stale_filename, "stale")
    _write_report_pair(tmp_path, fresh_filename, "買入")
    _write_snapshot(tmp_path, fresh_filename, "fresh")

    client = TestClient(api.app)

    shell = client.get("/")
    assert shell.status_code == 200
    assert "/static/ui_helpers.js" in shell.text
    assert "/static/api_client.js" in shell.text
    assert "/static/history_panel.js" in shell.text

    style = client.get("/static/style.css")
    assert style.status_code == 200
    assert "/static/styles/history_list.css" in style.text
    assert "/static/styles/preview_panel.css" in style.text
    for asset in (
        "/static/styles/base.css",
        "/static/styles/history_list.css",
        "/static/styles/preview_panel.css",
        "/static/ui_helpers.js",
        "/static/api_client.js",
        "/static/app.js",
    ):
        response = client.get(asset)
        assert response.status_code == 200, asset
        assert response.text.strip(), asset

    reports = client.get(
        "/api/reports",
        params={"pipeline": "v2", "recommendation": "持有", "data_trust": "stale", "limit": 20},
    )
    assert reports.status_code == 200
    payload = reports.json()
    assert payload["pagination"]["total"] == 1
    assert payload["reports"][0]["filename"] == stale_filename
    assert payload["reports"][0]["data_trust"]["status"] == "stale"

    html = client.get(f"/api/report/{stale_filename}")
    assert html.status_code == 200
    assert "sidebar-name" in html.text

    md = client.get(f"/api/report/{stale_filename}/download/md")
    assert md.status_code == 200
    assert "最終投資建議" in md.text

    data = client.get(f"/api/report/{stale_filename}/download/data")
    assert data.status_code == 200
    assert data.json()["data_trust"]["status"] == "stale"


def test_static_css_modules_keep_expected_component_selectors():
    selectors = {
        STATIC_DIR / "styles" / "history_list.css": [".history-item", ".history-pagination", ".data-trust-badge"],
        STATIC_DIR / "styles" / "provider_sla.css": [".provider-sla-panel", ".provider-sla-chip"],
        STATIC_DIR / "styles" / "preview_panel.css": [".report-preview", ".preview-open-button"],
    }
    for path, expected in selectors.items():
        css = path.read_text(encoding="utf-8")
        for selector in expected:
            assert selector in css
