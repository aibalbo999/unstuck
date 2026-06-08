from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "backend" / "templates"


def test_report_chart_template_is_modularized():
    entry = (TEMPLATE_DIR / "includes" / "report_charts.html.j2").read_text(encoding="utf-8")
    for include_name in [
        "includes/charts/setup.html.j2",
        "includes/charts/financial.html.j2",
        "includes/charts/moat.html.j2",
        "includes/charts/valuation.html.j2",
        "includes/charts/navigation.html.j2",
    ]:
        assert include_name in entry


def test_chart_modules_keep_expected_canvas_bindings():
    expected = {
        "financial.html.j2": ["revenueChart", "marginChart", "fcfChart", "roeChart"],
        "moat.html.j2": ["moatChart", "moat-scores-list", "moat-overall-score"],
        "valuation.html.j2": ["valuationChart", "peRiverChart"],
        "navigation.html.j2": ["scrollIntoView", "targetForItem", "sections[index]", "history.pushState"],
    }
    for filename, tokens in expected.items():
        text = (TEMPLATE_DIR / "includes" / "charts" / filename).read_text(encoding="utf-8")
        for token in tokens:
            assert token in text
