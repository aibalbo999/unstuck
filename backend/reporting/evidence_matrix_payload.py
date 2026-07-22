"""Tooltip JSON payload helpers for report evidence matrix sources."""

from __future__ import annotations

from typing import Any

from data_trust_audit import audit_status_label, source_label
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number

from .html_sanitizer import sanitize_report_plain_text
from .text_tokens import is_missing_text_token


def build_payload(context: dict, rows: list[dict]) -> dict:
    """Build JSON data used by click-to-source report tooltips."""
    data = _as_dict(_as_dict(context).get("data"))
    sources: dict[str, dict] = {}

    for entry in safe_dict_list(data.get("source_audit")):
        source_text = _text(entry.get("source"), "")
        source_id = _source_id(source_text or _text(entry.get("provider"), ""))
        if not source_id:
            continue
        provider = _text(entry.get("provider"))
        status = _text(entry.get("status"), "unknown")
        fetched_at = _text(entry.get("fetched_at"))
        message = _source_message_text(entry.get("message"), entry.get("error_kind"), entry.get("source"))
        sources[source_id] = {
            "source_id": source_id,
            "source": source_label(source_text or source_id),
            "source_document": provider,
            "status": status,
            "status_label": audit_status_label(status),
            "fetched_at": fetched_at,
            "text": message,
        }

    for index, row in enumerate(rows, start=1):
        row_map = _as_dict(row)
        source_id = f"evidence:{index}"
        sources[source_id] = {
            "source_id": source_id,
            "source": _text(row_map.get("source")),
            "source_document": _text(row_map.get("provider")),
            "status": _text(row_map.get("status"), "unknown"),
            "status_label": _text(row_map.get("status_label")),
            "fetched_at": _text(row_map.get("fetched_at")),
            "text": _text(row_map.get("basis")),
            "limitation": _text(row_map.get("limitation")),
        }

    return {"sources": sources, "rows": rows}


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _source_id(value: Any) -> str:
    text = _text(value, "").strip()
    return "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-", ".", ":"})[:96]


def _source_message_text(message: Any, error_kind: Any = None, source: Any = None) -> str:
    message_text = _source_message_candidate(message)
    if message_text:
        return message_text
    error_text = _source_message_candidate(error_kind)
    if error_text:
        return error_text
    if _has_message_value(message) or _has_message_value(error_kind):
        return "N/A"
    source_text = _source_message_candidate(source)
    return source_text or "N/A"


def _source_message_candidate(value: Any) -> str:
    if not _has_message_value(value):
        return ""
    return _text(value, "").strip()


def _has_message_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(_text(value, "").strip())
    if isinstance(value, (bytes, bytearray, memoryview, list, tuple, dict, set, frozenset)):
        try:
            return len(value) > 0
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return True


def _text(value: Any, default: str = "N/A") -> str:
    if is_non_finite_number(value):
        return default
    if is_missing_text_token(value):
        return default
    text = sanitize_report_plain_text(safe_text(value)).strip()
    return text or default

__all__ = ["build_payload"]
