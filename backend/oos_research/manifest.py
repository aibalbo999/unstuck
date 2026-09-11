"""Strict, versioned study registration manifest."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, TypedDict

from .canonical import canonical_bytes, sha256_bytes


class StudyManifest(TypedDict, total=False):
    schema_version: str
    study_id: str
    study_kind: str
    registered_at: str
    timezone: str
    selection_period: dict[str, str]
    ticker_universe: list[str]
    pipelines: list[str]
    horizons: dict[str, list[int]]
    policies: dict[str, Any]
    evaluator_version: str
    manifest_sha256: str


REQUIRED = {
    "schema_version",
    "study_id",
    "study_kind",
    "registered_at",
    "timezone",
    "selection_period",
    "ticker_universe",
    "pipelines",
    "horizons",
    "policies",
    "evaluator_version",
}
STUDY_KINDS = {"synthetic_validation", "retrospective_replay", "prospective"}


def build_manifest(**fields: Any) -> StudyManifest:
    manifest = dict(fields)
    validate_manifest(manifest)
    manifest["manifest_sha256"] = manifest_hash(manifest)
    return manifest  # type: ignore[return-value]


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("registered_at must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("registered_at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("registered_at must carry UTC timezone")
    return parsed


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be an object")
    missing = sorted(REQUIRED - set(manifest))
    if missing:
        raise ValueError(f"manifest missing required fields: {', '.join(missing)}")
    if not isinstance(manifest["schema_version"], str) or not manifest["schema_version"].startswith("oos."):
        raise ValueError("unsupported manifest schema_version")
    study_id = manifest["study_id"]
    if not isinstance(study_id, str) or not study_id or "/" in study_id or "\\" in study_id or ".." in study_id:
        raise ValueError("study_id must be a non-empty safe identifier")
    if manifest["study_kind"] not in STUDY_KINDS:
        raise ValueError("unknown study_kind")
    _parse_utc(manifest["registered_at"])
    if not isinstance(manifest["timezone"], str) or not manifest["timezone"]:
        raise ValueError("timezone must be explicit")
    period = manifest["selection_period"]
    if not isinstance(period, Mapping) or not isinstance(period.get("start"), str) or not isinstance(period.get("end"), str):
        raise ValueError("selection_period requires start and end")
    if period["start"] > period["end"]:
        raise ValueError("selection_period is reversed")
    for field in ("ticker_universe", "pipelines"):
        values = manifest[field]
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
            raise ValueError(f"{field} must be a non-empty list of strings")
        if len(set(values)) != len(values):
            raise ValueError(f"{field} must not contain duplicates")
    horizons = manifest["horizons"]
    if not isinstance(horizons, Mapping) or not horizons:
        raise ValueError("horizons must be an explicit mapping")
    for mode, values in horizons.items():
        if not isinstance(mode, str) or not isinstance(values, list) or not values:
            raise ValueError("each horizon entry must be a non-empty list")
        if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in values):
            raise ValueError("horizons must contain positive integers")
    if not isinstance(manifest["policies"], Mapping) or not manifest["policies"]:
        raise ValueError("policies must be explicit")
    if not isinstance(manifest["evaluator_version"], str) or not manifest["evaluator_version"]:
        raise ValueError("evaluator_version must be explicit")
    if "manifest_sha256" in manifest and manifest["manifest_sha256"] != manifest_hash(manifest):
        raise ValueError("manifest_sha256 does not match canonical manifest")


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_bytes(payload))
