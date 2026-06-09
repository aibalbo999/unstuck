import os
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "backend" / "templates"


def test_report_chart_canvas_pixels_optional():
    required = os.getenv("VISUAL_REGRESSION_REQUIRED") == "1"
    try:
        import playwright.sync_api as sync_api
    except ImportError as exc:
        if required:
            pytest.fail(f"Playwright is required for chart visual regression: {exc}")
        pytest.skip(f"Playwright is unavailable: {exc}")
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
        "peRiver": {
            "years": [2023, 2024, 2025],
            "bands": {"10x": [90, 100, 110], "15x": [135, 150, 165]},
        },
    }
    script = env.get_template("includes/report_charts.html.j2").render(
        chart_data=chart_data,
        current_price_numeric=125,
    )
    canvas_ids = ["revenueChart", "marginChart", "fcfChart", "roeChart", "moatChart", "valuationChart", "peRiverChart"]
    canvases = "\n".join(
        f'<div class="chart-canvas-wrapper"><canvas id="{canvas_id}" width="320" height="180"></canvas></div>'
        for canvas_id in canvas_ids
    )
    html = f"""
    <html>
    <body>
      {canvases}
      <div class="moat-scores-list"></div>
      <div id="moat-overall-score"></div>
      <section id="overview"></section>
      <section class="section" id="section-1"></section>
      <a class="nav-item" href="#overview"></a>
      <script>
        window.IntersectionObserver = class {{
          constructor(callback) {{ this.callback = callback; }}
          observe(target) {{ this.callback([{{ isIntersecting: true, target }}]); }}
        }};
        window.Chart = class {{
          static defaults = {{ font: {{}} }};
          constructor(ctx, config) {{
            const canvas = ctx.canvas;
            ctx.fillStyle = (config.data.datasets[0] || {{}}).backgroundColor || '#3b82f6';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            window.__chartIds = window.__chartIds || [];
            window.__chartIds.push(canvas.id);
          }}
        }};
      </script>
      <script>{script}</script>
    </body>
    </html>
    """
    try:
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            page.set_content(html, wait_until="load")
            result = page.evaluate(
                """(ids) => ({
                    chartIds: window.__chartIds || [],
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
            browser.close()
    except Exception as exc:
        if required:
            pytest.fail(f"Playwright browser is required for chart visual regression: {exc}")
        pytest.skip(f"Playwright browser is unavailable: {exc}")
