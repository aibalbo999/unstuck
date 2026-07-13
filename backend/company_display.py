"""Helpers for consistent company display names across reports and snapshots."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text


def company_display_name(data: Any, fallback: str = "") -> str:
    """Prefer curated identity display names over provider-only English names."""
    payload = data if isinstance(data, dict) else {}
    identity = payload.get("company_identity") if isinstance(payload.get("company_identity"), dict) else {}
    for key in ("display_name", "official_name"):
        value = safe_text(identity.get(key)).strip()
        if value and value != "N/A":
            return value
    value = safe_text(payload.get("company_name")).strip()
    if not value:
        value = safe_text(fallback).strip()
    if not value:
        value = safe_text(payload.get("ticker")).strip()
    return value or safe_text(fallback).strip()
