"""Complete candidate inventory and admission record helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical import content_hash

ADMISSION_STATUSES = {
    "admitted", "excluded_by_protocol", "insufficient_provenance", "integrity_failed", "missing_report",
}
INVENTORY_STATUSES = {"provisional", "closed", "incomplete"}


def validate_inventory(inventory: Mapping[str, Any]) -> str:
    if not isinstance(inventory, Mapping):
        raise ValueError("inventory must be an object")
    candidates = inventory.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("inventory candidates must be a list")
    ids = [c.get("candidate_id") for c in candidates if isinstance(c, Mapping)]
    if len(ids) != len(candidates) or any(not isinstance(cid, str) or not cid for cid in ids):
        raise ValueError("every candidate needs a candidate_id")
    if len(set(ids)) != len(ids):
        raise ValueError("candidate_id must be unique")
    status = inventory.get("coverage_status")
    if status not in INVENTORY_STATUSES:
        raise ValueError("coverage_status must be provisional, closed or incomplete")
    declared = inventory.get("inventory_sha256")
    actual = content_hash({k: v for k, v in inventory.items() if k != "inventory_sha256"})
    if declared is not None and declared != actual:
        raise ValueError("inventory hash mismatch")
    return actual


def admission_record(candidate: Mapping[str, Any], *, status: str, reasons: list[str], validator_version: str = "oos.admission.v1") -> dict[str, Any]:
    if status not in ADMISSION_STATUSES:
        raise ValueError("unknown admission status")
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id is required")
    return {
        "candidate_id": candidate_id,
        "status": status,
        "reason_codes": sorted(set(reasons)),
        "validator_version": validator_version,
        "candidate_hash": content_hash(candidate),
    }
