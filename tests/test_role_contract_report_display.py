"""Mode summaries expose new role-contract data without HTML or type leakage."""
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
import json

from reporting.decision_context import build_decision_context
from reporting.markdown_decision_context import build_markdown_decision_section
from reporting.mode_focus_context import build_mode_focus_context
from reporting.mode_templates import get_report_template_profile
from test_trade_catalyst_semantics import separated_case
from trade_financial_risk import NEGATIVE_FCF_WARNING


def test_d_main_summaries_preserve_typed_fields_and_display_financial_warning():
    setup, _ = separated_case()
    setup["financial_risk_flags"] = [NEGATIVE_FCF_WARNING]
    parsed = {"trade_setup": setup}
    context = build_decision_context(parsed, pipeline_id="v4")
    assert context["trade_setup"]["event_catalyst"] is None
    assert context["trade_setup"]["observed_source_refs"] == setup["observed_source_refs"]
    rendered = build_markdown_decision_section(parsed, pipeline_id="v4", mode_template=get_report_template_profile("v4"))
    rows = build_mode_focus_context({}, parsed, pipeline_id="v4")["rows"]
    assert NEGATIVE_FCF_WARNING in rendered
    assert any(row["label"] == "財務風險" and NEGATIVE_FCF_WARNING in row["value"] for row in rows)
    assert "事件日期未確認" in rendered


def test_d_dashboard_shows_separate_fields_and_escapes_html():
    setup, _ = separated_case()
    setup["observed_signal"] = '<script>alert(1)</script>可信觀測'
    setup["financial_risk_flags"] = [NEGATIVE_FCF_WARNING]
    context = build_decision_context({"trade_setup": setup}, pipeline_id="v4")
    env = Environment(loader=FileSystemLoader(Path(__file__).parents[1] / "backend/templates"), autoescape=select_autoescape(default=True))
    html = env.get_template("includes/charts/setup.html.j2").render(**context)
    assert "財務風險" in html and NEGATIVE_FCF_WARNING in html
    assert "可信觀測" in html and "<script>" not in html


def test_b_summary_preserves_research_basis_and_does_not_imply_zero_actual_holdings():
    parsed = {"position_plan": {"action": "等待", "position_size": "0%", "planning_context": "unassessed", "sizing_evidence": None}}
    context = build_decision_context(parsed, pipeline_id="v2")
    assert context["position_plan"]["planning_context"] == "unassessed"
    assert context["position_plan"]["sizing_evidence"] is None
    text = build_markdown_decision_section(parsed, pipeline_id="v2", mode_template=get_report_template_profile("v2"))
    assert "不代表使用者實際持倉為零" in text
    assert "未評估" in text


def test_runtime_to_parsed_report_preserves_all_distinct_catalyst_fields():
    from structured_output_runtime import process_agent_response
    from structured_output_parser import parse_structured_data
    setup, context = separated_case()
    context["pipeline_id"] = "v4"
    process_agent_response(24, json.dumps(setup), context)
    parsed = parse_structured_data(context)
    for field in ("observed_signal", "observed_source_refs", "event_catalyst", "recheck_condition", "financial_risk_flags"):
        assert parsed["trade_setup"][field] == context["structured_outputs"][24][field]
    rendered = build_markdown_decision_section(parsed, pipeline_id="v4", mode_template=get_report_template_profile("v4"))
    assert NEGATIVE_FCF_WARNING in rendered and setup["observed_signal"] in rendered
