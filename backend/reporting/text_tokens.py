"""Shared report text token guards."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text


MISSING_TEXT_TOKENS = {
    "N/A",
    "NA",
    "NONE",
    "NULL",
    "NIL",
    "MISSING",
    "-",
    "--",
    "NAN",
    "INF",
    "+INF",
    "-INF",
    "INFINITY",
    "+INFINITY",
    "-INFINITY",
}


def is_missing_text_token(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = safe_text(value).strip()
    return not text or text.upper() in MISSING_TEXT_TOKENS


def first_non_missing_text(*values: Any) -> str:
    for value in values:
        text = safe_text(value).strip()
        if text and not is_missing_text_token(text):
            return text
    return ""


__all__ = ["first_non_missing_text", "is_missing_text_token"]
