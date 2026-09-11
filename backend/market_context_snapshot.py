"""Preserve raw market assertions across snapshot sizing, never across input refreshes."""

from __future__ import annotations

from data_trust_snapshot_sanitizer import sanitize_for_snapshot
from market_context_manifest import (CONTRACT_VERSION, _encoded, _manifest_matches_input,
                                     manifest_matches_input, market_input_fingerprint, prompt_fingerprint)


def snapshot_market_fields(rerun: dict, data: dict, *, context: dict | None = None) -> dict:
    from market_context_assessment import assess_final_market_context

    agent = {"v1": 7, "v2": 16, "v3": 19}.get(rerun.get("pipeline_id"))
    if agent is None or rerun.get("market_context_contract_version") != CONTRACT_VERSION:
        return {}
    context = context or {}
    outputs = rerun.get("structured_outputs") or {}
    output = outputs.get(agent, outputs.get(str(agent))) if isinstance(outputs, dict) else None
    raw = (output.get("market_context_assessment") if isinstance(output, dict) else None) if output is not None else context.get("market_context_raw_assessment")
    fields = {"market_context_contract_version": CONTRACT_VERSION,
        "market_context_manifests": rerun.get("market_context_manifests", {}),
        "market_context_original_input_fingerprint": context.get("market_context_original_input_fingerprint", market_input_fingerprint(data)),
        "market_context_raw_assessment": raw}
    fields["market_context_assessment"] = assess_final_market_context({**rerun, **fields, "data": data})["assessment"]
    return sanitize_for_snapshot(fields)


def _receipt(manifest: dict, data: dict, raw, agent: int) -> dict:
    return {"version": 1, "agent_num": agent, "input_fingerprint": manifest.get("input_fingerprint"),
            "governed_input_fingerprint": market_input_fingerprint(data),
            "manifest_hash": prompt_fingerprint(_encoded(manifest)),
            "raw_assessment_hash": prompt_fingerprint(_encoded(raw))}


def preserve_market_snapshot_evidence(original: dict, governed: dict) -> None:
    """Issue a receipt only after validating the ORIGINAL runtime input, without an override."""
    governed.pop("market_context_snapshot_receipts", None)
    if original.get("market_context_contract_version") != CONTRACT_VERSION:
        return
    original_data, data = original.get("data", {}), governed.get("data", {})
    if market_input_fingerprint(original_data) == market_input_fingerprint(data):
        return
    agent = {"v1": 7, "v2": 16, "v3": 19}.get(original.get("pipeline"))
    manifests = original.get("market_context_manifests") or {}
    manifest = manifests.get(agent, manifests.get(str(agent))) if isinstance(manifests, dict) else None
    if agent is not None and manifest_matches_input(manifest, original_data, agent):
        governed["market_context_snapshot_receipts"] = {
            str(agent): _receipt(manifest, data, governed.get("market_context_raw_assessment"), agent)}


def snapshot_manifest_matches_input(context: dict, manifest: dict, data: dict, raw, agent: int) -> bool:
    """The receipt binds the trimmed data AND unchanged claims/manifest; source rows are rechecked."""
    receipts = context.get("market_context_snapshot_receipts")
    if (not context.get("snapshot_schema_version") or not context.get("snapshot_truncated")
            or not isinstance(receipts, dict) or not isinstance(manifest, dict)):
        return False
    receipt = receipts.get(str(agent))
    if not isinstance(receipt, dict) or receipt != _receipt(manifest, data, raw, agent):
        return False
    if receipt["input_fingerprint"] != context.get("market_context_original_input_fingerprint"):
        return False
    return _manifest_matches_input(manifest, data, agent, fingerprint=receipt["input_fingerprint"])
