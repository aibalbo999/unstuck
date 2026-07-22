"""Input extraction helpers for content credibility checks."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text
from numeric_safety import is_non_finite_number
from price_parser import extract_price_numbers

from .content_credibility_confidence import confidence_score as _confidence_score
from .content_credibility_target_prices import main_target_price, target_price_candidates
from .text_tokens import is_missing_text_token


def _input_text(value: Any) -> str:
    if is_non_finite_number(value):
        return ""
    text = safe_text(value).strip()
    return "" if is_missing_text_token(text) else text


def first_value_by_key_fragment(values: dict, fragment: str) -> Any:
    for key, value in values.items():
        if fragment in _input_text(key):
            return value
    return None


def first_price(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or is_non_finite_number(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        prices = extract_price_numbers(_input_text(value))
    except (TypeError, ValueError):
        return None
    price = float(prices[0]) if prices else None
    return None if is_non_finite_number(price) else price


def confidence_score(recommendation: dict) -> float | None:
    return _confidence_score(recommendation, text_for_key=_input_text)


def upside_pct(target_price: float, current_price: float) -> float:
    if current_price <= 0:
        return 0.0
    return (target_price - current_price) / current_price * 100


__all__ = ("confidence_score", "first_price", "first_value_by_key_fragment", "main_target_price",
           "target_price_candidates", "upside_pct")
