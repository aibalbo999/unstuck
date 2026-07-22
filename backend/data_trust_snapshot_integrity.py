"""Data snapshot integrity, validation, and size governance helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from data_trust_constants import (
    DATA_SNAPSHOT_SCHEMA_VERSION,
    SNAPSHOT_CORE_DATA_KEYS,
    SNAPSHOT_TRIMMABLE_LIST_FIELDS,
    SUPPORTED_DATA_SNAPSHOT_SCHEMA_VERSIONS,
)
from data_trust_snapshot_mapping import hashable_snapshot_value as _hashable_snapshot_value, mapping_get, mapping_has_key
from data_trust_snapshot_sanitizer import sanitize_for_snapshot, snapshot_text
from mapping_fields import safe_mapping_items as _safe_mapping_items, safe_text


def snapshot_size_bytes(snapshot: dict) -> int:
    return len(
        json.dumps(sanitize_for_snapshot(snapshot), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def snapshot_content_hash(snapshot: Mapping) -> str:
    if not isinstance(snapshot, Mapping):
        return ""
    stable = {}
    for key, value in _safe_mapping_items(snapshot):
        key_str = safe_text(key)
        if not key_str or key_str in {"snapshot_hash", "content_hash", "snapshot_size_bytes"}:
            continue
        stable[key_str] = _hashable_snapshot_value(key_str, value)
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def set_snapshot_integrity(snapshot: dict) -> dict:
    digest = snapshot_content_hash(snapshot)
    snapshot["snapshot_hash"] = digest
    snapshot["content_hash"] = digest
    packet = snapshot.get("reproducibility_packet")
    if isinstance(packet, dict):
        packet["data_snapshot_hash"] = digest
    return set_stable_snapshot_size(snapshot)


def verify_data_snapshot_integrity(snapshot: Any) -> dict:
    if not isinstance(snapshot, Mapping):
        return {"valid": False, "hash": "", "expected_hash": "", "errors": ["snapshot must be an object"]}
    expected = safe_text(mapping_get(snapshot, "snapshot_hash")).strip()
    if not expected:
        expected = safe_text(mapping_get(snapshot, "content_hash")).strip()
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
    if not isinstance(snapshot, Mapping):
        return {"valid": False, "errors": ["snapshot must be an object"]}
    schema_version = mapping_get(snapshot, "snapshot_schema_version")
    if schema_version not in SUPPORTED_DATA_SNAPSHOT_SCHEMA_VERSIONS:
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
    if schema_version == DATA_SNAPSHOT_SCHEMA_VERSION:
        required_keys.extend([
            "data_confidence_score",
            "conclusion_guardrails",
            "reproducibility_packet",
        ])
    for key in required_keys:
        if not mapping_has_key(snapshot, key):
            errors.append(f"missing {key}")
    if not isinstance(mapping_get(snapshot, "source_audit", []), list):
        errors.append("source_audit must be a list")
    if not isinstance(mapping_get(snapshot, "data_trust", {}), Mapping):
        errors.append("data_trust must be an object")
    integrity = verify_data_snapshot_integrity(snapshot)
    errors.extend(dict.get(integrity, "errors", []))
    return {"valid": not errors, "errors": errors}


def apply_snapshot_size_governance(snapshot: dict, max_bytes: int | None = None) -> dict:
    try:
        from config import DATA_SNAPSHOT_MAX_BYTES

        limit = int(max_bytes or DATA_SNAPSHOT_MAX_BYTES)
    except Exception:
        limit = int(max_bytes or 2 * 1024 * 1024)

    governed = json.loads(json.dumps(sanitize_for_snapshot(snapshot), ensure_ascii=False, default=str))
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
            text_value = safe_text(text)
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
