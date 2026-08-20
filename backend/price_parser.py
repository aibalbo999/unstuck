"""Currency and target-price parsing helpers."""
from __future__ import annotations

import math
import re
import unicodedata

from price_parser_patterns import *  # noqa: F403,F401

def parse_price_number(raw: str) -> float:
    return float(str(raw).replace(",", "").replace("，", "").replace("．", "."))
def _ordered_unique_tokens(matches: list[tuple[int, int, str]]) -> list[str]:
    unique = []
    seen_spans = set()
    for start, end, token in sorted(matches, key=lambda item: (item[0], item[1])):
        if token and (start, end) not in seen_spans:
            seen_spans.add((start, end))
            unique.append(token)
    return unique
def _remove_negative_price_tokens(text: str) -> str:
    source = str(text or "")
    def replacement(match: re.Match) -> str:
        prefix = source[:match.start()].rstrip()
        if prefix and prefix[-1].isdigit():
            return match.group(0)
        if len(prefix) >= 2 and prefix[-1] in {"元", "塊"} and prefix[-2].isdigit():
            return match.group(0)
        return ""
    return NEGATIVE_TARGET_PRICE_TOKEN_PATTERN.sub(replacement, source)
def _target_marker_context(text: str) -> str:
    price_marker_matches = list(PRICE_SPECIFIC_TARGET_MARKER_PATTERN.finditer(text))
    if price_marker_matches:
        return text[price_marker_matches[0].start():]
    marker_matches = list(TARGET_PRICE_MARKER_PATTERN.finditer(text))
    return text[marker_matches[0].start():] if marker_matches else text
def _long_term_target_context(text: str) -> str | None:
    for segment in TARGET_CONTEXT_SEGMENT_SEPARATOR_PATTERN.split(str(text or "")):
        if not LONG_TERM_TARGET_HORIZON_PATTERN.search(segment):
            continue
        if TARGET_PRICE_MARKER_PATTERN.search(segment):
            return _target_marker_context(segment.strip())
    return None


def _fast_explicit_target_price_values(text: str) -> list[float] | None:
    """Read an unambiguous target value before expensive metric filters."""
    for marker in reversed(tuple(PRICE_SPECIFIC_TARGET_MARKER_PATTERN.finditer(text))):
        if text[:marker.start()].strip():
            continue
        segment = _EXPLICIT_TARGET_PRICE_SEGMENT_SEPARATOR_PATTERN.split(text[marker.start():], maxsplit=1)[0]
        if (
            TARGET_PRICE_ADJUSTMENT_DELTA_PATTERN.search(segment)
            or TARGET_PRICE_PRE_MARKER_ADJUSTMENT_DELTA_PATTERN.search(text)
            or TARGET_PRICE_REVISION_TO_PATTERN.search(text)
        ):
            continue
        prefix_match = _EXPLICIT_TARGET_PRICE_DIRECT_PREFIX_PATTERN.match(segment)
        if not prefix_match:
            continue
        remainder = segment[prefix_match.end():].lstrip()
        if re.match(r"[A-Za-z]", remainder) and not re.match(
            r"(?:NT\$?|NTD|TWD|US\$|USD|HK\$|\$)(?![A-Za-z])", remainder, re.IGNORECASE
        ):
            continue
        if not (
            _EXPLICIT_TARGET_PRICE_CURRENCY_OR_UNIT_PATTERN.search(segment)
            or _EXPLICIT_TARGET_PRICE_RANGE_PATTERN.search(segment)
        ):
            continue
        prices = extract_price_numbers(segment)
        if not prices:
            continue
        if _EXPLICIT_TARGET_PRICE_RANGE_PATTERN.search(segment):
            return prices[:2]
        return prices[:1]
    return None
