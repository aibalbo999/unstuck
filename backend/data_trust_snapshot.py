"""Data snapshot sanitization, validation, and size governance."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Optional

from data_trust_audit import data_snapshot_filename_for_report, utc_now_iso
from data_trust_constants import (
    DATA_SNAPSHOT_SCHEMA_VERSION,
    SENSITIVE_KEY_RE,
    SNAPSHOT_CORE_DATA_KEYS,
    SNAPSHOT_RERUN_ANALYSIS_MAX_CHARS,
    SNAPSHOT_TRIMMABLE_LIST_FIELDS,
    SUPPORTED_DATA_SNAPSHOT_SCHEMA_VERSIONS,
)
from data_trust_scoring import build_data_trust, normalize_data_trust, unknown_data_trust
from report_reproducibility import build_data_confidence_controls, build_reproducibility_packet


def sanitize_for_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str.startswith("_") or (key_str != "prompt_version" and SENSITIVE_KEY_RE.search(key_str)):
                continue
            clean[key_str] = sanitize_for_snapshot(item)
        return clean
    if isinstance(value, list):
        return [sanitize_for_snapshot(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_snapshot(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def snapshot_text(value: Any, *, max_chars: int = SNAPSHOT_RERUN_ANALYSIS_MAX_CHARS) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[Snapshot truncated for size]"


def sanitize_rerun_context(context: dict) -> dict:
    if not isinstance(context, dict):
        return {"analyses": {}, "structured_outputs": {}, "parsed": {}}

    analyses = {}
    raw_analyses = context.get("analyses", {})
    if isinstance(raw_analyses, dict):
        for agent_num, text in raw_analyses.items():
            if text is None:
                continue
            analyses[str(agent_num)] = snapshot_text(text)

    return sanitize_for_snapshot({
        "analyses": analyses,
        "structured_outputs": context.get("structured_outputs", {}),
        "parsed": context.get("parsed", {}),
        "pipeline_id": context.get("pipeline_id"),
        "pipeline_label": context.get("pipeline_label"),
        "agent_sequence": context.get("agent_sequence"),
    })


def build_data_snapshot(
    context: dict,
    pipeline_id: Optional[str] = None,
    generated_at: Optional[str] = None,
    max_bytes: Optional[int] = None,
) -> dict:
    data = context.get("data", {}) if isinstance(context, dict) else {}
    if not isinstance(data, dict):
        data = {}
    data_trust = normalize_data_trust(data.get("data_trust")) if data.get("data_trust") else build_data_trust(data)
    try:
        from reporting.evidence_matrix import build_evidence_matrix_rows

        evidence_matrix = build_evidence_matrix_rows(context)
    except Exception:
        evidence_matrix = []
    snapshot_generated_at = generated_at or utc_now_iso()
    confidence_controls = build_data_confidence_controls(context, data_trust)
    snapshot = {
        "snapshot_schema_version": DATA_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_truncated": False,
        "snapshot_size_bytes": 0,
        "snapshot_omitted_sections": [],
        "snapshot_migrated_from_legacy": False,
        "ticker": context.get("ticker") or data.get("ticker"),
        "company_name": context.get("company_name") or data.get("company_name"),
        "pipeline": pipeline_id or context.get("pipeline_id"),
        "generated_at": snapshot_generated_at,
        "conclusion_generated_at": sanitize_for_snapshot(context.get("conclusion_generated_at") or snapshot_generated_at),
        "snapshot_refreshed_at": sanitize_for_snapshot(context.get("snapshot_refreshed_at", "")),
        "decision_validity_status": sanitize_for_snapshot(context.get("decision_validity_status") or "current"),
        "requires_rerun_reason": sanitize_for_snapshot(context.get("requires_rerun_reason", "")),
        "refreshed_from_report": sanitize_for_snapshot(context.get("refreshed_from_report", "")),
        "refreshed_without_analysis_rerun": bool(context.get("refreshed_without_analysis_rerun")),
        "analysis_text_stale_message": sanitize_for_snapshot(context.get("analysis_text_stale_message", "")),
        "data_schema_version": data.get("data_schema_version"),
        "source_freshness": sanitize_for_snapshot(data.get("source_freshness", {})),
        "source_audit": sanitize_for_snapshot(data.get("source_audit", [])),
        "data_trust": data_trust,
        "data_confidence_score": confidence_controls["data_confidence_score"],
        "data_confidence_status": confidence_controls["data_confidence_status"],
        "conclusion_guardrails": sanitize_for_snapshot(confidence_controls["conclusion_guardrails"]),
        "reproducibility_packet": sanitize_for_snapshot(
            build_reproducibility_packet(context, data_trust, snapshot_generated_at)
        ),
        "evidence_matrix": sanitize_for_snapshot(evidence_matrix),
        "data_source_notes": sanitize_for_snapshot(data.get("data_source_notes", [])),
        "deterministic_fallbacks": sanitize_for_snapshot(context.get("deterministic_fallbacks", [])),
        "report_lint": sanitize_for_snapshot(context.get("report_lint", {})),
        "rerun_context": sanitize_rerun_context(context),
        "data": sanitize_for_snapshot(data),
    }
    return apply_snapshot_size_governance(snapshot, max_bytes=max_bytes)


def snapshot_size_bytes(snapshot: dict) -> int:
    return len(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def snapshot_content_hash(snapshot: dict) -> str:
    if not isinstance(snapshot, dict):
        return ""
    stable = {
        key: _hashable_snapshot_value(key, value) for key, value in snapshot.items()
        if key not in {"snapshot_hash", "content_hash", "snapshot_size_bytes"}
    }
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _hashable_snapshot_value(key: str, value: Any) -> Any:
    if key == "reproducibility_packet" and isinstance(value, dict):
        packet = dict(value)
        packet.pop("data_snapshot_hash", None)
        return packet
    return value


def set_snapshot_integrity(snapshot: dict) -> dict:
    digest = snapshot_content_hash(snapshot)
    snapshot["snapshot_hash"] = digest
    snapshot["content_hash"] = digest
    packet = snapshot.get("reproducibility_packet")
    if isinstance(packet, dict):
        packet["data_snapshot_hash"] = digest
    return set_stable_snapshot_size(snapshot)


def verify_data_snapshot_integrity(snapshot: Any) -> dict:
    if not isinstance(snapshot, dict):
        return {"valid": False, "hash": "", "expected_hash": "", "errors": ["snapshot must be an object"]}
    expected = str(snapshot.get("snapshot_hash") or snapshot.get("content_hash") or "")
    if not expected:
        return {"valid": True, "hash": "", "expected_hash": "", "errors": []}
    actual = snapshot_content_hash(snapshot)
    return {
        "valid": actual == expected,
        "hash": actual,
        "expected_hash": expected,
        "errors": [] if actual == expected else ["snapshot_hash mismatch"],
    }


def set_stable_snapshot_size(snapshot: dict) -> dict:
    previous_size = -1
    while True:
        size = snapshot_size_bytes(snapshot)
        snapshot["snapshot_size_bytes"] = size
        if size == previous_size:
            return snapshot
        previous_size = size


def validate_data_snapshot(snapshot: Any) -> dict:
    errors = []
    if not isinstance(snapshot, dict):
        return {"valid": False, "errors": ["snapshot must be an object"]}
    if snapshot.get("snapshot_schema_version") not in SUPPORTED_DATA_SNAPSHOT_SCHEMA_VERSIONS:
        errors.append("unsupported snapshot_schema_version")
    required_keys = [
        "ticker",
        "pipeline",
        "generated_at",
        "data_schema_version",
        "source_freshness",
        "source_audit",
        "data_trust",
        "data",
    ]
    if snapshot.get("snapshot_schema_version") == DATA_SNAPSHOT_SCHEMA_VERSION:
        required_keys.extend([
            "data_confidence_score",
            "conclusion_guardrails",
            "reproducibility_packet",
        ])
    for key in required_keys:
        if key not in snapshot:
            errors.append(f"missing {key}")
    if not isinstance(snapshot.get("source_audit", []), list):
        errors.append("source_audit must be a list")
    if not isinstance(snapshot.get("data_trust", {}), dict):
        errors.append("data_trust must be an object")
    integrity = verify_data_snapshot_integrity(snapshot)
    errors.extend(integrity.get("errors", []))
    return {"valid": not errors, "errors": errors}


def apply_snapshot_size_governance(snapshot: dict, max_bytes: Optional[int] = None) -> dict:
    try:
        from config import DATA_SNAPSHOT_MAX_BYTES

        limit = int(max_bytes or DATA_SNAPSHOT_MAX_BYTES)
    except Exception:
        limit = int(max_bytes or 2 * 1024 * 1024)

    governed = json.loads(json.dumps(snapshot, ensure_ascii=False, default=str))
    governed["snapshot_truncated"] = False
    governed["snapshot_omitted_sections"] = []
    governed["snapshot_size_bytes"] = 0

    size = snapshot_size_bytes(governed)
    if size <= limit:
        return set_snapshot_integrity(governed)

    governed["snapshot_truncated"] = True
    data = governed.get("data") if isinstance(governed.get("data"), dict) else {}
    for key in SNAPSHOT_TRIMMABLE_LIST_FIELDS:
        value = data.get(key)
        if isinstance(value, list) and len(value) > 3:
            omitted = len(value) - 3
            data[key] = value[:3]
            governed["snapshot_omitted_sections"].append(f"data.{key}:{omitted}")

    size = snapshot_size_bytes(governed)
    if size > limit and isinstance(data, dict):
        removed_keys = sorted(key for key in data if key not in SNAPSHOT_CORE_DATA_KEYS)
        governed["data"] = {key: data[key] for key in data if key in SNAPSHOT_CORE_DATA_KEYS}
        if removed_keys:
            governed["snapshot_omitted_sections"].append(f"data.non_core_fields:{len(removed_keys)}")

    size = snapshot_size_bytes(governed)
    rerun_context = governed.get("rerun_context") if isinstance(governed.get("rerun_context"), dict) else {}
    analyses = rerun_context.get("analyses") if isinstance(rerun_context.get("analyses"), dict) else {}
    if size > limit and analyses:
        shortened = {}
        omitted_chars = 0
        for agent_num, text in analyses.items():
            text_value = str(text or "")
            shortened_text = snapshot_text(text_value, max_chars=2000)
            omitted_chars += max(0, len(text_value) - len(shortened_text))
            shortened[str(agent_num)] = shortened_text
        rerun_context["analyses"] = shortened
        if omitted_chars:
            governed["snapshot_omitted_sections"].append(f"rerun_context.analyses_chars:{omitted_chars}")

    size = snapshot_size_bytes(governed)
    if size > limit and rerun_context:
        removed_keys = [key for key in ("parsed", "structured_outputs") if key in rerun_context]
        for key in removed_keys:
            rerun_context.pop(key, None)
        if removed_keys:
            governed["snapshot_omitted_sections"].append(f"rerun_context.non_essential:{len(removed_keys)}")

    return set_snapshot_integrity(governed)


def write_data_snapshot(path: str | Path, context: dict, pipeline_id: Optional[str] = None) -> dict:
    snapshot = build_data_snapshot(context, pipeline_id=pipeline_id)
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def read_data_trust_from_snapshot(path: str | Path) -> dict:
    path_obj = Path(path)
    if not path_obj.exists():
        return unknown_data_trust()
    try:
        snapshot = json.loads(path_obj.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return unknown_data_trust()
    return normalize_data_trust(snapshot.get("data_trust") if isinstance(snapshot, dict) else {})
