"""Split report rendering helper."""

from __future__ import annotations

from datetime import datetime
from html import escape

from analysis_types import AnalysisContext
from company_display import company_display_name
from config import format_model_routes
from pipeline_modes import get_pipeline_definition

from .audit_trust import build_audit_banner_html, build_data_trust_html, build_source_audit_html
from .common import build_agent_model_labels, render_report_template
from .cover import prepare_report_cover_async
from .html_sanitizer import sanitize_report_image_url, sanitize_report_plain_text
from .sections import build_agent_sections, build_tear_sheet_summary
from .utils import (
    billion_twd_series_to_yi_twd,
    clean_markdown,
    filter_future_price_history,
    get_recommendation_color,
    get_recommendation_icon,
    normalize_moat_scores,
)


async def generate_html_report_async(context: AnalysisContext) -> str:
    """Async HTML report renderer that can optionally generate an Imagen cover."""
    await prepare_report_cover_async(context)
    return generate_html_report(context)


def generate_html_report(context: AnalysisContext) -> str:
    """生成完整的 HTML 報告"""
    
    data = dict(context.get("data", {}) or {})
    for text_key in ("company_name", "sector", "industry", "fetch_date", "current_price_fmt", "market_cap_fmt"):
        if text_key in data:
            data[text_key] = sanitize_report_plain_text(data.get(text_key))
    analyses = context.get("analyses", {})
    parsed = context.get("parsed", {})
    
    ticker = sanitize_report_plain_text(context.get("ticker", "N/A")) or "N/A"
    name = sanitize_report_plain_text(company_display_name(data, context.get("company_name", ticker))) or ticker
    fetch_date = data.get("fetch_date", datetime.now().strftime("%Y年%m月%d日"))
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
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
    price_history = filter_future_price_history(data.get("price_history", {}))
    
    # 護城河評分
    moat_scores = normalize_moat_scores(parsed.get("moat_scores", {}))
    moat_labels = list(moat_scores.keys())
    moat_values = list(moat_scores.values())
    overall_moat = moat_scores.get("整體護城河", 0)
    
    # 目標股價
    raw_price_targets = parsed.get("price_targets", {}) or {}
    price_targets = {
        sanitize_report_plain_text(key) or "情境": value
        for key, value in raw_price_targets.items()
    }
    recommendation = parsed.get("recommendation", {})
    pe_river = data.get("pe_river_chart", {}) or {}
    pe_river_source = str(pe_river.get("source", "") or "")
    pe_river_title = (
        "P/E 河流圖（EPS × 預設本益比通道）"
        if "default" in pe_river_source.lower()
        else "P/E 河流圖（EPS × 歷史本益比通道）"
    )
    
    def get_rec_val(rec_dict, target_sub, default="N/A"):
        for k, v in rec_dict.items():
            if target_sub in k:
                return v
        return default
        
    rec_text = sanitize_report_plain_text(get_rec_val(recommendation, "建議", "持有")) or "持有"
    if "強烈放空" in rec_text: rec_text = "強烈放空"
    elif "買進" in rec_text: rec_text = "買進"
    elif "買入" in rec_text or "Buy" in rec_text or "BUY" in rec_text: rec_text = "買入"
    elif "避免" in rec_text or "Avoid" in rec_text or "AVOID" in rec_text or "賣出" in rec_text or "放空" in rec_text: rec_text = "避免"
    else: rec_text = "持有"

    rec_color = get_recommendation_color(rec_text)
    rec_icon = get_recommendation_icon(rec_text)
    
    target_3m = sanitize_report_plain_text(get_rec_val(recommendation, "3個月", "N/A")) or "N/A"
    target_6m = sanitize_report_plain_text(get_rec_val(recommendation, "6個月", "N/A")) or "N/A"
    target_12m = sanitize_report_plain_text(get_rec_val(recommendation, "12個月", "N/A")) or "N/A"
    confidence = sanitize_report_plain_text(get_rec_val(recommendation, "信心", "N/A")) or "N/A"
    audit_banner_html = build_audit_banner_html(context)
    data_trust_html = build_data_trust_html(data)
    source_audit_html = build_source_audit_html(data, context)
    tear_sheet_summary = clean_markdown(build_tear_sheet_summary(context))
    report_cover = context.get("report_cover", {}) or {}
    report_cover_image = sanitize_report_image_url(report_cover.get("image", ""))
    report_cover_model = report_cover.get("model", "")
    
    agent_sections = build_agent_sections(context, html=True)
    
    # 準備 JSON 數據給圖表
    chart_data = {
        "years": years,
        "moneyUnit": "hundred_million_twd",
        "sourceMoneyUnit": "billion_twd",
        "revenue": billion_twd_series_to_yi_twd(revenue_data),
        "netIncome": billion_twd_series_to_yi_twd(net_income_data),
        "fcf": billion_twd_series_to_yi_twd(fcf_data),
        "grossMargin": [v for v in gross_margin_data],
        "opMargin": [v for v in op_margin_data],
        "netMargin": [v for v in net_margin_data],
        "roe": [v for v in roe_data],
        "priceHistory": price_history,
        "moatLabels": moat_labels,
        "moatValues": moat_values,
        "priceTargets": price_targets,
        "peRiver": pe_river,
    }
    
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
                <div class="metric-value">{escape(str(value))}</div>
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
        
        current = data.get("current_price", 0)
        price_num = price if isinstance(price, (int, float)) else None
        if price_num is None:
            try:
                price_num = float(str(price).replace(",", ""))
            except (TypeError, ValueError):
                price_num = None
        if isinstance(current, (int, float)) and current > 0 and price_num is not None:
            pct = ((price_num - current) / current) * 100
            pct_str = f"({'+' if pct > 0 else ''}{pct:.1f}%)"
        else:
            pct_str = ""
        price_display = f"NT${price_num:.0f}" if price_num is not None else escape(str(price))
        
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
    model_route_summary = format_model_routes(pipeline_id=pipeline_def["id"])
    
    current_price_numeric = data.get("current_price", 0) if isinstance(data.get("current_price", 0), (int, float)) else 0
    template_context = dict(locals())
    return render_report_template("report.html.j2", template_context)
