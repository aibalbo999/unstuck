"""Split report rendering helper."""

from __future__ import annotations

from analysis_types import AnalysisContext
from company_display import company_display_name
from agent_catalog import AGENT_NAMES
from config import AGENT_MODELS
from pipeline_modes import get_pipeline_definition
from structured_output_normalizer import structured_output_to_report_text

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
        return str(value)
    if isinstance(value, (int, float)):
        return f"NT${value:.0f}"
    return str(value)


def _get_dict_value_by_substring(values: dict, needle: str, default="N/A"):
    for key, value in (values or {}).items():
        if needle in str(key):
            return value
    return default


def build_structured_intro_block(agent_num: int, context: AnalysisContext) -> str:
    """Render the mandatory first-block format for structured-response agents."""
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    structured_agents = pipeline_def["structured_agents"]
    parsed = context.get("parsed", {}) or {}

    if agent_num == structured_agents.get("moat"):
        moat_scores = normalize_moat_scores(parsed.get("moat_scores", {}))
        if not moat_scores:
            return ""
        lines = ["[護城河評分]"]
        for key in ["品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術"]:
            lines.append(f"{key}: {moat_scores.get(key, 'N/A')}")
        lines.append(f"整體護城河: {moat_scores.get('整體護城河', 'N/A')}/10")
        lines.append("[/護城河評分]")
        return "\n".join(lines)

    if agent_num == structured_agents.get("valuation"):
        price_targets = parsed.get("price_targets", {}) or {}
        if not price_targets:
            return ""
        lines = ["[目標股價]"]
        for key in ["熊市情境", "基本情境", "牛市情境"]:
            lines.append(f"{key}: {_format_report_value(price_targets.get(key, 'N/A'))}")
        lines.append("[/目標股價]")
        return "\n".join(lines)

    if agent_num == structured_agents.get("recommendation"):
        recommendation = parsed.get("recommendation", {}) or {}
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


def build_agent_sections(context: AnalysisContext, *, html: bool = True) -> list[dict]:
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    analyses = context.get("analyses", {}) or {}
    agent_sequence = tuple(context.get("agent_sequence") or pipeline_def["agents"])
    agent_model_labels = build_agent_model_labels()
    structured_agents = pipeline_def["structured_agents"]
    debate_agents = set(pipeline_def.get("debate_agents", ()))
    sections = []

    for display_num, agent_num in enumerate(agent_sequence, 1):
        raw_source = analyses.get(agent_num, "分析進行中...")
        structured_intro = build_structured_intro_block(agent_num, context)
        if _structured_block_belongs_at_tail(agent_num, pipeline_def, structured_agents):
            structured = (context.get("structured_outputs", {}) or {}).get(agent_num)
            if isinstance(structured, dict):
                raw_source = structured_output_to_report_text(agent_num, structured, str(raw_source))
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
    model_summary = str(context.get("tear_sheet_summary", "") or "").strip()
    if model_summary:
        sanitized = sanitize_report_text(model_summary)
        if sanitized and not contains_prompt_leak_residue(sanitized):
            return sanitized[:900]

    data = context.get("data", {}) or {}
    parsed = context.get("parsed", {}) or {}
    recommendation = parsed.get("recommendation", {}) or {}
    price_targets = parsed.get("price_targets", {}) or {}
    trade_setup = parsed.get("trade_setup", {}) or {}

    if trade_setup:
        return (
            f"一頁式摘要：{data.get('ticker', 'N/A')} {company_display_name(data)} 的 1-2 週交易方向為"
            f"「{trade_setup.get('trade_direction', 'Neutral')}」，進場區間 {trade_setup.get('entry_zone', 'N/A')}，"
            f"目標價 {trade_setup.get('target_price', 'N/A')}，嚴格停損 {trade_setup.get('stop_loss', 'N/A')}。"
            f"核心催化劑為「{trade_setup.get('core_catalyst', '近期催化劑資料不足')}」，"
            f"短期波動風險為 {trade_setup.get('risk_level', 'High')}。"
        )

    rec = next((str(v) for k, v in recommendation.items() if "建議" in str(k)), "持有")
    confidence = next((str(v) for k, v in recommendation.items() if "信心" in str(k)), "N/A")
    base_target = price_targets.get("基本情境") or next((str(v) for k, v in recommendation.items() if "12個月" in str(k)), "N/A")
    catalysts = data.get("recent_catalysts", []) or []
    top_catalyst = catalysts[0]["title"] if catalysts and catalysts[0].get("title") else "近期催化劑資料不足"
    institutional = data.get("institutional_trading", {}) or {}
    chip_trend = institutional.get("trend", "N/A")
    chip_net = institutional.get("total_net_buy_thousand_shares", "N/A")
    pe_river = data.get("pe_river_chart", {}) or {}
    pe_source = pe_river.get("source", "N/A")

    return (
        f"一頁式摘要：{data.get('ticker', 'N/A')} {company_display_name(data)} 的綜合建議為「{rec}」，"
        f"信心指數 {confidence}，基本情境目標價為 NT${base_target if base_target != 'N/A' else 'N/A'}。"
        f"基本面重點在於 {data.get('industry', 'N/A')} 景氣、獲利品質與現金流能否支撐估值；"
        f"近 30 日關鍵催化劑為「{top_catalyst}」。"
        f"籌碼面顯示三大法人趨勢為 {chip_trend}，累計買賣超約 {chip_net} 張。"
        f"台股在地估值另以 P/E 河流圖檢視位階（來源：{pe_source}），"
        "若基本面、籌碼與河流圖位階互相背離，短線操作應降低部位與信心。"
    )
