"""Exact technical evidence: no borrowing from other indicators or price plans."""

import math
import re
from datetime import date
from typing import Any

from evidence_claim_numbers import NUMBER_IN_STRING_RE, clean_number
from evidence_daily_price_claims import DAILY_DATE_RE

_SMA = re.compile(r"(?<![A-Za-z0-9_])SMA[_ ]?(\d+)(?!\d)|(?<!\d)(\d+)\s*日\s*(?:簡單移動平均線|移動平均線|均線|SMA)", re.I)
MOVING_AVERAGE_PERIOD_LIST_RE = re.compile(r"\d+(?:\s*[/／、]\s*\d+)+\s*日\s*(?:均線|移動平均線|簡單移動平均線|SMA)(?![A-Za-z])", re.I)
_OTHER_BASIS = re.compile(r"EMA|指數|volume|成交量|收盤|close|price_history|高點|低點|新聞|news|catalyst|券商|研究|factset|unavailable|n/?a\b|null|不可用|無資料", re.I)
_NON_CURRENT_BASIS = re.compile(r"昨日|前日|前期|預估|預測|假設|如果|若|目標|previous|yesterday|forecast|projected|hypothetical", re.I)
_PARTIAL_DATE = re.compile(r"(?<!\d)(?:0?[1-9]|1[0-2])\s*[/月]\s*(?:0?[1-9]|[12]\d|3[01])(?:日)?(?!\d)|(?:19|20)\d{2}\s*年")
_ASSIGNED_VALUE = re.compile(r"\s*[:：=]\s*(?:NT\$|\$|TWD)?\s*(-?\d[\d,]*(?:\.\d+)?)\s*(?:元|TWD)?(?=$|[\s,，;；>><<）)\"。])", re.I)
MACD_FIELDS = frozenset({"macd", "macd_signal", "macd_histogram"})
_MACD_KEY = re.compile(r"(?<![A-Za-z0-9_])(?:macd_signal|macd_histogram|histogram|macd)(?![A-Za-z0-9_])", re.I)


def technical_indicator_path(claim: dict[str, Any]) -> tuple[str, ...] | None:
    """Delegate only unrecognized claims; an ambiguous MACD claim stays rejected."""
    macd_path = technical_macd_path(claim)
    return technical_sma_path(claim) if macd_path is None else macd_path


def technical_macd_path(claim: dict[str, Any]) -> tuple[str, ...] | None:
    """Bind only explicit key:value assertions; MACD prose does not select a field."""
    label = str(claim.get("label") or "")
    # Markdown label cleaning removes underscores; source text keeps exact keys.
    keys = list(re.finditer(r"(?<![A-Za-z0-9_])(?:macd_?signal|macd_?histogram|histogram|macd)(?![A-Za-z0-9_])", label, re.I))
    if not keys:
        return None
    if keys[-1].end() != len(label.strip()):
        return ()
    key = keys[-1].group().lower()
    canonical = {"histogram": "macd_histogram", "macdhistogram": "macd_histogram", "macdsignal": "macd_signal"}.get(key, key)
    text = re.sub(r"[*`]", "", str(claim.get("technical_context_text") or claim.get("raw_text") or ""))
    if _OTHER_BASIS.search(text) or _NON_CURRENT_BASIS.search(text) or str(claim.get("unit") or "").lower() not in {"", "元", "twd"}:
        return ()
    dates = list(DAILY_DATE_RE.finditer(text))
    if len(dates) > 1:
        return ()
    if dates:
        try:
            observed = date(*(int(part) for part in dates[0].groups())).isoformat()
        except ValueError:
            return ()
        if observed != claim.get("_technical_as_of"):
            return ()
    if _PARTIAL_DATE.search(DAILY_DATE_RE.sub(" ", text)):
        return ()
    assignments = []
    for match in _MACD_KEY.finditer(text):
        field = "macd_histogram" if match.group().lower() == "histogram" else match.group().lower()
        tail = text[match.end():]
        if field == canonical and re.match(r"\s*[:：=]", tail):
            value = _ASSIGNED_VALUE.match(tail)
            assignments.append(clean_number(value.group(1)) if value else None)
    if len(assignments) != 1 or assignments[0] != claim.get("reported_value"):
        return ()
    return (f"data.technical_indicators.{canonical}",)


