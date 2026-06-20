"""Shared numeric coercion helpers for deterministic financial tools."""

from __future__ import annotations

import math
from typing import Any, Optional


def safe_float(value: Any) -> Optional[float]:
    """Return a float for numeric-looking values, otherwise None."""
    if value is None or value == "N/A":
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("NT$", "").replace("$", "")
            cleaned = cleaned.replace("x", "").replace("%", "").strip()
            if not cleaned:
                return None
            value = cleaned
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def raw_twd_to_billion_twd(value: Any) -> Optional[float]:
    number = safe_float(value)
    if number is None:
        return None
    return round(number / 1e9, 4)


def pct_from_ratio(value: Any) -> Optional[float]:
    number = safe_float(value)
    if number is None:
        return None
    return round(number * 100, 4)
