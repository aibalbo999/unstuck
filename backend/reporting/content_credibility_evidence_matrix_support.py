"""Small input and output helpers for evidence-matrix credibility checks."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text

from .text_tokens import is_missing_text_token


USABLE_EVIDENCE_STATUSES = frozenset({"success", "skipped_fresh_cache", "degraded_enrichment"})


def as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def issue(issue_id: str, message: str, details: dict | None = None) -> dict:
    result = {"id": issue_id, "message": message}
    if details:
        result["details"] = details
    return result


def check(check_id: str, status: str, message: str, details: dict | None = None) -> dict:
    result = {"id": check_id, "status": status, "message": message}
    if details:
        result["details"] = details
    return result


def evidence_matrix_rows(context: dict, snapshot: dict) -> list:
    if "evidence_matrix" in snapshot:
        return safe_sequence_items(snapshot.get("evidence_matrix"))
    try:
        from .evidence_matrix import build_evidence_matrix_rows

        return build_evidence_matrix_rows(context)
    except Exception:
        return []


def evidence_claim_row(rows: list, claim: str) -> dict | None:
    for row in rows:
        row_map = as_dict(row)
        if safe_text(row_map.get("claim")).strip() == claim:
            return row_map
    return None


def usable_basis(row: dict) -> tuple[str, bool]:
    status = safe_text(row.get("status")).strip().lower() or "unknown"
    basis = safe_text(row.get("basis")).strip()
    return status, bool(basis) and not is_missing_text_token(basis)


__all__ = [
    "USABLE_EVIDENCE_STATUSES",
    "as_dict",
    "check",
    "evidence_claim_row",
    "evidence_matrix_rows",
    "issue",
    "usable_basis",
]
