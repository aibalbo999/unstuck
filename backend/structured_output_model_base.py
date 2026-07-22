"""Base helpers for structured output Pydantic models."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text


class StructuredModel(BaseModel):
    """Base model for native Google GenAI response_schema payloads."""

    model_config = ConfigDict(populate_by_name=True)


_ANALYSIS_MARKDOWN_FALLBACK = "資料不足"
_VALUATION_PRIMARY_METHODS = {"normalized_dcf", "relative_valuation", "blended"}
_MANAGEMENT_GUIDANCE_TONES = {"樂觀", "中立", "保守", "資料不足"}
_DOWNSIDE_RISK_SEVERITIES = {"warning", "high", "critical"}
_DCF_SCENARIOS = {"bear", "base", "bull"}
_MISSING_TEXT_TOKENS = {
    "NAN",
    "INF",
    "+INF",
    "-INF",
    "INFINITY",
    "+INFINITY",
    "-INFINITY",
    "MISSING",
    "NIL",
    "NONE",
    "NULL",
    "-",
    "--",
    "N/A",
    "NA",
}
_MOAT_SCORE_FIELDS = (
    ("品牌影響力", "brand_influence"),
    ("網路效應", "network_effect"),
    ("轉換成本", "switching_cost"),
    ("成本優勢", "cost_advantage"),
    ("專利技術", "patent_technology"),
    ("整體護城河", "overall_moat"),
)


def _safe_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return default
    text = safe_text(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n", ""}:
        return False
    return default


def _safe_number(value, *, default: float = 0.0, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    raw_value = value.replace(",", "").strip() if isinstance(value, str) else value
    try:
        number = float(raw_value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return default
    if not math.isfinite(number):
        return default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return round(number, 2)


def _safe_mapping_value(mapping: dict, *keys: str):
    for key in keys:
        if not isinstance(key, str):
            continue
        for raw_key, value in mapping.items():
            if type(raw_key) is str and raw_key == key:
                return value
    return None


def _safe_mapping_has_key(mapping: dict, key: str) -> bool:
    return any(type(raw_key) is str and raw_key == key for raw_key in mapping)


def _safe_string_text(value: Any, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    text = safe_text(value).strip()
    if not text or text.upper() in _MISSING_TEXT_TOKENS:
        return default
    return text


def _safe_string_text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    texts = []
    for item in safe_sequence_items(value):
        text = _safe_string_text(item)
        if text:
            texts.append(text)
    return texts


def _safe_required_text_list(value: Any, minimum: int, fallback: str) -> list[str]:
    texts = _safe_string_text_list(value)
    if not isinstance(value, (list, tuple)):
        return texts
    while len(texts) < minimum:
        texts.append(fallback)
    return texts


class AnalysisMarkdownMixin(StructuredModel):
    @model_validator(mode="before")
    @classmethod
    def sanitize_analysis_markdown(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return payload
        return {
            **root,
            "analysis_markdown": _safe_string_text(root.get("analysis_markdown"), _ANALYSIS_MARKDOWN_FALLBACK),
        }
