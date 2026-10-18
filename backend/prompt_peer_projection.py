"""Limit LLM comparison context to peers not explicitly marked unverified."""

from __future__ import annotations


def comparable_peer_rows(rows: list) -> list:
    return [row for row in rows
            if not isinstance(row, dict)
            or row.get("business_comparability_verified_current") is not False]
