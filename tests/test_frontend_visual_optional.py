from pathlib import Path
import os

import pytest


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_history_preview_visual_regression_optional(tmp_path):
    required = os.getenv("VISUAL_REGRESSION_REQUIRED") == "1"
    try:
        import playwright.sync_api as sync_api
    except ImportError as exc:
        if required:
            pytest.fail(f"Playwright is required for visual regression: {exc}")
        pytest.skip(f"Playwright is unavailable: {exc}")
    css = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            STATIC_DIR / "styles" / "base.css",
            STATIC_DIR / "styles" / "forms_controls.css",
            STATIC_DIR / "styles" / "history_shell.css",
            STATIC_DIR / "styles" / "provider_sla.css",
            STATIC_DIR / "styles" / "history_list.css",
            STATIC_DIR / "styles" / "preview_panel.css",
            STATIC_DIR / "styles" / "responsive.css",
        )
    )
    html = """
    <html>
    <head><style>
    """ + css + """
    </style></head>
    <body>
      <main id="home-view" class="view-container active">
        <div class="glass-panel text-center">
          <div class="history-section">
            <div class="history-workspace has-preview">
              <div class="history-list-pane">
                <div class="history-controls">
                  <input class="history-search" value="2449" />
                  <div class="history-filter-row">
                    <label class="history-filter-field"><span>報告類型</span><select class="history-filter-select"><option>模式 B</option></select></label>
                    <label class="history-filter-field"><span>報告建議</span><select class="history-filter-select"><option>持有</option></select></label>
                    <label class="history-filter-field"><span>本報告資料狀態</span><select class="history-filter-select"><option>部分過期</option></select></label>
                  </div>
                </div>
                <div class="history-list">
                  <div class="history-item is-selected" data-pipeline="v2">
                    <div class="history-info">
                      <div><span class="history-ticker">2449.TW</span><span class="history-company">京元電子</span></div>
                      <div class="history-date"><span class="history-mode is-v2">模式 B · 實戰交易派</span><span class="data-trust-badge is-stale">本報告部分過期</span></div>
                      <div class="history-decision"><span class="history-rec is-hold">持有</span><span>NT$309.50</span><span>7/10</span></div>
                    </div>
                  </div>
                </div>
              </div>
              <section class="report-preview">
                <div class="preview-header">
                  <div><div class="preview-mode"><span class="history-mode is-v2">模式 B</span><span class="preview-date">2026-06-06</span></div><h2 class="preview-title">2449.TW 京元電子</h2></div>
                </div>
                <div class="preview-decision-row">
                  <div class="preview-decision"><span class="preview-label">當日股價</span><strong>NT$309.50</strong></div>
                  <div class="preview-decision"><span class="preview-label">報告建議</span><strong id="preview-recommendation" class="is-hold">持有</strong></div>
                  <div class="preview-decision"><span class="preview-label">信心</span><strong>7/10</strong></div>
                </div>
                <div class="preview-targets"><div><span>3個月</span><strong>NT$273</strong></div><div><span>6個月</span><strong>NT$310</strong></div><div><span>12個月</span><strong>NT$350</strong></div></div>
                <p class="preview-summary">端到端視覺測試摘要，確認文字在桌面寬度下不會互相覆蓋。</p>
                <button class="preview-open-button">查看完整報告</button>
              </section>
            </div>
          </div>
        </div>
      </main>
    </body>
    </html>
    """

    try:
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.set_content(html, wait_until="load")
            screenshot = page.screenshot(full_page=True)
            shot_path = tmp_path / "history-preview.png"
            shot_path.write_bytes(screenshot)
            assert len(screenshot) > 10_000
            list_box = page.locator(".history-list-pane").bounding_box()
            preview_box = page.locator(".report-preview").bounding_box()
            assert list_box and preview_box
            assert list_box["x"] + list_box["width"] <= preview_box["x"]
            assert preview_box["width"] >= 360
            browser.close()
    except Exception as exc:
        if required:
            pytest.fail(f"Playwright browser is required for visual regression: {exc}")
        pytest.skip(f"Playwright browser is unavailable: {exc}")


def test_home_workspace_grouping_visual_regression_optional(tmp_path):
    required = os.getenv("VISUAL_REGRESSION_REQUIRED") == "1"
    try:
        import playwright.sync_api as sync_api
    except ImportError as exc:
        if required:
            pytest.fail(f"Playwright is required for visual regression: {exc}")
        pytest.skip(f"Playwright is unavailable: {exc}")

    base_css = (STATIC_DIR / "styles" / "base.css").read_text(encoding="utf-8")
    tabs_css = (STATIC_DIR / "styles" / "history_shell_tabs.css").read_text(encoding="utf-8")
    responsive_css = (STATIC_DIR / "styles" / "responsive.css").read_text(encoding="utf-8")
    html = f"""
    <html><head><style>
    :root {{ --glass-border: rgba(148, 163, 184, 0.3); --text-primary: #f0f4ff; --text-secondary: #8899bb; --text-muted: #6677aa; --accent: #00d4ff; }}
    {base_css}
    body {{ margin: 0; background: #040d1a; color: var(--text-primary); font-family: Inter, sans-serif; }}
    {tabs_css}
    {responsive_css}
    </style></head><body>
      <nav class="home-workspace-nav" aria-label="工作區導覽">
        <section class="home-workspace-group is-analysis"><h2 class="home-workspace-label">分析工作台</h2>
          <div class="home-tabs"><button class="home-tab-button">分析</button><button class="home-tab-button">市場掃描</button></div>
        </section>
        <section class="home-workspace-group is-monitoring"><h2 class="home-workspace-label">監控工作台</h2>
          <div class="home-tabs"><button class="home-tab-button">追蹤</button><button class="home-tab-button">商業版</button><button class="home-tab-button">報告與維運</button></div>
        </section>
      </nav>
    </body></html>
    """

    try:
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.set_content(html, wait_until="load")
            desktop_analysis = page.locator(".is-analysis").bounding_box()
            desktop_monitoring = page.locator(".is-monitoring").bounding_box()
            desktop_shot = page.screenshot(full_page=True)
            assert desktop_analysis and desktop_monitoring
            assert desktop_analysis["x"] < desktop_monitoring["x"]
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert len(desktop_shot) > 5_000

            page.set_viewport_size({"width": 390, "height": 844})
            page.set_content(html, wait_until="load")
            mobile_analysis = page.locator(".is-analysis").bounding_box()
            mobile_monitoring = page.locator(".is-monitoring").bounding_box()
            assert mobile_analysis and mobile_monitoring
            assert mobile_analysis["x"] == mobile_monitoring["x"]
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            browser.close()
    except Exception as exc:
        if required:
            pytest.fail(f"Playwright browser is required for visual regression: {exc}")
        pytest.skip(f"Playwright browser is unavailable: {exc}")
