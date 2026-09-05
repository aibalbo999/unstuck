#!/usr/bin/env python3
"""Render saved snapshots into QA copies and check real Chart.js at two widths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from report_artifacts import ReportArtifactLocator
from reporting.html_renderer import generate_html_report
from runtime_paths import current_runtime_paths
from storage.report_storage import LocalFileStorage


CHART_STATE = """() => [...document.querySelectorAll('.chart-canvas-wrapper canvas')].map(canvas => {
    const chart = window.Chart?.getChart(canvas);
    const rect = canvas.getBoundingClientRect();
    let pixels = 0;
    let plotPixels = 0;
    if (chart?.chartArea && rect.width > 0) {
        const {left, top, right, bottom} = chart.chartArea;
        const ratio = chart.currentDevicePixelRatio;
        const image = canvas.getContext('2d').getImageData(Math.ceil(left * ratio), Math.ceil(top * ratio), Math.max(1, Math.floor((right-left) * ratio)), Math.max(1, Math.floor((bottom-top) * ratio))).data;
        for (let i=0; i<image.length; i+=4) {
            if (image[i+3] > 0) plotPixels++;
            if (image[i+3] > 20 && Math.max(image[i],image[i+1],image[i+2]) - Math.min(image[i],image[i+1],image[i+2]) > 30) pixels++;
        }
    }
    const validValues = chart?.data.datasets.reduce((n,d) => n+d.data.filter(Number.isFinite).length,0) || 0;
    const zeroBars = validValues > 0 && chart.data.datasets.every((dataset, datasetIndex) => {
        const meta = chart.getDatasetMeta(datasetIndex);
        return dataset.data.every((value, index) => {
            if (!Number.isFinite(value)) return true;
            const element = meta.data[index];
            if (value !== 0 || meta.type !== 'bar' || !chart.isDatasetVisible(datasetIndex) || !element) return false;
            const point = element.getCenterPoint();
            return [point.x, point.y, element.base, element.width, element.height].every(Number.isFinite)
                && Math.abs(element.horizontal ? element.width : element.height) < 0.01
                && point.x >= chart.chartArea.left && point.x <= chart.chartArea.right
                && point.y >= chart.chartArea.top && point.y <= chart.chartArea.bottom;
        });
    });
    return {
        id: canvas.id, state: canvas.dataset.chartState,
        width: rect.width, height: rect.height, coloredPlotPixels: pixels, plotPixels,
        validValues, zeroBars,
        message: canvas.parentElement.querySelector('.chart-empty-state')?.textContent || '',
        overflow: rect.right > innerWidth + 1 || rect.left < -1,
    };
})"""


TOOLTIP_POINT = """id => {
    const chart = Chart.getChart(id);
    const rect = chart.canvas.getBoundingClientRect();
    for (let datasetIndex = 0; datasetIndex < chart.data.datasets.length; datasetIndex++) {
        if (!chart.isDatasetVisible(datasetIndex)) continue;
        const dataset = chart.data.datasets[datasetIndex];
        const meta = chart.getDatasetMeta(datasetIndex);
        for (let index = 0; index < dataset.data.length; index++) {
            const element = meta.data[index];
            if (!Number.isFinite(dataset.data[index]) || !element || element.skip || element.hidden) continue;
            const point = element.getCenterPoint();
            if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) continue;
            if (point.x < chart.chartArea.left || point.x > chart.chartArea.right
                || point.y < chart.chartArea.top || point.y > chart.chartArea.bottom) continue;
            return {id, x:rect.left+point.x, y:rect.top+point.y};
        }
    }
    return null;
}"""


def validate_chart_states(charts):
    assert charts, "no charts"
    assert len({chart["id"] for chart in charts}) == len(charts), "duplicate canvas IDs"
    for chart in charts:
        assert chart["state"] in ("ready", "empty"), chart
        if chart["state"] == "ready":
            # Zero-height bars have no colored fill; require their actual geometry
            # and a painted coordinate plane. Nonzero data still requires plot color.
            painted = chart["coloredPlotPixels"] > 20 or (chart["zeroBars"] and chart["plotPixels"] > 20)
            assert painted and chart["validValues"] > 0, chart
            assert chart["width"] > 100 and chart["height"] >= 180 and not chart["overflow"], chart
        else:
            assert chart["message"], chart


def verify_tooltip(page, charts):
    ready = [chart for chart in charts if chart["state"] == "ready"]
    if not ready:
        return "not_applicable"
    for chart in ready:
        page.locator(f'#{chart["id"]}').scroll_into_view_if_needed()
        point = page.evaluate(TOOLTIP_POINT, chart["id"])
        if point is not None:
            page.mouse.move(point["x"], point["y"])
            page.wait_for_function("id => Chart.getChart(id).tooltip.opacity > 0", arg=point["id"])
            return True
    raise AssertionError("ready charts have no visible finite tooltip point")


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filenames", nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, default=current_runtime_paths().output_dir)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    locator = ReportArtifactLocator(LocalFileStorage(str(args.source_dir)))
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for filename in args.filenames:
            bundle = locator.require_bundle(filename)
            snapshot = bundle.read_data_snapshot()
            context = {**snapshot, **snapshot.get("rerun_context", {})}
            context["pipeline_id"] = snapshot["pipeline"]
            mode = context["pipeline_id"]
            preview = output / Path(filename).name
            if preview.resolve() == (args.source_dir / bundle.html_key).resolve():
                raise ValueError("QA output must not overwrite the original report")
            preview.write_text(generate_html_report(context), encoding="utf-8")
            for width in (1280, 375):
                page = browser.new_page(viewport={"width": width, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(preview.as_uri(), wait_until="networkidle")
                page.wait_for_function("[...document.querySelectorAll('canvas')].every(c=>c.dataset.chartState)")
                page.evaluate("Object.values(Chart.instances).forEach(chart=>{chart.stop();chart.options.animation=false;chart.update('none')})")
                charts = page.evaluate(CHART_STATE)
                validate_chart_states(charts)
                selector = '#market-charts' if mode != 'v1' else '[data-report-section="financial_charts"]'
                page.locator(selector).screenshot(path=str(output / f"{mode}-{width}.png"))
                tooltip = verify_tooltip(page, charts)
                assert not errors, errors
                results.append({"mode": mode, "width": width, "charts": charts, "tooltip": tooltip, "errors": errors})
                print(f"{mode} {width}px: charts, pixels and layout passed; tooltip={tooltip}", flush=True)
                page.close()
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/chart.umd.min.js", lambda route: route.abort())
            page.goto(preview.as_uri(), wait_until="networkidle")
            states = page.locator("canvas").evaluate_all("items=>items.map(c=>c.dataset.chartState)")
            assert states and all(state == "unavailable" for state in states), states
            assert not errors, errors
            page.close()
        browser.close()
    (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{"mode": row["mode"], "width": row["width"], "ready": sum(c["state"] == "ready" for c in row["charts"]), "empty": [c["id"] for c in row["charts"] if c["state"] == "empty"], "tooltip": row["tooltip"], "errors": row["errors"]} for row in results], ensure_ascii=False, indent=2))
    print(f"QA copies and screenshots: {output}")


if __name__ == "__main__":
    main()
