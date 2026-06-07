"""Currency and target-price parsing helpers."""

from __future__ import annotations

import re


def parse_price_number(raw: str) -> float:
    return float(str(raw).replace(",", ""))


def extract_price_numbers(text: str) -> list[float]:
    """Extract currency-like prices while preserving thousands separators."""
    number_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
    currency_token = r"(?:NT\$?|NTD|TWD|US\$|USD|HK\$|\$|新台幣|臺幣|台幣)"
    currency_matches = [
        prefix_match or suffix_match
        for prefix_match, suffix_match in re.findall(
            rf"{currency_token}\s*({number_pattern})(?:\s*(?:元|塊))?|({number_pattern})\s*(?:元|塊)",
            text or "",
            flags=re.IGNORECASE,
        )
    ]
    matches = currency_matches or re.findall(number_pattern, text or "")
    return [parse_price_number(match) for match in matches]


_parse_price_number = parse_price_number
_extract_price_numbers = extract_price_numbers
