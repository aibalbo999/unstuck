"""Project snapshot-integrity failures into report repair candidates."""

from __future__ import annotations

from typing import Any

from mapping_fields import mapping_field, safe_mapping_dict, safe_text, safe_text_list


_GENERIC_SNAPSHOT_INTEGRITY_ERRORS = {
    "資料快照完整性未通過，不能直接引用報告結論。",
}


def snapshot_integrity_repair_item(integrity: Any) -> dict[str, Any] | None:
    integrity = safe_mapping_dict(integrity)
    if integrity is None:
        return None
    if not _invalid_integrity(integrity):
        return None
    errors = _integrity_errors(integrity)
    detail = "；".join(errors) if errors else "資料快照 hash 不一致，不能直接引用報告結論。"
    return {
        "severity": "blocked",
        "priority_score": 980,
        "recommended_action": "manual_review",
        "action_label": "人工審核",
        "title": "資料快照完整性未通過",
        "detail": detail,
        "reason_codes": ["data_snapshot_integrity_invalid"],
        "blocks_auto_rerun": True,
    }


def _integrity_errors(integrity: dict[str, Any]) -> list[str]:
    mismatch_error = _hash_mismatch_error(integrity)
    errors = safe_text_list(mapping_field(integrity, "errors"))
    if errors:
        return _focused_integrity_errors(_unique_texts(errors), mismatch_error)
    text = safe_text(mapping_field(integrity, "errors")).strip()
    if text:
        return _focused_integrity_errors([text], mismatch_error)
    return [mismatch_error] if mismatch_error else []


def _hash_mismatch_error(integrity: dict[str, Any]) -> str:
    hash_value = safe_text(mapping_field(integrity, "hash")).strip()
    expected_hash = safe_text(mapping_field(integrity, "expected_hash")).strip()
    if hash_value and expected_hash and hash_value != expected_hash:
        return "snapshot_hash mismatch"
    return ""


def _focused_integrity_errors(errors: list[str], mismatch_error: str = "") -> list[str]:
    specific_errors = [
        error
        for error in errors
        if error not in _GENERIC_SNAPSHOT_INTEGRITY_ERRORS
    ]
    if not specific_errors and mismatch_error:
        return [mismatch_error]
    return specific_errors or errors


def _unique_texts(values: list[str]) -> list[str]:
    unique = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _invalid_integrity(integrity: dict[str, Any]) -> bool:
    status = safe_text(mapping_field(integrity, "status")).strip().lower()
    if status == "invalid" or mapping_field(integrity, "valid") is False:
        return True
    if status:
        return False
    return False


__all__ = ["snapshot_integrity_repair_item"]
