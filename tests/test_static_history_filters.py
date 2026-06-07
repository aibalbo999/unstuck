from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_history_data_trust_filter_is_wired_to_api_params():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="history-data-trust-filter"' in index_html
    assert "historyDataTrustFilter" in app_js
    assert "params.set('data_trust', dataTrustFilter)" in app_js


def test_provider_sla_and_manual_refresh_controls_are_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    provider_sla_js = (STATIC_DIR / "provider_sla_panel.js").read_text(encoding="utf-8")
    report_rerun_js = (STATIC_DIR / "report_rerun.js").read_text(encoding="utf-8")

    assert 'id="provider-sla-panel"' in index_html
    assert 'id="provider-sla-window"' in index_html
    assert 'id="preview-refresh-data-btn"' in index_html
    assert 'id="preview-rerun-final-btn"' in index_html
    assert 'id="preview-rerun-modeb-btn"' in index_html
    assert 'id="preview-stale-notice"' in index_html
    assert "/static/provider_sla_panel.js" in index_html
    assert "/static/report_rerun.js" in index_html
    assert "providerSlaWindow" in app_js
    assert "StockAgentProviderSlaPanel.render" in app_js
    assert "providerSlaStatsForWindow" in provider_sla_js
    assert "analysis_text_stale" in app_js
    assert "rerunPreviewReport" in app_js
    assert "StockAgentReportRerun.rerunPreviewReport" in app_js
    assert "/rerun?scope=" in report_rerun_js
    assert "new EventSource" in report_rerun_js
    assert "params.set('window'" in app_js
    assert "/api/observability/provider-sla" in app_js
    assert "/refresh/data" in app_js