def extract_price_numbers(text: str) -> list[float]:
    """Extract currency-like prices while preserving thousands separators."""
    scientific, thousands_separator, decimal_separator, range_separator = r"(?:[eE][-+]?\d+)?", r"[,，]", r"[.．]", r"(?:-|–|—|－|−|~|～|〜|至|到|\bto\b)"
    number_pattern = (
        rf"\d{{1,3}}(?:{thousands_separator}\d{{3}})+(?:{decimal_separator}\d+)?{scientific}"
        rf"|\d+(?:{decimal_separator}\d+)?{scientific}"
    )
    currency_token, positive_sign, target_range_separator, target_context = CURRENCY_TOKEN_PATTERN, r"(?:[+＋]\s*)?", rf"(?:{range_separator}|\band\b|與|和)", r"(?:目標股價|目標價|合理價|目標|price\s+target(?:\s+range)?|target(?:\s+price)?(?:\s+range)?)"
    currency_pattern = (
        rf"{currency_token}\s*{positive_sign}({number_pattern})(?:\s*(?:元|塊))?"
        rf"|{positive_sign}({number_pattern})\s*(?:元|塊)"
    )
    currency_range_pattern = (
        rf"{currency_token}\s*{positive_sign}({number_pattern})\s*{range_separator}\s*"
        rf"(?:{currency_token}\s*)?{positive_sign}({number_pattern})(?:\s*(?:元|塊))?"
    )
    right_currency_range_pattern = (
        rf"{positive_sign}({number_pattern})\s*{range_separator}\s*"
        rf"{currency_token}\s*{positive_sign}({number_pattern})(?:\s*(?:元|塊))?"
    )
    unit_range_pattern = (
        rf"{positive_sign}({number_pattern})\s*(?:元|塊)\s*{range_separator}\s*"
        rf"(?:{currency_token}\s*)?{positive_sign}({number_pattern})(?:\s*(?:元|塊))?"
        rf"|{positive_sign}({number_pattern})(?:\s*(?:元|塊))?\s*{range_separator}\s*"
        rf"(?:{currency_token}\s*)?{positive_sign}({number_pattern})\s*(?:元|塊)"
    )
    target_context_range_pattern = (
        rf"{target_context}[^\d]{{0,12}}"
        rf"{positive_sign}({number_pattern})\s*{target_range_separator}\s*"
        rf"(?:{currency_token}\s*)?{positive_sign}({number_pattern})(?:\s*(?:元|塊))?"
    )
    currency_matches: list[tuple[int, int, str]] = []
    for match in re.finditer(currency_pattern, text or "", flags=re.IGNORECASE):
        group_index = 1 if match.group(1) else 2
        currency_matches.append((match.start(group_index), match.end(group_index), match.group(group_index)))
    for match in re.finditer(currency_range_pattern, text or "", flags=re.IGNORECASE):
        for group_index in (1, 2):
            currency_matches.append((match.start(group_index), match.end(group_index), match.group(group_index)))
    for match in re.finditer(right_currency_range_pattern, text or "", flags=re.IGNORECASE):
        for group_index in (1, 2):
            currency_matches.append((match.start(group_index), match.end(group_index), match.group(group_index)))
    for match in re.finditer(unit_range_pattern, text or "", flags=re.IGNORECASE):
        for group_index in (1, 2, 3, 4):
            if match.group(group_index):
                currency_matches.append((match.start(group_index), match.end(group_index), match.group(group_index)))
    for match in re.finditer(target_context_range_pattern, text or "", flags=re.IGNORECASE):
        for group_index in (1, 2):
            currency_matches.append((match.start(group_index), match.end(group_index), match.group(group_index)))
    matches = _ordered_unique_tokens(currency_matches) or re.findall(number_pattern, text or "")
    prices = []
    for match in matches:
        price = parse_price_number(match)
        if math.isfinite(price):
            prices.append(price)
    return prices
