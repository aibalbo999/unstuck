"""JSON-safe chart payload shaping for HTML reports."""

from __future__ import annotations

import math
import re

from mapping_fields import safe_mapping_dict, safe_mapping_items, safe_sequence_items, safe_text

from .chart_values import filter_future_price_history
from .html_sanitizer import sanitize_report_plain_text
from .text_tokens import is_missing_text_token


CHART_NUMERIC_TOKEN_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


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
        label_text = _unique_chart_label(bands, _chart_text(label), "估值通道")
        bands[label_text] = chart_number_series(series)
    payload["bands"] = bands

    for key in ("eps_twd", "eps", "multiples"):
        if key in value:
            payload[key] = chart_number_series(value.get(key))
    return payload


def _chart_text(value) -> str:
    text = sanitize_report_plain_text(safe_text(value)).strip()
    if is_missing_text_token(text):
        return ""
    return text


def _unique_chart_label(existing: dict, label: str, fallback: str) -> str:
    base = label or fallback
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base} {suffix}"
        suffix += 1
    return candidate


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
            tokens = CHART_NUMERIC_TOKEN_RE.findall(text)
            if len(tokens) != 1:
                return None
            try:
                number = float(tokens[0])
            except ValueError:
                return None
    number *= scale
    if not math.isfinite(number):
        return None
    return round(number, 4)
