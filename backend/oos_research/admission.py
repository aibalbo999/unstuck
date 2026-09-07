"""Strict candidate bundle admission; every candidate remains in the ledger."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical import content_hash, sha256_bytes
from .inventory import admission_record
from .provenance import verify_seal, verify_time_chain


def _artifact_hashes(candidate: Mapping[str, Any]) -> list[str]:
    artifacts = candidate.get("artifacts")
    if not isinstance(artifacts, Mapping) or not artifacts:
        return ["missing_artifacts"]
    reasons: list[str] = []
    for name in ("html", "markdown", "snapshot", "parsed_plan"):
        item = artifacts.get(name)
        if not isinstance(item, Mapping) or "sha256" not in item or "content" not in item:
            reasons.append(f"missing_{name}_hash")
            continue
        raw = item["content"]
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if not isinstance(raw, (bytes, bytearray)) or sha256_bytes(bytes(raw)) != item["sha256"]:
            reasons.append(f"{name}_hash_mismatch")
    return reasons


def evaluate_candidate(candidate: Mapping[str, Any], *, study_kind: str, allow_dirty: bool = False) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be an object")
    reasons = _artifact_hashes(candidate)
    report = candidate.get("report")
    if report is None:
        return admission_record(candidate, status="missing_report", reasons=["missing_report"] + reasons)
    if not isinstance(report, Mapping):
        return admission_record(candidate, status="integrity_failed", reasons=["malformed_report"] + reasons)
    for field in ("ticker", "pipeline_id", "prompt_fingerprint", "code_commit", "model_id"):
        if not isinstance(report.get(field), str) or not report.get(field):
            reasons.append(f"missing_{field}")
    if report.get("code_dirty") is True and not allow_dirty:
        reasons.append("dirty_code_not_allowed")
    if report.get("code_dirty") not in {True, False}:
        reasons.append("missing_code_dirty")
    quality = report.get("quality_metadata")
    if not isinstance(quality, Mapping) or not report.get("quality_metadata_hash"):
        reasons.append("missing_quality_metadata")
    elif content_hash(quality) != report.get("quality_metadata_hash"):
        reasons.append("quality_metadata_hash_mismatch")
    reasons.extend(verify_time_chain(report))
    reasons.extend(verify_seal(study_kind=study_kind, report_available_at=report.get("report_available_at"),
                               sealed_at=candidate.get("sealed_at"), first_session_date=candidate.get("first_session_date")))
    if report.get("source_publication_at") is None:
        reasons.append("missing_source_publication_time")
    if report.get("data_snapshot_hash") is None:
        reasons.append("missing_data_snapshot_hash")
    pipeline = report.get("pipeline_id")
    plan = report.get("plan")
    if pipeline in {"v2", "v3"}:
        if not isinstance(plan, Mapping):
            reasons.append("missing_execution_plan")
        elif isinstance(plan.get("horizon_trading_days"), bool) or not isinstance(plan.get("horizon_trading_days"), int) or not 1 <= plan["horizon_trading_days"] <= 252:
            reasons.append("missing_explicit_trade_horizon")
    elif pipeline == "v4" and not isinstance(plan, Mapping):
        reasons.append("missing_execution_plan")
    if reasons:
        status = "integrity_failed" if any("hash" in reason or "malformed" in reason for reason in reasons) else "insufficient_provenance"
    else:
        status = "admitted"
    return admission_record(candidate, status=status, reasons=reasons)


def candidate_bundle_hash(candidate: Mapping[str, Any]) -> str:
    return content_hash(candidate)
