"""Tear-sheet summary fallback helpers for report renderers."""

from __future__ import annotations

from analysis_types import AnalysisContext
from company_display import company_display_name
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from pipeline_modes import get_pipeline_definition

from .structured_intro import get_dict_value_by_substring, safe_report_text, target_price_text
from .utils import contains_prompt_leak_residue, sanitize_report_text


_MISSING_AGENT_VALUE = object()


def _agent_keyed_value(values: dict, agent_num: int, default=None):
    value = values.get(agent_num, _MISSING_AGENT_VALUE)
    if value is not _MISSING_AGENT_VALUE:
        return value
    return values.get(str(agent_num), default)


def _analysis_excerpt(context: AnalysisContext, heading_fragment: str) -> str:
    analyses = safe_mapping_dict(context.get("analyses", {})) or {}
    for agent_num in (19, 18, 17, 24):
        text = safe_text(_agent_keyed_value(analyses, agent_num, ""))
        if heading_fragment not in text:
            continue
        tail = text.split(heading_fragment, 1)[-1]
        tail = tail.split("\n## ", 1)[0].split("\n### ", 1)[0]
        cleaned = " ".join(tail.replace("-", " ").replace("#", " ").split())
        if not cleaned:
            continue
        separator_positions = [
            cleaned.find(sep)
            for sep in ("。", ".", "；", ";")
            if sep in cleaned
        ]
        if separator_positions:
            cleaned = cleaned[:min(separator_positions)]
        return cleaned[:120]
    return ""


def build_tear_sheet_summary(context: AnalysisContext) -> str:
    """Build a one-page style summary, preferring model output when available."""
    model_summary = safe_report_text(context.get("tear_sheet_summary", ""), "")
    if model_summary:
        sanitized = sanitize_report_text(model_summary)
        if sanitized and not contains_prompt_leak_residue(sanitized):
            return sanitized[:900]

    pipeline_id = get_pipeline_definition(context.get("pipeline_id", "v1"))["id"]
    data = safe_mapping_dict(context.get("data", {})) or {}
    parsed = safe_mapping_dict(context.get("parsed", {})) or {}
    recommendation = safe_mapping_dict(parsed.get("recommendation", {})) or {}
    price_targets = safe_mapping_dict(parsed.get("price_targets", {})) or {}
    trade_setup = safe_mapping_dict(parsed.get("trade_setup", {})) or {}

    if pipeline_id == "v4" and trade_setup:
        ticker = safe_report_text(data.get("ticker"))
        company_name = safe_report_text(company_display_name(data), "")
        trade_direction = safe_report_text(trade_setup.get("trade_direction"), "Neutral")
        entry_zone = safe_report_text(trade_setup.get("entry_zone"))
        target_price = safe_report_text(trade_setup.get("target_price"))
        stop_loss = safe_report_text(trade_setup.get("stop_loss"))
        core_catalyst = safe_report_text(trade_setup.get("core_catalyst"), "近期催化劑資料不足")
        risk_level = safe_report_text(trade_setup.get("risk_level"), "High")
        return (
            f"事件波段摘要：{ticker} {company_name} 的 1-2 週交易方向為"
            f"「{trade_direction}」，進場區間 {entry_zone}，"
            f"目標價 {target_price}，嚴格停損 {stop_loss}。"
            f"核心催化劑為「{core_catalyst}」，"
            f"短期波動風險為 {risk_level}。"
        )

    ticker = safe_report_text(data.get("ticker"))
    company_name = safe_report_text(company_display_name(data), "")
    rec = get_dict_value_by_substring(recommendation, "建議", "持有")
    confidence = get_dict_value_by_substring(recommendation, "信心")
    base_target = safe_report_text(price_targets.get("基本情境"), "")
    if not base_target:
        base_target = get_dict_value_by_substring(recommendation, "12個月")
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

    if pipeline_id == "v3":
        target_3m = get_dict_value_by_substring(recommendation, "3個月", "N/A")
        target_6m = get_dict_value_by_substring(recommendation, "6個月", "N/A")
        crash = _analysis_excerpt(context, "做空觸發條件") or "尚需等待可驗證的崩盤催化"
        stop = _analysis_excerpt(context, "防軋空停損點") or "若基本面改善或股價突破風控位，需暫停空方假設"
        return (
            f"逆勢風險摘要：{ticker} {company_name} 的空方判斷為「{rec}」，"
            f"信心指數 {confidence}。短期壓力參考 {target_3m}，中期回歸參考 {target_6m}，"
            f"泡沫檢查重點在估值敘事、Forward EPS 隱含預期、法證財務與法人籌碼是否互相背離。"
            f"做空觸發為「{crash}」；防軋空或 thesis invalidation 條件為「{stop}」。"
        )

    if pipeline_id == "v2":
        target_3m = get_dict_value_by_substring(recommendation, "3個月", "N/A")
        return (
            f"實戰交易摘要：{ticker} {company_name} 的部位判斷為「{rec}」，"
            f"信心指數 {confidence}，3 個月參考 {target_3m}，12 個月參考 {base_target}。"
            f"本模式優先檢查總經、估值、籌碼與市場情緒是否支持進場、續抱、減碼或等待；"
            f"目前三大法人趨勢為 {chip_trend}，累計買賣超約 {chip_net} 張。"
            f"若估值區間、籌碼方向與建議隱含報酬互相矛盾，應先降低部位與信心。"
        )

    return (
        f"一頁式摘要：{ticker} {company_name} 的綜合建議為「{rec}」，"
        f"信心指數 {confidence}，基本情境目標價為 {base_target_display}。"
        f"基本面重點在於 {safe_report_text(data.get('industry'))} 景氣、獲利品質與現金流能否支撐估值；"
        f"近 30 日關鍵催化劑為「{top_catalyst}」。"
        f"籌碼面顯示三大法人趨勢為 {chip_trend}，累計買賣超約 {chip_net} 張。"
        f"台股在地估值另以 P/E 河流圖檢視位階（來源：{pe_source}），"
        "若基本面、籌碼與河流圖位階互相背離，短線操作應降低部位與信心。"
    )
