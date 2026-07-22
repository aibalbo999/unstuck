"""Detect explicit target-price fields in report context payloads."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

from mapping_fields import safe_mapping_dict, safe_mapping_items, safe_sequence_items, safe_text
from price_parser import (
    HORIZON_ONLY_PATTERN as _HORIZON_ONLY_RE,
    NON_PRICE_METRIC_TARGET_PATTERN as _NON_PRICE_METRIC_TARGET_RE,
    NON_PRICE_METRIC_VALUE_PATTERN as _NON_PRICE_METRIC_VALUE_RE,
    NON_PRICE_TARGET_METRIC_PATTERN,
    NON_PRICE_TARGET_METRIC_VALUE_PATTERN,
    PEOPLE_COMPLIANCE_ACKNOWLEDGMENT_TARGET_VALUE_PATTERN as _PEOPLE_COMPLIANCE_ACKNOWLEDGMENT_TARGET_VALUE_RE,
    RISK_REWARD_RATIO_PATTERN,
    TARGET_PRICE_ADJUSTMENT_DELTA_PATTERN as _ADJUSTMENT_DELTA_PATTERN,
    TARGET_PRICE_PRE_MARKER_ADJUSTMENT_DELTA_PATTERN as _PRE_MARKER_ADJUSTMENT_DELTA_PATTERN,
    TARGET_PRICE_REVISION_TO_PATTERN as _REVISION_TO_PATTERN,
)

_PRICE_NUMBER_PATTERN = r"\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?"
_PRICE_NUMBER_RE = re.compile(_PRICE_NUMBER_PATTERN)
_PERCENT_TOKEN_RE = re.compile(rf"[+\-]?\s*{_PRICE_NUMBER_PATTERN}\s*[%％]", re.IGNORECASE)
_MULTIPLE_TOKEN_RE = re.compile(rf"{_PRICE_NUMBER_PATTERN}\s*(?:x|X|倍)(?:\s*(?:P/?E|PE|本益比|營收|sales|revenue))?", re.IGNORECASE)
_DATE_TOKEN_RE = re.compile(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_SIGNED_PRICE_RE = re.compile(
    rf"(?:^|[^\d])(?:NT\$?|NTD|TWD|US\$|USD|HK\$|\$|新台幣|臺幣|台幣)?\s*"
    rf"([+\-]?)\s*({_PRICE_NUMBER_PATTERN})",
    re.IGNORECASE,
)
_TARGET_KEY_MARKERS = ("target_price", "price_targets", "targetprice", "目標價", "目標", "3個月", "6個月", "12個月", "1-2週目標")
_TARGET_MARKER_RE = re.compile(
    r"(?:目標價|合理價值|合理股價|合理價|參考目標|目標|price\s+target|target(?:\s+price)?)",
    re.IGNORECASE,
)
_PRICE_SPECIFIC_TARGET_RE = re.compile(r"(?:目標價|目標股價|合理價值|合理股價|合理價|(?<!gold )(?<!silver )(?<!dram )(?<!nand )(?<!memory )(?<!panel )price\s+target|target\s+price)", re.IGNORECASE)
_RANGE_PATTERN = re.compile(
    r"(?:(?<=\d)\s*(?:-|–|—|－|−|~|～|〜)\s*(?=(?:NT\$?|NTD|TWD|US\$|USD|HK\$|\$|新台幣|臺幣|台幣)?\s*\d)|(?<=\d)\s*(?:至|到)\s*(?=(?:NT\$?|NTD|TWD|US\$|USD|HK\$|\$|新台幣|臺幣|台幣)?\s*\d)|\bto\b|\band\b|(?<=\d)\s*(?:與|和)\s*(?=(?:NT\$?|NTD|TWD|US\$|USD|HK\$|\$|新台幣|臺幣|台幣)?\s*\d)|介於|between|區間|range)",
    re.IGNORECASE,
)
_MULTI_TARGET_UNCERTAINTY_PATTERN = re.compile(r"(?:[/／]|或|、|熊市|基本|牛市)")
_NON_PRICE_TARGET_METRIC_PATH_RE = re.compile(r"(?:upside|downside|return|roi|probability|confidence|score|rank|ranking|pct|報酬|上行|下行|機率|概率|信心|分數|排名|名次)", re.IGNORECASE)
_INSUFFICIENT_TEXT_MARKERS = ("資料不足", "不足", "無法", "不產生", "不提供", "未提供")
_INSUFFICIENT_NA_RE = re.compile(r"(?<![A-Za-z0-9])N/?A(?![A-Za-z0-9])", re.IGNORECASE)

def detect_explicit_target_price_fields(context: dict) -> list[str]:
    context_map = safe_mapping_dict(context) or {}
    fields: list[str] = []
    for root in ("parsed", "structured_outputs"):
        value = dict.get(context_map, root)
        fields.extend(_detect_target_prices(value, (root,)))
    return sorted(dict.fromkeys(fields))


def _detect_target_prices(value: Any, path: tuple[str, ...]) -> list[str]:
    if isinstance(value, dict):
        fields: list[str] = []
        for key, item in safe_mapping_items(value):
            key_text = safe_text(key)
            if not key_text:
                continue
            fields.extend(_detect_target_prices(item, (*path, key_text)))
        return fields
    mapping_value = safe_mapping_dict(value)
    if mapping_value is not None:
        fields = []
        for key, item in mapping_value.items():
            key_text = safe_text(key)
            if not key_text:
                continue
            fields.extend(_detect_target_prices(item, (*path, key_text)))
        return fields
    if isinstance(value, (list, tuple)):
        fields = []
        for index, item in enumerate(safe_sequence_items(value)):
            fields.extend(_detect_target_prices(item, (*path, str(index))))
        return fields
    if _is_target_path(path) and _is_explicit_price(value, path):
        return [".".join(path)]
    return []


def _is_target_path(path: tuple[str, ...]) -> bool:
    key_text = ".".join(path).lower().replace(" ", "")
    return any(marker.lower().replace(" ", "") in key_text for marker in _TARGET_KEY_MARKERS)
def _is_explicit_price(value: Any, path: tuple[str, ...]) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if _is_non_price_target_metric_path(path):
        return False
    if isinstance(value, (int, float)):
        if _is_horizon_path(path):
            return False
        return math.isfinite(float(value)) and float(value) > 0
    text = safe_text(value).strip()
    if not text:
        return False
    if _has_insufficient_marker(text):
        return False
    normalized = _normalized_number_text(text)
    if _HORIZON_ONLY_RE.match(normalized):
        return False
    if _PEOPLE_COMPLIANCE_ACKNOWLEDGMENT_TARGET_VALUE_RE.search(normalized) and not _PRICE_SPECIFIC_TARGET_RE.search(normalized):
        return False
    if _is_non_price_metric_target(normalized):
        return False
    if NON_PRICE_TARGET_METRIC_PATTERN.search(normalized) and not _PRICE_SPECIFIC_TARGET_RE.search(normalized):
        return False
    stripped_normalized = _strip_non_price_tokens(normalized)
    full_revision_tail = _revision_target_tail(stripped_normalized)
    if full_revision_tail is not None:
        if _has_range_or_multi_target(full_revision_tail):
            return False
        return bool(_positive_price_numbers(full_revision_tail))
    if _PRE_MARKER_ADJUSTMENT_DELTA_PATTERN.search(normalized):
        return False
    price_text = _strip_non_price_tokens(_target_price_context(stripped_normalized))
    revision_tail = _revision_target_tail(price_text)
    if revision_tail is not None:
        if _has_range_or_multi_target(revision_tail):
            return False
        return bool(_positive_price_numbers(revision_tail))
    if _ADJUSTMENT_DELTA_PATTERN.search(price_text):
        return False
    if _has_range_or_multi_target(price_text):
        return False
    return bool(_positive_price_numbers(price_text))


def _normalized_number_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace("，", ",").replace("−", "-").replace("－", "-")

def _has_insufficient_marker(text: str) -> bool:
    upper_text = text.upper()
    return any(marker.upper() in upper_text for marker in _INSUFFICIENT_TEXT_MARKERS) or bool(_INSUFFICIENT_NA_RE.search(text))

def _strip_non_price_tokens(text: str) -> str:
    without_dates = _DATE_TOKEN_RE.sub("", text)
    without_percent = _PERCENT_TOKEN_RE.sub("", without_dates)
    without_multiples = _MULTIPLE_TOKEN_RE.sub("", without_percent)
    without_ratios = RISK_REWARD_RATIO_PATTERN.sub("", without_multiples)
    without_people_compliance_acknowledgment = _PEOPLE_COMPLIANCE_ACKNOWLEDGMENT_TARGET_VALUE_RE.sub("", without_ratios)
    return _NON_PRICE_METRIC_VALUE_RE.sub("", NON_PRICE_TARGET_METRIC_VALUE_PATTERN.sub("", without_people_compliance_acknowledgment))


def _target_price_context(text: str) -> str:
    price_marker_matches = list(_PRICE_SPECIFIC_TARGET_RE.finditer(text))
    if price_marker_matches:
        return text[price_marker_matches[-1].start():]
    marker_matches = list(_TARGET_MARKER_RE.finditer(text))
    return text[marker_matches[-1].start():] if marker_matches else text
def _is_non_price_metric_target(text: str) -> bool:
    return bool(_NON_PRICE_METRIC_TARGET_RE.search(text)) and not _PRICE_SPECIFIC_TARGET_RE.search(text)

def _is_horizon_path(path: tuple[str, ...]) -> bool:
    key_text = ".".join(path).lower().replace(" ", "")
    return any(marker in key_text for marker in ("horizon", "timeframe", "period", "date", "期限", "期間", "日期"))

def _is_non_price_target_metric_path(path: tuple[str, ...]) -> bool:
    key_text = ".".join(path).lower().replace(" ", "_").replace("-", "_")
    return bool(_NON_PRICE_TARGET_METRIC_PATH_RE.search(key_text))

def _revision_target_tail(text: str) -> str | None:
    match = _REVISION_TO_PATTERN.search(text)
    return match.group("target") if match else None

def _has_range_or_multi_target(text: str) -> bool:
    return (
        len(_PRICE_NUMBER_RE.findall(text)) >= 2
        and (_RANGE_PATTERN.search(text) or _MULTI_TARGET_UNCERTAINTY_PATTERN.search(text))
    )


def _positive_price_numbers(text: str) -> list[float]:
    prices: list[float] = []
    for match in _SIGNED_PRICE_RE.finditer(text):
        sign, raw_number = match.group(1), match.group(2)
        if sign == "-":
            continue
        try:
            price = float(raw_number.replace(",", ""))
        except ValueError:
            continue
        if math.isfinite(price) and price > 0:
            prices.append(price)
    return prices
