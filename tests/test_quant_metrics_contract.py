"""Raw financial inputs cannot become placeholder valuations."""

import pytest

from financial_tools import build_financial_tool_context, calculate_dcf
from quant_engine import QuantEngine
from reporting.analysis_overlays import build_dcf_scenario_rows
from reporting.quant_warning import build_quant_warning_html, build_quant_warning_markdown


def raw_financials():
    return {
        "current_price": 208.0, "shares_raw": 66_000_000,
        "shares_outstanding": "NT$0.66億 (0.07B)",
        "market_cap_raw": 13_728_000_000, "total_debt_raw": 2_898_000_000,
        "total_cash_raw": 500_000_000, "free_cash_flow_raw": 461_411_616,
        "trailing_eps": 5.0,
    }


class BrokenQuantMappingAccess(dict):
    def get(self, *_args, **_kwargs):
        raise RuntimeError("custom get is unavailable")

    def __getitem__(self, _key):
        raise RuntimeError("custom item access is unavailable")

    def items(self):
        raise RuntimeError("custom items is unavailable")


def test_raw_facts_and_nested_wacc_sources_survive_broken_mapping_accessors():
    from quant_input_contract import read_quant_inputs, wacc_policy

    data = {**raw_financials(), "tax_rate": 0.25, "beta": 1.2,
            "revenue_history": [100, 120], "net_income_history": [5, 6], "fcf_history": [1, 2],
            "macro_indicators": {"indicators": {"us_10y_yield": {"value": 4.2, "series_id": "DGS10"}}}}
    expected = QuantEngine.compute_all(data)
    data["macro_indicators"] = BrokenQuantMappingAccess({"indicators": BrokenQuantMappingAccess({
        "us_10y_yield": BrokenQuantMappingAccess({"value": 4.2, "series_id": "DGS10"})})})
    broken = BrokenQuantMappingAccess(data)

    actual = QuantEngine.compute_all(broken)

    assert actual == expected
    facts, provenance, _reasons = read_quant_inputs(broken)
    assert facts["shares_raw"] == 66_000_000
    assert provenance["free_cash_flow_raw"]["value"] == 461_411_616
    assert wacc_policy(broken)["risk_free_rate_source"] == "FRED:DGS10"


def test_nested_readonly_mapping_wacc_inputs_preserve_source_values():
    from types import MappingProxyType

    data = {**raw_financials(), "macro_indicators": MappingProxyType({"indicators": MappingProxyType({
        "us_10y_yield": MappingProxyType({"value": 4.2, "series_id": "DGS10"})})})}
    quant = QuantEngine.compute_all(data)
    assert quant["wacc_assumptions"]["risk_free_rate_pct"] == 4.2
    assert quant["wacc_assumptions"]["risk_free_rate_source"] == "FRED:DGS10"


def test_negative_raw_fcf_never_uses_sample_cash_flows():
    data = {**raw_financials(), "free_cash_flow_raw": -461_411_616, "fcf_history": [1, 2]}
    result = QuantEngine.compute_all(data)
    assert result["dcf_intrinsic_value"] is None
    assert result["margin_of_safety"] is None
    assert result["contract_version"] == "quant_metrics.v2"
    assert result["metric_status"]["dcf"]["status"] == "unavailable"
    assert "free_cash_flow_raw_non_positive" in result["metric_status"]["dcf"]["reason_codes"]
    assert result["metric_status"]["wacc"]["status"] == "available"
    assert result["implied_pe_ratio"] == 41.6


@pytest.mark.parametrize("field", ["shares_raw", "total_debt_raw", "total_cash_raw", "free_cash_flow_raw"])
@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), "NT$1億"])
def test_unusable_fact_never_falls_back_to_formatted_or_default_values(field, value):
    result = QuantEngine.compute_all({**raw_financials(), field: value})
    assert result["dcf_intrinsic_value"] is None
    assert result["margin_of_safety"] is None
    assert result["dcf_scenarios"] == {}
    assert result["metric_status"]["dcf"]["status"] == "unavailable"
    assert result["metric_status"]["implied_pe"]["status"] == "available"


@pytest.mark.parametrize("eps", [None, 0, -2, True, float("inf")])
def test_unavailable_pe_does_not_disable_valid_dcf(eps):
    result = QuantEngine.compute_all({**raw_financials(), "trailing_eps": eps})
    assert result["implied_pe_ratio"] is None
    assert result["metric_status"]["implied_pe"]["status"] == "unavailable"
    assert result["metric_status"]["dcf"]["status"] == "available"


@pytest.mark.parametrize("debt,cash", [(0, 0), (0, 500_000_000), (2_898_000_000, 500_000_000)])
def test_positive_dcf_uses_existing_math_and_exactly_once_units(debt, cash):
    data = {**raw_financials(), "total_debt_raw": debt, "total_cash_raw": cash}
    result = QuantEngine.compute_all(data)
    tool = build_financial_tool_context(data)
    base = result["dcf_scenarios"]["base"]
    expected = calculate_dcf(
        base_fcf_billion_twd=data["free_cash_flow_raw"] / 1e9,
        growth_rate_pct=base["growth_rate_pct"], wacc_pct=base["wacc_pct"],
        terminal_growth_pct=base["terminal_growth_pct"], shares_outstanding=data["shares_raw"],
        net_debt_billion_twd=(debt - cash) / 1e9,
    )
    assert result["dcf_intrinsic_value"] == expected["price_per_share_twd"]
    assert result["wacc_computed"] == pytest.approx(base["wacc_pct"] / 100)
    assert result["dcf_scenarios"] == tool["dcf_scenarios"]
    assert base["intrinsic_value"] == tool["calculations"]["dcf_scenarios_default"]["scenarios"]["base"]["price_per_share_twd"]
    assert result["input_provenance"]["shares_raw"]["path"] == "data.shares_raw"
    assert result["input_provenance"]["shares_raw"]["unit"] == "shares"
    assert result["unit_contract"]["price"] == "twd_per_share"
    assert result["assumptions"]["wacc"]["tax_rate_pct"] == 20.0


