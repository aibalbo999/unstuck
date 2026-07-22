"""Split report rendering helper."""

from __future__ import annotations

from datetime import datetime

from analysis_types import AnalysisContext
from company_display import company_display_name
from config import format_model_routes
from investment_thesis import build_investment_thesis, investment_thesis_markdown
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from pipeline_modes import get_pipeline_definition

from .audit_trust import build_audit_banner_html, build_data_trust_html, build_source_audit_html
from .analysis_overlays import (
    build_dcf_scenario_rows,
    build_downside_view,
    build_management_sentiment,
    build_peer_comparison_rows,
)
from .common import build_agent_model_labels, render_report_template
from .evidence_matrix import build_evidence_matrix_payload
from .execution_summary import build_execution_summary_html
from .html_chart_context import build_html_chart_context
from .html_decision_context import build_decision_context
from .html_context import collect_next_catalysts, display_text, format_time_str
from .html_sanitizer import sanitize_report_image_url, sanitize_report_plain_text
from .mode_templates import build_mode_template_html, get_report_template_profile
from .reading_notice import build_report_reading_notice_html
from .sections import build_agent_sections, build_tear_sheet_summary
from .utils import clean_markdown


async def generate_html_report_async(context: AnalysisContext) -> str:
    """Async HTML report renderer."""
    return generate_html_report(context)


def generate_html_report(context: AnalysisContext) -> str:
    """生成完整的 HTML 報告"""

    data = safe_mapping_dict(context.get("data", {})) or {}
    for text_key in ("ticker", "company_name", "sector", "industry", "fetch_date",
                     "current_price_fmt", "market_cap_fmt"):
        if text_key in data:
            default = "" if text_key == "fetch_date" else "N/A"
            data[text_key] = sanitize_report_plain_text(display_text(data.get(text_key), default))
    analyses = context.get("analyses", {})
    parsed = safe_mapping_dict(context.get("parsed", {})) or {}

    ticker = sanitize_report_plain_text(display_text(context.get("ticker"), "N/A")) or "N/A"
    name = (
        sanitize_report_plain_text(
            display_text(company_display_name(data, context.get("company_name", ticker)), ticker)
        )
        or ticker
    )
    fetch_date = data.get("fetch_date") or datetime.now().strftime("%Y年%m月%d日")
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    mode_template = get_report_template_profile(pipeline_def["id"])
    report_title = pipeline_def["report_title"]
    report_subtitle = pipeline_def["report_subtitle"]
    pipeline_label = pipeline_def["label"]

    chart_context = build_html_chart_context(data, parsed)
    decision_context = build_decision_context(parsed, pipeline_id=pipeline_def["id"])

    audit_banner_html = build_audit_banner_html(context)
    report_reading_notice_html = build_report_reading_notice_html(context)
    data_trust_html = build_data_trust_html(data, context)
    model_route_summary = format_model_routes(pipeline_id=pipeline_def["id"])
    execution_summary_html = build_execution_summary_html(context, model_routes=model_route_summary)
    mode_template_html = build_mode_template_html(mode_template)
    source_audit_html = build_source_audit_html(data, context)
    audit_entries = safe_dict_list(data.get("source_audit"))
    report_ticker = display_text(data.get("ticker") or ticker, ticker)
    is_taiwan_ticker = report_ticker.split(".")[0].isdigit()
    twse_official_unavailable = is_taiwan_ticker and not any(
        safe_text(entry.get("source")).strip() == "twse_official"
        and safe_text(entry.get("status")).strip() == "success"
        for entry in audit_entries
    )
    tear_sheet_summary = clean_markdown(build_tear_sheet_summary(context))
    thesis_payload = safe_mapping_dict(context.get("investment_thesis"))
    if not thesis_payload:
        thesis_payload = build_investment_thesis(context)
    investment_thesis_html = clean_markdown(investment_thesis_markdown(thesis_payload))
    executive_thesis = sanitize_report_plain_text(display_text(context.get("executive_thesis"), ""))
    smoothed_markdown_html = clean_markdown(display_text(context.get("smoothed_markdown"), ""))
    report_cover = safe_mapping_dict(context.get("report_cover", {})) or {}
    report_cover_image = sanitize_report_image_url(report_cover.get("image", ""))

    agent_sections = build_agent_sections(context, html=True)
    dcf_scenario_rows = build_dcf_scenario_rows(data)
    management_sentiment = build_management_sentiment(context)
    downside_view = build_downside_view(context)
    peer_comparison_rows = build_peer_comparison_rows(data)

    evidence_payload = build_evidence_matrix_payload(context)
    next_catalysts = collect_next_catalysts(context)

    # 競爭對手比較表格中的值
    comp_pe = data.get("pe_ratio", "N/A")
    comp_pb = data.get("pb_ratio", "N/A")
    comp_ev_ebitda = data.get("ev_ebitda", "N/A")

    time_str = format_time_str(context.get("total_time", 0))
    agent_model_labels = build_agent_model_labels()
    template_context = {**locals(), **chart_context, **decision_context}
    return render_report_template("report.html.j2", template_context)
