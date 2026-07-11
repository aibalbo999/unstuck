import asyncio
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import analysis_jobs  # noqa: E402
import job_store  # noqa: E402
import provider_sla  # noqa: E402
import report_index  # noqa: E402
from agent_runtime import AnalysisResult  # noqa: E402
from data_fetch import FetchResult  # noqa: E402
from fixtures.data_payloads import fresh_audited_payload  # noqa: E402
from report_persistence import report_bundle_keys_for_filename  # noqa: E402


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


def _write_snapshot(
    output_dir: Path,
    filename: str,
    status: str,
    evidence_exit_gate: dict | None = None,
    report_conformance: dict | None = None,
    content_credibility: dict | None = None,
):
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
    if evidence_exit_gate is not None:
        snapshot["evidence_exit_gate"] = evidence_exit_gate
    if report_conformance is not None:
        snapshot["report_conformance"] = report_conformance
    if content_credibility is not None:
        snapshot["content_credibility"] = content_credibility
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
    assert "/static/pipeline_mode_fallback.js" in shell.text
    assert "/static/ui_helpers.js" in shell.text
    assert "/static/api_client.js" in shell.text
    assert "/static/home_tabs.js" in shell.text
    assert "/static/history_panel.js" in shell.text

    style = client.get("/static/style.css")
    assert style.status_code == 200
    assert "/static/styles/history_list.css" in style.text
    assert "/static/styles/preview_panel.css" in style.text
    for asset in (
        "/static/styles/base.css",
        "/static/styles/history_shell_tabs.css",
        "/static/styles/history_shell_commercial.css",
        "/static/styles/history_list.css",
        "/static/styles/preview_panel.css",
        "/static/styles/stock_snapshot_overview_trend.css",
        "/static/styles/stock_snapshot_overview_performance.css",
        "/static/styles/stock_snapshot_overview_technical.css",
        "/static/styles/stock_snapshot_research_analyst.css",
        "/static/styles/stock_snapshot_signal_dividend.css",
        "/static/styles/stock_snapshot_signal_events.css",
        "/static/styles/stock_snapshot_core_peer_ownership.css",
        "/static/styles/stock_snapshot_responsive_headers.css",
        "/static/styles/stock_snapshot_responsive_mobile.css",
        "/static/pipeline_mode_fallback.js",
        "/static/ui_helpers.js",
        "/static/api_client.js",
        "/static/report_quality_gate_policy.js",
        "/static/report_quality_policy.js",
        "/static/history_panel_quality_helpers.js",
        "/static/operator_summary_quality_helpers.js",
        "/static/home_tabs.js",
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
    assert payload["reports"][0]["decision_tracking"]["status"] == "tracked"
    assert payload["reports"][0]["decision_tracking"]["return_pct"] == 0.0
    assert payload["reports"][0]["html_hash"]
    assert payload["reports"][0]["markdown_hash"]
    assert payload["reports"][0]["data_file_hash"]

    html = client.get(f"/api/report/{stale_filename}")
    assert html.status_code == 200
    assert "sidebar-name" in html.text

    md = client.get(f"/api/report/{stale_filename}/download/md")
    assert md.status_code == 200
    assert "最終投資建議" in md.text

    data = client.get(f"/api/report/{stale_filename}/download/data")
    assert data.status_code == 200
    assert data.json()["data_trust"]["status"] == "stale"


def test_fake_provider_job_generates_report_snapshot_visible_in_history(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)

    class FakeStockDataService:
        async def fetch_async(self, request):
            data = fresh_audited_payload(ticker=request.ticker)
            return FetchResult(
                request=request,
                data=data,
                source_audit=data["source_audit"],
                data_trust=data["data_trust"],
            )

    class FakePipelineRunner:
        async def run_async(self, request):
            data = request.data
            if request.progress_callback:
                request.progress_callback(1, 7, "Fake Agent")
            parsed = {
                "moat_scores": {
                    "品牌影響力": 6,
                    "網路效應": 5,
                    "轉換成本": 6,
                    "成本優勢": 7,
                    "專利技術": 6,
                    "整體護城河": 6,
                },
                "price_targets": {"熊市情境": 105, "基本情境": 130, "牛市情境": 155},
                "recommendation": {
                    "建議": "持有",
                    "短期目標（3個月）": "US$130",
                    "中期目標（6個月）": "US$138",
                    "長期目標（12個月）": "US$150",
                    "長期潛力（5年）": "穩健成長",
                    "信心指數": "6/10",
                },
            }
            analyses = {
                agent_num: "Fake provider E2E analysis keeps report rendering deterministic."
                for agent_num in range(1, 17)
            }
            context = {
                "ticker": data["ticker"],
                "company_name": data["company_name"],
                "data": data,
                "pipeline_id": request.pipeline_id,
                "analyses": analyses,
                "parsed": parsed,
                "structured_outputs": {},
                "tear_sheet_summary": "Fake provider E2E summary with fresh audited data.",
                "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
            }
            return AnalysisResult(context=context, pipeline_id=request.pipeline_id)

    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", FakeStockDataService())
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", FakePipelineRunner())

    job_id = job_store.create_job("FAKE", "v1")
    filename = asyncio.run(analysis_jobs.run_stock_analysis_job_async(job_id, "FAKE", "v1"))

    assert filename.startswith("FAKE_v1_report_")
    keys = report_bundle_keys_for_filename(filename)
    assert (tmp_path / keys.html_key).exists()
    assert (tmp_path / keys.data_key).exists()

    client = TestClient(api.app)
    reports = client.get("/api/reports", params={"q": "Fake Semiconductor", "data_trust": "fresh", "limit": 20})
    assert reports.status_code == 200
    reports_payload = reports.json()
    assert reports_payload["pagination"]["total"] == 1
    assert reports_payload["reports"][0]["filename"] == filename
    assert "job_" not in reports_payload["reports"][0]["date"]
    assert reports_payload["reports"][0]["data_trust"]["status"] == "fresh"
    assert reports_payload["reports"][0]["data_snapshot_hash"]
    assert reports_payload["reports"][0]["html_hash"]
    assert reports_payload["reports"][0]["markdown_hash"]
    assert reports_payload["reports"][0]["data_file_hash"]

    data_snapshot = client.get(f"/api/report/{filename}/download/data")
    assert data_snapshot.status_code == 200
    snapshot = data_snapshot.json()
    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["snapshot_hash"] == reports_payload["reports"][0]["data_snapshot_hash"]
    assert "fresh_core_sources" in snapshot["data_trust"]["reason_codes"]
    assert snapshot["source_audit"][0]["provider"] == "fake-provider"
    assert snapshot["data"]["ticker"] == "FAKE"


def test_report_history_exposes_evidence_exit_gate_for_operator_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    filename = "2449_v2_report_20260606_030000.html"
    _write_report_pair(tmp_path, filename, "持有")
    _write_snapshot(
        tmp_path,
        filename,
        "fresh",
        evidence_exit_gate={
            "verdict": "rejected",
            "summary": "超過半數抽樣數字無法對上資料快照。",
            "failed_count": 2,
            "sampled_count": 3,
        },
    )

    client = TestClient(api.app)
    response = client.get("/api/reports", params={"limit": 20})

    assert response.status_code == 200
    report = response.json()["reports"][0]
    assert report["filename"] == filename
    assert report["data_trust"]["status"] == "fresh"
    assert report["evidence_exit_gate"]["verdict"] == "rejected"
    assert report["evidence_exit_gate"]["failed_count"] == 2


def test_report_history_exposes_report_conformance_for_operator_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    filename = "2449_v2_report_20260606_040000.html"
    _write_report_pair(tmp_path, filename, "持有")
    _write_snapshot(
        tmp_path,
        filename,
        "fresh",
        report_conformance={
            "status": "blocked",
            "summary": "報告未符合輸出契約，需修正後再採用。",
            "blocking_issues": [{"id": "required_visibility", "message": "報告缺少必要可見段落。"}],
            "warnings": [],
        },
    )

    client = TestClient(api.app)
    response = client.get("/api/reports", params={"limit": 20})

    assert response.status_code == 200
    report = response.json()["reports"][0]
    assert report["filename"] == filename
    assert report["report_conformance"]["status"] == "blocked"
    assert report["report_conformance"]["blocking_issues"][0]["id"] == "required_visibility"


def test_report_history_exposes_content_credibility_for_repair_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    filename = "2449_v2_report_20260606_050000.html"
    _write_report_pair(tmp_path, filename, "買入")
    _write_snapshot(
        tmp_path,
        filename,
        "fresh",
        content_credibility={
            "status": "blocked",
            "summary": "買入建議與主要目標價矛盾。",
            "blocking_issues": [{"id": "buy_target_below_current_price"}],
        },
    )

    client = TestClient(api.app)
    response = client.get("/api/reports", params={"limit": 20})

    assert response.status_code == 200
    report = response.json()["reports"][0]
    assert report["filename"] == filename
    assert report["content_credibility"]["status"] == "blocked"
    assert report["content_credibility"]["blocking_issues"][0]["id"] == "buy_target_below_current_price"


def test_static_css_modules_keep_expected_component_selectors():
    selectors = {
        STATIC_DIR / "styles" / "history_shell.css": [".history-section", ".history-title"],
        STATIC_DIR / "styles" / "history_shell_tabs.css": [".home-tabs", ".home-tab-button", ".home-tab-panel[hidden]"],
        STATIC_DIR / "styles" / "history_shell_commercial.css": [".commercial-entry-launchpad", ".commercial-operator-brief", ".commercial-entry-command-row", ".commercial-entry-status-grid", ".commercial-entry-card-action"],
        STATIC_DIR / "styles" / "history_list.css": [".history-item", ".data-trust-badge", ".data-trust-reason", ".history-tracking", ".history-action-badge"],
        STATIC_DIR / "styles" / "history_list_controls.css": [".history-filter-select", ".history-pagination", ".delete-btn", ".pager-btn"],
        STATIC_DIR / "styles" / "provider_sla.css": [".provider-sla-panel", ".provider-sla-chip"],
        STATIC_DIR / "styles" / "provider_sla_controls.css": [".provider-sla-window", ".maintenance-actions", ".maintenance-button"],
        STATIC_DIR / "styles" / "preview_panel.css": [".report-preview", ".preview-tracking"],
        STATIC_DIR / "styles" / "preview_panel_actions.css": [".preview-open-button", ".preview-refresh-button", ".preview-rerun-button"],
        STATIC_DIR / "styles" / "stock_snapshot_overview.css": [".stock-snapshot-company-profile", ".stock-snapshot-company-profile-grid", ".stock-snapshot-session", ".stock-snapshot-session-grid"],
        STATIC_DIR / "styles" / "stock_snapshot_overview_trend.css": [".stock-snapshot-trend", ".stock-snapshot-trend-chart", ".stock-snapshot-trend-returns"],
        STATIC_DIR / "styles" / "stock_snapshot_overview_performance.css": [".stock-snapshot-performance", ".stock-snapshot-performance-controls", ".stock-snapshot-performance-chart"],
        STATIC_DIR / "styles" / "stock_snapshot_overview_technical.css": [".stock-snapshot-technical", ".stock-snapshot-technical-header", ".stock-snapshot-technical-grid"],
        STATIC_DIR / "styles" / "stock_snapshot_research.css": [".stock-snapshot-valuation-range", ".stock-snapshot-valuation-band", ".stock-snapshot-earnings", ".stock-snapshot-earnings-grid"],
        STATIC_DIR / "styles" / "stock_snapshot_research_analyst.css": [".stock-snapshot-analyst", ".stock-snapshot-analyst-header", ".stock-snapshot-analyst-grid"],
        STATIC_DIR / "styles" / "stock_snapshot_signal.css": [".stock-snapshot-shares", ".stock-snapshot-risk", ".stock-snapshot-profitability"],
        STATIC_DIR / "styles" / "stock_snapshot_signal_dividend.css": [".stock-snapshot-dividend", ".stock-snapshot-dividend-grid", ".stock-snapshot-dividend-bars"],
        STATIC_DIR / "styles" / "stock_snapshot_signal_events.css": [".stock-snapshot-calendar", ".stock-snapshot-calendar-grid", ".stock-snapshot-alerts", ".stock-snapshot-alert-grid"],
        STATIC_DIR / "styles" / "stock_snapshot_core.css": [".stock-snapshot-fundamentals", ".stock-snapshot-financial-trends", ".stock-snapshot-financial-trend-row"],
        STATIC_DIR / "styles" / "stock_snapshot_core_peer_ownership.css": [".stock-snapshot-peers", ".stock-snapshot-peer-table", ".stock-snapshot-ownership", ".stock-snapshot-ownership-grid"],
        STATIC_DIR / "styles" / "stock_snapshot_responsive_headers.css": ["@media (max-width: 760px)", ".stock-snapshot-header,", ".stock-snapshot-company-profile-header", ".stock-snapshot-alert-header"],
        STATIC_DIR / "styles" / "stock_snapshot_responsive.css": ["@media (max-width: 760px)", ".stock-snapshot-grid", ".stock-snapshot-summary-rail", ".stock-snapshot-peer-row"],
        STATIC_DIR / "styles" / "stock_snapshot_responsive_mobile.css": ["@media (max-width: 520px)", ".stock-snapshot-peer-table", ".stock-snapshot-financial-trend-row", ".stock-snapshot-valuation-bands"],
    }
    for path, expected in selectors.items():
        css = path.read_text(encoding="utf-8")
        for selector in expected:
            assert selector in css
