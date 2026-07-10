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


def test_commercial_styles_define_single_task_layout_and_responsive_contracts():
    tokens = read("styles/tokens.css")
    shell = read("styles/shell.css")
    components = read("styles/components.css")
    responsive = read("styles/responsive.css")

    assert "--commercial-primary" in tokens
    assert "width: min(100% - 32px, 1200px)" in shell
    assert ".commercial-primary-action" in components
    assert "min-height: 44px" in components
    assert "@media (max-width: 560px)" in responsive
    assert "grid-template-columns: 1fr" in responsive


def test_decision_page_is_a_single_task_queue_without_demo_fallbacks():
    html = read("research-workbench.html")
    js = read("pages/decision_page.js")

    assert 'data-commercial-page="decision"' in html
    assert 'id="decision-title"' in html
    assert ">今日決策</h1>" in html
    assert html.count("commercial-primary-action") == 1
    assert 'id="decision-task-list"' in html
    assert 'type="module" src="/static/commercial/pages/decision_page.js' in html
    assert "/api/decision-tracking" in js
    assert "stockPageHref" in js
    assert "fallbackTickers" not in js
    assert "localStorage" not in js


def test_stock_page_has_one_snapshot_action_and_four_evidence_tabs():
    html = read("stock-detail.html")
    js = read("pages/stock_page.js")

    assert 'data-commercial-page="stock"' in html
    assert html.count("commercial-primary-action") == 1
    for name in ("answer", "fundamentals", "events", "technical"):
        assert f'data-tab="{name}"' in html
    assert "/api/stocks/" in js and "/snapshot" in js
    assert "bindTabs" in js
    assert "isValidTicker" in js
    assert "fallbackTickers" not in js
    assert "fallbackSnapshot" not in js
