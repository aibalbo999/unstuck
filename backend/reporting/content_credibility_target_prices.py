"""Target-price candidate extraction for content credibility checks."""

from __future__ import annotations

import re
from typing import Any

from mapping_fields import safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number
from price_parser import extract_target_price_numbers

from .text_tokens import is_missing_text_token


PERCENT_NUMBER_PATTERN = r"(?:[+＋\-−－]\s*)?\d+(?:[.．]\d+)?(?:[eE][-+]?\d+)?\s*[%％]"
RANGE_SEPARATOR_PATTERN = r"(?:-|–|—|－|−|~|～|〜|至|到|\bto\b|\band\b|與|和)"
TARGET_CONTEXT_SEGMENT_SEPARATOR_PATTERN = re.compile(r"[;；\n]|(?<!\d)[,，]|[,，](?!\d)")
HORIZON_LABEL_PATTERNS = {
    "12個月": re.compile(r"(?:12\s*(?:個月|月)|12\s*(?:months?|m)\b|長期|long\s*[- ]?\s*term)", re.IGNORECASE),
    "6個月": re.compile(r"(?:6\s*(?:個月|月)|6\s*(?:months?|m)\b|中期|mid\s*[- ]?\s*term)", re.IGNORECASE),
    "3個月": re.compile(r"(?:3\s*(?:個月|月)|3\s*(?:months?|m)\b|短期|short\s*[- ]?\s*term)", re.IGNORECASE),
}


def _input_text(value: Any) -> str:
    if is_non_finite_number(value):
        return ""
    text = safe_text(value).strip()
    return "" if is_missing_text_token(text) else text


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _first_value_by_key_fragment(values: dict, fragment: str) -> Any:
    for key, value in values.items():
        if fragment in _input_text(key):
            return value
    return None


def _looks_like_price_range(text: str) -> bool:
    return bool(
        re.search(
            rf"\d\s*(?:元|塊)?\s*{RANGE_SEPARATOR_PATTERN}\s*"
            rf"(?:NT\$?|NTD|TWD|新台幣|臺幣|台幣)?\s*\d",
            text,
        )
    )


def _horizon_context(text: str, label: str) -> str:
    horizon_pattern = HORIZON_LABEL_PATTERNS.get(label)
    if horizon_pattern is None:
        return text
    for segment in TARGET_CONTEXT_SEGMENT_SEPARATOR_PATTERN.split(str(text or "")):
        if horizon_pattern.search(segment):
            return segment.strip()
    return text


def _target_price(value: Any, *, label: str = "") -> float | None:
    if isinstance(value, bool) or value is None or is_non_finite_number(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _input_text(value)
    if not text:
        return None
    cleaned = re.sub(PERCENT_NUMBER_PATTERN, "", text)
    cleaned = _horizon_context(cleaned, label)
    try:
        prices = [price for price in extract_target_price_numbers(cleaned) if price > 0]
    except (TypeError, ValueError):
        return None
    if not prices:
        return None
    if _looks_like_price_range(cleaned) and len(prices) >= 2:
        return sum(prices[:2]) / 2
    price = float(prices[0])
    return None if is_non_finite_number(price) else price


def target_price_candidates(parsed: dict) -> list[dict]:
    recommendation = _as_dict(parsed.get("recommendation"))
    price_targets = _as_dict(parsed.get("price_targets"))
    candidates: list[dict] = []
    for label in ("12個月", "6個月", "3個月"):
        value = _first_value_by_key_fragment(recommendation, label)
        price = _target_price(value, label=label)
        if price is not None:
            candidates.append({"source": f"recommendation.{label}", "label": label, "price": price, "raw": value})
    for label in ("基本情境", "牛市情境", "熊市情境"):
        value = price_targets.get(label)
        price = _target_price(value)
        if price is not None:
            candidates.append({"source": f"price_targets.{label}", "label": label, "price": price, "raw": value})
    if not candidates:
        for label, value in price_targets.items():
            price = _target_price(value)
            name = _input_text(label)
            if price is not None and name:
                candidates.append({"source": f"price_targets.{name}", "label": name, "price": price, "raw": value})
    return candidates


def main_target_price(parsed: dict) -> dict | None:
    candidates = target_price_candidates(parsed)
    return candidates[0] if candidates else None


__all__ = ("main_target_price", "target_price_candidates")
