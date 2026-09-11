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


def validate_inventory_scope(
    inventory: Mapping[str, Any], *, manifest: Mapping[str, Any]
) -> str:
    """Bind a registered fixed cohort to its exact ticker/pipeline product."""
    inventory_hash = validate_inventory(inventory)
    policies = manifest.get("policies")
    declared_count = policies.get("cohort_candidate_count") if isinstance(policies, Mapping) else None
    if declared_count is None:
        return inventory_hash
    if isinstance(declared_count, bool) or not isinstance(declared_count, int) or declared_count <= 0:
        raise ValueError("registered candidate count is invalid")
    tickers = manifest.get("ticker_universe")
    pipelines = manifest.get("pipelines")
    if not isinstance(tickers, list) or not isinstance(pipelines, list):
        raise ValueError("registered candidate scope is invalid")
    expected = {(ticker, pipeline) for ticker in tickers for pipeline in pipelines}
    if declared_count != len(expected):
        raise ValueError("registered candidate count does not match manifest scope")
    pairs: list[tuple[str, str]] = []
    for candidate in inventory["candidates"]:
        ticker = candidate.get("ticker") if isinstance(candidate, Mapping) else None
        pipeline = candidate.get("pipeline_id") if isinstance(candidate, Mapping) else None
        if not isinstance(ticker, str) or not ticker or not isinstance(pipeline, str) or not pipeline:
            raise ValueError("registered candidate set contains an invalid identity")
        pairs.append((ticker, pipeline))
    if len(pairs) != declared_count or len(set(pairs)) != len(pairs) or set(pairs) != expected:
        raise ValueError("registered candidate set does not match manifest scope")
    return inventory_hash


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
