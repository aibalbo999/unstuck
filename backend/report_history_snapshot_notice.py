"""Snapshot-integrity notice context for report history views."""

from __future__ import annotations

import json
from typing import Any

from data_trust_snapshot import verify_data_snapshot_integrity
from mapping_fields import safe_mapping_dict, safe_text, safe_text_list
from report_history_storage import load_storage_item
from storage.report_storage import ReportStorage


GENERIC_SNAPSHOT_INTEGRITY_ERRORS = {
    "資料快照完整性未通過，不能直接引用報告結論。",
}


def invalid_snapshot_notice_context(storage: ReportStorage, filename: str) -> dict | None:
    item = load_storage_item(storage, filename, kind="data")
    if item is None:
        return snapshot_notice_context(
            "unverified",
            valid=None,
            errors=["資料快照不存在，請先核對來源與限制。"],
        )
    try:
        snapshot = json.loads(item.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return snapshot_notice_context("invalid", valid=False, errors=["資料快照無法解析，不能直接引用報告結論。"])
    if not isinstance(snapshot, dict):
        return snapshot_notice_context("invalid", valid=False, errors=["資料快照格式不是物件，不能直接引用報告結論。"])

    recorded_integrity_context = recorded_snapshot_integrity_notice_context(snapshot)
    if recorded_integrity_context is not None:
        return recorded_integrity_context

    integrity = verify_data_snapshot_integrity(snapshot)
    expected_hash = str(integrity.get("expected_hash") or "").strip()
    if not expected_hash or integrity.get("valid") is not False:
        return None

    return snapshot_notice_context(
        "invalid",
        valid=False,
        errors=[str(error) for error in integrity.get("errors", []) if str(error)],
        data_trust=snapshot.get("data_trust", {}),
        evidence_exit_gate=snapshot.get("evidence_exit_gate", {}),
        content_credibility=snapshot.get("content_credibility", {}),
        report_conformance=snapshot.get("report_conformance", {}),
        hash_value=str(integrity.get("hash") or ""),
        expected_hash=expected_hash,
    )


def recorded_snapshot_integrity_notice_context(snapshot: dict[str, Any]) -> dict | None:
    integrity = recorded_snapshot_integrity(snapshot)
    if integrity is None:
        return None
    status = safe_text(dict.get(integrity, "status")).strip().lower()
    if status != "invalid" and dict.get(integrity, "valid") is not False:
        return None
    return snapshot_notice_context(
        "invalid",
        valid=False,
        errors=recorded_snapshot_integrity_errors(integrity),
        data_trust=snapshot.get("data_trust", {}),
        evidence_exit_gate=snapshot.get("evidence_exit_gate", {}),
        content_credibility=snapshot.get("content_credibility", {}),
        report_conformance=snapshot.get("report_conformance", {}),
        hash_value=safe_text(dict.get(integrity, "hash")).strip(),
        expected_hash=safe_text(dict.get(integrity, "expected_hash")).strip(),
    )


def recorded_snapshot_integrity(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    candidates = []
    integrity = safe_mapping_dict(dict.get(snapshot, "snapshot_integrity"))
    if integrity is not None:
        candidates.append(integrity)
    data = safe_mapping_dict(dict.get(snapshot, "data"))
    if data is not None:
        nested_integrity = safe_mapping_dict(dict.get(data, "snapshot_integrity"))
        if nested_integrity is not None:
            candidates.append(nested_integrity)
    invalid_candidates = []
    for candidate in candidates:
        status = safe_text(dict.get(candidate, "status")).strip().lower()
        if status == "invalid" or dict.get(candidate, "valid") is False:
            invalid_candidates.append(candidate)
    for candidate in invalid_candidates:
        if recorded_snapshot_integrity_specific_errors(candidate):
            return candidate
    for candidate in invalid_candidates:
        if recorded_snapshot_integrity_errors(candidate):
            return candidate
    if invalid_candidates:
        return invalid_candidates[0]
    return candidates[0] if candidates else None


def recorded_snapshot_integrity_specific_errors(integrity: dict[str, Any]) -> list[str]:
    return specific_snapshot_integrity_errors(recorded_snapshot_integrity_errors(integrity))


def recorded_snapshot_integrity_errors(integrity: dict[str, Any]) -> list[str]:
    errors = snapshot_integrity_errors(dict.get(integrity, "errors"))
    mismatch_error = recorded_snapshot_integrity_hash_mismatch_error(integrity)
    if errors:
        specific_errors = specific_snapshot_integrity_errors(errors)
        if specific_errors:
            return specific_errors
        if mismatch_error:
            return [mismatch_error]
        return errors
    if mismatch_error:
        return [mismatch_error]
    return []


def specific_snapshot_integrity_errors(errors: list[str]) -> list[str]:
    return [error for error in errors if error not in GENERIC_SNAPSHOT_INTEGRITY_ERRORS]


def recorded_snapshot_integrity_hash_mismatch_error(integrity: dict[str, Any]) -> str:
    hash_value = safe_text(dict.get(integrity, "hash")).strip()
    expected_hash = safe_text(dict.get(integrity, "expected_hash")).strip()
    if hash_value and expected_hash and hash_value != expected_hash:
        return "snapshot_hash mismatch"
    return ""


def snapshot_integrity_errors(value: Any) -> list[str]:
    errors = safe_text_list(value)
    if errors:
        return unique_texts(errors)
    text = safe_text(value).strip()
    return [text] if text else []


def unique_texts(values: list[str]) -> list[str]:
    unique = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def snapshot_notice_context(
    status: str,
    *,
    valid: bool | None,
    errors: list[str] | None = None,
    data_trust: Any = None,
    evidence_exit_gate: Any = None,
    content_credibility: Any = None,
    report_conformance: Any = None,
    hash_value: str = "",
    expected_hash: str = "",
) -> dict:
    details = [error for error in errors or [] if error]
    if not details:
        details = ["資料快照完整性未通過，不能直接引用報告結論。"]
    return {
        "data": {"data_trust": data_trust or {}},
        "evidence_exit_gate": evidence_exit_gate or {},
        "content_credibility": content_credibility or {},
        "report_conformance": report_conformance or {},
        "snapshot_integrity": {
            "status": status,
            "valid": valid,
            "hash": hash_value,
            "expected_hash": expected_hash,
            "errors": details,
        },
    }
