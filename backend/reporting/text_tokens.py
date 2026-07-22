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


__all__ = ["is_missing_text_token"]
