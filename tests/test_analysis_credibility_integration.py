"""Cross-layer credibility findings must reach the correct bounded repair policy."""

from final_audit import run_final_report_audit
from market_context_manifest import build_market_context_manifest, build_source_blocks


def _context():
    recommendation = {"建議": "持有", "短期目標（3個月）": "100 元", "中期目標（6個月）": "110 元",
                      "長期目標（12個月）": "120 元", "信心指數": "5/10"}
    return {"pipeline_id": "v1", "agent_sequence": (4, 7),
            "data": {"ticker": "1623.TW", "company_name": "大東電", "current_price": 100},
            "analyses": {4: "相對估值。", 7: "持有，維持目標價與結論。"},
            "structured_outputs": {4: {"primary_method": "relative_valuation"}, 7: {"recommendation": recommendation}},
            "parsed": {"recommendation": recommendation,
                       "moat_scores": {key: 5 for key in ("品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河")},
                       "price_targets": {"熊市情境": 80, "基本情境": 100, "牛市情境": 120}}}


def _with_market(context):
    context["market_context_contract_version"] = "market_context.v1"
    context["data"]["international_news_context"] = {"topics": [{"headline": "利率決策", "summary": "央行維持利率。"}]}
    blocks = build_source_blocks(context["data"], agent_num=7)
    prompt = "\n".join(block["text"] for block in blocks)
    context["market_context_manifests"] = {7: build_market_context_manifest(context["data"], prompt, blocks, agent_num=7)}
    return context


def test_visible_market_coverage_reaches_optional_not_critical_repair():
    audit = run_final_report_audit(_with_market(_context()), append_section=False)
    assert audit.get("coverage_repair_agent_issues", {}).get(7)
    assert audit["market_context"]["status"] == "warning"
    assert audit["critical"] == []


def test_fabricated_market_reference_reaches_blocking_agent_repair():
    context = _with_market(_context())
    context["structured_outputs"][7]["market_context_assessment"] = {
        "international_news_context": {"impact": "no_material_impact", "reason": "維持估值假設。", "source_refs": ["model-invented-ref"]}}
    audit = run_final_report_audit(context, append_section=False)
    assert any("來源引用" in issue for issue in audit["critical"])
    assert any("來源引用" in issue for issue in audit["repair_agent_issues"][7])


def test_unavailable_canonical_dcf_claim_is_not_only_a_warning():
    context = _context()
    context["data"]["quant_metrics"] = {"contract_version": "quant_metrics.v2",
        "metric_status": {"dcf": {"status": "unavailable", "reason_codes": ["fcf_nonpositive"]}}}
    context["structured_outputs"][4] = {"primary_method": "normalized_dcf", "dcf_scenarios": [
        {"scenario": "base", "intrinsic_value": 217.27, "wacc_pct": 8.5}]}
    audit = run_final_report_audit(context, append_section=False)
    assert any("DCF" in issue for issue in audit["critical"])
    assert any("DCF" in issue for issue in audit["repair_agent_issues"][4])


def test_legacy_context_does_not_invent_market_visibility():
    audit = run_final_report_audit(_context(), append_section=False)
    assert audit.get("coverage_repair_agent_issues") == {}
    assert audit["market_context"]["status"] == "not_recorded"


def test_typed_prompt_projection_rejects_stale_upstream_reports():
    from types import SimpleNamespace
    from analysis_dependencies import initialize_result_provenance, record_result_provenance
    from agent_runtime.state_prompt_projection import restrict_state_reports

    context = {"pipeline_id": "v1", "analyses": {4: "old valuation", 6: "old debate"}}
    initialize_result_provenance(context)
    context["analyses"][4] = "accepted corrected valuation"
    record_result_provenance(4, context)
    state = SimpleNamespace(agent_reports={key: SimpleNamespace(risk_flags=[]) for key in ("4", "6")})
    view = {"agent_reports": {"4": {"markdown": "new"}, "6": {"markdown": "stale"}}}
    projected = restrict_state_reports(view, state, 7, context)
    assert set(projected["agent_reports"]) == {"4"}


def test_role_specific_quant_view_keeps_availability_and_provenance():
    from quant_engine import QuantEngine
    from state_memory import initialize_agent_state, state_view_for

    data = {"ticker": "1623.TW", "current_price": 208, "shares_raw": 66000000,
            "market_cap_raw": 13728000000, "total_debt_raw": 2898000000,
            "total_cash_raw": 500000000, "free_cash_flow_raw": -461411616}
    data["quant_metrics"] = QuantEngine.compute_all(data)
    state = initialize_agent_state(data)
    for agent in (4, 7, 14, 16, 19):
        view = state_view_for(agent, state)["quant_metrics"]
        assert view.get("contract_version") == "quant_metrics.v2"
        assert view["metric_status"]["dcf"]["status"] == "unavailable"
        assert view["input_provenance"]["shares_raw"]["path"] == "data.shares_raw"


def test_prompt_requires_availability_before_using_dcf_as_floor():
    from prompt_builder import format_data_for_prompt

    text = format_data_for_prompt({"ticker": "1623.TW", "free_cash_flow_raw": -461411616})
    assert "metric_status" in text and "不得作為下行保護底線" in text
    assert "twd_per_share" in text


def test_deterministic_relative_fallback_does_not_claim_dcf_or_wacc_calculation():
    from agent_runtime.deterministic_fallbacks import _deterministic_structured_fallback
    context = _context()
    accepted, _ = _deterministic_structured_fallback(4, context["data"], context, "")
    assert accepted
    summary = context["structured_outputs"][4]["valuation_summary"]
    assert summary["uses_market_value_wacc"] is False
    assert summary["uses_normalized_fcf"] is False


def test_new_market_contract_survives_graph_roundtrip_without_upgrading_legacy():
    from types import SimpleNamespace
    from workflow_services import initialize_graph_state
    from workflow_context import legacy_context_from_graph, graph_delta_from_legacy_context

    services = SimpleNamespace(progress_callback=None, cancel_check=None)
    for pipeline in ("v1", "v2", "v3"):
        state = initialize_graph_state({"ticker": "1623.TW"}, pipeline_id=pipeline)
        assert state.get("market_context_contract_version") == "market_context.v1"
        state["market_context_manifests"] = {"7": {"sentinel": "saved-attempt"}}
        context = legacy_context_from_graph(state, services)
        assert context["market_context_manifests"][7] == {"sentinel": "saved-attempt"}
        restored = graph_delta_from_legacy_context(context)
        assert restored["market_context_contract_version"] == "market_context.v1"
        assert restored["market_context_manifests"]["7"] == {"sentinel": "saved-attempt"}
    assert not initialize_graph_state({"ticker": "1623.TW"}, pipeline_id="v4").get("market_context_contract_version")
    legacy_state = initialize_graph_state({"ticker": "1623.TW"}, pipeline_id="v1")
    legacy_state.pop("market_context_contract_version")
    legacy_state.pop("market_context_manifests")
    legacy = legacy_context_from_graph(legacy_state, services)
    assert not legacy.get("market_context_contract_version")
