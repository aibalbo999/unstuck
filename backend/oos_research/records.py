"""Immutable record envelopes and result identities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .canonical import canonical_bytes, content_hash


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_record(record_type: str, record_id: str, payload: Mapping[str, Any], *, created_at: str | None = None) -> dict[str, Any]:
    if not record_type or not record_id:
        raise ValueError("record_type and record_id are required")
    body = dict(payload)
    return {
        "schema_version": "oos.record.v1",
        "record_type": record_type,
        "record_id": record_id,
        "created_at": created_at or utc_now(),
        "payload": body,
        "payload_sha256": content_hash(body),
    }


def validate_record(record: Mapping[str, Any]) -> None:
    required = {"schema_version", "record_type", "record_id", "created_at", "payload", "payload_sha256"}
    missing = required - set(record)
    if missing:
        raise ValueError(f"record missing fields: {', '.join(sorted(missing))}")
    if record["schema_version"] != "oos.record.v1" or not isinstance(record["payload"], Mapping):
        raise ValueError("unsupported or malformed record")
    actual = content_hash(record["payload"])
    if actual != record["payload_sha256"]:
        raise ValueError("record payload hash mismatch")
    if not isinstance(record["record_id"], str) or not record["record_id"]:
        raise ValueError("record_id must be non-empty")


def result_identity(*, study_id: str, candidate_id: str, report_bundle_hash: str, horizon_unit: str,
                    horizon_value: int, evaluator_version: str, dataset_hash: str,
                    calendar_hash: str, policy_hash: str, as_of: str) -> str:
    return content_hash({
        "study_id": study_id,
        "candidate_id": candidate_id,
        "report_bundle_hash": report_bundle_hash,
        "horizon_unit": horizon_unit,
        "horizon_value": horizon_value,
        "evaluator_version": evaluator_version,
        "dataset_hash": dataset_hash,
        "calendar_hash": calendar_hash,
        "policy_hash": policy_hash,
        "as_of": as_of,
    })
