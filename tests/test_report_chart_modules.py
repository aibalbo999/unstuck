from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "backend" / "templates"


def test_report_chart_template_is_modularized():
    entry = (TEMPLATE_DIR / "includes" / "report_charts.html.j2").read_text(encoding="utf-8")
    for include_name in [
        "includes/charts/runtime.html.j2",
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
        "navigation.html.j2": ["scrollIntoView", "targetForItem", "document.getElementById(id)", "history.pushState"],
    }
    for filename, tokens in expected.items():
        text = (TEMPLATE_DIR / "includes" / "charts" / filename).read_text(encoding="utf-8")
        for token in tokens:
            assert token in text


def test_moat_score_rows_use_dom_nodes_instead_of_html_string_concatenation():
    text = (TEMPLATE_DIR / "includes" / "charts" / "moat.html.j2").read_text(
        encoding="utf-8"
    )

    assert "moatList.innerHTML +=" not in text
    assert "document.createElement('div')" in text
    assert ".textContent = label" in text
    assert ".textContent = String(val)" in text
    assert 'style="' not in text


def test_moat_chart_uses_string_safe_labels_and_explicit_overall_score():
    text = (TEMPLATE_DIR / "includes" / "charts" / "moat.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function moatLabelText(value)" in text
    assert "return value === null || value === undefined ? '' : String(value);" in text
    assert "function isOverallMoatLabel(label)" in text
    assert "return moatLabelText(label).includes('整體');" in text
    assert "const moatLabels = CHART_DATA.moatLabels.map(moatLabelText);" in text
    assert ".filter(l => !l.includes('整體'))" not in text
    assert "CHART_DATA.moatLabels[i].includes('整體')" not in text
    assert "function moatOverallValue(labels, values, filteredValues)" in text
    assert "if (Number.isFinite(explicitOverall)) return explicitOverall;" in text
    assert "if (!numericValues.length) return null;" in text
    assert "overallEl.textContent = overall === null ? 'N/A' : String(overall);" in text


def test_financial_charts_format_missing_values_without_positive_color_bias():
    text = (TEMPLATE_DIR / "includes" / "charts" / "financial.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function finiteChartValue(value)" in text
    assert "return Number.isFinite(value) ? value : null;" in text
    assert "function moneyYiLabel(value)" in text
    assert "return number === null ? 'N/A' : `NT$${number}億`;" in text
    assert "function percentLabel(value)" in text
    assert "return number === null ? 'N/A' : `${number}%`;" in text
    assert "function fcfBarColor(value)" in text
    assert "if (number === null) return 'rgba(148,163,184,0.45)';" in text
    assert "const fcfColors = (CHART_DATA.fcf || []).map(fcfBarColor);" in text
    assert "ctx => `${ctx.dataset.label}: ${moneyYiLabel(ctx.raw)}`" in text
    assert "ctx => `${ctx.dataset.label}: ${percentLabel(ctx.raw)}`" in text
    assert "ctx => `自由現金流: ${moneyYiLabel(ctx.raw)}`" in text
    assert "ctx => `ROE: ${percentLabel(ctx.raw)}`" in text
    assert "ctx.raw}億" not in text
    assert "ctx.raw}%" not in text
    assert "v >= 0 ? 'rgba(16,185,129,0.7)'" not in text


def test_chart_runtime_uses_json_script_as_single_chart_payload_source():
    text = (TEMPLATE_DIR / "includes" / "charts" / "runtime.html.j2").read_text(
        encoding="utf-8"
    )

    assert "{{ chart_data|tojson }}" not in text
    assert "document.getElementById('report-chart-data')" in text
    assert "const CHART_DATA = readChartPayload();" in text
    assert "Object.assign(CHART_DATA" not in text


def test_chart_runtime_falls_back_to_empty_payload_shape_when_json_is_unavailable():
    text = (TEMPLATE_DIR / "includes" / "charts" / "runtime.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function defaultChartData()" in text
    assert "function readChartPayload()" in text
    assert "if (!chartPayload) return defaultChartData();" in text
    assert "catch (_) {" in text
    assert "return defaultChartData();" in text
    for token in [
        "years: []",
        "revenue: []",
        "netIncome: []",
        "grossMargin: []",
        "opMargin: []",
        "netMargin: []",
        "fcf: []",
        "roe: []",
        "moatLabels: []",
        "moatValues: []",
        "priceTargets: {}",
        "currentPrice: null",
        "peRiver: null",
    ]:
        assert token in text


def test_chart_runtime_normalizes_invalid_payload_field_types_before_chart_modules_run():
    text = (TEMPLATE_DIR / "includes" / "charts" / "runtime.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function chartArray(value)" in text
    assert "return Array.isArray(value) ? value : [];" in text
    assert "function chartObject(value)" in text
    assert "return value && typeof value === 'object' && !Array.isArray(value) ? value : {};" in text
    for key in [
        "years",
        "moatLabels",
    ]:
        assert f"{key}: chartArray(parsed.{key})" in text
    assert "priceTargets: normalizePriceTargets(parsed.priceTargets)" in text


def test_chart_runtime_normalizes_pe_river_nested_payload_fields_before_render():
    text = (TEMPLATE_DIR / "includes" / "charts" / "runtime.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function normalizePeRiverBands(value)" in text
    assert "const bands = chartObject(value);" in text
    assert "normalized[label] = chartNumberSeries(bands[label]);" in text
    assert "function normalizePeRiver(value)" in text
    assert "const peRiver = chartObject(value);" in text
    assert "years: chartArray(peRiver.years)" in text
    assert "bands: normalizePeRiverBands(peRiver.bands)" in text
    assert "eps: chartNumberSeries(peRiver.eps)" in text
    assert "peRiver: normalizePeRiver(parsed.peRiver)" in text


def test_chart_runtime_normalizes_price_target_values_before_tooltips_use_to_fixed():
    text = (TEMPLATE_DIR / "includes" / "charts" / "runtime.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function finiteChartNumber(value)" in text
    assert "const number = Number(value);" in text
    assert "return Number.isFinite(number) ? number : null;" in text
    assert "function normalizePriceTargets(value)" in text
    assert "const targets = chartObject(value);" in text
    assert "const price = finiteChartNumber(targets[label]);" in text
    assert "if (price !== null) normalized[label] = price;" in text
    assert "priceTargets: normalizePriceTargets(parsed.priceTargets)" in text
    assert "currentPrice: finiteChartNumber(parsed.currentPrice)" in text


def test_valuation_charts_use_chart_payload_current_price_without_inline_literal():
    text = (TEMPLATE_DIR / "includes" / "charts" / "valuation.html.j2").read_text(
        encoding="utf-8"
    )

    assert "{{ current_price_numeric }}" not in text
    assert text.count("const currentPrice = CHART_DATA.currentPrice;") == 2
    assert "CHART_DATA.currentPrice || 0" not in text


def test_valuation_charts_format_missing_price_tooltips_as_na():
    text = (TEMPLATE_DIR / "includes" / "charts" / "valuation.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function finitePriceValue(value)" in text
    assert "return Number.isFinite(value) ? value : null;" in text
    assert "function ntPriceLabel(value)" in text
    assert "return number === null ? 'N/A' : `NT$${number.toFixed(0)}`;" in text
    assert "label: ctx => ntPriceLabel(ctx.raw)" in text
    assert "label: ctx => `${ctx.dataset.label}: ${ntPriceLabel(ctx.raw)}`" in text
    assert "ctx.raw.toFixed(0)" not in text
    assert "Number(ctx.raw || 0).toFixed(0)" not in text


def test_valuation_chart_filters_missing_price_rows_before_rendering():
    text = (TEMPLATE_DIR / "includes" / "charts" / "valuation.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function valuationScenarioColor(label)" in text
    assert "function valuationRow(label, price, color)" in text
    assert "const number = finitePriceValue(price);" in text
    assert "return number === null ? null : { label, price: number, color };" in text
    assert "const valuationRows = [" in text
    assert "valuationRow('當前股價', currentPrice, 'rgba(245,158,11,0.7)')" in text
    assert "...scenarios.map(s => valuationRow(s, targets[s], valuationScenarioColor(s)))," in text
    assert "].filter(Boolean);" in text
    assert "labels: valuationRows.map(row => row.label)" in text
    assert "data: valuationRows.map(row => row.price)" in text
    assert "backgroundColor: valuationRows.map(row => row.color)" in text
    assert "borderColor: valuationRows.map(row => row.color.replace('0.7', '1'))" in text
    assert "const allLabels = ['當前股價', ...scenarios];" not in text
    assert "const allPrices = [currentPrice, ...prices];" not in text


def test_pe_river_chart_filters_empty_band_datasets_before_rendering():
    text = (TEMPLATE_DIR / "includes" / "charts" / "valuation.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function hasFinitePriceSeries(values)" in text
    assert "return Array.isArray(values) && values.some(value => finitePriceValue(value) !== null);" in text
    assert "const bandDatasets = Object.keys(bands).map((label, idx) => ({" in text
    assert "data: bands[label]," in text
    assert "})).filter(dataset => hasFinitePriceSeries(dataset.data));" in text


def test_pe_river_chart_requires_valid_band_before_current_price_line():
    text = (TEMPLATE_DIR / "includes" / "charts" / "valuation.html.j2").read_text(
        encoding="utf-8"
    )

    assert "const hasRiverBandDatasets = bandDatasets.length > 0;" in text
    assert "if (hasRiverBandDatasets && currentPrice > 0) {" in text
    assert "if (hasRiverBandDatasets) {" in text
    assert "if (currentPrice > 0) {" not in text
    assert "if (bandDatasets.length > 0) {" not in text


def test_chart_runtime_treats_blank_null_and_boolean_target_values_as_missing():
    text = (TEMPLATE_DIR / "includes" / "charts" / "runtime.html.j2").read_text(
        encoding="utf-8"
    )

    assert "if (value === null || value === undefined) return null;" in text
    assert "if (typeof value === 'boolean') return null;" in text
    assert "if (typeof value === 'string' && !value.trim()) return null;" in text
    assert "const number = Number(value);" in text


def test_chart_runtime_normalizes_numeric_dataset_series_values_before_chart_js():
    text = (TEMPLATE_DIR / "includes" / "charts" / "runtime.html.j2").read_text(
        encoding="utf-8"
    )

    assert "function chartNumberSeries(value)" in text
    assert "return chartArray(value).map(item => finiteChartNumber(item));" in text
    for key in [
        "revenue",
        "netIncome",
        "grossMargin",
        "opMargin",
        "netMargin",
        "fcf",
        "roe",
        "moatValues",
    ]:
        assert f"{key}: chartNumberSeries(parsed.{key})" in text
    assert "normalized[label] = chartNumberSeries(bands[label]);" in text
    assert "eps: chartNumberSeries(peRiver.eps)" in text
