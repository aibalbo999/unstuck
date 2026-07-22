"""Basis text helpers for conclusion-level evidence matrix rows."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text
from numeric_safety import is_non_finite_number

from .html_sanitizer import sanitize_report_plain_text
from .text_tokens import is_missing_text_token


def price_target_basis(price_targets: dict) -> str:
    if not price_targets:
        return ""
    parts = []
    seen_scenarios = set()
    for scenario, price in price_targets.items():
        scenario_text = _unique_display_label(seen_scenarios, _text(scenario, "情境"))
        parts.append(f"{scenario_text}: {_format_price(price)}")
    return "；".join(parts)


def moat_basis(moat_scores: dict) -> str:
    if not moat_scores:
        return ""
    overall = moat_scores.get("整體護城河")
    parts = []
    if overall is not None:
        parts.append(f"整體護城河: {_text(overall)}/10")
    for metric, score in moat_scores.items():
        metric_text = _text(metric, "")
        if not metric_text or metric_text == "整體護城河":
            continue
        parts.append(f"{metric_text}: {_text(score)}/10")
    return "；".join(parts)


def recommendation_basis(recommendation: dict) -> str:
    if not recommendation:
        return ""
    fields = []
    for label in ("建議", "3個月", "6個月", "12個月", "信心"):
        value = next((item for key, item in recommendation.items() if label in safe_text(key)), None)
        value_text = _basis_value_text(value)
        if value_text:
            fields.append(f"{label}: {value_text}")
    return "；".join(fields)


def _basis_value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _text(value, "").strip()
    if isinstance(value, (list, tuple, dict, set, frozenset)):
        try:
            if len(value) == 0:
                return ""
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return ""
    return _text(value, "").strip()


def _format_price(value: Any) -> str:
    if isinstance(value, bool):
        return "N/A"
    if is_non_finite_number(value):
        return "N/A"
    if isinstance(value, (int, float)):
        return f"NT${value:,.0f}"
    return _text(value)


def _text(value: Any, default: str = "N/A") -> str:
    if is_non_finite_number(value):
        return default
    text = sanitize_report_plain_text(safe_text(value)).strip()
    if is_missing_text_token(text):
        return default
    return text


def _unique_display_label(seen: set[str], label: str) -> str:
    candidate = label
    suffix = 2
    while candidate in seen:
        candidate = f"{label} {suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


__all__ = ["moat_basis", "price_target_basis", "recommendation_basis"]
