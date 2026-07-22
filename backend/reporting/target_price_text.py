"""Target-price text normalization for report summaries."""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

from mapping_fields import safe_text


_PRICE_NUMERIC_TOKEN_RE = re.compile(
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)


def target_price_text(value: Any) -> str:
    if value is None or value == "" or isinstance(value, bool):
        return "N/A"
    if isinstance(value, Decimal):
        return f"NT${value:.0f}" if value.is_finite() else "N/A"
    if isinstance(value, (int, float)):
        return f"NT${value:.0f}" if math.isfinite(value) else "N/A"
    text = safe_text(value).strip()
    if not text:
        return "N/A"
    price = _single_finite_price_number(" ".join(line.strip() for line in text.splitlines() if line.strip()))
    return f"NT${price:,.0f}" if price is not None else "N/A"


def _single_finite_price_number(text: str) -> float | None:
    tokens = [match.group(0) for match in _PRICE_NUMERIC_TOKEN_RE.finditer(text.replace(",", ""))]
    if len(tokens) != 1:
        return None
    try:
        number = float(tokens[0])
    except (ArithmeticError, AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


__all__ = ["target_price_text"]
