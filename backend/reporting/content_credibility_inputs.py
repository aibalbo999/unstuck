"""Input extraction helpers for content credibility checks."""

from __future__ import annotations

import re
from typing import Any

from mapping_fields import safe_text
from numeric_safety import is_non_finite_number
from price_parser import extract_price_numbers

from .content_credibility_confidence import confidence_score as _confidence_score
from .content_credibility_price_context import has_contextual_price_range, strip_contextual_reference_prices, strip_non_price_metric_tokens
from .content_credibility_target_prices import main_target_price, target_price_candidates
from .text_tokens import is_missing_text_token


_CALENDAR_DATE_PATTERN = re.compile(
    r"(?:19|20)\d{2}\s*(?:年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日號]?|[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2})"
    r"|\d{1,2}\s*[-~～]\s*\d{1,2}\s*月\s*\d{0,2}\s*[日號]?"
    r"|\d{1,2}\s*月\s*\d{1,2}\s*[日號]"
    r"|\d{1,2}\s*[-/.]\s*\d{1,2}\s*[日號]"
)
_BARE_MONTH_DAY_PATTERN = re.compile(
    r"(?<![\d.])(?:1[0-2]|0?[1-9])\s*/\s*(?:[12]\d|3[01]|0?[1-9])"
    r"(?!\s*(?:[/.]\d|[A-Za-z]))"
)
_PERIOD_NUMBER_PATTERN = re.compile(
    r"(?<![\d.,])"
    r"(?:\d+(?:[.．]\d+)?"
    r"(?:\s*(?:[-–—~～至到]|\bto\b)\s*\d+(?:[.．]\d+)?)?)"
    r"\s*(?:週|周|個月|月|年|天|日|weeks?|months?|years?|days?)(?![A-Za-z])",
    flags=re.IGNORECASE,
)
_PRICE_RANGE_PATTERN = re.compile(
    r"(?<![\d.,])\d+(?:[.,]\d+)?\s*(?:(?:NT\$|\$|TWD|元)\s*)?"
    r"(?:[-–—－−~～〜至到]|\bto\b)\s*(?:(?:NT\$|\$|TWD|元)\s*)?"
    r"\d+(?:[.,]\d+)?(?![A-Za-z])",
    flags=re.IGNORECASE,
)


def _strip_temporal_numeric_tokens(text: str) -> str:
    """Keep calendar/period labels from being mistaken for prices."""
    cleaned = _CALENDAR_DATE_PATTERN.sub(" ", text)
    cleaned = _BARE_MONTH_DAY_PATTERN.sub(" ", cleaned)
    return _PERIOD_NUMBER_PATTERN.sub(" ", re.sub(r"[+\-＋－−]?\s*\d+(?:[.．]\d+)?(?:[eE][-+]?\d+)?\s*[%％]", " ", cleaned))


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
    prices = price_candidates(value)
    return prices[0] if prices else None


def price_candidates(value: Any) -> list[float]:
    """Extract finite prices after removing calendar and horizon tokens."""
    if isinstance(value, bool) or value is None or is_non_finite_number(value):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    try:
        text = strip_non_price_metric_tokens(strip_contextual_reference_prices(_input_text(value)))
        prices = extract_price_numbers(_strip_temporal_numeric_tokens(text))
    except (TypeError, ValueError):
        return []
    return [float(price) for price in prices if not is_non_finite_number(price)]


def has_explicit_price_range(value: Any) -> bool:
    """Return whether the input contains a deliberate two-endpoint price range."""
    return bool(_PRICE_RANGE_PATTERN.search(_strip_temporal_numeric_tokens(_input_text(value))) or has_contextual_price_range(_input_text(value)))


def confidence_score(recommendation: dict) -> float | None:
    return _confidence_score(recommendation, text_for_key=_input_text)


def upside_pct(target_price: float, current_price: float) -> float:
    if current_price <= 0:
        return 0.0
    return (target_price - current_price) / current_price * 100

__all__ = ("confidence_score", "first_price", "first_value_by_key_fragment",
           "has_explicit_price_range", "main_target_price", "price_candidates",
           "target_price_candidates", "upside_pct")