def extract_target_price_numbers(text: str) -> list[float]:
    """Extract prices from target-price wording without treating horizon labels as prices."""
    normalized_text = unicodedata.normalize("NFKC", str(text or ""))
    cleaned = re.sub(PERCENT_NUMBER_PATTERN, "", normalized_text)
    if HORIZON_ONLY_PATTERN.match(cleaned):
        return []
    explicit_target_prices = _fast_explicit_target_price_values(cleaned)
    if explicit_target_prices is not None:
        return [price for price in explicit_target_prices if price > 0]
    has_price_specific_marker = PRICE_SPECIFIC_TARGET_MARKER_PATTERN.search(cleaned)
    if not has_price_specific_marker:
        if QUALITY_SERVICE_TIME_TO_METRIC_FAST_VALUE_PATTERN.search(cleaned):
            return []
        if QUALITY_SERVICE_QUEUE_METRIC_FAST_VALUE_PATTERN.search(cleaned):
            return []
        if QUALITY_SERVICE_TIME_TO_METRIC_PATTERN.search(cleaned) or QUALITY_SERVICE_TIME_TO_METRIC_PERMUTATION_PATTERN.search(cleaned) or QUALITY_SERVICE_QUEUE_METRIC_PATTERN.search(cleaned):
            return []
    cleaned = RISK_REWARD_RATIO_PATTERN.sub("", cleaned)
    if NON_PRICE_TARGET_METRIC_PATTERN.search(cleaned) and not has_price_specific_marker:
        return []
    if NON_PRICE_TARGET_METRIC_VALUE_PATTERN.search(cleaned) and not has_price_specific_marker:
        return []
    if NON_PRICE_METRIC_TARGET_PATTERN.search(cleaned) and not has_price_specific_marker:
        return []
    cleaned = PEOPLE_COMPLIANCE_ACKNOWLEDGMENT_TARGET_VALUE_PATTERN.sub("", NON_PRICE_METRIC_VALUE_PATTERN.sub("", QUALITY_SERVICE_QUEUE_METRIC_VALUE_PATTERN.sub("", QUALITY_SERVICE_TIME_TO_METRIC_PERMUTATION_VALUE_PATTERN.sub("", QUALITY_SERVICE_TIME_TO_METRIC_VALUE_PATTERN.sub("", cleaned)))))
    preferred_context = _long_term_target_context(cleaned)
    price_marker_matches, marker_matches = list(PRICE_SPECIFIC_TARGET_MARKER_PATTERN.finditer(cleaned)), list(TARGET_PRICE_MARKER_PATTERN.finditer(cleaned))
    if preferred_context:
        context = preferred_context
    elif price_marker_matches:
        context = cleaned[price_marker_matches[-1].start():]
    else:
        context = cleaned[marker_matches[-1].start():] if marker_matches else cleaned
    context = PEOPLE_COMPLIANCE_ACKNOWLEDGMENT_TARGET_VALUE_PATTERN.sub("", NON_PRICE_METRIC_VALUE_PATTERN.sub("", QUALITY_SERVICE_QUEUE_METRIC_VALUE_PATTERN.sub("", context)))
    context = RISK_REWARD_RATIO_PATTERN.sub("", VALUATION_MULTIPLE_VALUE_PATTERN.sub("", NON_PRICE_TARGET_METRIC_VALUE_PATTERN.sub("", context)))
    cleaned = RISK_REWARD_RATIO_PATTERN.sub("", VALUATION_MULTIPLE_VALUE_PATTERN.sub("", NON_PRICE_TARGET_METRIC_VALUE_PATTERN.sub("", cleaned)))
    revision_match = TARGET_PRICE_REVISION_TO_PATTERN.search(cleaned) or TARGET_PRICE_REVISION_TO_PATTERN.search(context)
    if revision_match:
        context = cleaned = revision_match.group("target")
    elif TARGET_PRICE_ADJUSTMENT_DELTA_PATTERN.search(context) or TARGET_PRICE_PRE_MARKER_ADJUSTMENT_DELTA_PATTERN.search(cleaned):
        return []
    context, cleaned = _remove_negative_price_tokens(context), _remove_negative_price_tokens(cleaned); return [price for price in (extract_price_numbers(context) or extract_price_numbers(cleaned)) if price > 0]
QUALITY_SERVICE_TIME_TO_METRIC_PERMUTATION_PATTERN = re.compile(rf"time\s+to\s+(?:renew|issue|verify|schedule|complete|attend|validate|certify)\s+(?=(?:validation|recertification|attendance|renewal|certification)(?:\s+(?:validation|recertification|attendance|renewal|certification)){{4}}\s+(?:target|forecast|actual|baseline|current)\b)(?=(?:(?:validation|recertification|attendance|renewal|certification)\s+){{0,4}}validation\b)(?=(?:(?:validation|recertification|attendance|renewal|certification)\s+){{0,4}}recertification\b)(?=(?:(?:validation|recertification|attendance|renewal|certification)\s+){{0,4}}attendance\b)(?=(?:(?:validation|recertification|attendance|renewal|certification)\s+){{0,4}}renewal\b)(?=(?:(?:validation|recertification|attendance|renewal|certification)\s+){{0,4}}certification\b)(?:validation|recertification|attendance|renewal|certification)(?:\s+(?:validation|recertification|attendance|renewal|certification)){{4}}", re.IGNORECASE); QUALITY_SERVICE_TIME_TO_METRIC_PERMUTATION_VALUE_PATTERN = re.compile(rf"{QUALITY_SERVICE_TIME_TO_METRIC_PERMUTATION_PATTERN.pattern}\s+(?:target|forecast|actual|baseline|current)\s*{TARGET_NUMBER_PATTERN}", re.IGNORECASE); QUALITY_SERVICE_QUEUE_METRIC_PATTERN = re.compile(r"\b(?:queue\s+(?:items?|reviews?)|work\s+queue)\s+(?:target|forecast|actual|baseline|current)\b", re.IGNORECASE); QUALITY_SERVICE_QUEUE_METRIC_VALUE_PATTERN = re.compile(rf"{QUALITY_SERVICE_QUEUE_METRIC_PATTERN.pattern}\s*{TARGET_NUMBER_PATTERN}", re.IGNORECASE); _parse_price_number, _extract_price_numbers, _extract_target_price_numbers = parse_price_number, extract_price_numbers, extract_target_price_numbers
