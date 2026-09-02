"""Strict text decoding for report artifacts."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text


def decode_utf8_artifact_text(content: Any) -> str | None:
    """Return readable artifact text without replacing undecodable bytes."""
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray, memoryview)):
        try:
            return bytes(content).decode("utf-8")
        except UnicodeDecodeError:
            return None
    return safe_text(content)


__all__ = ["decode_utf8_artifact_text"]
