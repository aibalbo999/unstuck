"""Real-browser regressions for QA handling of valid missing/zero chart values."""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from data_trust import data_snapshot_filename_for_report


ROOT = Path(__file__).resolve().parents[1]


def load_qa_module():
    spec = importlib.util.spec_from_file_location("qa_report_charts", ROOT / "scripts/qa_report_charts.py")
    qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa)
    return qa


@pytest.mark.parametrize("changes", [
    {"zeroBars": True, "plotPixels": 0},
    {"zeroBars": False, "plotPixels": 500},
    {"zeroBars": True, "plotPixels": 500, "validValues": 0},
])
def test_chart_validation_rejects_blank_or_unpainted_nonzero_data(changes):
    chart = {
        "id": "test", "state": "ready", "width": 384, "height": 240,
        "validValues": 2, "coloredPlotPixels": 0, "zeroBars": False,
        "plotPixels": 0, "overflow": False, **changes,
    }
    with pytest.raises(AssertionError):
        load_qa_module().validate_chart_states([chart])


@pytest.mark.skipif(os.getenv("VISUAL_REGRESSION_REQUIRED") != "1", reason="Requires real Chart.js browser checks")
@pytest.mark.parametrize("case,mode,data", [
    ("empty", "v4", {}),
    ("later_dataset", "v1", {
        "years": [2023, 2024, 2025], "revenue_history": [None, None, None],
        "net_income_history": [1, 2, 3],
    }),
    ("zero_bars", "v4", {"institutional_trading": {
        "latest_date": "2026-01-03",
        "daily_total_net_buy_last_10": [
            {"date": "2026-01-02", "net_buy_thousand_shares": 0},
            {"date": "2026-01-03", "net_buy_thousand_shares": 0},
        ],
        "net_buy_thousand_shares_by_category": {"foreign": 0, "investment_trust": 0, "dealer": 0},
    }}),
])
def test_snapshot_qa_accepts_valid_missing_and_zero_values(tmp_path, monkeypatch, case, mode, data):
    from playwright.sync_api import Page

    qa = load_qa_module()
    original_goto = Page.goto

    def isolated_goto(page, url, **kwargs):
        page.route("**/*", lambda route: route.fallback() if (
            route.request.url.startswith("file://")
            or route.request.url == "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
        ) else route.abort())
        return original_goto(page, url, **kwargs)

    monkeypatch.setattr(Page, "goto", isolated_goto)
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "qa"
    filename = f"2330_TW_{mode}_report_20260104_010000.html"
    (source / filename).write_text("<html>saved report</html>", encoding="utf-8")
    (source / filename.replace(".html", ".md")).write_text("# Saved report", encoding="utf-8")
    snapshot = {"ticker": "2330.TW", "pipeline": mode, "data": data, "parsed": {}, "analyses": {}}
    (source / data_snapshot_filename_for_report(filename)).write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["qa_report_charts.py", filename, "--source-dir", str(source), "--output-dir", str(output)])

    qa.main()

    results = json.loads((output / "results.json").read_text())
    assert len(results) == 2
    assert {row["width"] for row in results} == {375, 1280}
    assert all(not row["errors"] for row in results)
    if case == "empty":
        assert all(row["tooltip"] == "not_applicable" for row in results)
        assert all(chart["state"] == "empty" for row in results for chart in row["charts"])
    elif case == "later_dataset":
        assert all(row["tooltip"] is True for row in results)
        assert all(next(chart for chart in row["charts"] if chart["id"] == "revenueChart")["state"] == "ready" for row in results)
    else:
        for row in results:
            flows = [chart for chart in row["charts"] if chart["id"].startswith("institutional")]
            assert len(flows) == 2
            assert all(chart["state"] == "ready" and chart["zeroBars"] for chart in flows)
            assert all(chart["coloredPlotPixels"] == 0 and chart["plotPixels"] > 20 for chart in flows)
