"""Primitive helpers for structured output normalization."""

from __future__ import annotations

import math
import re
from numbers import Real
from typing import Any

from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text
from structured_output_rendering import normalize_escaped_newlines


_NUMERIC_TOKEN_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_MANAGEMENT_GUIDANCE_TONES = {"樂觀", "中立", "保守", "資料不足"}
_TRADE_DIRECTIONS = {"Long", "Short", "Neutral"}
_TRADE_RISK_LEVELS = {"High", "Medium", "Low"}
_MISSING_TEXT_TOKENS = {
    "N/A", "NA", "NONE", "NULL", "NIL", "MISSING", "-", "--",
    "NAN", "INF", "+INF", "-INF", "INFINITY", "+INFINITY", "-INFINITY",
}


def _number_text(value: str) -> str:
    tokens = [match.group(0) for match in _NUMERIC_TOKEN_RE.finditer(value.replace(",", ""))]
    return tokens[0] if len(tokens) == 1 else ""


def _coerce_number(value, minimum=None, maximum=None):
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = _number_text(value)
    elif not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return None
    if not math.isfinite(number):
        return None
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return round(number, 2)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n", ""}:
            return False
        return default
    return default


def _pick_mapping_value(mapping: dict, *keys):
    for key in keys:
        if not isinstance(key, str):
            continue
        for raw_key, value in mapping.items():
            if type(raw_key) is str and raw_key == key:
                return value
    return None


def _has_string_key(mapping: dict, *keys: str) -> bool:
    return any(type(raw_key) is str and raw_key in keys for raw_key in mapping)


def _raw_structured_payload_is_complete_enough(agent_num: int, payload: Any) -> bool:
    if not isinstance(payload, dict):
        return True

    if agent_num in {3, 12} and _has_string_key(payload, "moat_scores"):
        return _has_string_key(payload, "reasoning_steps")

    if agent_num in {4, 14} and _has_string_key(payload, "price_targets"):
        targets = safe_mapping_dict(_pick_mapping_value(payload, "price_targets"))
        if targets is None:
            return False
        return _has_string_key(payload, "valuation_summary")

    if (
        agent_num in {7, 16, 19}
        and _has_string_key(payload, "recommendation")
        and _has_string_key(payload, "reasoning_steps")
    ):
        recommendation = safe_mapping_dict(_pick_mapping_value(payload, "recommendation"))
        if recommendation is None:
            return False
        return (
            (_has_string_key(recommendation, "建議") or _has_string_key(recommendation, "recommendation"))
            and (_has_string_key(recommendation, "短期目標（3個月）") or _has_string_key(recommendation, "target_3m"))
            and (_has_string_key(recommendation, "中期目標（6個月）") or _has_string_key(recommendation, "target_6m"))
            and (_has_string_key(recommendation, "長期目標（12個月）") or _has_string_key(recommendation, "target_12m"))
            and (
                _has_string_key(recommendation, "長期潛力（5年）")
                or _has_string_key(recommendation, "long_term_potential_5y")
            )
            and (_has_string_key(recommendation, "信心指數") or _has_string_key(recommendation, "confidence"))
        )

    return True


_MOAT_SCORE_ALIASES = {
    "品牌影響力": ("品牌影響力", "brand_influence"),
    "網路效應": ("網路效應", "network_effect"),
    "轉換成本": ("轉換成本", "switching_cost"),
    "成本優勢": ("成本優勢", "cost_advantage"),
    "專利技術": ("專利技術", "patent_technology"),
    "整體護城河": ("整體護城河", "overall_moat"),
}


_PRICE_TARGET_ALIASES = {
    "熊市情境": ("熊市情境", "bear_case", "bear"),
    "基本情境": ("基本情境", "base_case", "base"),
    "牛市情境": ("牛市情境", "bull_case", "bull"),
}

_SCENARIO_TRIGGER_FALLBACK = {
    "trigger_condition": "待後續資料確認觸發條件",
    "action": "重新檢查投資結論",
    "direction": "neutral_review",
}


def _display_text(value: Any, default: str = "") -> str:
    if not isinstance(value, str):
        if isinstance(value, bool) or not isinstance(value, Real):
            return default
        if not math.isfinite(float(value)):
            return default
    text = safe_text(value).strip()
    return default if not text or text.upper() in _MISSING_TEXT_TOKENS else text


def _display_line(value: Any, default: str = "") -> str:
    text = _display_text(value, default)
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


def _analysis_markdown_text(value: Any, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    return _display_text(value, default)


def _string_field_text(value: Any, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    return _display_text(value, default)


def _string_field_line(value: Any, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    return _display_line(value, default)


def _normalized_analysis_markdown(raw_payload: Any, payload: dict, default: str = "資料不足") -> str:
    raw_mapping = safe_mapping_dict(raw_payload) or {}
    if "analysis_markdown" in raw_mapping:
        return _analysis_markdown_text(raw_mapping.get("analysis_markdown"), default)
    return _analysis_markdown_text(payload.get("analysis_markdown"), default)


def _display_price_target(value: Any) -> str:
    price = _coerce_number(value)
    return f"NT${price:,.0f}" if price is not None else "N/A"


def _report_body_text(analysis_markdown: Any, fallback_text: Any) -> str:
    return normalize_escaped_newlines(_analysis_markdown_text(analysis_markdown) or _analysis_markdown_text(fallback_text))


def _legacy_body_text(body: str) -> str:
    return "資料不足" if body and len(body) < 2 else body
