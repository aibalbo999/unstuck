import json
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
def test_commercial_pages_keep_operator_flow_visible_and_responsive(width, height):
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
            assert answer_box and action_box
            if width >= 1024:
                assert answer_box["y"] < height
                assert action_box["y"] + action_box["height"] <= height
            else:
                assert action_box["y"] < height * 1.5
                assert answer_box["y"] < height * 2
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


def test_five_million_operator_controls_have_visible_results():
    sync_api = live_browser()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        decision_payload = {
            "items": [
                {
                    "ticker": "2330",
                    "company_name": "台積電",
                    "last_refresh_status": "success",
                    "latest_report": {
                        "ticker": "2330.TW",
                        "company_name": "台積電",
                        "decision_tracking": {
                            "recommendation": "買進",
                            "latest_price": 100,
                            "return_pct": 4.5,
                            "target_12m_gap_pct": 25,
                            "confidence": "8/10",
                        },
                        "decision_freshness": {"requires_rerun": True},
                    },
                },
                {
                    "ticker": "2308",
                    "company_name": "台達電",
                    "last_refresh_status": "success",
                    "latest_report": {
                        "ticker": "2308.TW",
                        "company_name": "台達電",
                        "decision_tracking": {
                            "recommendation": "持有",
                            "latest_price": 80,
                            "return_pct": -3,
                            "target_12m_gap_pct": 8,
                            "confidence": "6/10",
                        },
                        "decision_freshness": {"requires_rerun": False},
                    },
                },
            ]
        }
        page.route(
            "**/api/decision-tracking",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(decision_payload),
            ),
        )
        page.goto(
            f"{BASE_URL}/static/commercial/research-workbench.html",
            wait_until="networkidle",
        )
        assert "NT$5,000,000" in page.locator("#decision-policy").inner_text()
        assert page.locator("#decision-task-list li").count() == 2
        page.get_by_role("button", name="需重跑").click()
        assert page.locator("#decision-task-list li").count() == 1
        assert "2330.TW" in page.locator("#decision-task-list").inner_text()
        assert "2308.TW" not in page.locator("#decision-task-list").inner_text()

        stock_payload = {
            "ticker": "2330.TW",
            "identity": {"company_name": "台積電"},
            "quote": {
                "price": 100,
                "price_label": "NT$100",
                "as_of": "2026-07-11",
            },
            "valuation": {
                "pe_ratio": {"label": "20x"},
                "forward_pe": {"label": "18x"},
                "pb_ratio": {"label": "5x"},
                "ps_ratio": {"label": "8x"},
                "analyst_target": {
                    "price": 125,
                    "label": "NT$125",
                    "upside_pct": 25,
                },
            },
            "analyst_outlook": {
                "label": "目標價上行",
                "consensus": {"recommendation_label": "買進"},
                "signals": ["目標價上行 +25%"],
            },
            "technical_summary": {
                "moving_averages": {"ma_6m": {"value": 90}},
                "signals": ["現價高於 6M 均線"],
            },
            "financial_health": {},
            "profitability_quality": {"signals": []},
            "event_calendar": {"events": [], "next_event": {}},
            "data_quality": {"score": 90, "status": "fresh"},
        }
        page.route(
            "**/api/stocks/*/snapshot",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(stock_payload),
            ),
        )
        page.goto(
            f"{BASE_URL}/static/commercial/stock-detail.html?ticker=2330.TW",
            wait_until="networkidle",
        )
        assert "NT$500,000" in page.locator("#stock-position-metrics").inner_text()
        page.locator("#stock-stop-price").fill("95")
        assert "NT$37,500" in page.locator("#stock-position-metrics").inner_text()

        portfolio_payload = {
            "total_positions": 3,
            "positions": [
                {
                    "ticker": "2330.TW",
                    "weight_pct": 22,
                    "sector": "Semi",
                    "country": "TW",
                },
                {
                    "ticker": "AAPL",
                    "weight_pct": 68,
                    "sector": "Software",
                    "country": "US",
                },
                {
                    "ticker": "CASH",
                    "weight_pct": 10,
                    "sector": "Cash",
                    "country": "TW",
                },
            ],
            "concentration": {
                "top_position": {"ticker": "AAPL", "weight_pct": 68},
                "sector_weights": {"Software": 68, "Semi": 22, "Cash": 10},
                "country_weights": {"US": 68, "TW": 32},
            },
            "thesis_health": {"invalidated": [], "missing": ["AAPL"]},
            "risk_flags": ["single_position_over_40_pct"],
        }
        page.route(
            "**/api/watchlist/portfolio/risk",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(portfolio_payload),
            ),
        )
        page.goto(
            f"{BASE_URL}/static/commercial/portfolio-dashboard.html",
            wait_until="networkidle",
        )
        page.get_by_role("button", name="分析 500 萬組合").click()
        page.locator("#portfolio-position-rows tr").first.wait_for()
        assert "NT$5,000,000" in page.locator("#portfolio-capital-metrics").inner_text()
        assert "NT$350,000" in page.locator("#portfolio-position-table").inner_text()
        assert "現金保留" in page.locator("#portfolio-position-table").inner_text()
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
        page.get_by_role("button", name="分析 500 萬組合").click()
        page.locator("#portfolio-source-status[data-state=error]").wait_for()
        assert "portfolio unavailable" in page.locator("#portfolio-source-status").inner_text()
        assert page.locator("#portfolio-recommendations li").count() == 0
        browser.close()
