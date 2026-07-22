"""Snapshot integrity helpers for report reading notices."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text
from numeric_safety import is_non_finite_number

from .text_tokens import is_missing_text_token


_GENERIC_SNAPSHOT_INTEGRITY_ERRORS = {"資料快照完整性未通過，不能直接引用報告結論。"}

def snapshot_integrity(context: dict) -> dict:
    integrity = _as_dict(dict.get(context, "snapshot_integrity"))
    data = _as_dict(dict.get(context, "data"))
    nested_integrity = _as_dict(dict.get(data, "snapshot_integrity"))
    invalid_candidates = [
        candidate
        for candidate in (integrity, nested_integrity)
        if snapshot_integrity_invalid(candidate)
    ]
    if invalid_candidates:
        return max(invalid_candidates, key=_snapshot_integrity_detail_specificity)
    return integrity or nested_integrity


def snapshot_integrity_invalid(integrity: dict) -> bool:
    status = _status(dict.get(integrity, "status")).lower()
    return status == "invalid" or dict.get(integrity, "valid") is False


def snapshot_integrity_verified(integrity: dict) -> bool:
    return _status(dict.get(integrity, "status")).lower() == "verified"


def snapshot_integrity_label(integrity: dict) -> str:
    if snapshot_integrity_invalid(integrity):
        return "未通過"
    status = _status(dict.get(integrity, "status"), "not_recorded").lower()
    return {
        "verified": "已驗證",
        "unverified": "未驗證",
        "not_recorded": "未記錄",
        "": "未記錄",
    }.get(status, status or "未記錄")


def snapshot_integrity_detail(integrity: dict) -> str:
    errors = _snapshot_integrity_errors(integrity)
    mismatch_error = _snapshot_integrity_hash_mismatch_error(integrity)
    if not errors and mismatch_error:
        return mismatch_error
    errors = _unique_texts(errors)
    specific_errors = _specific_snapshot_integrity_errors(errors)
    if specific_errors:
        errors = specific_errors
    elif mismatch_error:
        return mismatch_error
    return "；".join(errors)


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _status(value: Any, default: str = "") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _snapshot_integrity_detail_specificity(integrity: dict) -> int:
    errors = _snapshot_integrity_errors(integrity)
    errors = _unique_texts(errors)
    if _specific_snapshot_integrity_errors(errors):
        return 3
    if _snapshot_integrity_hash_mismatch_error(integrity):
        return 2
    if errors:
        return 1
    return 0


def _snapshot_integrity_hash_mismatch_error(integrity: dict) -> str:
    hash_value = _status(dict.get(integrity, "hash"))
    expected_hash = _status(dict.get(integrity, "expected_hash"))
    return "snapshot_hash mismatch" if hash_value and expected_hash and hash_value != expected_hash else ""


def _snapshot_integrity_errors(integrity: dict) -> list[str]:
    errors = [text for item in safe_sequence_items(dict.get(integrity, "errors")) if (text := _status(item))]
    if errors:
        return errors
    text = _status(dict.get(integrity, "errors"))
    return [text] if text else []


def _specific_snapshot_integrity_errors(errors: list[str]) -> list[str]:
    return [error for error in errors if error not in _GENERIC_SNAPSHOT_INTEGRITY_ERRORS]


def _unique_texts(values: list[str]) -> list[str]:
    unique = []
    seen = set()
    for value in values:
        value = _status(value)
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


__all__ = [
    "snapshot_integrity", "snapshot_integrity_detail", "snapshot_integrity_invalid", "snapshot_integrity_label",
    "snapshot_integrity_verified",
]
