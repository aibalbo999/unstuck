"""Tear-sheet summary fallback helpers for report renderers."""

from __future__ import annotations

from analysis_types import AnalysisContext
from company_display import company_display_name
from mapping_fields import safe_dict_list, safe_mapping_dict
from pipeline_modes import get_pipeline_definition

from .mode_tear_sheet_summary import build_mode_tear_sheet_summary
from .structured_intro import get_dict_value_by_substring, safe_report_text, target_price_text
from .utils import contains_prompt_leak_residue, sanitize_report_text


def build_tear_sheet_summary(context: AnalysisContext) -> str:
    """Build a one-page summary without letting generic prose hide mode fields."""
    model_summary = safe_report_text(context.get("tear_sheet_summary", ""), "")
    sanitized_model_summary = ""
    if model_summary:
        sanitized = sanitize_report_text(model_summary)
        if sanitized and not contains_prompt_leak_residue(sanitized):
            sanitized_model_summary = sanitized[:900]

    pipeline_id = get_pipeline_definition(context.get("pipeline_id", "v1"))["id"]
    data = safe_mapping_dict(context.get("data", {})) or {}
    parsed = safe_mapping_dict(context.get("parsed", {})) or {}
    recommendation = safe_mapping_dict(parsed.get("recommendation", {})) or {}
    price_targets = safe_mapping_dict(parsed.get("price_targets", {})) or {}

    ticker = safe_report_text(data.get("ticker"))
    company_name = safe_report_text(company_display_name(data), "")
    rec = get_dict_value_by_substring(recommendation, "建議", "持有")
    confidence = get_dict_value_by_substring(recommendation, "信心")
    base_target = safe_report_text(price_targets.get("基本情境"), "")
    if not base_target:
        base_target = get_dict_value_by_substring(recommendation, "12個月")
    mode_summary = build_mode_tear_sheet_summary(
        context,
        pipeline_id=pipeline_id,
        data=data,
        parsed=parsed,
        ticker=ticker,
        company_name=company_name,
        rec=rec,
        confidence=confidence,
        base_target=base_target,
    )
    if pipeline_id != "v1" and mode_summary:
        return mode_summary
    if sanitized_model_summary:
        return sanitized_model_summary
    if mode_summary:
        return mode_summary
    base_target_display = target_price_text(base_target)
    catalysts = safe_dict_list(data.get("recent_catalysts"))
    top_catalyst = "近期催化劑資料不足"
    if catalysts:
        top_catalyst = safe_report_text(catalysts[0].get("title"), top_catalyst)
    institutional = safe_mapping_dict(data.get("institutional_trading", {})) or {}
    chip_trend = safe_report_text(institutional.get("trend"))
    chip_net = safe_report_text(institutional.get("total_net_buy_thousand_shares"))
    pe_river = safe_mapping_dict(data.get("pe_river_chart", {})) or {}
    pe_source = safe_report_text(pe_river.get("source"))

    return (
        f"一頁式摘要：{ticker} {company_name} 的綜合建議為「{rec}」，"
        f"信心指數 {confidence}，基本情境目標價為 {base_target_display}。"
        f"基本面重點在於 {safe_report_text(data.get('industry'))} 景氣、獲利品質與現金流能否支撐估值；"
        f"近 30 日關鍵催化劑為「{top_catalyst}」。"
        f"籌碼面顯示三大法人趨勢為 {chip_trend}，累計買賣超約 {chip_net} 張。"
        f"台股在地估值另以 P/E 河流圖檢視位階（來源：{pe_source}），"
        "若基本面、籌碼與河流圖位階互相背離，短線操作應降低部位與信心。"
    )