def _explicit_assignment_path(text: str, label: str, claim: dict) -> tuple[str, ...] | None:
    """Bind a named key:value pair, rather than borrowing another number on its line."""
    label = MOVING_AVERAGE_PERIOD_LIST_RE.sub(" ", label)
    label_matches = list(_SMA.finditer(label))
    if len(label_matches) != 1 or label_matches[0].end() != len(label.strip()):
        return None
    period = int(label_matches[0].group(1) or label_matches[0].group(2))
    assignments = []
    for indicator in _SMA.finditer(text):
        if int(indicator.group(1) or indicator.group(2)) == period:
            tail = text[indicator.end():]
            if re.match(r"\s*[:：=]", tail):
                value = _ASSIGNED_VALUE.match(tail)
                assignments.append(clean_number(value.group(1)) if value else None)
    if len(assignments) != 1 or assignments[0] != claim.get("reported_value"):
        return ()
    return (f"data.technical_indicators.sma_{period}",)


def technical_sma_path(claim: dict[str, Any]) -> tuple[str, ...] | None:
    """None delegates non-SMA claims; () explicitly rejects ambiguous SMA claims."""
    text = re.sub(r"[*`]", "", str(claim.get("technical_context_text") or claim.get("raw_text") or ""))
    if not re.search(r"SMA|EMA|均線|移動平均線", text, re.I):
        return None
    label = str(claim.get("label") or "")
    if not re.search(r"支撐|壓力|價格|股價|均線|SMA|EMA|support|resistance", label, re.I):
        return None
    matches = list(_SMA.finditer(text))
    if _OTHER_BASIS.search(text) or _NON_CURRENT_BASIS.search(text) or str(claim.get("unit") or "").lower() not in {"", "元", "twd"}:
        return ()
    dates = list(DAILY_DATE_RE.finditer(text))
    if len(dates) > 1:
        return ()
    if dates:
        try:
            claimed_date = date(*(int(part) for part in dates[0].groups())).isoformat()
        except ValueError:
            return ()
        if claimed_date != claim.get("_technical_as_of"):
            return ()
    if _PARTIAL_DATE.search(MOVING_AVERAGE_PERIOD_LIST_RE.sub(" ", DAILY_DATE_RE.sub(" ", text))):
        return ()  # A historical month/day without a year cannot prove the snapshot date.
    assignment = _explicit_assignment_path(text, label, claim)
    if assignment is not None:
        return assignment
    if len(matches) != 1:
        return ()
    # Remove only the identified period and optional date; exactly one price remains.
    spans = [(m.start(), m.end()) for m in matches + dates]
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + " " + text[end:]
    numbers = list(NUMBER_IN_STRING_RE.finditer(text))
    if len(numbers) != 1 or clean_number(numbers[0].group()) != claim.get("reported_value"):
        return ()
    remaining = text[:numbers[0].start()] + text[numbers[0].end():]
    remaining = remaining.replace(label, "", 1)
    remaining = re.sub(r"NT\$|TWD|元|的|[\s\W_]", "", remaining, flags=re.I)
    if remaining:
        return ()  # Additional prose is another basis, not an exact SMA assertion.
    period = int(matches[0].group(1) or matches[0].group(2))
    return (f"data.technical_indicators.sma_{period}",)


def technical_snapshot_values(value: dict) -> list[dict]:
    """Only finite, dated, available SMA/MACD scalars are canonical evidence."""
    if value.get("availability") not in {"available", "partial"} or not valid_technical_date(value.get("as_of")):
        return []
    source = value.get("source")
    if not isinstance(source, str) or source.strip().lower() in {"", "n/a", "null", "unknown", "unavailable"}:
        return []
    missing = value.get("missing_indicators", [])
    if not isinstance(missing, list):
        return []
    return [{"path": f"data.technical_indicators.{key}", "value": float(number)}
            for key, number in value.items()
            if (re.fullmatch(r"sma_\d+", key) or key in MACD_FIELDS) and key not in missing
            and isinstance(number, (int, float)) and not isinstance(number, bool)
            and math.isfinite(number) and (key in MACD_FIELDS or number > 0)]


def valid_technical_date(value: Any) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None
