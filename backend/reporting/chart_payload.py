"""JSON-safe chart payload shaping for HTML reports."""

from __future__ import annotations

import math
import re

from mapping_fields import safe_mapping_dict, safe_mapping_items, safe_sequence_items, safe_text

from .html_sanitizer import sanitize_report_plain_text
from .utils import filter_future_price_history


def chart_text_series(values) -> list[str]:
    return [_chart_text(value) for value in safe_sequence_items(values)]


def chart_number(value, *, scale: float = 1) -> float | None:
    return _chart_number(value, scale=scale)


def chart_number_series(values, *, scale: float = 1) -> list[float | None]:
    return [chart_number(value, scale=scale) for value in safe_sequence_items(values)]


def chart_price_history(value) -> dict:
    value = safe_mapping_dict(value) or {}
    filtered = filter_future_price_history(value)
    if not isinstance(filtered, dict):
        return {}
    dates = filtered.get("dates", [])
    prices = filtered.get("prices", [])
    date_items = safe_sequence_items(dates)
    price_items = safe_sequence_items(prices)
    if date_items or price_items:
        safe_dates = []
        safe_prices = []
        for date_value, price_value in zip(date_items, price_items):
            date_text = _chart_text(date_value)
            if not date_text:
                continue
            safe_dates.append(date_text)
            safe_prices.append(_chart_number(price_value))
        return {"dates": safe_dates, "prices": safe_prices}

    return {
        _chart_text(key): _chart_number(price)
        for key, price in safe_mapping_items(filtered)
    }


def chart_pe_river(value) -> dict:
    value = safe_mapping_dict(value)
    if value is None:
        return {}

    payload = {}
    source = _chart_text(value.get("source", ""))
    if source:
        payload["source"] = source

    payload["years"] = chart_text_series(value.get("years", []))
    bands = {}
    raw_bands = safe_mapping_dict(value.get("bands", {})) or {}
    for label, series in safe_mapping_items(raw_bands):
        bands[_chart_text(label)] = chart_number_series(series)
    payload["bands"] = bands

    for key in ("eps_twd", "eps", "multiples"):
        if key in value:
            payload[key] = chart_number_series(value.get(key))
    return payload


def _chart_text(value) -> str:
    return sanitize_report_plain_text(safe_text(value)).strip()


def _chart_number(value, *, scale: float = 1) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = safe_text(value).replace(",", "").strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            match = re.search(r"-?\d+(?:\.\d+)?", text)
            if not match:
                return None
            try:
                number = float(match.group(0))
            except ValueError:
                return None
    number *= scale
    if not math.isfinite(number):
        return None
    return round(number, 4)
