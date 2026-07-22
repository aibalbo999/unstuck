"""Context helpers for generated HTML reports."""

from __future__ import annotations

import math
import re

from analysis_types import AnalysisContext
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number

from .html_sanitizer import sanitize_report_plain_text
from .text_tokens import is_missing_text_token


PRICE_NUMERIC_TOKEN_RE = re.compile(
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)


def structured_output_values(context: AnalysisContext) -> list[dict]:
    outputs = safe_mapping_dict(context.get("structured_outputs", {})) or {}
    values = []
    for value in outputs.values():
        output = safe_mapping_dict(value)
        if output is not None:
            values.append(output)
    return values


def collect_next_catalysts(context: AnalysisContext) -> list[dict[str, str]]:
    catalysts: list[dict[str, str]] = []
    for source in [context, *structured_output_values(context)]:
        source_map = safe_mapping_dict(source) or {}
        for item in safe_dict_list(source_map.get("next_catalysts")):
            trigger = sanitize_report_plain_text(display_text(item.get("trigger_condition"), ""))
            event_name = sanitize_report_plain_text(display_text(item.get("event_name"), "")) or "未命名催化事件"
            if not trigger:
                continue
            catalysts.append({
                "event_name": event_name,
                "expected_timeframe": sanitize_report_plain_text(display_text(item.get("expected_timeframe"), "")) or "待確認",
                "impact_direction": sanitize_report_plain_text(display_text(item.get("impact_direction"), "")) or "volatile",
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


def display_text(value, default: str = "N/A") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return default
    return text or default


def format_time_str(value: object) -> str:
    try:
        seconds = float(display_text(value, "").replace(",", ""))
    except (OverflowError, TypeError, ValueError):
        return "N/A"
    return f"{seconds:.0f} 秒" if math.isfinite(seconds) and seconds != 0 else "N/A"


def price_target_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    tokens = PRICE_NUMERIC_TOKEN_RE.findall(safe_text(value).replace(",", ""))
    if len(tokens) != 1:
        return None
    try:
        number = float(tokens[0])
    except ValueError:
        return None
    return number if math.isfinite(number) else None


__all__ = [
    "collect_next_catalysts",
    "display_text",
    "format_time_str",
    "price_target_number",
    "structured_output_values",
]
