"""Mode-specific one-page report summaries."""

from __future__ import annotations

import re

from analysis_types import AnalysisContext
from mapping_fields import safe_mapping_dict, safe_text

from .structured_intro import get_dict_value_by_substring, safe_report_text


_MISSING_AGENT_VALUE = object()
_LEADING_MARKUP_RE = re.compile(r"^\s*(?:#{1,6}|[-*+])\s+")
_HEADING_SUFFIX_RE = re.compile(r"^\s*(?:（[^）]*）|\([^)]*\))\s*")
_SENTENCE_END_RE = re.compile(r"。|；|;|(?<!\d)\.(?!\d)")


def _analysis_excerpt(context: AnalysisContext, heading_fragment: str) -> str:
    analyses = safe_mapping_dict(context.get("analyses", {})) or {}
    for agent_num in (19, 18, 17, 24):
        value = analyses.get(agent_num, _MISSING_AGENT_VALUE)
        text = safe_text(value if value is not _MISSING_AGENT_VALUE else analyses.get(str(agent_num), ""))
        if heading_fragment not in text:
            continue
        tail = text.split(heading_fragment, 1)[-1].split("\n## ", 1)[0].split("\n### ", 1)[0]
        tail = _HEADING_SUFFIX_RE.sub("", tail)
        cleaned = " ".join(_LEADING_MARKUP_RE.sub("", line).strip() for line in tail.splitlines())
        cleaned = " ".join(cleaned.split())
        sentence_end = _SENTENCE_END_RE.search(cleaned)
        if cleaned:
            return cleaned[:sentence_end.start() if sentence_end else 120][:120]
    return ""


def _event_swing_summary(data: dict, parsed: dict, ticker: str, company_name: str) -> str:
    setup = safe_mapping_dict(parsed.get("trade_setup")) or {}
    if not setup:
        return (
            f"事件波段摘要：{ticker} {company_name} 的交易計畫資料不足，"
            "目前無法形成可驗證的 1-2 週方向、進場、目標與停損，應維持觀望並重新產出報告。"
        )
    support = safe_report_text(setup.get("support_level"), "")
    resistance = safe_report_text(setup.get("resistance_level"), "")
    levels = f"支撐 {support or 'N/A'}，壓力 {resistance or 'N/A'}。" if support or resistance else ""
    return (
        f"事件波段摘要：{ticker} {company_name} 的 1-2 週交易方向為"
        f"「{safe_report_text(setup.get('trade_direction'), 'Neutral')}」，"
        f"進場區間 {safe_report_text(setup.get('entry_zone'))}，"
        f"目標價 {safe_report_text(setup.get('target_price'))}，"
        f"嚴格停損 {safe_report_text(setup.get('stop_loss'))}。{levels}"
        f"核心催化劑為「{safe_report_text(setup.get('core_catalyst'), '近期催化劑資料不足')}」，"
        f"短期波動風險為 {safe_report_text(setup.get('risk_level'), 'High')}。"
    )


def _contrarian_summary(
    context: AnalysisContext,
    parsed: dict,
    ticker: str,
    company_name: str,
    rec: str,
    confidence: str,
) -> str:
    recommendation = safe_mapping_dict(parsed.get("recommendation")) or {}
    setup = safe_mapping_dict(parsed.get("short_setup")) or {}
    crash = safe_report_text(setup.get("entry_trigger"), "")
    crash = crash or _analysis_excerpt(context, "做空觸發條件") or "尚需等待可驗證的崩盤催化"
    stop = safe_report_text(setup.get("cover_stop"), "")
    stop = stop or _analysis_excerpt(context, "防軋空停損點") or "若基本面改善或股價突破風控位，需暫停空方假設"
    if setup:
        execution = (
            f"做空觸發為「{crash}」，下行目標 {safe_report_text(setup.get('downside_target'), 'N/A')}；"
            f"回補停損為「{stop}」。軋空風險為「{safe_report_text(setup.get('squeeze_risk'), '資料不足')}」，"
            f"論點失效條件為「{safe_report_text(setup.get('thesis_invalidation'), '資料不足')}」。"
        )
    else:
        execution = f"做空觸發為「{crash}」；防軋空或 thesis invalidation 條件為「{stop}」。"
    return (
        f"逆勢風險摘要：{ticker} {company_name} 的空方判斷為「{rec}」，信心指數 {confidence}。"
        f"短期壓力參考 {get_dict_value_by_substring(recommendation, '3個月', 'N/A')}，"
        f"中期回歸參考 {get_dict_value_by_substring(recommendation, '6個月', 'N/A')}，"
        "泡沫檢查重點在估值敘事、Forward EPS 隱含預期、法證財務與法人籌碼是否互相背離。"
        f"{execution}"
    )


def _trading_summary(data: dict, parsed: dict, ticker: str, company_name: str, rec: str, confidence: str, base_target: str) -> str:
    recommendation = safe_mapping_dict(parsed.get("recommendation")) or {}
    plan = safe_mapping_dict(parsed.get("position_plan")) or {}
    if plan:
        return (
            f"實戰交易摘要：{ticker} {company_name} 的操作動作「{safe_report_text(plan.get('action'))}」，"
            f"進場 {safe_report_text(plan.get('entry_zone'))}，部位 {safe_report_text(plan.get('position_size'))}，"
            f"停損 {safe_report_text(plan.get('stop_loss'))}，風險報酬 {safe_report_text(plan.get('risk_reward'))}。"
            f"信心指數 {confidence}；假設失效條件為「{safe_report_text(plan.get('invalidation_condition'))}」。"
        )
    institutional = safe_mapping_dict(data.get("institutional_trading")) or {}
    return (
        f"實戰交易摘要：{ticker} {company_name} 的部位判斷為「{rec}」，信心指數 {confidence}，"
        f"3 個月參考 {get_dict_value_by_substring(recommendation, '3個月', 'N/A')}，12 個月參考 {base_target}。"
        "本模式優先檢查總經、估值、籌碼與市場情緒是否支持進場、續抱、減碼或等待；"
        f"目前三大法人趨勢為 {safe_report_text(institutional.get('trend'))}，"
        f"累計買賣超約 {safe_report_text(institutional.get('total_net_buy_thousand_shares'))} 張。"
        "若估值區間、籌碼方向與建議隱含報酬互相矛盾，應先降低部位與信心。"
    )


def build_mode_tear_sheet_summary(
    context: AnalysisContext,
    *,
    pipeline_id: str,
    data: dict,
    parsed: dict,
    ticker: str,
    company_name: str,
    rec: str,
    confidence: str,
    base_target: str,
) -> str:
    if pipeline_id == "v4":
        return _event_swing_summary(data, parsed, ticker, company_name)
    if pipeline_id == "v3":
        return _contrarian_summary(context, parsed, ticker, company_name, rec, confidence)
    if pipeline_id == "v2":
        return _trading_summary(data, parsed, ticker, company_name, rec, confidence, base_target)
    return ""


__all__ = ["build_mode_tear_sheet_summary"]
