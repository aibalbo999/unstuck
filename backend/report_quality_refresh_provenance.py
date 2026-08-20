"""Quality-gate provenance captured when a report data snapshot is refreshed."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_text


SCHEMA_VERSION = 1
_GATE_CONTRACTS = (
    ("report_conformance", "status", frozenset({"passed", "warning", "blocked", "failed", "rejected"})),
    ("evidence_exit_gate", "verdict", frozenset({"approved", "caution", "rejected"})),
    ("content_credibility", "status", frozenset({"passed", "warning", "blocked", "failed", "rejected"})),
)


def build_quality_metadata_refresh_provenance(snapshot: Any) -> dict[str, Any]:
    """Record which quality gates existed before a data-only refresh."""
    snapshot_map = safe_mapping_dict(snapshot) or {}
    recorded_fields: dict[str, str] = {}
    missing_fields: list[str] = []
    for field, state_key, allowed_states in _GATE_CONTRACTS:
        gate = safe_mapping_dict(dict.get(snapshot_map, field, {})) or {}
        state = safe_text(dict.get(gate, state_key)).strip().lower()
        if state in allowed_states:
            recorded_fields[field] = state
        else:
            missing_fields.append(field)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "previous_snapshot_before_refresh",
        "recorded_fields": recorded_fields,
        "missing_fields": missing_fields,
    }


__all__ = ["SCHEMA_VERSION", "build_quality_metadata_refresh_provenance"]
