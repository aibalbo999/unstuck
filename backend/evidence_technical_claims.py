"""Exact SMA evidence: no borrowing from volume, other periods or price plans."""

import math
import re
from datetime import date
from typing import Any

from evidence_claim_numbers import NUMBER_IN_STRING_RE, clean_number
from evidence_daily_price_claims import DAILY_DATE_RE

_SMA = re.compile(r"(?<![A-Za-z0-9_])SMA[_ ]?(\d+)(?!\d)|(?<!\d)(\d+)\s*日\s*(?:簡單移動平均線|移動平均線|均線|SMA)", re.I)
_OTHER_BASIS = re.compile(r"EMA|指數|volume|成交量|收盤|close|price_history|高點|低點|新聞|news|catalyst|券商|研究|factset|unavailable|n/?a\b|null|不可用|無資料", re.I)


def technical_sma_path(claim: dict[str, Any]) -> tuple[str, ...] | None:
    """None delegates non-SMA claims; () explicitly rejects ambiguous SMA claims."""
    text = re.sub(r"[*`]", "", str(claim.get("technical_context_text") or claim.get("raw_text") or ""))
    if not re.search(r"SMA|EMA|均線|移動平均線", text, re.I):
        return None
    label = str(claim.get("label") or "")
    if not re.search(r"支撐|壓力|價格|股價|均線|SMA|EMA|support|resistance", label, re.I):
        return None
    matches = list(_SMA.finditer(text))
    if len(matches) != 1 or _OTHER_BASIS.search(text) or str(claim.get("unit") or "").lower() not in {"", "元", "twd"}:
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
    """Only finite, dated, available scalar SMA fields are canonical evidence."""
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
            if re.fullmatch(r"sma_\d+", key) and key not in missing
            and isinstance(number, (int, float)) and not isinstance(number, bool)
            and math.isfinite(number) and number > 0]


def valid_technical_date(value: Any) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None
