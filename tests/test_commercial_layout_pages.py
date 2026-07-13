from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMERCIAL_DIR = ROOT / "backend" / "static" / "commercial"


def read(relative: str) -> str:
    return (COMMERCIAL_DIR / relative).read_text(encoding="utf-8")


def test_commercial_shared_modules_define_request_state_and_navigation_contracts():
    api = read("shared/api.js")
    async_state = read("shared/async_state.js")
    shell = read("shared/shell.js")
    source_status = read("shared/source_status.js")
    ticker_options_path = COMMERCIAL_DIR / "shared" / "ticker_options.js"

    assert ticker_options_path.exists()
    ticker_options = ticker_options_path.read_text(encoding="utf-8")

    assert "export class ApiError" in api
    assert "X-Mutation-Token" in api
    assert "export async function requestJson" in api
    assert "export function setAsyncState" in async_state
    assert "export function normalizeTicker" in shell
    assert "export function isValidTicker" in shell
    assert "export function stockPageHref" in shell
    assert "export function focusPageHeading" in shell
    assert "export function bindTabs" in shell
    assert "export function renderSourceStatus" in source_status
    assert "export async function loadTickerChoices" in ticker_options
    for endpoint in ("/api/watchlist/symbols", "/api/decision-tracking", "/api/reports"):
        assert endpoint in ticker_options


def test_three_pages_mount_the_configurable_operator_policy_editor():
    editor_path = COMMERCIAL_DIR / "shared" / "operator_policy_ui.js"
    assert editor_path.exists()
    editor = editor_path.read_text(encoding="utf-8")

    for filename in (
        "research-workbench.html",
        "stock-detail.html",
        "portfolio-dashboard.html",
    ):
        html = read(filename)
        assert 'data-operator-policy-editor' in html
        assert "500 萬操作護欄" not in html

    for text in (
        "操作資金",
        "現金保留",
        "單一持股上限",
        "單筆最大風險",
        "套用設定",
        "恢復預設",
    ):
        assert text in editor
    assert "mountOperatorPolicyEditor" in editor
    assert "readOperatorPolicy" in editor
    assert "writeOperatorPolicy" in editor


def test_commercial_styles_define_single_task_layout_and_responsive_contracts():
    tokens = read("styles/tokens.css")
    shell = read("styles/shell.css")
    components = read("styles/components.css")
    responsive = read("styles/responsive.css")

    assert "--commercial-primary" in tokens
    assert "width: min(100% - 32px, 1200px)" in shell
    assert ".commercial-primary-action" in components
    assert "min-height: 44px" in components
    for selector in (
        ".commercial-policy-strip",
        ".commercial-policy-editor",
        ".commercial-data-table",
        ".commercial-status-badge",
        ".commercial-position-planner",
        ".commercial-filter-bar",
    ):
        assert selector in components
    assert "font-variant-numeric: tabular-nums" in components
    assert "overflow-x: auto" in components
    assert ".commercial-capital-metrics" in components
    assert ".commercial-metric small" in components and "display: block" in components
    assert "repeat(auto-fit, minmax(160px, 1fr))" in components
    assert ".commercial-field .commercial-input-with-suffix input" in components
    assert ".commercial-import-details summary" in components
    assert "display: list-item" in components
    assert "@media (max-width: 560px)" in responsive
    assert "@media (max-width: 768px)" in responsive
    assert "grid-template-columns: 1fr" in responsive


def test_decision_page_is_a_single_task_queue_without_demo_fallbacks():
    html = read("research-workbench.html")
    js = read("pages/decision_page.js")

    assert 'data-commercial-page="decision"' in html
    assert 'id="decision-title"' in html
    assert ">今日決策</h1>" in html
    assert html.count("commercial-primary-action") == 1
    assert 'id="decision-task-list"' in html
    assert 'id="decision-policy"' in html
    assert 'id="decision-summary-metrics"' in html
    assert 'id="decision-filters"' in html
    for name in ("all", "rerun", "weak"):
        assert f'data-filter="{name}"' in html
    assert 'id="decision-all-action"' in html
    assert ">查看全部追蹤股票</a>" in html
    assert 'type="module" src="/static/commercial/pages/decision_page.js' in html
    assert "/api/decision-tracking" in js
    assert "stockPageHref" in js
    for field in (
        "recommendation",
        "latestPrice",
        "returnPct",
        "targetGap",
        "confidence",
    ):
        assert field in js
    assert ".slice(0, 5)" in js
    assert "renderFilteredTasks" in js
    assert "operator_policy.js" in js
    assert "allAction.hidden = false" in js
    assert "fallbackTickers" not in js
    assert "localStorage" not in js


