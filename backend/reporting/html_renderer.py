"""Split report rendering helper."""

from __future__ import annotations

from datetime import datetime
from html import escape
import math
import re

from analysis_types import AnalysisContext
from company_display import company_display_name
from config import format_model_routes
from investment_thesis import build_investment_thesis, investment_thesis_markdown
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from pipeline_modes import get_pipeline_definition
from recommendation_labels import normalize_recommendation_label

from .audit_trust import build_audit_banner_html, build_data_trust_html, build_source_audit_html
from .analysis_overlays import (
    build_dcf_scenario_rows,
    build_downside_view,
    build_management_sentiment,
    build_peer_comparison_rows,
)
from .chart_payload import chart_number, chart_number_series, chart_pe_river, chart_price_history, chart_text_series
from .common import build_agent_model_labels, render_report_template
from .evidence_matrix import build_evidence_matrix_payload
from .execution_summary import build_execution_summary_html
from .html_sanitizer import sanitize_report_image_url, sanitize_report_plain_text
from .mode_templates import build_mode_template_html, get_report_template_profile
from .reading_notice import build_report_reading_notice_html
from .sections import build_agent_sections, build_tear_sheet_summary
from .utils import (
    clean_markdown,
    get_recommendation_color,
    get_recommendation_icon,
    normalize_moat_scores,
)


def _structured_output_values(context: AnalysisContext) -> list[dict]:
    outputs = safe_mapping_dict(context.get("structured_outputs", {})) or {}
    values = []
    for value in outputs.values():
        output = safe_mapping_dict(value)
        if output is not None:
            values.append(output)
    return values


def _collect_next_catalysts(context: AnalysisContext) -> list[dict[str, str]]:
    catalysts: list[dict[str, str]] = []
    for source in [context, *_structured_output_values(context)]:
        source_map = safe_mapping_dict(source) or {}
        for item in safe_dict_list(source_map.get("next_catalysts")):
            trigger = sanitize_report_plain_text(item.get("trigger_condition"))
            event_name = sanitize_report_plain_text(item.get("event_name")) or "未命名催化事件"
            if not trigger:
                continue
            catalysts.append({
                "event_name": event_name,
                "expected_timeframe": sanitize_report_plain_text(item.get("expected_timeframe")) or "待確認",
                "impact_direction": sanitize_report_plain_text(item.get("impact_direction")) or "volatile",
                "trigger_condition": trigger,
            })
    unique = []
    seen = set()
    for item in catalysts:
        marker = (item["event_name"], item["trigger_condition"])
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(item)
    return unique[:5]


def _display_text(value, default: str = "N/A") -> str:
    text = safe_text(value).strip()
    return text or default


async def generate_html_report_async(context: AnalysisContext) -> str:
    """Async HTML report renderer."""
    return generate_html_report(context)


