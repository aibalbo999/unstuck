from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_history_data_trust_filter_is_wired_to_api_params():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    api_client_js = (STATIC_DIR / "api_client.js").read_text(encoding="utf-8")

    assert 'id="history-data-trust-filter"' in index_html
    assert "historyDataTrustFilter" in app_js
    assert "params.set('data_trust', dataTrust)" in api_client_js


def test_provider_sla_and_manual_refresh_controls_are_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    provider_sla_js = (STATIC_DIR / "provider_sla_panel.js").read_text(encoding="utf-8")
    active_jobs_js = (STATIC_DIR / "active_jobs_panel.js").read_text(encoding="utf-8")
    report_rerun_js = (STATIC_DIR / "report_rerun.js").read_text(encoding="utf-8")
    analysis_stream_js = (STATIC_DIR / "analysis_stream.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    report_preview_js = (STATIC_DIR / "report_preview_panel.js").read_text(encoding="utf-8")
    api_client_js = (STATIC_DIR / "api_client.js").read_text(encoding="utf-8")
    ui_helpers_js = (STATIC_DIR / "ui_helpers.js").read_text(encoding="utf-8")

    assert 'id="provider-sla-panel"' in index_html
    assert "全系統資料來源狀態" in index_html
    assert "本報告資料狀態" in index_html
    assert 'id="active-jobs-panel"' in index_html
    assert 'id="provider-sla-window"' in index_html
    assert '<option value="last_24h" selected>24 小時</option>' in index_html
    assert 'id="preview-refresh-data-btn"' in index_html
    assert 'id="preview-rerun-final-btn"' in index_html
    assert 'id="preview-rerun-modeb-btn"' in index_html
    assert 'id="preview-rerun-cancel-btn"' in index_html
    assert 'id="preview-stale-notice"' in index_html
    assert "/static/provider_sla_panel.js" in index_html
    assert "/static/active_jobs_panel.js" in index_html
    assert "/static/report_rerun.js" in index_html
    assert "/static/analysis_stream.js" in index_html
    assert "/static/history_panel.js" in index_html
    assert "/static/report_preview_panel.js" in index_html
    assert "/static/view_controller.js" in index_html
    assert "/static/history_filters.js" in index_html
    assert "/static/report_actions.js" in index_html
    assert "/static/history_workspace.js" in index_html
    assert "/static/ui_helpers.js" in index_html
    assert "/static/api_client.js" in index_html
    assert "providerSlaWindow" in app_js
    assert "StockAgentProviderSlaPanel.render" in app_js
    assert "StockAgentActiveJobsPanel.render" in app_js
    assert "StockAgentHistoryPanel.create" in history_workspace_js
    assert "StockAgentReportPreviewPanel.create" in history_workspace_js
    assert "StockAgentViewController.create" in app_js
    assert "StockAgentHistoryFilters.create" in history_workspace_js
    assert "StockAgentReportActions.bindDownloads" in app_js
    assert "history-item" in history_panel_js
    assert "preview-date" in report_preview_js
    assert "configureRerunButtons" in report_preview_js
    assert "重跑模式 A 最終建議" in report_preview_js
    assert "重跑模式 B 最終建議" in report_preview_js
    assert "重跑完整模式 B" in report_preview_js
    assert "產生模式 B 報告" in report_preview_js
    assert "產生模式 B 報告" in index_html
    assert "history-item" not in app_js
    assert "providerSlaStatsForWindow" in provider_sla_js
    assert "groupedProviderRows" in provider_sla_js
    assert "股價與基本資料" in provider_sla_js
    assert "同業指標" in provider_sla_js
    assert "可安心使用" in provider_sla_js
    assert "provider-sla-insight" in provider_sla_js
    assert "正式分析流程" in provider_sla_js
    assert "資料取得率" in provider_sla_js
    assert "analysis_text_stale" in history_workspace_js
    assert "rerunPreviewReport" in history_workspace_js
    assert "StockAgentReportRerun.rerunPreviewReport" in history_workspace_js
    assert "/rerun?scope=" in report_rerun_js
    assert "/rerun/cancel" in report_rerun_js
    assert "buttons.cancel" in report_rerun_js
    assert "new EventSource" in report_rerun_js
    assert "StockAgentAnalysisStream.create" in app_js
    assert "resetAndConnect" in analysis_stream_js
    assert "/api/analyze/" in analysis_stream_js
    assert "new EventSource" in analysis_stream_js
    assert "params.set('window'" in api_client_js
    assert "/api/observability/provider-sla" in api_client_js
    assert "/api/observability/active-jobs" in api_client_js
    assert "llm_error_counts" in active_jobs_js
    assert "renderPipelineModeBadge" in ui_helpers_js
    assert "renderDataTrustReason" in ui_helpers_js
    assert "data-trust-reason" in ui_helpers_js
    assert "本報告資料新鮮" in ui_helpers_js
    assert "系統來源當時不穩" in ui_helpers_js
    assert "/refresh/data" in api_client_js


def test_frontend_static_modules_are_sized():
    size_limits = {
        "app.js": 300,
        "history_workspace.js": 260,
        "ui_helpers.js": 140,
        "api_client.js": 80,
        "provider_sla_panel.js": 160,
        "view_controller.js": 40,
        "history_filters.js": 50,
        "report_actions.js": 45,
        "style.css": 40,
        "styles/history_list.css": 320,
        "styles/preview_panel.css": 220,
        "styles/provider_sla.css": 120,
    }
    for relative_path, limit in size_limits.items():
        path = STATIC_DIR / relative_path
        assert len(path.read_text(encoding="utf-8").splitlines()) < limit, relative_path


def test_visual_regression_script_is_documented():
    script = ROOT / "scripts" / "visual_regression.sh"
    setup_script = ROOT / "scripts" / "setup_visual_regression.sh"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert script.exists()
    assert setup_script.exists()
    assert "tests/test_frontend_visual_optional.py" in script.read_text(encoding="utf-8")
    assert "tests/test_report_chart_visual_optional.py" in script.read_text(encoding="utf-8")
    assert "VISUAL_REGRESSION_REQUIRED" in script.read_text(encoding="utf-8")
    assert "playwright install chromium" in setup_script.read_text(encoding="utf-8")
    assert "scripts/setup_visual_regression.sh" in readme
    assert "scripts/visual_regression.sh" in readme
    assert "RUN_VISUAL_REGRESSION=1 scripts/ci_gate.sh" in readme
