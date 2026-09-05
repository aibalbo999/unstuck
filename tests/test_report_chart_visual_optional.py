import json
import os
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "backend" / "templates"


def test_report_chart_canvas_pixels_optional():
    required = os.getenv("VISUAL_REGRESSION_REQUIRED") == "1"
    if not required:
        pytest.skip("Set VISUAL_REGRESSION_REQUIRED=1 to run real Chart.js browser checks")
    try:
        import playwright.sync_api as sync_api
    except ImportError as exc:
        pytest.fail(f"Playwright is required for chart visual regression: {exc}")
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
    chart_data = {
        "years": [2023, 2024, 2025],
        "revenue": [100, 120, 150],
        "netIncome": [12, 14, 20],
        "fcf": [8, -3, 11],
        "grossMargin": [32, 34, 35],
        "opMargin": [12, 13, 14],
        "netMargin": [8, 9, 10],
        "roe": [12, 13, 15],
        "moatLabels": ["品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"],
        "moatValues": [6, 4, 7, 7, 6, 6],
        "priceTargets": {"熊市情境": 80, "基本情境": 120, "牛市情境": 160},
        "currentPrice": 125,
        "market": {
            "price": {"dates": ["2025-01-02", "2025-01-03"], "prices": [120, 125]},
            "dailyFlow": {"dates": ["2025-01-02", "2025-01-03"], "values": [-20, 10]},
            "categoryFlow": {"labels": ["外資", "投信", "自營商"], "values": [-30, 20, 0]},
            "currency": "TWD",
        },
        "peRiver": {
            "years": [2023, 2024, 2025],
            "bands": {"10x": [90, 100, 110], "15x": [135, 150, 165]},
        },
    }
    script = env.get_template("includes/report_charts.html.j2").render(
        chart_data=chart_data,
        current_price_numeric=125,
    )
    canvas_ids = ["revenueChart", "marginChart", "fcfChart", "roeChart", "moatChart", "valuationChart", "peRiverChart", "marketPriceChart", "institutionalDailyChart", "institutionalCategoryChart"]
    canvases = "\n".join(
        f'<div class="chart-canvas-wrapper"><canvas id="{canvas_id}" width="320" height="180"></canvas></div>'
        for canvas_id in canvas_ids
    )
    html = f"""
    <html>
    <head>
      <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
      <style>.chart-canvas-wrapper {{ position: relative; height: 240px; width: 400px; }}</style>
    </head>
    <body>
      {canvases}
      <div class="moat-scores-list"></div>
      <div id="moat-overall-score"></div>
      <section id="overview"></section>
      <section class="section" id="section-1"></section>
      <a class="nav-item" href="#overview"></a>
      <script id="report-chart-data" type="application/json">{json.dumps(chart_data)}</script>
      <script>{script}</script>
    </body>
    </html>
    """
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(html, wait_until="load")
        page.wait_for_function("typeof Chart !== 'undefined' && Object.keys(Chart.instances).length === 10")
        page.evaluate("Object.values(Chart.instances).forEach(c=>{c.options.animation=false;c.update('none')})")
        result = page.evaluate(
            """(ids) => ({
                chartIds: Object.values(Chart.instances).map(c=>c.canvas.id),
                nonBlank: ids.filter(id => {
                    const canvas = document.getElementById(id);
                    const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
                    return Array.from(data).some(value => value !== 0);
                }),
                moatBars: document.querySelectorAll('.moat-score-item').length,
                overall: document.getElementById('moat-overall-score').textContent,
            })""",
            canvas_ids,
        )
        assert set(result["chartIds"]) == set(canvas_ids)
        assert set(result["nonBlank"]) == set(canvas_ids)
        assert result["moatBars"] == 5
        assert result["overall"] == "6"
        assert not errors
        browser.close()
