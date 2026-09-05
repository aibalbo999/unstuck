import base64
import hashlib
import os
from dataclasses import fields
from html.parser import HTMLParser

import pytest

from report_history_downloads import secure_html_response
from reporting.html_renderer import generate_html_report


class ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = {"attrs": dict(attrs), "text": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append(self.current)
            self.current = None


def script_hash(text):
    digest = hashlib.sha256(text.encode()).digest()
    return "'sha256-" + base64.b64encode(digest).decode() + "'"


def sample_report():
    return generate_html_report({
        "ticker": "2330.TW", "company_name": "Test", "pipeline_id": "v4",
        "data": {
            "current_price": 100,
            "price_history_ranges": {"ranges": {"1m": {
                "dates": ["2026-01-02", "2026-01-03"], "prices": [98, 100],
            }}},
            "institutional_trading": {
                "daily_total_net_buy_last_10": [
                    {"date": "2026-01-02", "net_buy_thousand_shares": 0},
                    {"date": "2026-01-03", "net_buy_thousand_shares": 10},
                ],
                "net_buy_thousand_shares_by_category": {"foreign": -10, "investment_trust": 20, "dealer": 0},
            },
        }, "analyses": {}, "parsed": {},
    })


def report_route_response(tmp_path, html, suffix):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.reports import ReportRouteDeps, create_reports_router
    from storage.report_storage import LocalFileStorage

    def unexpected_call(*args, **kwargs):
        pytest.fail("Chart view must not call a mutation/analysis dependency")

    filename = "2330_TW_v4_report_20260104_010000.html"
    (tmp_path / filename).write_text(html, encoding="utf-8")
    storage = LocalFileStorage(str(tmp_path))
    values = {field.name: unexpected_call for field in fields(ReportRouteDeps)}
    values.update(get_output_dir=lambda: str(tmp_path), get_report_storage=lambda: storage)
    app = FastAPI()
    app.include_router(create_reports_router(ReportRouteDeps(**values)))
    with TestClient(app) as client:
        return client.get(f"/api/report/{filename}{suffix}")


def test_rendered_report_allows_only_trusted_chart_runtime():
    html = sample_report()
    parser = ScriptCollector()
    parser.feed(html)
    runtime = next(script["text"] for script in parser.scripts if not script["attrs"])
    malicious = "window.reportInjected = true"
    response = secure_html_response(html + f"<script>{malicious}</script>")
    policy = response.headers["content-security-policy"]

    assert script_hash(runtime) in policy
    assert "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js" in policy
    assert script_hash(malicious) not in policy
    assert "script-src-attr 'none'" in policy
    script_sources = next(part for part in policy.split(";") if part.strip().startswith("script-src "))
    assert "'unsafe-inline'" not in script_sources
    assert "'unsafe-eval'" not in script_sources
    assert "'self'" not in script_sources


def test_changed_or_unknown_report_scripts_remain_blocked():
    html = sample_report().replace("const chartPayload", "window.reportInjected = true; const chartPayload")
    for content in (html, '<script src="https://evil.example/payload.js"></script>', "<h1>report</h1>"):
        policy = secure_html_response(content).headers["content-security-policy"]
        assert "script-src 'none'" in policy
        assert "sha256-" not in policy


@pytest.mark.parametrize("suffix", ["", "/download/html"])
def test_formal_report_routes_preserve_chart_hash_through_read_time_repair(tmp_path, suffix):
    response = report_route_response(tmp_path, sample_report(), suffix)
    assert response.status_code == 200
    assert "資料快照不存在" in response.text
    assert "sha256-" in response.headers["content-security-policy"]
    assert "script-src-attr 'none'" in response.headers["content-security-policy"]
    if suffix:
        assert "attachment" in response.headers["content-disposition"]


@pytest.mark.skipif(os.getenv("VISUAL_REGRESSION_REQUIRED") != "1", reason="Requires real Chart.js browser checks")
@pytest.mark.parametrize("suffix", ["", "/download/html"])
def test_browser_runs_charts_but_blocks_injected_scripts(tmp_path, suffix):
    from playwright.sync_api import sync_playwright

    injected = '<script>window.reportInjected = true</script><img src="missing" onerror="window.reportInjected = true">'
    response = report_route_response(tmp_path, sample_report() + injected, suffix)
    assert response.status_code == 200
    assert "sha256-" in response.headers["content-security-policy"]
    assert "資料快照不存在" in response.text  # The real read-time repair ran.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", lambda route: route.continue_() if (
            route.request.url == "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
        ) else route.abort())
        # Present download bytes as a page while retaining its real CSP headers.
        headers = {key: value for key, value in response.headers.items() if key != "content-disposition"}
        page.route("https://report.test/view", lambda route: route.fulfill(
            status=response.status_code, headers=headers, body=response.content,
        ))
        page.goto("https://report.test/view", wait_until="networkidle")
        page.wait_for_function("() => typeof Chart !== 'undefined' && [...document.querySelectorAll('canvas')].every(c => ['ready', 'empty'].includes(c.dataset.chartState))")
        assert page.locator('canvas[data-chart-state="ready"]').count() == 3
        assert page.evaluate("() => Object.values(Chart.instances).every(chart => chart.data.datasets.some(dataset => dataset.data.some(Number.isFinite)))")
        assert page.evaluate("() => Chart.getChart('marketPriceChart').data.datasets[0].data") == [98, 100]
        assert page.evaluate("() => window.reportInjected === undefined")
        assert not errors
        browser.close()
