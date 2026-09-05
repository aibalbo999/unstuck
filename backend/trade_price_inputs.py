"""Pure, conservative price and percentage parsing for execution contracts."""

from __future__ import annotations

import math
import re
import unicodedata

from data_trust_values import has_value
from mapping_fields import safe_text


NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_NUMBER = re.compile(rf"(?<![A-Za-z0-9_.]){NUMBER}(?![A-Za-z0-9_.])")
_RANGE = re.compile(rf"{NUMBER}\s*(?:(?:NT\$|\$|TWD|元)\s*)?(?:[-–—－−~～至到]|\bto\b)\s*(?:(?:NT\$|\$|TWD|元)\s*)?{NUMBER}", re.I)
_DATES = re.compile(r"(?:19|20)\d{2}\s*(?:年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日號]?|[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2})|\d{1,2}\s*月\s*\d{1,2}\s*[日號]|(?<![\d.])(?:1[0-2]|0?[1-9])/(?:[12]\d|3[01]|0?[1-9])(?!\s*(?:[/.]\d|TWD|元))", re.I)
_PERIODS = re.compile(r"\d+(?:\.\d+)?(?:\s*(?:[-–—~～至到]|\bto\b)\s*\d+(?:\.\d+)?)?\s*(?:個)?(?:交易日|日|天|週|周|月|季|年|trading\s+days?|days?|weeks?|months?|quarters?|years?)(?![A-Za-z])", re.I)
_PERCENT = re.compile(r"[+\-]?\d+(?:\.\d+)?\s*%")
_MULTIPLES = re.compile(r"(?:P/?E|本益比|估值|valuation|band)\s*[:：=]?\s*\d+(?:\.\d+)?\s*(?:x|倍)?|\d+(?:\.\d+)?\s*(?:x|倍)(?:\s*(?:P/?E|本益比|估值|valuation|band))?", re.I)
_INVALID = re.compile(r"(?<![A-Za-z0-9_])(?:[+-]?(?:inf(?:inity)?|nan)|\d+(?:\.\d+)?[eE][+-]?\d+)(?![A-Za-z0-9_])", re.I)
_NEGATIVE = re.compile(r"(?<![\d.,])(?:NT\$|TWD|\$)?\s*[-−]\s*\d", re.I)
_REFERENCE = re.compile(r"[（(\[【][^）)\]】]*(?:52\s*週|52\s*week|高點|低點|壓力|支撐)[^）)\]】]*[）)\]】]", re.I)


def execution_value_missing(value) -> bool:
    text = safe_text(value).strip()
    return not has_value(text) or any(marker in text for marker in ("資料不足", "待補", "無法驗證"))


def optional_execution_text(value) -> str | None:
    """Preserve explicit zero and null through schema/coercion round trips."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return "無效數值格式"
    return safe_text(value).strip() or None


def price_contract_text(value) -> str:
    """Remove explicitly non-price tokens without borrowing unrelated numbers."""
    text = unicodedata.normalize("NFKC", safe_text(value))
    text = _REFERENCE.sub(" ", text)
    return _MULTIPLES.sub(" ", _PERCENT.sub(" ", _PERIODS.sub(" ", _DATES.sub(" ", text))))


def parse_price_range(value) -> tuple[float, float] | None:
    if isinstance(value, bool) or execution_value_missing(value):
        return None
    text = price_contract_text(value)
    if any(text[:match.start()].rstrip().endswith(("-", "−")) for match in _RANGE.finditer(text)):
        return None
    # Remove a legitimate range before checking for negative-price syntax.
    if _INVALID.search(text) or _NEGATIVE.search(_RANGE.sub(" ", text)):
        return None
    numbers = [float(match.group().replace(",", "")) for match in _NUMBER.finditer(text)]
    if not numbers or any(not math.isfinite(number) or number <= 0 for number in numbers):
        return None
    if len(numbers) > 2 or (len(numbers) == 2 and not _RANGE.search(text)):
        return None
    if len(numbers) == 2 and numbers[0] > numbers[1]:
        return None
    return min(numbers), max(numbers)


def parse_position_percentage(value) -> tuple[float, float] | None:
    text = unicodedata.normalize("NFKC", safe_text(value)).strip()
    if execution_value_missing(value):
        return None
    match = re.fullmatch(r"(?:[^\d%+\-]*?)([+\-]?\d+(?:\.\d+)?)\s*%?(?:\s*(?:-|–|~|至|到)\s*(\d+(?:\.\d+)?))?\s*%(?:[^\d%]*)", text)
    if not match:
        return None
    low, high = float(match[1]), float(match[2] or match[1])
    return (low, high) if 0 <= low <= high <= 100 else None


def parse_risk_reward(value) -> float | None:
    text = unicodedata.normalize("NFKC", safe_text(value))
    matches = list(re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)(?![\d.])", text))
    if len(matches) != 1:
        return None
    reward, risk = map(float, matches[0].groups())
    if re.search(r"風險\s*[:/]\s*(?:報酬|收益)|risk\s*[:/]\s*reward", text, re.I):
        reward, risk = risk, reward
    return reward / risk if reward > 0 and risk > 0 else None


__all__ = ["execution_value_missing", "optional_execution_text", "parse_position_percentage", "parse_price_range", "parse_risk_reward", "price_contract_text"]
