"""Metric value parsing helpers for the quality funnel."""

from __future__ import annotations

import math
from typing import Any


def first_number(metrics: dict[str, Any], keys: list[str]) -> float | None:
    lower_map = {str(key).strip().lower(): value for key, value in metrics.items()}
    for key in keys:
        if key in metrics:
            value = to_number(metrics[key])
            if value is not None:
                return value
        value = to_number(lower_map.get(str(key).strip().lower()))
        if value is not None:
            return value
    return None


def to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    if not text or text in {"-", "--", "N/A", "na", "null"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.replace(",", "").replace("%", "").replace("+", "").replace("(", "").replace(")", "")
    try:
        number = float(text)
    except ValueError:
        return None
    if negative:
        number = -number
    return number if math.isfinite(number) else None


def format_metric_value(value: float, unit: str) -> str:
    if abs(value) >= 1000 and unit == "":
        text = f"{value:,.0f}"
    elif float(value).is_integer():
        text = f"{value:.0f}"
    else:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}{unit}" if unit else text
