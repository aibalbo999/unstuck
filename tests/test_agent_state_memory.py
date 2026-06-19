import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agent_state import AgentReport, ProviderValue, RiskFlag, Severity
from state_memory import initialize_agent_state, merge_agent_report, sync_context_from_state, state_view_for


def test_initialize_agent_state_preserves_raw_data_and_identity():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "company_identity": {"stock_id": "2308", "official_name": "台達電子工業股份有限公司"},
        "revenue_history": [100, 120],
    }

    state = initialize_agent_state(data, run_id="run-1")

    assert state.run_id == "run-1"
    assert state.ticker == "2308.TW"
    assert state.company_name == "台達電"
    assert state.company_identity["stock_id"] == "2308"
    assert state.raw_financial_data["input"]["revenue_history"] == [100, 120]


def test_initialize_agent_state_deep_copies_derived_containers():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "company_identity": {"nested": {"stock_id": "2308"}},
        "source_audit": [{"provider": "mops", "meta": {"ok": True}}],
        "dynamic_peer_metrics": [{"ticker": "2357.TW", "scores": {"business_overlap": 0.7}}],
        "deterministic_financial_tool_results": {"calculations": {"base": {"price": 100}}},
    }

    state = initialize_agent_state(data, run_id="run-copy")
    data["company_identity"]["nested"]["stock_id"] = "mutated"
    data["source_audit"][0]["meta"]["ok"] = False
    data["dynamic_peer_metrics"][0]["scores"]["business_overlap"] = 0.1
    data["deterministic_financial_tool_results"]["calculations"]["base"]["price"] = 1

    assert state.company_identity["nested"]["stock_id"] == "2308"
    assert state.source_audit[0]["meta"]["ok"] is True
    assert state.peer_context["dynamic_peer_metrics"][0]["scores"]["business_overlap"] == 0.7
    assert state.quant_metrics["calculations"]["base"]["price"] == 100


def test_merge_agent_report_updates_reports_risk_flags_and_legacy_context():
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="run-2")
    flag = RiskFlag(
        id="accounting:fcf_conversion",
        severity=Severity.high,
        category="accounting",
        title="FCF conversion deteriorated",
        evidence_refs=["normalized_financials.cash_flow.free_cash_flow"],
        source_agents=["forensic_accounting"],
        impact="Lower confidence in DCF base case.",
        confidence=0.82,
    )
    report = AgentReport(
        agent_id="forensic_accounting",
        role="財務排雷專家",
        markdown="## 財務排雷\nFCF 轉換率惡化。",
        extracted_facts={"fcf_quality": "weak"},
        risk_flags=[flag],
    )

    state = merge_agent_report(state, report)
    context = {"analyses": {}, "structured_outputs": {}}
    sync_context_from_state(context, state)

    assert state.agent_reports["forensic_accounting"].extracted_facts["fcf_quality"] == "weak"
    assert state.risk_flags[0].id == "accounting:fcf_conversion"
    assert context["analyses"]["forensic_accounting"].startswith("## 財務排雷")
    assert context["agent_state"].ticker == "2330.TW"


def test_sync_context_from_state_normalizes_numeric_agent_ids_for_legacy_context():
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="run-legacy")
    report = AgentReport(
        agent_id="4",
        role="估值分析師",
        markdown="## 估值\nBase case.",
        structured_output={"price_targets": {"基本情境": 100}},
    )

    state = merge_agent_report(state, report)
    context = {"analyses": {}, "structured_outputs": {}}
    sync_context_from_state(context, state)

    assert context["analyses"][4] == "## 估值\nBase case."
    assert context["structured_outputs"][4]["price_targets"]["基本情境"] == 100
    assert "4" not in context["analyses"]
    assert "4" not in context["structured_outputs"]


def test_merge_agent_report_replaces_stale_risk_flags_on_retry():
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="run-retry")
    stale_flag = RiskFlag(
        id="valuation:stale",
        severity=Severity.high,
        category="valuation",
        title="Stale valuation concern",
        source_agents=["4"],
        impact="Old retry output should not survive.",
        confidence=0.9,
    )
    replacement_flag = RiskFlag(
        id="valuation:replacement",
        severity=Severity.warning,
        category="valuation",
        title="Replacement valuation concern",
        source_agents=["4"],
        impact="Latest retry output should be active.",
        confidence=0.7,
    )

    state = merge_agent_report(
        state,
        AgentReport(agent_id="4", role="估值分析師", markdown="old", risk_flags=[stale_flag]),
    )
    state = merge_agent_report(
        state,
        AgentReport(agent_id="4", role="估值分析師", markdown="new", risk_flags=[replacement_flag]),
    )

    assert state.agent_reports["4"].markdown == "new"
    assert [flag.id for flag in state.risk_flags] == ["valuation:replacement"]


def test_state_view_for_valuation_uses_whitelisted_paths_only():
    state = initialize_agent_state({"ticker": "2317.TW", "company_name": "鴻海"}, run_id="run-3")
    state.normalized_financials = {"revenue_history": [100, 110], "secret_debug": "do-not-include"}
    state.quant_metrics = {"calculations": {"dcf_scenarios_default": {"base": {"price_per_share_twd": 100}}}}
    state.peer_context = {"selected_peers": [{"ticker": "4938.TW", "score": 0.74}]}

    view = state_view_for("valuation", state)

    assert view["normalized_financials"]["revenue_history"] == [100, 110]
    assert "secret_debug" not in view["normalized_financials"]
    assert view["peer_context"]["selected_peers"][0]["ticker"] == "4938.TW"


def test_state_view_for_valuation_returns_json_safe_whitelisted_sections():
    state = initialize_agent_state({"ticker": "2317.TW", "company_name": "鴻海"}, run_id="run-json")
    state.quant_metrics = {
        "calculations": {
            "provider_value": ProviderValue(
                provider="mops",
                field="revenue",
                value=100.0,
                fetched_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
            )
        }
    }

    view = state_view_for("valuation", state)

    assert view["quant_metrics"]["calculations"]["provider_value"]["fetched_at"] == "2026-06-19T12:00:00Z"
    json.dumps(view)
