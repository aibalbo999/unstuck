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
