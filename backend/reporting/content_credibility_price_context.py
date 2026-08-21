"""Price-context cleanup for deterministic content-credibility inputs."""

from __future__ import annotations

import re


_CONTEXT_MARKER = (
    r"(?:52\s*週|52\s*week|最高(?:價|點)?|最低(?:價|點)?|高點|低點|"
    r"壓力(?:位|區)?|支撐(?:位|區)?)"
)
_CONTEXT_MARKER_PATTERN = re.compile(_CONTEXT_MARKER, flags=re.IGNORECASE)
_REFERENCE_PRICE_PATTERN = re.compile(
    r"(?<![\d.,])\d+(?:[.,]\d+)?\s*(?:NT\$|\$|TWD|元)\s*"
    rf"(?=(?:.{{0,18}}){_CONTEXT_MARKER})",
    flags=re.IGNORECASE,
)
_PREFIXED_REFERENCE_PRICE_PATTERN = re.compile(
    rf"{_CONTEXT_MARKER}\s*\d+(?:[.,]\d+)?\s*(?:NT\$|\$|TWD|元)",
    flags=re.IGNORECASE,
)
_CONTEXTUAL_RANGE_PATTERN = re.compile(
    r"(?<![\d.,])\d+(?:[.,]\d+)?\s*(?:NT\$|\$|TWD|元)?\s*(?:至|到)\s*"
    r"(?:52\s*週\s*(?:高點|低點|最高(?:價|點)?|最低(?:價|點)?)|52\s*week\s*"
    r"(?:high|low))\s*\d+(?:[.,]\d+)?\s*(?:NT\$|\$|TWD|元)?",
    flags=re.IGNORECASE,
)
_BRACKET_PATTERN = re.compile(r"([\(（\[【])([^\)）\]】]*)([\)）\]】])")


def strip_contextual_reference_prices(text: str) -> str:
    """Remove only bracketed price references explicitly labeled as context."""
    def clean_bracket(match: re.Match[str]) -> str:
        inner = match.group(2)
        if not _CONTEXT_MARKER_PATTERN.search(inner):
            return match.group(0)
        inner = _REFERENCE_PRICE_PATTERN.sub(" ", inner)
        inner = _PREFIXED_REFERENCE_PRICE_PATTERN.sub(" ", inner)
        return f"{match.group(1)}{inner}{match.group(3)}"

    return _BRACKET_PATTERN.sub(clean_bracket, text)


def has_contextual_price_range(text: str) -> bool:
    """Recognize a range whose second endpoint carries a 52-week label."""
    return bool(_CONTEXTUAL_RANGE_PATTERN.search(text))


__all__ = ("has_contextual_price_range", "strip_contextual_reference_prices")
