"""Portable report-key validation and MIME fallback helpers."""

from __future__ import annotations

import mimetypes
from pathlib import PurePosixPath, PureWindowsPath


_STANDARD_CONTENT_TYPES = {
    ".htm": "text/html",
    ".html": "text/html",
    ".json": "application/json",
    ".markdown": "text/markdown",
    ".md": "text/markdown",
}


def normalize_report_key(key: str) -> str:
    """Return a portable relative report key or reject an unsafe path."""
    if not isinstance(key, str):
        raise TypeError("report key must be a string")
    if not key:
        raise ValueError("report key must not be empty")
    if "\\" in key:
        raise ValueError("report key must use forward slashes")
    if "\x00" in key:
        raise ValueError("report key must not contain null bytes")

    posix_path = PurePosixPath(key)
    windows_path = PureWindowsPath(key)
    if posix_path.is_absolute() or windows_path.is_absolute():
        raise ValueError("report key must be relative")
    if any(component in {".", ".."} for component in key.split("/")):
        raise ValueError("report key must not contain dot path components")

    normalized = posix_path.as_posix()
    if normalized in {"", "."}:
        raise ValueError("report key must identify a report")
    return normalized


def validate_report_prefix(prefix: str) -> str:
    if not isinstance(prefix, str):
        raise TypeError("report prefix must be a string")
    if not prefix:
        return prefix
    if "\\" in prefix or "\x00" in prefix:
        raise ValueError("report prefix contains an unsafe path character")
    if PurePosixPath(prefix).is_absolute() or PureWindowsPath(prefix).is_absolute():
        raise ValueError("report prefix must be relative")
    if any(component in {".", ".."} for component in prefix.split("/")):
        raise ValueError("report prefix must not contain dot path components")
    return prefix


def content_type_for_key(key: str) -> str:
    suffix = PurePosixPath(key).suffix.lower()
    if suffix in _STANDARD_CONTENT_TYPES:
        return _STANDARD_CONTENT_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(key, strict=False)
    return guessed or "application/octet-stream"


def is_sha256_hexdigest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
