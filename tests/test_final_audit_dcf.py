"""DCF comparisons follow method, unit and scenario identity."""

import pytest

from final_audit_dcf import dcf_conflict_warnings, dcf_audit_findings
from quant_engine import QuantEngine


def canonical_quant():
    return QuantEngine.compute_all({
        "current_price": 100, "shares_raw": 100_000_000,
        "market_cap_raw": 10_000_000_000, "total_debt_raw": 0,
        "total_cash_raw": 0, "free_cash_flow_raw": 1_000_000_000,
    })


def test_relative_targets_are_not_dcf_scenarios():
    quant = canonical_quant()
    structured = {4: {"valuation_summary": {"primary_method": "relative_valuation"},
        "price_targets": {"bear": 2000, "base": 3000, "bull": 4000},
        "dcf_scenarios": list(reversed(list(quant["dcf_scenarios"].values())))}}
    analyses = {4: "熊市目標 NT$2000，基本 NT$3000，牛市 NT$4000；DCF 不作主要定價。"}
    assert dcf_conflict_warnings(analyses, {"quant_metrics": quant}, structured) == []


def test_same_scenario_mismatch_retains_thirty_percent_tolerance():
    quant = canonical_quant()
    rows = [dict(row) for row in reversed(list(quant["dcf_scenarios"].values()))]
    rows[0]["intrinsic_value"] *= 2
    warnings = dcf_conflict_warnings({4: "DCF 情境已列出。"}, {"quant_metrics": quant}, {4: {"dcf_scenarios": rows}})
    assert len(warnings) == 1
    assert "牛市情境" in warnings[0]
    assert "DCF 來源衝突" in warnings[0]


def test_unavailable_system_dcf_claim_is_critical():
    from final_audit_dcf import dcf_audit_findings

    quant = QuantEngine.compute_all({"free_cash_flow_raw": -1})
    structured = {4: {"dcf_scenarios": [{"scenario": "base", "intrinsic_value": 150, "method": "fcf_dcf", "unit": "twd_per_share"}]}}
    findings = dcf_audit_findings({4: "系統 DCF 基準為 NT$150。"}, {"quant_metrics": quant}, structured)
    assert findings[0]["severity"] == "critical"
    assert findings[0]["code"] == "dcf_unavailable_claim"
    assert findings[0]["agent"] == 4


def test_normalized_label_alone_does_not_create_canonical_evidence():
    from final_audit_dcf import dcf_audit_findings

    quant = canonical_quant()
    structured = {4: {"valuation_summary": {"primary_method": "normalized_dcf", "uses_normalized_fcf": True},
        "dcf_scenarios": [{"scenario": "base", "intrinsic_value": 150, "method": "normalized_dcf", "unit": "twd_per_share"}]}}
    findings = dcf_audit_findings({4: "正規化 DCF 基準為 NT$150。"}, {"quant_metrics": quant}, structured)
    assert findings[0]["severity"] == "critical"
    assert findings[0]["code"] == "dcf_unverified_method"


def test_legacy_numeric_snapshot_is_not_compared_as_canonical():
    data = {"quant_metrics": {"dcf_intrinsic_value": 100, "fallback_fields": ["free_cash_flows"]}}
    assert dcf_conflict_warnings({4: "相對估值目標 NT$300，DCF 不可用。"}, data) == []


def test_wrong_unit_is_unverified_instead_of_compared_to_per_share():
    from final_audit_dcf import dcf_audit_findings

    structured = {14: {"dcf_scenarios": [{"scenario": "base", "intrinsic_value": 15, "method": "fcf_dcf", "unit": "billion_twd"}]}}
    findings = dcf_audit_findings({14: "DCF 估值"}, {"quant_metrics": canonical_quant()}, structured, valuation_agent=14)
    assert findings[0]["severity"] == "critical"
    assert findings[0]["agent"] == 14
    assert findings[0]["code"] == "dcf_unverified_method"


