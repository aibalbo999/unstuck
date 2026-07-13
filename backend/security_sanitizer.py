"""Small helpers for redacting secrets from API-visible text."""

from __future__ import annotations

import re


_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*([:=])\s*['\"]?[^'\"\s,;]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{10,}"),
]


def sanitize_error_message(message: object, *, max_length: int = 240) -> str | None:
    if message is None:
        return None
    try:
        text = str(message)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)\\b"):
            text = pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    if len(text) > max_length:
        return text[: max_length - 1] + "…"
    return text
