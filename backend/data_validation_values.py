"""Shared numeric helpers for financial validation."""

from __future__ import annotations

import math
from typing import Any


def safe_float(value: Any) -> float | None:
    if value is None or value == "N/A":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("NT$", "").replace("$", "").replace("%", "").strip()
            if not value:
                return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def relative_divergence(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1.0) * 100
