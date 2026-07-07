from __future__ import annotations

from typing import Any
import math
import re


def _metric(raw: Any, label: Any) -> dict[str, Any]:
    return {"value": _number(raw, _number_from_label(label)), "label": _label(label, raw)}

def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()

def _profile_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text and text.upper() not in {"N/A", "NA", "NONE", "NULL", "--", "-"}:
            return text
    return ""

def _number(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            number = float(value)
            if math.isfinite(number):
                return number
            continue
        text = str(value).strip().replace(",", "")
        if not text or text.upper() in {"N/A", "NA", "NONE", "NULL", "--", "-"}:
            continue
        text = text.replace("NT$", "").replace("$", "").replace("%", "").replace("x", "")
        try:
            number = float(text)
        except ValueError:
            continue
        if math.isfinite(number):
            return number
    return None

def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

def _number_from_label(value: Any) -> float | None:
    text = _text(value).replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None

def _int(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None

def _label(label: Any, raw: Any) -> str:
    text = _text(label)
    if text and text.upper() not in {"N/A", "NA", "NONE", "NULL"}:
        return text
    number = _number(raw)
    return "" if number is None else f"{number:g}"

def _percent_change(target: float | None, base: float | None) -> float | None:
    if target is None or base is None or base == 0:
        return None
    return round((target / base - 1) * 100, 2)

def _pct_points(*values: Any) -> float | None:
    number = _number(*values)
    if number is None:
        return None
    return round(number * 100, 2) if -1 <= number <= 1 else round(number, 2)

def _trend_return(points: list[dict[str, Any]], periods_back: int) -> float | None:
    if len(points) < 2 or periods_back <= 0:
        return None
    start_index = max(0, len(points) - 1 - periods_back)
    start = _number(points[start_index].get("price"))
    end = _number(points[-1].get("price"))
    return _percent_change(end, start)

def _percent_of(part: float | None, whole: float | None) -> float | None:
    if part is None or whole is None or whole == 0:
        return None
    return round((part / whole) * 100, 2)

def _signed_percent_label(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+.1f}%"
