"""Key evidence row assembly for rendered reports."""

from __future__ import annotations

from data_trust import audit_status_label, source_label
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_sequence_items, safe_text
from numeric_safety import is_non_finite_number

from .evidence_definitions import KEY_EVIDENCE_DEFINITIONS
from .text_tokens import is_missing_text_token


def _audit_entries_by_source(data: dict) -> dict[str, list[dict]]:
    data = safe_mapping_dict(data) or {}
    entries = safe_dict_list(data.get("source_audit"))
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        source = _safe_text(entry.get("source"))
        if not source:
            continue
        grouped.setdefault(source, []).append(entry)
    return grouped


def _has_evidence_value(data: dict, keys: tuple[str, ...]) -> bool:
    data = safe_mapping_dict(data) or {}
    for key in keys:
        if _has_usable_evidence_value(data.get(key)):
            return True
    return False


def _has_usable_evidence_value(value) -> bool:
    if value is None or isinstance(value, (bool, bytes, bytearray, memoryview)):
        return False
    if is_non_finite_number(value):
        return False
    if isinstance(value, str):
        return not is_missing_text_token(value)
    if isinstance(value, (list, tuple)):
        return any(_has_usable_evidence_value(item) for item in safe_sequence_items(value))
    value_map = safe_mapping_dict(value)
    if value_map is not None:
        return any(_has_usable_evidence_value(child) for child in value_map.values())
    return not is_missing_text_token(safe_text(value).strip())


def _record_count(entry: dict) -> int:
    return max(0, safe_int(entry.get("record_count")))


def _safe_bool_flag(value) -> bool:
    return value if isinstance(value, bool) else False


def _source_evidence_entry(data: dict, source: str, keys: tuple[str, ...]) -> dict:
    data = safe_mapping_dict(data) or {}
    entries = _audit_entries_by_source(data).get(source, [])
    if not entries:
        return {}
    successful = [
        entry for entry in entries
        if _safe_text(entry.get("status")) in {"success", "skipped_fresh_cache"}
        and _record_count(entry) > 0
    ]
    if _has_evidence_value(data, keys) and successful:
        providers = []
        for entry in successful:
            provider = _safe_text(entry.get("provider"))
            if provider and provider not in providers:
                providers.append(provider)
        fetched_at = next(
            (
                text
                for entry in reversed(successful)
                if (text := _safe_text(entry.get("fetched_at")))
            ),
            None,
        )
        return {
            "provider": " + ".join(providers) if providers else "未記錄",
            "status": "success",
            "fetched_at": fetched_at or "N/A",
            "record_count": sum(_record_count(entry) for entry in successful),
            "stale": all(_safe_bool_flag(entry.get("stale")) for entry in successful),
        }
    return entries[-1]


def build_key_evidence_rows(data: dict) -> list[dict]:
    data = safe_mapping_dict(data)
    if data is None:
        return []
    rows = []
    for label, source, keys in KEY_EVIDENCE_DEFINITIONS:
        if not _has_evidence_value(data, keys):
            continue
        entry = _source_evidence_entry(data, source, keys)
        status = _safe_text(entry.get("status")) or "unknown"
        rows.append({
            "label": label,
            "source_label": source_label(source),
            "provider": _safe_text(entry.get("provider")) or "未記錄",
            "status": status,
            "status_label": audit_status_label(status),
            "fetched_at": _safe_text(entry.get("fetched_at")) or "N/A",
            "record_count": _record_count(entry),
            "stale": _safe_bool_flag(entry.get("stale")),
        })
    return rows


def _safe_text(value, default: str = "") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    return default if is_missing_text_token(text) else text


__all__ = ["build_key_evidence_rows"]
