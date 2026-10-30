"""Target-price text normalization for report summaries."""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

from mapping_fields import safe_text
from report_price_format import format_report_price


_PRICE_NUMERIC_TOKEN_RE = re.compile(
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)


def target_price_text(value: Any) -> str:
    if value is None or value == "" or isinstance(value, bool):
        return "N/A"
    if isinstance(value, Decimal):
        return format_report_price(value)
    if isinstance(value, (int, float)):
        return format_report_price(value)
    text = safe_text(value).strip()
    if not text:
        return "N/A"
    price = _single_finite_price_number(" ".join(line.strip() for line in text.splitlines() if line.strip()))
    return format_report_price(price)


def _single_finite_price_number(text: str) -> float | None:
    tokens = [match.group(0) for match in _PRICE_NUMERIC_TOKEN_RE.finditer(text.replace(",", ""))]
    if len(tokens) != 1:
        return None
    try:
        number = float(tokens[0])
    except (ArithmeticError, AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


__all__ = ["target_price_text"]
