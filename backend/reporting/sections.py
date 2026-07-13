"""Split report rendering helper."""

from __future__ import annotations

from typing import Any

from analysis_types import AnalysisContext
from company_display import company_display_name
from agent_catalog import AGENT_NAMES
from config import AGENT_MODELS
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from pipeline_modes import get_pipeline_definition
from structured_output_normalizer import structured_output_to_report_text

from .audit_trust import _mask_blocking_issue
from .common import build_agent_model_labels
from .utils import (
    clean_markdown,
    contains_prompt_leak_residue,
    format_debate_text,
    normalize_moat_scores,
    sanitize_report_text,
    strip_structured_blocks,
)

def _strip_legacy_structured_tags(text: str) -> str:
    for tag in [
        "[護城河評分]",
        "[/護城河評分]",
        "[目標股價]",
        "[/目標股價]",
        "[投資建議]",
        "[/投資建議]",
    ]:
        text = text.replace(tag, "")
    return text.strip()


def _format_report_value(value) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, bool):
        return "N/A"
    if isinstance(value, (int, float)):
        return f"NT${value:.0f}"
    return _safe_report_text(value)


def _get_dict_value_by_substring(values: dict, needle: str, default="N/A"):
    for key, value in (safe_mapping_dict(values) or {}).items():
        if needle in safe_text(key):
            return _safe_report_text(value, default)
    return default


def _safe_report_text(value: Any, default: str = "N/A") -> str:
    text = safe_text(value).strip()
    if not text:
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _target_price_text(value: Any) -> str:
    text = _safe_report_text(value, "")
    if not text or text == "N/A":
        return "N/A"
    upper_text = text.upper()
    if text.startswith("$") or text.startswith("NT$") or upper_text.startswith(("TWD", "NTD")):
        return text
    return f"NT${text}"


def build_structured_intro_block(agent_num: int, context: AnalysisContext) -> str:
    """Render the mandatory first-block format for structured-response agents."""
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    structured_agents = pipeline_def["structured_agents"]
    parsed = safe_mapping_dict(context.get("parsed", {})) or {}

    if agent_num == structured_agents.get("moat"):
        moat_scores = normalize_moat_scores(safe_mapping_dict(parsed.get("moat_scores", {})) or {})
        if not moat_scores:
            return ""
        lines = ["[護城河評分]"]
        for key in ["品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術"]:
            lines.append(f"{key}: {moat_scores.get(key, 'N/A')}")
        lines.append(f"整體護城河: {moat_scores.get('整體護城河', 'N/A')}/10")
        lines.append("[/護城河評分]")
        return "\n".join(lines)

    if agent_num == structured_agents.get("valuation"):
        price_targets = safe_mapping_dict(parsed.get("price_targets", {})) or {}
        if not price_targets:
            return ""
        lines = ["[目標股價]"]
        for key in ["熊市情境", "基本情境", "牛市情境"]:
            lines.append(f"{key}: {_format_report_value(price_targets.get(key, 'N/A'))}")
        lines.append("[/目標股價]")
        return "\n".join(lines)

    if agent_num == structured_agents.get("recommendation"):
        recommendation = safe_mapping_dict(parsed.get("recommendation", {})) or {}
        if not recommendation:
            return ""
        lines = [
            "[投資建議]",
            f"建議：{_get_dict_value_by_substring(recommendation, '建議', 'N/A')}",
            f"短期目標（3個月）：{_get_dict_value_by_substring(recommendation, '3個月', 'N/A')}",
            f"中期目標（6個月）：{_get_dict_value_by_substring(recommendation, '6個月', 'N/A')}",
            f"長期目標（12個月）：{_get_dict_value_by_substring(recommendation, '12個月', 'N/A')}",
            f"長期潛力（5年）：{_get_dict_value_by_substring(recommendation, '5年', 'N/A')}",
            f"信心指數：{_get_dict_value_by_substring(recommendation, '信心', 'N/A')}",
            "[/投資建議]",
        ]
        return "\n".join(lines)

    return ""


def _structured_block_belongs_at_tail(agent_num: int, pipeline_def: dict, structured_agents: dict) -> bool:
    return pipeline_def.get("id") == "v3" and agent_num == structured_agents.get("recommendation")


_MISSING_AGENT_VALUE = object()


def _agent_keyed_value(values: dict, agent_num: int, default: Any = None) -> Any:
    value = values.get(agent_num, _MISSING_AGENT_VALUE)
    if value is not _MISSING_AGENT_VALUE:
        return value
    return values.get(str(agent_num), default)


def _agent_sequence(context: AnalysisContext, pipeline_def: dict) -> tuple[int, ...]:
    raw_sequence = context.get("agent_sequence") or pipeline_def["agents"]
    if not isinstance(raw_sequence, (list, tuple)):
        raw_sequence = pipeline_def["agents"]
    sequence: list[int] = []
    for item in raw_sequence:
        if isinstance(item, (bool, bytes, bytearray, memoryview)):
            continue
        try:
            agent_num = int(item)
        except (TypeError, ValueError):
            continue
        if agent_num > 0:
            sequence.append(agent_num)
    return tuple(sequence) or tuple(pipeline_def["agents"])


