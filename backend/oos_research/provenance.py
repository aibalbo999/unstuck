"""Time and provenance checks for frozen research candidates."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Mapping
from urllib.parse import urlsplit


SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
REGISTRATION_RECEIPT_FIELDS = frozenset({
    "schema_version",
    "source",
    "remote_url",
    "ref",
    "commit",
    "observed_at",
    "manifest_sha256",
    "remote_evidence",
    "remote_evidence_sha256",
})


def parse_timestamp(value: Any, *, field: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an offset-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def verify_time_chain(values: Mapping[str, Any]) -> list[str]:
    """Return stable reason codes; no timestamp is inferred from mtime."""
    required = ("analysis_input_cutoff", "conclusion_generated_at", "report_available_at")
    parsed: dict[str, datetime] = {}
    reasons: list[str] = []
    for field in required:
        try:
            parsed[field] = parse_timestamp(values.get(field), field=field)
        except ValueError:
            reasons.append(f"missing_or_invalid_{field}")
    first_available = values.get("input_first_available_at")
    try:
        first = parse_timestamp(first_available, field="input_first_available_at")
    except ValueError:
        first = None
        reasons.append("missing_input_first_available_at")
    if not reasons and first and not (first <= parsed["analysis_input_cutoff"] <= parsed["conclusion_generated_at"] <= parsed["report_available_at"]):
        reasons.append("timestamp_order_invalid")
    return reasons


def verify_seal(*, study_kind: str, report_available_at: Any, sealed_at: Any, first_session_date: str | None) -> list[str]:
    reasons: list[str] = []
    try:
        available = parse_timestamp(report_available_at, field="report_available_at")
        sealed = parse_timestamp(sealed_at, field="sealed_at")
    except ValueError:
        return ["missing_or_invalid_seal_receipt"]
    if study_kind == "prospective":
        if not first_session_date:
            reasons.append("missing_first_session")
        else:
            try:
                first_session = datetime.fromisoformat(first_session_date).date()
                if sealed.date() >= first_session:
                    reasons.append("late_seal")
            except ValueError:
                reasons.append("invalid_first_session")
        if sealed < available:
            reasons.append("seal_before_report_available")
    return reasons


def _verify_registration_receipt(
    evidence: Mapping[str, Any] | None,
    *,
    manifest_sha256: str | None,
    analysis_input_cutoff: Any = None,
) -> list[str]:
    """Validate a recorded external Git receipt without performing network I/O."""
    if not isinstance(evidence, Mapping):
        return ["missing_or_invalid_external_registration_receipt"]
    reasons: list[str] = []
    if set(evidence) != {"external_registration_receipt"}:
        reasons.append("unexpected_registration_evidence_fields")
    receipt = evidence.get("external_registration_receipt")
    if not isinstance(receipt, Mapping):
        return sorted(set(reasons + ["missing_or_invalid_external_registration_receipt"]))
    if set(receipt) != REGISTRATION_RECEIPT_FIELDS:
        reasons.append("unexpected_registration_receipt_fields")
    if receipt.get("schema_version") != "oos.registration-receipt.v1":
        reasons.append("unsupported_registration_receipt_schema")
    if receipt.get("source") != "git_remote":
        reasons.append("invalid_registration_receipt_source")
    remote_url = receipt.get("remote_url")
    if not isinstance(remote_url, str):
        reasons.append("invalid_registration_receipt_url")
    else:
        try:
            parsed_url = urlsplit(remote_url)
            invalid_url = (
                parsed_url.scheme != "https"
                or not parsed_url.hostname
                or parsed_url.username
                or parsed_url.password
                or parsed_url.query
                or parsed_url.fragment
            )
        except ValueError:
            invalid_url = True
        if invalid_url:
            reasons.append("invalid_registration_receipt_url")
    remote_ref = receipt.get("ref")
    if (
        not isinstance(remote_ref, str)
        or not remote_ref.startswith(("refs/heads/", "refs/tags/"))
        or any(character.isspace() for character in remote_ref)
    ):
        reasons.append("invalid_registration_receipt_ref")
    if not isinstance(receipt.get("commit"), str) or not COMMIT_RE.fullmatch(receipt["commit"]):
        reasons.append("invalid_registration_receipt_commit")
    receipt_manifest_hash = receipt.get("manifest_sha256")
    if not isinstance(receipt_manifest_hash, str) or not SHA256_RE.fullmatch(receipt_manifest_hash):
        reasons.append("invalid_registration_receipt_manifest_hash")
    if not isinstance(manifest_sha256, str) or not SHA256_RE.fullmatch(manifest_sha256):
        reasons.append("missing_or_invalid_expected_manifest_hash")
    elif receipt_manifest_hash != manifest_sha256:
        reasons.append("registration_manifest_hash_mismatch")
    evidence_hash = receipt.get("remote_evidence_sha256")
    if not isinstance(evidence_hash, str) or not SHA256_RE.fullmatch(evidence_hash):
        reasons.append("invalid_registration_evidence_hash")
    remote_evidence = receipt.get("remote_evidence")
    if not isinstance(remote_evidence, str) or not remote_evidence or len(remote_evidence.encode("utf-8")) > 4096:
        reasons.append("missing_or_invalid_registration_remote_evidence")
    else:
        if isinstance(evidence_hash, str) and hashlib.sha256(remote_evidence.encode("utf-8")).hexdigest() != evidence_hash:
            reasons.append("registration_evidence_hash_mismatch")
        commit = receipt.get("commit")
        if isinstance(commit, str) and isinstance(remote_ref, str) and remote_evidence != f"{commit}\t{remote_ref}\n":
            reasons.append("registration_evidence_identity_mismatch")
    try:
        observed_at = parse_timestamp(receipt.get("observed_at"), field="registration_observed_at")
    except ValueError:
        observed_at = None
        reasons.append("missing_or_invalid_registration_observed_at")
    if analysis_input_cutoff is not None and observed_at is not None:
        try:
            cutoff = parse_timestamp(analysis_input_cutoff, field="analysis_input_cutoff")
        except ValueError:
            cutoff = None
        if cutoff is not None and observed_at > cutoff:
            reasons.append("registration_after_analysis_input_cutoff")
    return sorted(set(reasons))


def verify_registration_capture_receipt(
    evidence: Mapping[str, Any] | None,
    *,
    manifest_sha256: str | None,
    analysis_input_cutoff: Any = None,
) -> list[str]:
    """Validate capture integrity without treating its local clock as external proof."""
    return _verify_registration_receipt(
        evidence,
        manifest_sha256=manifest_sha256,
        analysis_input_cutoff=analysis_input_cutoff,
    )


def verify_registration_receipt(
    evidence: Mapping[str, Any] | None,
    *,
    manifest_sha256: str | None,
    analysis_input_cutoff: Any = None,
) -> list[str]:
    """Validate admission evidence and reject v1's unattested local timestamp."""
    reasons = _verify_registration_receipt(
        evidence,
        manifest_sha256=manifest_sha256,
        analysis_input_cutoff=analysis_input_cutoff,
    )
    receipt = evidence.get("external_registration_receipt") if isinstance(evidence, Mapping) else None
    if isinstance(receipt, Mapping) and receipt.get("schema_version") == "oos.registration-receipt.v1":
        reasons.append("registration_time_not_externally_attested")
    return sorted(set(reasons))


def registration_receipt_projection(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return only bounded receipt fields suitable for an immutable audit record."""
    if not isinstance(evidence, Mapping):
        return {}
    receipt = evidence.get("external_registration_receipt")
    if not isinstance(receipt, Mapping):
        return {}
    return {"external_registration_receipt": {
        key: receipt[key] for key in REGISTRATION_RECEIPT_FIELDS if key in receipt
    }}


def classify_study_kind(
    study_kind: str,
    *,
    evidence: Mapping[str, Any] | None = None,
    manifest_sha256: str | None = None,
) -> str:
    """Never upgrade retrospective/synthetic data to prospective."""
    if study_kind not in {"synthetic_validation", "retrospective_replay", "prospective"}:
        raise ValueError("unknown study kind")
    if study_kind != "prospective":
        return study_kind
    if verify_registration_receipt(evidence, manifest_sha256=manifest_sha256):
        return "prospective_unverified"
    return "prospective"
