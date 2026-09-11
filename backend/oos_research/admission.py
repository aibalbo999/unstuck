"""Strict candidate bundle admission; every candidate remains in the ledger."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Mapping

from data_trust_snapshot_integrity import snapshot_content_hash
from .canonical import content_hash, sha256_bytes
from .inventory import admission_record
from .provenance import exchange_date, parse_timestamp, verify_registration_receipt, verify_seal, verify_time_chain


SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


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


def evaluate_candidate(
    candidate: Mapping[str, Any],
    *,
    study_kind: str,
    allow_dirty: bool = False,
    registration_evidence: Mapping[str, Any] | None = None,
    manifest_sha256: str | None = None,
    expected_code_commit: str | None = None,
    expected_prompt_fingerprint: str | None = None,
    expected_model_route_policy_sha256: str | None = None,
    timezone_name: str = "Asia/Taipei",
    selection_period: Mapping[str, Any] | None = None,
    expected_horizons: Mapping[str, Any] | None = None,
    session_open_local_time: str = "09:00:00",
) -> dict[str, Any]:
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
    if study_kind == "prospective":
        reasons.extend(_prospective_identity_reasons(
            candidate, report, registration_evidence,
            expected_code_commit=expected_code_commit,
            expected_prompt_fingerprint=expected_prompt_fingerprint,
            expected_model_route_policy_sha256=expected_model_route_policy_sha256,
        ))
        reasons.extend(_selection_reasons(report, selection_period, timezone_name))
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
    if study_kind == "prospective":
        reasons.extend(verify_registration_receipt(
            registration_evidence,
            manifest_sha256=manifest_sha256,
            analysis_input_cutoff=report.get("analysis_input_cutoff"),
        ))
    reasons.extend(verify_seal(study_kind=study_kind, report_available_at=report.get("report_available_at"),
                               sealed_at=candidate.get("sealed_at"), first_session_date=candidate.get("first_session_date"),
                               timezone_name=timezone_name, session_open_local_time=session_open_local_time))
    reasons.extend(_publication_reasons(report))
    pipeline = report.get("pipeline_id")
    plan = report.get("plan")
    if pipeline in {"v2", "v3"}:
        if not isinstance(plan, Mapping):
            reasons.append("missing_execution_plan")
        elif isinstance(plan.get("horizon_trading_days"), bool) or not isinstance(plan.get("horizon_trading_days"), int) or not 1 <= plan["horizon_trading_days"] <= 252:
            reasons.append("missing_explicit_trade_horizon")
        elif isinstance(expected_horizons, Mapping) and plan["horizon_trading_days"] not in expected_horizons.get(pipeline, []):
            reasons.append("trade_horizon_not_registered")
    elif pipeline == "v4" and not isinstance(plan, Mapping):
        reasons.append("missing_execution_plan")
    if reasons:
        status = "integrity_failed" if any(_is_integrity_failure(reason) for reason in reasons) else "insufficient_provenance"
    else:
        status = "admitted"
    return admission_record(candidate, status=status, reasons=reasons)


def candidate_bundle_hash(candidate: Mapping[str, Any]) -> str:
    return content_hash(candidate)


def _prospective_identity_reasons(
    candidate: Mapping[str, Any], report: Mapping[str, Any], evidence: Mapping[str, Any] | None,
    *, expected_code_commit: str | None, expected_prompt_fingerprint: str | None,
    expected_model_route_policy_sha256: str | None,
) -> list[str]:
    reasons: list[str] = []
    for field in ("ticker", "pipeline_id"):
        planned = candidate.get(field)
        if isinstance(planned, str) and planned and report.get(field) != planned:
            reasons.append(f"candidate_{field}_mismatch")
    checks = (("prompt_fingerprint", SHA256_RE), ("analysis_input_hash", SHA256_RE),
              ("data_snapshot_hash", SHA256_RE), ("model_route_policy_sha256", SHA256_RE),
              ("code_commit", COMMIT_RE))
    for field, pattern in checks:
        value = report.get(field)
        if not isinstance(value, str) or not pattern.fullmatch(value):
            reasons.append(f"invalid_{field}" if value else f"missing_{field}")
    for field, expected in (("code_commit", expected_code_commit),
                            ("prompt_fingerprint", expected_prompt_fingerprint),
                            ("model_route_policy_sha256", expected_model_route_policy_sha256)):
        if expected and report.get(field) != expected:
            reasons.append(f"{field}_mismatch")
    receipt = evidence.get("external_registration_receipt") if isinstance(evidence, Mapping) else None
    if isinstance(receipt, Mapping) and receipt.get("schema_version") == "oos.registration-receipt.v2":
        if report.get("code_commit") != receipt.get("source_commit"):
            reasons.append("report_commit_not_attested")
    executions = report.get("model_executions")
    if not isinstance(executions, list) or not executions:
        reasons.append("missing_model_execution_receipt")
    elif any(not _valid_model_execution(row) for row in executions):
        reasons.append("invalid_model_execution_receipt")
    elif report.get("model_id") not in {row.get("model_id") for row in executions if isinstance(row, Mapping)}:
        reasons.append("model_id_not_in_execution_receipt")
    if not isinstance(report.get("model_revision_unknown"), bool):
        reasons.append("missing_model_revision_policy")
    if report.get("source_provenance_coverage") != "complete":
        reasons.append("source_provenance_incomplete")
    reasons.extend(_snapshot_identity_reasons(candidate, report))
    return reasons


def _snapshot_identity_reasons(candidate: Mapping[str, Any], report: Mapping[str, Any]) -> list[str]:
    artifacts = candidate.get("artifacts")
    snapshot = artifacts.get("snapshot") if isinstance(artifacts, Mapping) else None
    raw = snapshot.get("content") if isinstance(snapshot, Mapping) else None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ["snapshot_content_invalid"]
    try:
        payload = json.loads(raw) if isinstance(raw, str) else None
    except (json.JSONDecodeError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        return ["snapshot_content_invalid"]
    actual = snapshot_content_hash(payload)
    if payload.get("snapshot_hash", payload.get("content_hash")) != actual:
        return ["snapshot_canonical_hash_mismatch"]
    return [] if report.get("data_snapshot_hash") == actual else ["data_snapshot_hash_mismatch"]


def _publication_reasons(report: Mapping[str, Any]) -> list[str]:
    publication = report.get("source_publication_at")
    if publication is None:
        return ["missing_source_publication_time"]
    try:
        published = parse_timestamp(publication, field="source_publication_at")
        cutoff = parse_timestamp(report.get("analysis_input_cutoff"), field="analysis_input_cutoff")
    except ValueError:
        return ["missing_or_invalid_source_publication_at"]
    return ["source_publication_after_analysis_input_cutoff"] if published > cutoff else []


def _selection_reasons(report, selection_period, timezone_name):
    if not isinstance(selection_period, Mapping):
        return ["missing_selection_period"]
    try:
        start = date.fromisoformat(selection_period.get("start"))
        end = date.fromisoformat(selection_period.get("end"))
        available = exchange_date(report.get("report_available_at"), timezone_name)
    except (TypeError, ValueError):
        return ["invalid_selection_period"]
    return [] if start <= available <= end else ["report_outside_selection_period"]


def _valid_model_execution(row):
    if not isinstance(row, Mapping):
        return False
    agent = row.get("agent_num")
    if isinstance(agent, bool) or not isinstance(agent, int) or agent <= 0:
        return False
    if not isinstance(row.get("model_id"), str) or not row["model_id"].strip():
        return False
    route_index = row.get("route_index")
    if isinstance(route_index, bool) or not isinstance(route_index, int) or route_index < 0:
        return False
    route_lists = {}
    for field in ("route_considered", "provider_call_models", "route_skipped", "failed_models"):
        values = row.get(field)
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not value for value in values)
            or len(values) != len(set(values))
        ):
            return False
        route_lists[field] = values
    considered = route_lists["route_considered"]
    model_id = row["model_id"]
    if (
        route_index >= len(considered)
        or considered[route_index] != model_id
        or any(value not in considered for field in ("provider_call_models", "route_skipped", "failed_models")
               for value in route_lists[field])
    ):
        return False
    fallback_used = row.get("fallback_used")
    cache_hit = row.get("cache_hit")
    if not isinstance(fallback_used, bool) or not isinstance(cache_hit, bool):
        return False
    if not cache_hit and model_id not in route_lists["provider_call_models"]:
        return False
    return fallback_used is (route_index > 0)


def _is_integrity_failure(reason: str) -> bool:
    return (
        reason.startswith("malformed")
        or reason.endswith("_hash_mismatch")
        or reason in {"snapshot_content_invalid", "registration_evidence_identity_mismatch"}
    )