def generate_html_report(context: AnalysisContext) -> str:
    """生成完整的 HTML 報告"""
    
    data = safe_mapping_dict(context.get("data", {})) or {}
    for text_key in ("ticker", "company_name", "sector", "industry", "fetch_date", "current_price_fmt", "market_cap_fmt"):
        if text_key in data:
            data[text_key] = sanitize_report_plain_text(safe_text(data.get(text_key)))
    analyses = context.get("analyses", {})
    parsed = safe_mapping_dict(context.get("parsed", {})) or {}
    
    ticker = sanitize_report_plain_text(safe_text(context.get("ticker", "N/A"))) or "N/A"
    name = sanitize_report_plain_text(company_display_name(data, context.get("company_name", ticker))) or ticker
    fetch_date = data.get("fetch_date") or datetime.now().strftime("%Y年%m月%d日")
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    mode_template = get_report_template_profile(pipeline_def["id"])
    report_title = pipeline_def["report_title"]
    report_subtitle = pipeline_def["report_subtitle"]
    pipeline_label = pipeline_def["label"]
    
    # 準備圖表數據
    years = data.get("years", [])
    revenue_data = data.get("revenue_history", [])
    net_income_data = data.get("net_income_history", [])
    fcf_data = data.get("fcf_history", [])
    gross_margin_data = data.get("gross_margin_history", [])
    op_margin_data = data.get("op_margin_history", [])
    net_margin_data = data.get("net_margin_history", [])
    roe_data = data.get("roe_history", [])
    price_history = chart_price_history(data.get("price_history", {}))
    
    # 護城河評分
    moat_scores = normalize_moat_scores(safe_mapping_dict(parsed.get("moat_scores", {})) or {})
    moat_labels = list(moat_scores.keys())
    moat_values = list(moat_scores.values())
    overall_moat = moat_scores.get("整體護城河", 0)
    
    # 目標股價
    raw_price_targets = safe_mapping_dict(parsed.get("price_targets", {})) or {}
    price_targets = {
        sanitize_report_plain_text(safe_text(key)) or "情境": _price_target_number(value)
        for key, value in raw_price_targets.items()
    }
    recommendation = safe_mapping_dict(parsed.get("recommendation", {})) or {}
    pe_river = chart_pe_river(data.get("pe_river_chart", {}))
    pe_river_source = safe_text(pe_river.get("source", "")).strip()
    pe_river_title = (
        "P/E 河流圖（EPS × 預設本益比通道）"
        if "default" in pe_river_source.lower()
        else "P/E 河流圖（EPS × 歷史本益比通道）"
    )
    
    def get_rec_val(rec_dict, target_sub, default="N/A"):
        for k, v in (rec_dict or {}).items():
            if target_sub in safe_text(k):
                return v
        return default
        
    rec_text = normalize_recommendation_label(
        sanitize_report_plain_text(_display_text(get_rec_val(recommendation, "建議", "持有"), "持有")) or "持有"
    )

    rec_color = get_recommendation_color(rec_text)
    rec_icon = get_recommendation_icon(rec_text)
    
    target_3m = sanitize_report_plain_text(_display_text(get_rec_val(recommendation, "3個月", "N/A"))) or "N/A"
    target_6m = sanitize_report_plain_text(_display_text(get_rec_val(recommendation, "6個月", "N/A"))) or "N/A"
    target_12m = sanitize_report_plain_text(_display_text(get_rec_val(recommendation, "12個月", "N/A"))) or "N/A"
    confidence = sanitize_report_plain_text(_display_text(get_rec_val(recommendation, "信心", "N/A"))) or "N/A"
    raw_trade_setup = safe_mapping_dict(parsed.get("trade_setup", {})) or {}
    trade_setup = {
        key: sanitize_report_plain_text(safe_text(raw_trade_setup.get(key, "")))
        for key in (
            "trade_direction",
            "entry_zone",
            "target_price",
            "stop_loss",
            "core_catalyst",
            "risk_level",
        )
    } if isinstance(raw_trade_setup, dict) else {}
    trade_setup = {key: value for key, value in trade_setup.items() if value}

    trade_direction = trade_setup.get("trade_direction", "Neutral")
    trade_direction_label = {
        "Long": "偏多 Long",
        "Short": "偏空 Short",
        "Neutral": "中性 Neutral",
    }.get(trade_direction, "中性 Neutral")
    trade_direction_icon = {"Long": "↑", "Short": "↓", "Neutral": "→"}.get(trade_direction, "→")
    swing_entry_zone = trade_setup.get("entry_zone", "N/A")
    swing_target_price = trade_setup.get("target_price", "N/A")
    swing_stop_loss = trade_setup.get("stop_loss", "N/A")
    swing_risk_level = {
        "High": "高",
        "Medium": "中",
        "Low": "低",
    }.get(trade_setup.get("risk_level", "High"), "高")
    if pipeline_def["id"] == "v4" and trade_setup:
        rec_color = {"Long": "#16a34a", "Short": "#dc2626", "Neutral": "#d97706"}.get(
            trade_direction,
            "#d97706",
        )
    audit_banner_html = build_audit_banner_html(context)
    report_reading_notice_html = build_report_reading_notice_html(context)
    data_trust_html = build_data_trust_html(data, context)
    model_route_summary = format_model_routes(pipeline_id=pipeline_def["id"])
    execution_summary_html = build_execution_summary_html(context, model_routes=model_route_summary)
    mode_template_html = build_mode_template_html(mode_template)
    source_audit_html = build_source_audit_html(data, context)
    audit_entries = safe_dict_list(data.get("source_audit"))
    report_ticker = _display_text(data.get("ticker") or ticker, ticker)
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
    executive_thesis = sanitize_report_plain_text(safe_text(context.get("executive_thesis", "")))
    smoothed_markdown_html = clean_markdown(safe_text(context.get("smoothed_markdown", "")))
    report_cover = safe_mapping_dict(context.get("report_cover", {})) or {}
    report_cover_image = sanitize_report_image_url(report_cover.get("image", ""))
    
    agent_sections = build_agent_sections(context, html=True)
    dcf_scenario_rows = build_dcf_scenario_rows(data)
    management_sentiment = build_management_sentiment(context)
    downside_view = build_downside_view(context)
    peer_comparison_rows = build_peer_comparison_rows(data)
    
    # 準備 JSON 數據給圖表
    chart_data = {
        "years": chart_text_series(years),
        "moneyUnit": "hundred_million_twd",
        "sourceMoneyUnit": "billion_twd",
        "revenue": chart_number_series(revenue_data, scale=10),
        "netIncome": chart_number_series(net_income_data, scale=10),
        "fcf": chart_number_series(fcf_data, scale=10),
        "grossMargin": chart_number_series(gross_margin_data),
        "opMargin": chart_number_series(op_margin_data),
        "netMargin": chart_number_series(net_margin_data),
        "roe": chart_number_series(roe_data),
        "priceHistory": price_history,
        "moatLabels": chart_text_series(moat_labels),
        "moatValues": chart_number_series(moat_values),
        "priceTargets": price_targets,
        "peRiver": pe_river,
    }
    evidence_payload = build_evidence_matrix_payload(context)
    next_catalysts = _collect_next_catalysts(context)
    current_price_numeric = chart_number(data.get("current_price", 0)) or 0
    
    # 關鍵指標卡片
    key_metrics = [
        ("股價", data.get("current_price_fmt", "N/A"), ""),
        ("市值", data.get("market_cap_fmt", "N/A"), ""),
        ("P/E", data.get("pe_ratio", "N/A"), ""),
        ("P/B", data.get("pb_ratio", "N/A"), ""),
        ("毛利率", data.get("gross_margin", "N/A"), ""),
        ("ROE", data.get("roe", "N/A"), ""),
        ("殖利率", data.get("dividend_yield", "N/A"), ""),
        ("Beta", data.get("beta", "N/A"), ""),
    ]
    
    metrics_html = ""
    for label, value, hint in key_metrics:
        metrics_html += f'''
            <div class="metric-card">
                <div class="metric-label">{escape(str(label))}</div>
                <div class="metric-value">{escape(_display_text(value))}</div>
            </div>'''
    
    # 目標股價卡片
    price_targets_html = ""
    for scenario, price in price_targets.items():
        scenario_text = sanitize_report_plain_text(scenario)
        if "熊" in scenario:
            color = "#ef4444"
            icon = "↓"
        elif "牛" in scenario:
            color = "#10b981"
            icon = "↑"
        else:
            color = "#3b82f6"
            icon = "→"
        
        current = current_price_numeric
        price_num = _price_target_number(price)
        if isinstance(current, (int, float)) and current > 0 and price_num is not None:
            pct = ((price_num - current) / current) * 100
            pct_str = f"({'+' if pct > 0 else ''}{pct:.1f}%)"
        else:
            pct_str = ""
        price_display = f"NT${price_num:.0f}" if price_num is not None else "N/A"
        
        price_targets_html += f'''
            <div class="price-target-card" style="border-color: {color};">
                <div class="pt-scenario">{escape(scenario_text)}</div>
                <div class="pt-price" style="color: {color};">{icon} {price_display}</div>
                <div class="pt-pct" style="color: {color};">{escape(pct_str)}</div>
            </div>'''
    
    # 競爭對手比較表格中的值
    comp_pe = data.get("pe_ratio", "N/A")
    comp_pb = data.get("pb_ratio", "N/A")
    comp_ev_ebitda = data.get("ev_ebitda", "N/A")
    
    total_time = context.get("total_time", 0)
    time_str = f"{total_time:.0f} 秒" if total_time else "N/A"
    agent_model_labels = build_agent_model_labels()
    template_context = dict(locals())
    return render_report_template("report.html.j2", template_context)


def _price_target_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = safe_text(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if math.isfinite(number) else None