def test_method_unit_and_source_survive_formal_normalization():
    from structured_output_normalizer import normalize_structured_output

    row = {"scenario": "base", "intrinsic_value": 150, "wacc_pct": 10,
           "revenue_growth_bias_pct": 0, "margin_bias_pct": 0,
           "method": "normalized_dcf", "unit": "billion_twd", "source_ref": "quant_metrics.dcf_scenarios.base"}
    normalized = normalize_structured_output(4, {"price_targets": {"熊市情境": 100, "基本情境": 150, "牛市情境": 200},
        "valuation_summary": {"primary_method": "normalized_dcf", "uses_market_value_wacc": True,
                              "uses_normalized_fcf": True, "double_counting_check": "獨立檢查"},
        "dcf_scenarios": [row], "analysis_markdown": "DCF 估值測試"})
    output = normalized["dcf_scenarios"][0]
    assert output["method"] == "normalized_dcf"
    assert output["unit"] == "billion_twd"
    assert output["source_ref"] == "quant_metrics.dcf_scenarios.base"
    from final_audit_dcf import dcf_audit_findings
    findings = dcf_audit_findings({4: normalized["analysis_markdown"]}, {"quant_metrics": canonical_quant()}, {4: normalized})
    assert findings[0]["code"] == "dcf_unverified_method"


def test_fabricated_or_cross_scenario_source_ref_is_critical():
    from final_audit_dcf import dcf_audit_findings
    quant = canonical_quant()
    row = {**quant["dcf_scenarios"]["base"], "source_ref": "quant_metrics.dcf_scenarios.bull"}
    findings = dcf_audit_findings({4: "DCF 情境"}, {"quant_metrics": quant}, {4: {"dcf_scenarios": [row]}})
    assert findings[0]["code"] == "dcf_unverified_method"


def test_normalized_claim_requires_recorded_inputs_and_tool_source():
    from final_audit_dcf import dcf_audit_findings
    quant = QuantEngine.compute_all({"market_cap_raw": 1e10, "total_debt_raw": 0,
        "total_cash_raw": 0, "shares_raw": 1e8, "free_cash_flow_raw": 4e9,
        "revenue_history": [1, 2], "net_income_history": [1, 2], "fcf_history": [1, 4]})
    row = {**quant["dcf_scenarios"]["base"], "method": "normalized_dcf", "source_ref": "quant_metrics.dcf_scenarios.base"}
    assert dcf_audit_findings({4: "工具正規化 DCF 情境"}, {"quant_metrics": quant}, {4: {"dcf_scenarios": [row]}}) == []


@pytest.mark.parametrize("text", ["系統 DCF 提供有效每股值 NT$150。", "系統 DCF 基準為150元。"])
def test_unavailable_system_dcf_claim_does_not_require_a_named_scenario(text):
    from quant_engine import QuantEngine
    quant = QuantEngine.compute_all({"free_cash_flow_raw": -1})
    findings = dcf_audit_findings({4: text}, {"quant_metrics": quant}, {4: {"dcf_scenarios": []}})
    assert any(item["severity"] == "critical" for item in findings)


@pytest.mark.parametrize("prefix", ["系統 ", ""])
def test_correct_structured_row_does_not_exempt_conflicting_system_dcf_prose(prefix):
    quant = canonical_quant()
    findings = dcf_audit_findings({4: f"{prefix}DCF 牛市每股值 NT$999999。"}, {"quant_metrics": quant},
                                 {4: {"dcf_scenarios": [quant["dcf_scenarios"]["base"]]}})
    assert any(item["code"] == "dcf_source_mismatch" and item["scenario"] == "bull" for item in findings)


def test_dcf_mentioned_before_relative_target_does_not_change_its_method():
    quant = canonical_quant()
    text = "DCF 與相對估值交叉討論，牛市相對目標 NT$999999。"
    findings = dcf_audit_findings({4: text}, {"quant_metrics": quant}, {4: {"dcf_scenarios": []}})
    assert findings == []
