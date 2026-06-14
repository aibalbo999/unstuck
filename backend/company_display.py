"""Helpers for consistent company display names across reports and snapshots."""

from __future__ import annotations

from typing import Any


def company_display_name(data: Any, fallback: str = "") -> str:
    """Prefer curated identity display names over provider-only English names."""
    payload = data if isinstance(data, dict) else {}
    identity = payload.get("company_identity") if isinstance(payload.get("company_identity"), dict) else {}
    for key in ("display_name", "official_name"):
        value = str(identity.get(key) or "").strip()
        if value and value != "N/A":
            return value
    value = str(payload.get("company_name") or fallback or payload.get("ticker") or "").strip()
    return value or str(fallback or "").strip()
