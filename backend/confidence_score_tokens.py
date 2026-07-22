"""Normalize confidence score number tokens."""

from __future__ import annotations

import re
import unicodedata

from numeric_safety import is_non_finite_number


CHINESE_TENTHS_CONFIDENCE = {
    "零": 0.0,
    "一": 1.0,
    "二": 2.0,
    "兩": 2.0,
    "三": 3.0,
    "四": 4.0,
    "五": 5.0,
    "六": 6.0,
    "七": 7.0,
    "八": 8.0,
    "九": 9.0,
    "十": 10.0,
}


def numeric_token(value: str) -> float:
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)))
    return float(normalized.replace("．", ".").replace("點", ".").replace("点", "."))


def tenths_token(value: str | None) -> float | None:
    if not value:
        return None
    if value == "半":
        return 5.0
    if value in CHINESE_TENTHS_CONFIDENCE:
        return CHINESE_TENTHS_CONFIDENCE[value]

    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))
    normalized = normalized.replace("点", "點").replace(".", "點").replace("．", "點")
    if "點" in normalized:
        whole_text, decimal_text = normalized.split("點", 1)
        whole = tenths_token(whole_text)
        decimal = tenths_token(decimal_text)
        if whole is None or decimal is None:
            return None
        return whole + decimal / 10
    if normalized in CHINESE_TENTHS_CONFIDENCE:
        return CHINESE_TENTHS_CONFIDENCE[normalized]
    return float(normalized) if normalized.isdigit() else None


def confidence_token(value: str) -> float:
    compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)))
    numeric = compact.replace("．", ".").replace("點", ".").replace("点", ".")
    try:
        return float(numeric)
    except ValueError:
        pass

    normalized = compact.replace("点", "點").replace(".", "點").replace("．", "點")
    if "點" in normalized:
        whole_text, decimal_text = normalized.split("點", 1)
        return _chinese_integer_token(whole_text) + _chinese_integer_token(decimal_text) / 10
    return float(_chinese_integer_token(normalized))


def confidence_token_with_half(value: str, half_token: str | None = None) -> float:
    score = confidence_token(value)
    return score + 0.5 if half_token and score < 10 else score


def normalize_score(score: float) -> float | None:
    if is_non_finite_number(score):
        return None
    if 0 <= score <= 1:
        return round(score * 10, 2)
    if score > 10:
        return min(10.0, round(score / 10.0, 2))
    return round(score, 2)


def midpoint(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round((left + right) / 2, 2)


def ratio_score(numerator_text: str, denominator_text: str) -> float | None:
    try:
        numerator = confidence_token(numerator_text)
        denominator = confidence_token(denominator_text)
    except (TypeError, ValueError):
        return None
    return min(10.0, round(numerator / denominator * 10, 2)) if denominator > 0 else None


def ratio_score_with_half(numerator_text: str, half_token: str | None, denominator_text: str) -> float | None:
    try:
        numerator = confidence_token_with_half(numerator_text, half_token)
        denominator = confidence_token(denominator_text)
    except (TypeError, ValueError):
        return None
    return min(10.0, round(numerator / denominator * 10, 2)) if denominator > 0 else None


def _chinese_integer_token(value: str) -> float:
    if not value:
        return 0.0
    if value in CHINESE_TENTHS_CONFIDENCE:
        return CHINESE_TENTHS_CONFIDENCE[value]
    if value == "百":
        return 100.0
    if "百" in value:
        left, right = value.split("百", 1)
        hundreds = CHINESE_TENTHS_CONFIDENCE[left] if left else 1.0
        return hundreds * 100 + _chinese_integer_token(right)
    if "十" not in value:
        raise ValueError(f"Unsupported Chinese number token: {value}")
    left, right = value.split("十", 1)
    tens = CHINESE_TENTHS_CONFIDENCE[left] if left else 1.0
    ones = CHINESE_TENTHS_CONFIDENCE[right] if right else 0.0
    return tens * 10 + ones


__all__ = (
    "CHINESE_TENTHS_CONFIDENCE",
    "confidence_token",
    "confidence_token_with_half",
    "midpoint",
    "normalize_score",
    "numeric_token",
    "ratio_score",
    "ratio_score_with_half",
    "tenths_token",
)
