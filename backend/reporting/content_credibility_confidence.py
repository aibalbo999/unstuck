"""Confidence-score extraction for content credibility checks."""

from __future__ import annotations

from confidence_score_parser import parse_confidence_score_text


def confidence_score(recommendation: dict, *, text_for_key) -> float | None:
    value = _first_value_by_key_fragment(recommendation, "信心", text_for_key)
    return parse_confidence_score_text(text_for_key(value)) if value is not None else None


def _first_value_by_key_fragment(values: dict, fragment: str, text_for_key) -> object:
    for key, value in values.items():
        if fragment in text_for_key(key):
            return value
    return None


__all__ = ("confidence_score",)
