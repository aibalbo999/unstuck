"""Parse confidence score text into a normalized 0-10 score."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from confidence_score_tokens import confidence_token as _confidence_token
from confidence_score_tokens import midpoint as _midpoint
from confidence_score_tokens import normalize_score as _normalize_score
from confidence_score_tokens import numeric_token as _numeric_token
from confidence_score_tokens import ratio_score as _ratio_score
from confidence_score_tokens import ratio_score_with_half as _ratio_score_with_half
from confidence_score_tokens import tenths_token as _tenths_token
from numeric_safety import is_non_finite_number
from price_parser import extract_price_numbers


CHINESE_SCORE_TOKEN_CHARS = "零一二兩三四五六七八九十"
CHINESE_SCORE_TOKEN_PATTERN = rf"[{CHINESE_SCORE_TOKEN_CHARS}](?:\s*[點点.．]\s*[{CHINESE_SCORE_TOKEN_CHARS}])?"
CHINESE_NUMBER_TOKEN_CHARS = f"{CHINESE_SCORE_TOKEN_CHARS}百"
CHINESE_NUMBER_TOKEN_PATTERN = rf"[{CHINESE_NUMBER_TOKEN_CHARS}]+(?:\s*[點点.．]\s*[{CHINESE_SCORE_TOKEN_CHARS}]+)?"
NUMERIC_SCORE_TOKEN_PATTERN = r"\d+(?:\s*[.．點点]\s*\d+)?"
CONFIDENCE_TOKEN_PATTERN = rf"(?:{CHINESE_NUMBER_TOKEN_PATTERN}|{NUMERIC_SCORE_TOKEN_PATTERN})"
TENTHS_SCORE_TOKEN_PATTERN = rf"(?:{CHINESE_SCORE_TOKEN_PATTERN}|{NUMERIC_SCORE_TOKEN_PATTERN})"
UNITLESS_DECIMAL_TOKEN_PATTERN = (
    rf"(?:[{CHINESE_SCORE_TOKEN_CHARS}]+|\d+)\s*[點点.．]\s*(?:[{CHINESE_SCORE_TOKEN_CHARS}]+|\d+)"
)
CHINESE_TENTHS_PATTERN = rf"({TENTHS_SCORE_TOKEN_PATTERN})\s*成\s*([半五0-9０-９])?"
RANGE_SEPARATOR_PATTERN = r"(?:-|–|—|－|−|~|～|〜|至|到|、)"
RATIO_CONFIDENCE_PATTERN = (
    rf"({CONFIDENCE_TOKEN_PATTERN})\s*(?:分|星|顆星|顆)?\s*(半)?\s*"
    rf"(?:[/／]|[oO]ut\s+[oO]f|[oO]f|滿分)\s*({CONFIDENCE_TOKEN_PATTERN})"
)
SCALE_CONFIDENCE_PATTERN = (
    rf"({CONFIDENCE_TOKEN_PATTERN})\s*(?:分|星|顆星|顆)\s*(?:制|給|给)\s*"
    rf"({CONFIDENCE_TOKEN_PATTERN})\s*(?:分|星|顆星|顆)?\s*(半)?"
)
RATIO_CONFIDENCE_RANGE_PATTERN = (
    rf"({NUMERIC_SCORE_TOKEN_PATTERN})\s*[/／]\s*({NUMERIC_SCORE_TOKEN_PATTERN})\s*{RANGE_SEPARATOR_PATTERN}\s*"
    rf"({NUMERIC_SCORE_TOKEN_PATTERN})\s*[/／]\s*({NUMERIC_SCORE_TOKEN_PATTERN})"
)
RATIO_CONFIDENCE_COMPACT_RANGE_PATTERN = (
    rf"({NUMERIC_SCORE_TOKEN_PATTERN})\s*{RANGE_SEPARATOR_PATTERN}\s*"
    rf"({NUMERIC_SCORE_TOKEN_PATTERN})\s*[/／]\s*({NUMERIC_SCORE_TOKEN_PATTERN})"
)
PERCENT_CONFIDENCE_PATTERN = rf"({NUMERIC_SCORE_TOKEN_PATTERN})\s*[%％]"
PERCENT_CONFIDENCE_RANGE_PATTERN = (
    rf"({NUMERIC_SCORE_TOKEN_PATTERN})\s*[%％]?\s*{RANGE_SEPARATOR_PATTERN}\s*"
    rf"({NUMERIC_SCORE_TOKEN_PATTERN})\s*[%％]"
)
TEN_DENOMINATOR_CONFIDENCE_PATTERN = rf"(?:十分之|10\s*分之|１０\s*分之)\s*({CONFIDENCE_TOKEN_PATTERN})"
HUNDRED_DENOMINATOR_CONFIDENCE_PATTERN = rf"百分(?:之)?\s*({CONFIDENCE_TOKEN_PATTERN})"
DENOMINATOR_FIRST_CONFIDENCE_PATTERN = rf"({CONFIDENCE_TOKEN_PATTERN})\s*分之\s*({CONFIDENCE_TOKEN_PATTERN})"
OUT_OF_TEN_CONFIDENCE_PATTERN = rf"(?:10|１０|十)\s*分?\s*(?:中|內給|内给|給|给)\s*({CONFIDENCE_TOKEN_PATTERN})"
CHINESE_TENTHS_RANGE_PATTERN = (
    rf"({TENTHS_SCORE_TOKEN_PATTERN})\s*成\s*([半五0-9０-９])?\s*"
    rf"{RANGE_SEPARATOR_PATTERN}\s*({TENTHS_SCORE_TOKEN_PATTERN})\s*成\s*([半五0-9０-９])?"
)
CHINESE_TENTHS_COMPACT_RANGE_PATTERN = (
    rf"({TENTHS_SCORE_TOKEN_PATTERN})\s*([半五0-9０-９])?\s*"
    rf"{RANGE_SEPARATOR_PATTERN}\s*({TENTHS_SCORE_TOKEN_PATTERN})\s*成\s*([半五0-9０-９])?"
)
CHINESE_TENTHS_ADJACENT_RANGE_PATTERN = r"([零一二兩三四五六七八九])\s*([一二兩三四五六七八九十])\s*成"
CHINESE_POINT_CONFIDENCE_PATTERN = (
    rf"(信心(?:指數|分數)?|評分|分數|給分|給予|給)"
    rf"([^{CHINESE_SCORE_TOKEN_CHARS}]{{0,12}})({CHINESE_SCORE_TOKEN_PATTERN})\s*分\s*(半)?"
)
CHINESE_POINT_CONFIDENCE_RANGE_PATTERN = (
    rf"(信心(?:指數|分數)?|評分|分數|給分|給予|給)?"
    rf"([^{CHINESE_SCORE_TOKEN_CHARS}]{{0,12}})({CHINESE_SCORE_TOKEN_PATTERN})\s*分\s*(半)?\s*"
    rf"{RANGE_SEPARATOR_PATTERN}\s*({CHINESE_SCORE_TOKEN_PATTERN})\s*分\s*(半)?"
)
CHINESE_POINT_COMPACT_RANGE_PATTERN = (
    rf"(信心(?:指數|分數)?|評分|分數|給分|給予|給)?"
    rf"([^{CHINESE_SCORE_TOKEN_CHARS}]{{0,12}})({CHINESE_SCORE_TOKEN_PATTERN})\s*"
    rf"{RANGE_SEPARATOR_PATTERN}\s*({CHINESE_SCORE_TOKEN_PATTERN})\s*分\s*(半)?"
)
LABELED_POINT_CONFIDENCE_PATTERN = (
    r"(信心(?:指數|分數)?|評分|分數|給分|給予|給)"
    rf"([^0-9０-９.．點点]{{0,12}})({NUMERIC_SCORE_TOKEN_PATTERN})\s*分\s*(半)?"
)
LABELED_POINT_CONFIDENCE_RANGE_PATTERN = (
    rf"(信心(?:指數|分數)?|評分|分數|給分|給予|給)?"
    rf"([^0-9０-９.．點点]{{0,12}})({NUMERIC_SCORE_TOKEN_PATTERN})\s*分\s*(半)?\s*"
    rf"{RANGE_SEPARATOR_PATTERN}\s*({NUMERIC_SCORE_TOKEN_PATTERN})\s*分\s*(半)?"
)
LABELED_POINT_COMPACT_RANGE_PATTERN = (
    rf"(信心(?:指數|分數)?|評分|分數|給分|給予|給)?"
    rf"([^0-9０-９.．點点]{{0,12}})({NUMERIC_SCORE_TOKEN_PATTERN})\s*"
    rf"{RANGE_SEPARATOR_PATTERN}\s*({NUMERIC_SCORE_TOKEN_PATTERN})\s*分\s*(半)?"
)
POINT_UNIT_CONFIDENCE_PATTERN = rf"({TENTHS_SCORE_TOKEN_PATTERN})\s*分\s*(半)?"
UNITLESS_DECIMAL_CONFIDENCE_PATTERN = (
    rf"(?:^|[，,、；;。:：\s]|信心(?:指數|分數)?|評分|分數|給分|給予|給|約為|約莫|大約|約|為|为|是)"
    rf"({UNITLESS_DECIMAL_TOKEN_PATTERN})(?:$|[，,、；;。:：\s])"
)


def parse_confidence_score_text(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or is_non_finite_number(value):
        return None
    if isinstance(value, (int, float)):
        return _normalize_score(float(value))
    text = str(value or "")
    range_score = _range_confidence(text)
    if range_score is not None:
        return range_score
    ratio_score = _ratio_confidence(text)
    if ratio_score is not None:
        return ratio_score
    scale_score = _scale_confidence(text)
    if scale_score is not None:
        return scale_score
    percent_score = _percent_confidence(text)
    if percent_score is not None:
        return percent_score
    denominator_score = _denominator_confidence(text)
    if denominator_score is not None:
        return denominator_score
    out_of_ten_score = _out_of_ten_confidence(text)
    if out_of_ten_score is not None:
        return out_of_ten_score
    chinese_score = _chinese_tenths_confidence(text)
    if chinese_score is not None:
        return chinese_score
    chinese_point_score = _chinese_point_confidence(text)
    if chinese_point_score is not None:
        return chinese_point_score
    labeled_score = _labeled_point_confidence(text)
    if labeled_score is not None:
        return labeled_score
    point_unit_score = _point_unit_confidence(text)
    if point_unit_score is not None:
        return point_unit_score
    unitless_decimal_score = _unitless_decimal_confidence(text)
    if unitless_decimal_score is not None:
        return unitless_decimal_score
    try:
        numbers = extract_price_numbers(text)
    except (TypeError, ValueError):
        return None
    if not numbers:
        return None
    return _normalize_score(float(numbers[0]))


def _range_confidence(text: str) -> float | None:
    return (
        _ratio_confidence_range(text)
        or _percent_confidence_range(text)
        or _chinese_tenths_confidence_range(text)
        or _chinese_point_confidence_range(text)
        or _labeled_point_confidence_range(text)
    )


def _ratio_confidence_range(text: str) -> float | None:
    match = re.search(RATIO_CONFIDENCE_RANGE_PATTERN, text)
    if match:
        left = _ratio_score(match.group(1), match.group(2))
        right = _ratio_score(match.group(3), match.group(4))
        return _midpoint(left, right)

    match = re.search(RATIO_CONFIDENCE_COMPACT_RANGE_PATTERN, text)
    if not match:
        return None
    denominator = match.group(3)
    left = _ratio_score(match.group(1), denominator)
    right = _ratio_score(match.group(2), denominator)
    return _midpoint(left, right)


def _ratio_confidence(text: str) -> float | None:
    match = re.search(RATIO_CONFIDENCE_PATTERN, text)
    if not match:
        return None
    return _ratio_score_with_half(match.group(1), match.group(2), match.group(3))


def _scale_confidence(text: str) -> float | None:
    match = re.search(SCALE_CONFIDENCE_PATTERN, text)
    return _ratio_score_with_half(match.group(2), match.group(3), match.group(1)) if match else None


def _percent_confidence_range(text: str) -> float | None:
    match = re.search(PERCENT_CONFIDENCE_RANGE_PATTERN, text)
    if not match:
        return None
    return _midpoint(_percent_score(match.group(1)), _percent_score(match.group(2)))


def _percent_confidence(text: str) -> float | None:
    match = re.search(PERCENT_CONFIDENCE_PATTERN, text)
    if not match:
        return None
    return _percent_score(match.group(1))


def _percent_score(value: str) -> float:
    score = _numeric_token(value)
    return min(10.0, round(score / 10, 2))


def _denominator_confidence(text: str) -> float | None:
    match = re.search(TEN_DENOMINATOR_CONFIDENCE_PATTERN, text)
    if match:
        return _ratio_score(str(_confidence_token(match.group(1))), "10")

    match = re.search(HUNDRED_DENOMINATOR_CONFIDENCE_PATTERN, text)
    if match:
        return _ratio_score(str(_confidence_token(match.group(1))), "100")

    match = re.search(DENOMINATOR_FIRST_CONFIDENCE_PATTERN, text)
    if not match:
        return None
    return _ratio_score(match.group(2), match.group(1))


def _out_of_ten_confidence(text: str) -> float | None:
    match = re.search(OUT_OF_TEN_CONFIDENCE_PATTERN, text)
    if not match:
        return None
    return _ratio_score(str(_confidence_token(match.group(1))), "10")


def _chinese_tenths_confidence_range(text: str) -> float | None:
    for pattern in (CHINESE_TENTHS_RANGE_PATTERN, CHINESE_TENTHS_COMPACT_RANGE_PATTERN):
        match = re.search(pattern, text)
        if not match:
            continue
        left = _tenths_score(match.group(1), match.group(2))
        right = _tenths_score(match.group(3), match.group(4))
        return _midpoint(left, right)
    adjacent_match = re.search(CHINESE_TENTHS_ADJACENT_RANGE_PATTERN, text)
    if adjacent_match:
        left = _tenths_score(adjacent_match.group(1), None)
        right = _tenths_score(adjacent_match.group(2), None)
        return _midpoint(left, right)
    return None


def _chinese_tenths_confidence(text: str) -> float | None:
    match = re.search(CHINESE_TENTHS_PATTERN, text)
    if not match:
        return None
    return _tenths_score(match.group(1), match.group(2))


def _tenths_score(token: str, suffix_token: str | None) -> float | None:
    score = _tenths_token(token)
    suffix = _tenths_token(suffix_token)
    return score + 0.5 if score is not None and suffix == 5.0 and score < 10 else score


def _chinese_point_confidence(text: str) -> float | None:
    for match in re.finditer(CHINESE_POINT_CONFIDENCE_PATTERN, text):
        if "滿分" in match.group(2):
            continue
        return _point_score(match.group(3), match.group(4))
    return None


def _chinese_point_confidence_range(text: str) -> float | None:
    match = re.search(CHINESE_POINT_CONFIDENCE_RANGE_PATTERN, text)
    if match is not None and "滿分" not in match.group(2):
        left = _point_score(match.group(3), match.group(4))
        right = _point_score(match.group(5), match.group(6))
        return _midpoint(left, right)

    match = re.search(CHINESE_POINT_COMPACT_RANGE_PATTERN, text)
    if match is not None and "滿分" not in match.group(2):
        left = _point_score(match.group(3))
        right = _point_score(match.group(4), match.group(5))
        return _midpoint(left, right)
    return None


def _point_score(value: str, half_token: str | None = None) -> float | None:
    normalized = unicodedata.normalize("NFKC", str(value)).replace("点", "點").replace(".", "點").strip()
    if "點" in normalized:
        whole_text, decimal_text = normalized.split("點", 1)
        whole = _tenths_token(whole_text.strip())
        decimal = _tenths_token(decimal_text.strip())
        if whole is None or decimal is None:
            return None
        score = whole + decimal / 10
    else:
        score = _tenths_token(normalized.strip())
        if score is None:
            try:
                score = _numeric_token(normalized)
            except ValueError:
                return None
    if half_token and score < 10:
        score += 0.5
    return min(10.0, round(score, 2))


def _labeled_point_confidence(text: str) -> float | None:
    for match in re.finditer(LABELED_POINT_CONFIDENCE_PATTERN, text):
        if "滿分" in match.group(2):
            continue
        return _normalize_score(_numeric_token(match.group(3)) + (0.5 if match.group(4) else 0.0))
    return None


def _labeled_point_confidence_range(text: str) -> float | None:
    match = re.search(LABELED_POINT_CONFIDENCE_RANGE_PATTERN, text)
    if match is not None and "滿分" not in match.group(2):
        left = _normalize_score(_numeric_token(match.group(3)) + (0.5 if match.group(4) else 0.0))
        right = _normalize_score(_numeric_token(match.group(5)) + (0.5 if match.group(6) else 0.0))
        return _midpoint(left, right)

    match = re.search(LABELED_POINT_COMPACT_RANGE_PATTERN, text)
    if match is not None and "滿分" not in match.group(2):
        left = _normalize_score(_numeric_token(match.group(3)))
        right = _normalize_score(_numeric_token(match.group(4)) + (0.5 if match.group(5) else 0.0))
        return _midpoint(left, right)
    return None


def _point_unit_confidence(text: str) -> float | None:
    for match in re.finditer(POINT_UNIT_CONFIDENCE_PATTERN, text):
        if _is_denominator_point_match(text, match):
            continue
        return _point_score(match.group(1), match.group(2))
    return None


def _unitless_decimal_confidence(text: str) -> float | None:
    match = re.search(UNITLESS_DECIMAL_CONFIDENCE_PATTERN, text)
    if not match:
        return None
    return _normalize_score(_confidence_token(match.group(1)))


def _is_denominator_point_match(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 8) : match.start()]
    after = text[match.end() : match.end() + 4]
    before_clause = re.split(r"[，,、；;。:：\s]", before)[-1]
    after_clause = re.split(r"[，,、；;。:：\s]", after)[0]
    denominator_words = ("滿分", "满分", "總分", "总分")
    return any(word in before_clause or word in after_clause for word in denominator_words)


__all__ = ("parse_confidence_score_text",)