def test_stock_page_has_one_snapshot_action_and_five_operator_tabs():
    html = read("stock-detail.html")
    js = read("pages/stock_page.js")

    assert 'data-commercial-page="stock"' in html
    assert html.count("commercial-primary-action") == 1
    assert '<div class="commercial-workspace-grid">' in html
    for marker in (
        'id="stock-policy"',
        'id="stock-ticker-select"',
        'id="stock-position-form"',
        'id="stock-entry-price"',
        'id="stock-stop-price"',
        'id="stock-position-metrics"',
    ):
        assert marker in html
    for name in ("plan", "valuation", "fundamentals", "events", "technical"):
        assert f'data-tab="{name}"' in html
    assert "/api/stocks/" in js and "/snapshot" in js
    assert "loadTickerOptions" in js
    assert "loadTickerChoices" in js
    assert "ticker_options.js" in js
    assert "bindTabs" in js
    assert "isValidTicker" in js
    assert "positionPlan" in js
    assert "renderPositionPlan" in js
    assert "operator_policy.js" in js
    assert "海外股票需要匯率" in js
    assert "fallbackTickers" not in js
    assert "fallbackSnapshot" not in js


def test_portfolio_page_translates_risk_into_five_million_amounts():
    html = read("portfolio-dashboard.html")
    js = read("pages/portfolio_page.js")

    assert 'data-commercial-page="portfolio"' in html
    assert html.count("commercial-primary-action") == 1
    assert 'id="portfolio-csv"' in html
    assert 'id="portfolio-csv-file"' in html
    assert 'accept=".csv,text/csv"' in html
    assert 'id="portfolio-csv-file-status"' in html
    assert 'id="portfolio-recommendations"' in html
    for marker in (
        'id="portfolio-policy"',
        'id="portfolio-ticker-select"',
        'id="portfolio-holding-amount"',
        'id="portfolio-holding-add"',
        'id="portfolio-holding-list"',
        'id="portfolio-holding-error"',
        'id="portfolio-capital-metrics"',
        'id="portfolio-position-table"',
    ):
        assert marker in html
    for name in ("allocation", "exposure", "thesis", "actions"):
        assert f'data-tab="{name}"' in html
    assert "/api/watchlist/portfolio/risk" in js
    assert "validatePortfolioCsv" in js
    assert "readPortfolioFile" in js
    assert ".text()" in js
    assert "loadTickerChoices" in js
    assert "upsertAmountHolding" in js
    assert "removeAmountHolding" in js
    assert "parseAmountHoldings" in js
    assert "renderHoldingDraft" in js
    assert "投入金額" in html
    assert 'id="portfolio-holding-weight"' not in html
    assert "amountForWeight" in js
    assert "trimToPositionLimit" in js
    assert "renderPositionTable" in js
    assert "operator_policy.js" in js
    assert "fallbackPortfolio" not in js
    assert "localStorage" not in js


def test_three_pages_share_navigation_and_do_not_load_legacy_bundle():
    pages = {
        "research-workbench.html": "decision_page.js",
        "stock-detail.html": "stock_page.js",
        "portfolio-dashboard.html": "portfolio_page.js",
    }
    for filename, module in pages.items():
        html = read(filename)
        assert html.count('class="commercial-primary-action') == 1
        assert 'href="/static/commercial/research-workbench.html"' in html
        assert 'href="/static/commercial/stock-detail.html"' in html
        assert 'href="/static/commercial/portfolio-dashboard.html"' in html
        assert f"/static/commercial/pages/{module}" in html
        assert "commercial_pages.js" not in html
        assert "commercial_pages.css" not in html
        assert '<a class="commercial-brand" href="/"' in html


def test_three_pages_bust_cached_assets_with_the_same_current_version():
    pages = {
        "research-workbench.html": "pages/decision_page.js",
        "stock-detail.html": "pages/stock_page.js",
        "portfolio-dashboard.html": "pages/portfolio_page.js",
    }
    for filename, module in pages.items():
        html = read(filename)
        assert html.count("?v=20260711-operator6") == 5
        assert "operator_policy.js?v=20260711-operator6" in read(module)
        assert "operator_policy_ui.js?v=20260711-operator6" in read(module)


def test_metrics_tabs_focus_and_visibility_follow_accessible_contracts():
    components = read("styles/components.css")
    shell = read("shared/shell.js")
    for filename in (
        "research-workbench.html",
        "stock-detail.html",
        "portfolio-dashboard.html",
    ):
        html = read(filename)
        assert 'class="commercial-metric" role="button"' not in html
    assert "ArrowLeft" in shell and "ArrowRight" in shell
    assert "focusPageHeading" in shell
    assert ":focus-visible" in components
    assert '.commercial-page h1[tabindex="-1"]:focus' in components
    assert "outline: 2px solid" in components
    assert "outline: none" not in components
    assert "min-height: 44px" in components
    assert "[hidden]" in components
    assert ".commercial-source-status:empty" in components
    assert ".commercial-page > .commercial-answer" in components


def test_legacy_commercial_bundle_is_removed_after_page_modules_take_over():
    assert not (COMMERCIAL_DIR / "commercial_pages.js").exists()
    assert not (COMMERCIAL_DIR / "commercial_pages.css").exists()
