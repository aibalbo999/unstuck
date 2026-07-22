"""Shared report identity helpers for daily decision queue items."""

from __future__ import annotations

from typing import Any

from mapping_fields import mapping_field as _field
from mapping_fields import safe_text


def report_key(row: dict[str, Any]) -> str:
    filename = safe_text(_field(row, "filename")).strip() or safe_text(_field(row, "report_filename")).strip()
    if filename:
        return filename
    ticker = safe_text(_field(row, "ticker")).strip()
    if not ticker:
        return ""
    pipeline_id = safe_text(_field(row, "pipeline_id")).strip() or "v1"
    return f"{ticker}:{pipeline_id}"


__all__ = ["report_key"]