def build_agent_sections(context: AnalysisContext, *, html: bool = True) -> list[dict]:
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    analyses = safe_mapping_dict(context.get("analyses", {})) or {}
    structured_outputs = safe_mapping_dict(context.get("structured_outputs", {})) or {}
    agent_sequence = _agent_sequence(context, pipeline_def)
    agent_model_labels = build_agent_model_labels()
    structured_agents = pipeline_def["structured_agents"]
    debate_agents = set(pipeline_def.get("debate_agents", ()))
    sections = []

    for display_num, agent_num in enumerate(agent_sequence, 1):
        raw_source = _agent_keyed_value(analyses, agent_num, "分析進行中...")
        raw_source = _mask_blocking_issue(raw_source)
        structured_intro = build_structured_intro_block(agent_num, context)
        if _structured_block_belongs_at_tail(agent_num, pipeline_def, structured_agents):
            structured = _agent_keyed_value(structured_outputs, agent_num)
            structured_map = safe_mapping_dict(structured)
            if structured_map is not None:
                raw_source = structured_output_to_report_text(agent_num, structured_map, str(raw_source))
        raw = strip_structured_blocks(sanitize_report_text(raw_source))
        raw = _strip_legacy_structured_tags(raw)
        if structured_intro:
            if _structured_block_belongs_at_tail(agent_num, pipeline_def, structured_agents):
                raw = f"{raw}\n\n{structured_intro}".strip()
            elif structured_intro not in raw:
                raw = f"{structured_intro}\n\n{raw}".strip()
        if html:
            body = format_debate_text(raw) if agent_num in debate_agents else clean_markdown(raw)
        else:
            body = raw

        kind = "standard"
        if agent_num == structured_agents.get("moat"):
            kind = "moat"
        elif agent_num == structured_agents.get("valuation"):
            kind = "valuation"
        elif agent_num == structured_agents.get("recommendation"):
            kind = "final"
        elif agent_num == structured_agents.get("trade_setup"):
            kind = "trade_setup"

        sections.append({
            "display_num": display_num,
            "agent_num": agent_num,
            "title": AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
            "model_label": agent_model_labels.get(agent_num, AGENT_MODELS.get(agent_num, "N/A")),
            "body": body,
            "kind": kind,
            "is_debate": agent_num in debate_agents,
        })

    return sections


def build_tear_sheet_summary(context: AnalysisContext) -> str:
    """Build a one-page style summary, preferring model output when available."""
    model_summary = safe_text(context.get("tear_sheet_summary", "")).strip()
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
        ticker = _safe_report_text(data.get("ticker"))
        company_name = _safe_report_text(company_display_name(data), "")
        trade_direction = _safe_report_text(trade_setup.get("trade_direction"), "Neutral")
        entry_zone = _safe_report_text(trade_setup.get("entry_zone"))
        target_price = _safe_report_text(trade_setup.get("target_price"))
        stop_loss = _safe_report_text(trade_setup.get("stop_loss"))
        core_catalyst = _safe_report_text(trade_setup.get("core_catalyst"), "近期催化劑資料不足")
        risk_level = _safe_report_text(trade_setup.get("risk_level"), "High")
        return (
            f"事件波段摘要：{ticker} {company_name} 的 1-2 週交易方向為"
            f"「{trade_direction}」，進場區間 {entry_zone}，"
            f"目標價 {target_price}，嚴格停損 {stop_loss}。"
            f"核心催化劑為「{core_catalyst}」，"
            f"短期波動風險為 {risk_level}。"
        )

    ticker = _safe_report_text(data.get("ticker"))
    company_name = _safe_report_text(company_display_name(data), "")
    rec = _get_dict_value_by_substring(recommendation, "建議", "持有")
    confidence = _get_dict_value_by_substring(recommendation, "信心")
    base_target = _safe_report_text(price_targets.get("基本情境"), "")
    if not base_target:
        base_target = _get_dict_value_by_substring(recommendation, "12個月")
    base_target_display = _target_price_text(base_target)
    catalysts = safe_dict_list(data.get("recent_catalysts"))
    top_catalyst = "近期催化劑資料不足"
    if catalysts:
        top_catalyst = _safe_report_text(catalysts[0].get("title"), top_catalyst)
    institutional = safe_mapping_dict(data.get("institutional_trading", {})) or {}
    chip_trend = _safe_report_text(institutional.get("trend"))
    chip_net = _safe_report_text(institutional.get("total_net_buy_thousand_shares"))
    pe_river = safe_mapping_dict(data.get("pe_river_chart", {})) or {}
    pe_source = _safe_report_text(pe_river.get("source"))

    if pipeline_id == "v3":
        target_3m = _get_dict_value_by_substring(recommendation, "3個月", "N/A")
        target_6m = _get_dict_value_by_substring(recommendation, "6個月", "N/A")
        crash = _analysis_excerpt(context, "做空觸發條件") or "尚需等待可驗證的崩盤催化"
        stop = _analysis_excerpt(context, "防軋空停損點") or "若基本面改善或股價突破風控位，需暫停空方假設"
        return (
            f"逆勢風險摘要：{ticker} {company_name} 的空方判斷為「{rec}」，"
            f"信心指數 {confidence}。短期壓力參考 {target_3m}，中期回歸參考 {target_6m}，"
            f"泡沫檢查重點在估值敘事、Forward EPS 隱含預期、法證財務與法人籌碼是否互相背離。"
            f"做空觸發為「{crash}」；防軋空或 thesis invalidation 條件為「{stop}」。"
        )

    if pipeline_id == "v2":
        target_3m = _get_dict_value_by_substring(recommendation, "3個月", "N/A")
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
        f"基本面重點在於 {_safe_report_text(data.get('industry'))} 景氣、獲利品質與現金流能否支撐估值；"
        f"近 30 日關鍵催化劑為「{top_catalyst}」。"
        f"籌碼面顯示三大法人趨勢為 {chip_trend}，累計買賣超約 {chip_net} 張。"
        f"台股在地估值另以 P/E 河流圖檢視位階（來源：{pe_source}），"
        "若基本面、籌碼與河流圖位階互相背離，短線操作應降低部位與信心。"
    )


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
        for sep in ("。", ".", "；", ";"):
            if sep in cleaned:
                cleaned = cleaned.split(sep, 1)[0]
                break
        return cleaned[:120]
    return ""
