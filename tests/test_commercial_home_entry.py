from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_home_commercial_tab_prioritizes_today_decisions():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    entry_css = (STATIC_DIR / "commercial" / "styles" / "home_entry.css").read_text(encoding="utf-8")

    assert "/static/commercial/styles/home_entry.css?v=20260711-simple" in index_html
    assert 'id="home-panel-commercial"' in index_html
    assert 'class="commercial-entry-primary"' in index_html
    assert 'href="/static/commercial/research-workbench.html"' in index_html
    assert "今天先處理什麼" in index_html
    assert index_html.count('class="commercial-entry-secondary"') == 2
    assert "產生 AI 報告" not in index_html
    assert "建立再平衡單" not in index_html
    assert ".commercial-entry-primary" in entry_css
    assert ".commercial-entry-secondary" in entry_css
    assert "@media (max-width: 560px)" in entry_css