def test_unavailable_contract_blocks_numeric_fallback_in_report_and_warns():
    quant = QuantEngine.compute_all({**raw_financials(), "free_cash_flow_raw": -1})
    data = {"quant_metrics": quant, "deterministic_financial_tool_results": {
        "calculations": {"dcf_scenarios_default": {"scenarios": {"base": {"price_per_share_twd": 999}}}},
    }}
    assert build_dcf_scenario_rows(data) == []
    assert "DCF 不可用" in build_quant_warning_html(data)
    assert "DCF 不可用" in build_quant_warning_markdown(data)


def test_legacy_fact_fallback_is_not_a_trusted_dcf_projection():
    data = {"quant_metrics": {"fallback_fields": ["free_cash_flows"], "dcf_scenarios": {
        "base": {"intrinsic_value": 999},
    }}}
    assert build_dcf_scenario_rows(data) == []


def test_derived_margin_overflow_is_not_exposed_as_a_number():
    result = QuantEngine.compute_all({**raw_financials(), "current_price": 1e308,
                                     "free_cash_flow_raw": 1000000, "total_debt_raw": 0, "total_cash_raw": 0})
    assert result["dcf_intrinsic_value"] is not None
    assert result["margin_of_safety"] is None


def test_current_contract_warning_is_not_hidden_by_legacy_message():
    quant = QuantEngine.compute_all({**raw_financials(), "free_cash_flow_raw": -1})
    quant["data_quality_warning"] = "舊記錄：估值僅供參考。"
    assert "DCF 不可用" in build_quant_warning_html({"quant_metrics": quant})
    assert "DCF 不可用" in build_quant_warning_markdown({"quant_metrics": quant})


def test_extreme_growth_inputs_do_not_emit_infinite_assumptions():
    import json
    result = QuantEngine.compute_all({**raw_financials(), "revenue_history": [1e-300, 1e300]})
    assert result["assumptions"]["dcf"]["latest_revenue_growth_pct"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("field,value", [("market_cap_raw", 0), ("market_cap_raw", True),
    ("market_cap_raw", float("nan")), ("shares_raw", -1), ("total_cash_raw", -1), ("total_debt_raw", -1)])
def test_invalid_sign_and_market_cap_disable_only_dependent_metrics(field, value):
    result = QuantEngine.compute_all({**raw_financials(), field: value})
    assert result["dcf_intrinsic_value"] is None
    assert result["implied_pe_ratio"] == 41.6


def test_history_units_and_latest_negative_are_preserved():
    data = raw_financials()
    data.pop("free_cash_flow_raw")
    result = QuantEngine.compute_all({**data, "fcf_history": [1.0, -0.2]})
    assert result["dcf_intrinsic_value"] is None
    assert result["input_provenance"]["free_cash_flow_raw"] == {
        "path": "data.fcf_history[1]", "unit": "billion_twd", "value": -0.2}
    positive = QuantEngine.compute_all({**data, "fcf_history": [0.2, 0.5]})
    assert positive["dcf_scenarios"]["base"]["base_fcf_billion_twd"] == 0.5


def test_nonfinite_derived_pe_is_unavailable():
    result = QuantEngine.compute_all({**raw_financials(), "trailing_eps": 1e-308})
    assert result["implied_pe_ratio"] is None
    assert result["metric_status"]["implied_pe"]["status"] == "unavailable"


def test_normalization_keeps_existing_history_conversion_policy():
    data = {**raw_financials(), "free_cash_flow_raw": 10e9, "revenue_history": [1, 2], "net_income_history": [1, 2]}
    without_conversion = QuantEngine.compute_all(data)
    assert without_conversion["dcf_scenarios"]["base"]["base_fcf_billion_twd"] == 10
    with_conversion = QuantEngine.compute_all({**data, "fcf_history": [1, 4]})
    assert with_conversion["dcf_scenarios"]["base"]["base_fcf_billion_twd"] == 1.6
    assert with_conversion["input_provenance"]["normalization_fcf"]["path"] == "data.fcf_history[1]"


def test_contract_label_without_complete_provenance_is_not_trusted():
    from quant_metric_contract import trusted_dcf_scenarios
    quant = QuantEngine.compute_all(raw_financials())
    quant["input_provenance"].pop("shares_raw")
    assert trusted_dcf_scenarios(quant) == {}


def test_tool_only_unavailable_contract_cannot_revive_legacy_calculation():
    quant = QuantEngine.compute_all({**raw_financials(), "free_cash_flow_raw": -1})
    quant["calculations"]["dcf_scenarios_default"] = {"scenarios": {"base": {"price_per_share_twd": 999}}}
    assert build_dcf_scenario_rows({"deterministic_financial_tool_results": quant}) == []


def test_legacy_numeric_display_explicitly_discloses_unverified_contract():
    data = {"quant_metrics": {"dcf_intrinsic_value": 100, "dcf_scenarios": {"base": {"intrinsic_value": 100}}}}
    assert "未依目前契約驗證" in build_quant_warning_html(data)
