"""Cheap, shared prefilters for explicit target-price detection."""

import re

from price_parser import (
    QUALITY_SERVICE_QUEUE_METRIC_FAST_VALUE_PATTERN,
    QUALITY_SERVICE_QUEUE_METRIC_PATTERN,
    QUALITY_SERVICE_QUEUE_METRIC_VALUE_PATTERN,
    QUALITY_SERVICE_TIME_TO_METRIC_FAST_VALUE_PATTERN,
    QUALITY_SERVICE_TIME_TO_METRIC_PATTERN,
    QUALITY_SERVICE_TIME_TO_METRIC_PERMUTATION_PATTERN,
)

_DIRECT_CURRENCY_TARGET_RE = re.compile(
    r"(?:目標價|目標股價|合理價值|合理股價|合理價|price\s+target|target\s+price)"
    r"\s*(?:(?:is|at|around|about|approximately|為|約|介於|落在|between)\s*)?"
    r"(?:NT\$?|NTD|TWD|US\$|USD|HK\$|\$|新台幣|臺幣|台幣)\s*"
    r"[+＋]?\d[\d,，]*(?:[.．]\d+)?",
    re.IGNORECASE,
)
_DIRECT_TARGET_SEGMENT_SEPARATOR_RE = re.compile(r"\bwith\b|[,，;；\n]", re.IGNORECASE)
_DIRECT_TARGET_MULTI_RE = re.compile(r"(?:[/／]|或|、|熊市|基本|牛市|\bto\b|\band\b)", re.IGNORECASE)
_DIRECT_PRICE_NUMBER_RE = re.compile(r"\d[\d,，]*(?:[.．]\d+)?")


def has_fast_non_price_target(text: str, has_price_specific_target: bool) -> bool:
    if has_price_specific_target:
        return False
    return any(
        pattern.search(text)
        for pattern in (
            QUALITY_SERVICE_TIME_TO_METRIC_FAST_VALUE_PATTERN,
            QUALITY_SERVICE_QUEUE_METRIC_FAST_VALUE_PATTERN,
            QUALITY_SERVICE_QUEUE_METRIC_VALUE_PATTERN,
            QUALITY_SERVICE_TIME_TO_METRIC_PATTERN,
            QUALITY_SERVICE_TIME_TO_METRIC_PERMUTATION_PATTERN,
            QUALITY_SERVICE_QUEUE_METRIC_PATTERN,
        )
    )


def has_fast_direct_target(text: str, has_price_specific_target: bool) -> bool:
    if not has_price_specific_target:
        return False
    match = _DIRECT_CURRENCY_TARGET_RE.search(text)
    if not match or text[: match.start()].strip():
        return False
    segment = _DIRECT_TARGET_SEGMENT_SEPARATOR_RE.split(text, maxsplit=1)[0]
    return not (
        len(_DIRECT_PRICE_NUMBER_RE.findall(segment)) >= 2
        and _DIRECT_TARGET_MULTI_RE.search(segment)
    )
