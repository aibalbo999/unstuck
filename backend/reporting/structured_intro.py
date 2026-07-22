"""Structured first-block rendering for report agent sections."""

from __future__ import annotations

from typing import Any

from analysis_types import AnalysisContext
from mapping_fields import safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number
from pipeline_modes import get_pipeline_definition

from .chart_values import normalize_moat_scores
from .target_price_text import target_price_text
from .text_tokens import is_missing_text_token


def strip_legacy_structured_tags(text: str) -> str:
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
            lines.append(f"{key}: {target_price_text(price_targets.get(key, 'N/A'))}")
        lines.append("[/目標股價]")
        return "\n".join(lines)

    if agent_num == structured_agents.get("recommendation"):
        recommendation = safe_mapping_dict(parsed.get("recommendation", {})) or {}
        if not recommendation:
            return ""
        lines = [
            "[投資建議]",
            f"建議：{get_dict_value_by_substring(recommendation, '建議', 'N/A')}",
            f"短期目標（3個月）：{get_dict_value_by_substring(recommendation, '3個月', 'N/A')}",
            f"中期目標（6個月）：{get_dict_value_by_substring(recommendation, '6個月', 'N/A')}",
            f"長期目標（12個月）：{get_dict_value_by_substring(recommendation, '12個月', 'N/A')}",
            f"長期潛力（5年）：{get_dict_value_by_substring(recommendation, '5年', 'N/A')}",
            f"信心指數：{get_dict_value_by_substring(recommendation, '信心', 'N/A')}",
            "[/投資建議]",
        ]
        return "\n".join(lines)

    return ""


def get_dict_value_by_substring(values: dict, needle: str, default="N/A"):
    for key, value in (safe_mapping_dict(values) or {}).items():
        if needle in safe_text(key):
            return safe_report_text(value, default)
    return default


def safe_report_text(value: Any, default: str = "N/A") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


__all__ = [
    "build_structured_intro_block",
    "get_dict_value_by_substring",
    "safe_report_text",
    "strip_legacy_structured_tags",
    "target_price_text",
]
