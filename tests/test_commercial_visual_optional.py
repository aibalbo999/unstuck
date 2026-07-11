import os
from urllib.error import URLError
from urllib.request import urlopen

import pytest


BASE_URL = os.getenv("COMMERCIAL_BASE_URL", "http://127.0.0.1:8080")
PAGES = (
    ("research-workbench.html", "今日決策"),
    ("stock-detail.html", "單股研究"),
    ("portfolio-dashboard.html", "組合健檢"),
)


def live_browser():
    required = os.getenv("VISUAL_REGRESSION_REQUIRED") == "1"
    try:
        urlopen(f"{BASE_URL}/static/commercial/research-workbench.html", timeout=2).close()
        import playwright.sync_api as sync_api
    except (ImportError, URLError, OSError) as exc:
        if required:
            pytest.fail(f"Live commercial browser is required: {exc}")
        pytest.skip(f"Live commercial browser is unavailable: {exc}")
    return sync_api


@pytest.mark.parametrize("width,height", ((375, 812), (768, 900), (1280, 720)))
def test_commercial_pages_keep_answer_and_primary_action_in_first_viewport(width, height):
    sync_api = live_browser()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        for filename, heading in PAGES:
            page.goto(f"{BASE_URL}/static/commercial/{filename}", wait_until="networkidle")
            assert page.get_by_role("heading", name=heading, level=1).is_visible()
            assert page.locator(".commercial-primary-action:visible").count() == 1
            assert page.locator("button:visible").count() <= 12
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            answer_box = page.locator(".commercial-answer").bounding_box()
            action_box = page.locator(".commercial-primary-action:visible").bounding_box()
            assert answer_box and answer_box["y"] < height
            assert action_box and action_box["y"] + action_box["height"] <= height
        browser.close()


def test_decision_empty_and_api_error_states_never_render_sample_stocks():
    sync_api = live_browser()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.route(
            "**/api/decision-tracking",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"items": []}',
            ),
        )
        page.goto(f"{BASE_URL}/static/commercial/research-workbench.html", wait_until="networkidle")
        assert page.get_by_role("heading", name="尚無追蹤股票", level=2).is_visible()
        assert page.get_by_role("link", name="設定追蹤股票").is_visible()
        assert "2330" not in page.locator("#decision-task-list").inner_text()

        page.unroute("**/api/decision-tracking")
        page.route(
            "**/api/decision-tracking",
            lambda route: route.fulfill(
                status=502,
                content_type="application/json",
                body='{"detail": "tracking unavailable"}',
            ),
        )
        page.reload(wait_until="networkidle")
        assert page.locator("#decision-source-status[data-state=error]").is_visible()
        assert "2330" not in page.locator("#decision-task-list").inner_text()
        browser.close()


def test_stock_and_portfolio_api_errors_show_recovery_state_without_fallbacks():
    sync_api = live_browser()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        page.route(
            "**/api/stocks/*/snapshot",
            lambda route: route.fulfill(
                status=502,
                content_type="application/json",
                body='{"detail": "stock unavailable"}',
            ),
        )
        page.goto(
            f"{BASE_URL}/static/commercial/stock-detail.html?ticker=2330.TW",
            wait_until="networkidle",
        )
        assert page.locator("#stock-source-status[data-state=error]").is_visible()
        assert "stock unavailable" in page.locator("#stock-source-status").inner_text()

        page.route(
            "**/api/watchlist/portfolio/risk",
            lambda route: route.fulfill(
                status=502,
                content_type="application/json",
                body='{"detail": "portfolio unavailable"}',
            ),
        )
        page.goto(f"{BASE_URL}/static/commercial/portfolio-dashboard.html", wait_until="networkidle")
        page.get_by_role("button", name="產生調整建議").click()
        page.locator("#portfolio-source-status[data-state=error]").wait_for()
        assert "portfolio unavailable" in page.locator("#portfolio-source-status").inner_text()
        assert page.locator("#portfolio-recommendations li").count() == 0
        browser.close()
