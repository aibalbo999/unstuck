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

    assert 'id="provider-sla-panel"' in index_html
    assert 'id="preview-refresh-data-btn"' in index_html
    assert "/api/observability/provider-sla" in app_js
    assert "/refresh/data" in app_js
