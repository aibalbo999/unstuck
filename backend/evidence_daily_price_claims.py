"""Exact dated OHLC evidence hints; never fall back to a nearby close value."""

import re
from datetime import date
from typing import Any

from evidence_claim_numbers import NUMBER_IN_STRING_RE, clean_number


DAILY_DATE_RE = re.compile(r"(20\d{2})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})(?!\d)")
EXTREME_WORD = r"最高價|最低價|最高點|最低點|高點|低點|\bhigh\b|\blow\b"
DAILY_WORD = r"當日|當天|盤中|日內|daily|intraday"
DAILY_EXTREME_RE = re.compile(rf"\s*日?\s*的?\s*(?:{DAILY_WORD})?\s*({EXTREME_WORD})", re.I)


def dated_daily_extreme_path(claim: dict[str, Any]) -> tuple[str, ...] | None:
    """None delegates legacy prices; an empty tuple rejects ambiguous daily evidence."""
    label = str(claim.get("label") or "")
    price_label = any(marker in label for marker in (
        "支撐", "壓力", "高點", "低點", "最高價", "最低價", "股價", "價格",
    )) or re.search(r"\b(?:high|low|support|resistance)\b", label, re.I)
    if not price_label or str(claim.get("unit") or "").lower() not in {"", "twd", "元"}:
        return None
    text = re.sub(r"[*_`]", "", str(claim.get("raw_text") or ""))
    dates = list(DAILY_DATE_RE.finditer(text))
    if not dates:
        return None
    paired = [(day, kind) for day in dates if (kind := DAILY_EXTREME_RE.match(text, day.end()))]
    day = dates[0]
    opening = max(text.rfind("(", 0, day.start()), text.rfind("（", 0, day.start()))
    closing = re.search(r"[)）]", text[day.end():])
    reference = text[opening + 1:day.end() + closing.start()] if opening >= 0 and closing else text
    daily_kind = re.search(rf"(?:{DAILY_WORD})\s*({EXTREME_WORD})", reference, re.I)
    if "pricehistory" in reference.lower() and re.search(r"收盤|close|closing", reference, re.I):
        return None
    label_kind = re.search(EXTREME_WORD, label, re.I)
    # A high/low label may explicitly describe a close or month-end price instead.
    legacy_basis = re.search(r"收盤|close|closing|pricehistory|月底價|價格基準|52\s*(?:週|week)", text, re.I)
    if not paired and not daily_kind and (not label_kind or legacy_basis):
        return None
    if len(dates) != 1 or any(marker in text.lower() for marker in ("market_catalysts", "catalyst", "新聞", "news", "催化劑")):
        return ()
    previous = list(NUMBER_IN_STRING_RE.finditer(text[:day.start()]))
    if previous and clean_number(previous[-1].group()) != float(claim.get("reported_value") or 0):
        return ()
    try:
        day_text = date(*(int(part) for part in day.groups())).isoformat()
    except ValueError:
        return ()
    kind_text = paired[0][1].group(1) if paired else daily_kind.group(1) if daily_kind else label_kind.group()
    kind = "low" if "低" in kind_text or kind_text.lower() == "low" else "high"
    return (f"data.daily_market_data.bars[{day_text}].{kind}",)
