"""Data snapshot sanitization, validation, and size governance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from data_trust_audit import data_snapshot_filename_for_report, utc_now_iso
from data_trust_constants import (
    DATA_SNAPSHOT_SCHEMA_VERSION,
)
from data_trust_snapshot_integrity import (
    apply_snapshot_size_governance,
    set_snapshot_integrity,
    set_stable_snapshot_size,
    snapshot_content_hash,
    snapshot_size_bytes,
    validate_data_snapshot,
    verify_data_snapshot_integrity,
)
from data_trust_snapshot_sanitizer import sanitize_for_snapshot, snapshot_text
from data_trust_scoring import build_data_trust, normalize_data_trust, unknown_data_trust
from mapping_fields import (
    safe_text,
    safe_mapping_dict,
)
from report_reproducibility import build_data_confidence_controls, build_reproducibility_packet


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return False


def _safe_text(value: Any) -> str:
    return safe_text(value)


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = _safe_text(value)
        if text != "":
            return text
    return default


def sanitize_rerun_context(context: dict) -> dict:
    if not isinstance(context, dict):
        return {"analyses": {}, "structured_outputs": {}, "parsed": {}}

    analyses = {}
    raw_analyses = dict.get(context, "analyses", {})
    if isinstance(raw_analyses, dict):
        for agent_num, text in raw_analyses.items():
            if text is None:
                continue
            agent_key = _safe_text(agent_num)
            if not agent_key:
                continue
            analyses[agent_key] = snapshot_text(text)

    return sanitize_for_snapshot({
        "analyses": analyses,
        "structured_outputs": dict.get(context, "structured_outputs", {}),
        "parsed": dict.get(context, "parsed", {}),
        "pipeline_id": dict.get(context, "pipeline_id"),
        "pipeline_label": dict.get(context, "pipeline_label"),
        "agent_sequence": dict.get(context, "agent_sequence"),
    })


def build_data_snapshot(
    context: dict,
    pipeline_id: Optional[str] = None,
    generated_at: Optional[str] = None,
    max_bytes: Optional[int] = None,
) -> dict:
    context_map = safe_mapping_dict(context)
    if context_map is None:
        context = {}
    else:
        context = context_map
    data = dict.get(context, "data", {}) if isinstance(context, dict) else {}
    data_map = safe_mapping_dict(data)
    if data_map is None:
        data = {}
    else:
        data = data_map
    existing_data_trust = dict.get(data, "data_trust")
    existing_data_trust_map = safe_mapping_dict(existing_data_trust)
    data_trust = (
        normalize_data_trust(existing_data_trust_map)
        if existing_data_trust_map is not None
        else build_data_trust(data)
    )
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
        "ticker": _first_text(dict.get(context, "ticker"), dict.get(data, "ticker")),
        "company_name": _first_text(dict.get(context, "company_name"), dict.get(data, "company_name")),
        "pipeline": _first_text(pipeline_id, dict.get(context, "pipeline_id"), dict.get(data, "pipeline_id")),
        "generated_at": snapshot_generated_at,
        "conclusion_generated_at": sanitize_for_snapshot(
            dict.get(context, "conclusion_generated_at") or snapshot_generated_at
        ),
        "snapshot_refreshed_at": sanitize_for_snapshot(dict.get(context, "snapshot_refreshed_at", "")),
        "decision_validity_status": sanitize_for_snapshot(
            dict.get(context, "decision_validity_status") or "current"
        ),
        "requires_rerun_reason": sanitize_for_snapshot(dict.get(context, "requires_rerun_reason", "")),
        "refreshed_from_report": sanitize_for_snapshot(dict.get(context, "refreshed_from_report", "")),
        "refreshed_without_analysis_rerun": _safe_bool(
            dict.get(context, "refreshed_without_analysis_rerun")
        ),
        "analysis_text_stale_message": sanitize_for_snapshot(
            dict.get(context, "analysis_text_stale_message", "")
        ),
        "data_schema_version": dict.get(data, "data_schema_version"),
        "source_freshness": sanitize_for_snapshot(dict.get(data, "source_freshness", {})),
        "source_audit": sanitize_for_snapshot(dict.get(data, "source_audit", [])),
        "data_trust": data_trust,
        "data_confidence_score": confidence_controls["data_confidence_score"],
        "data_confidence_status": confidence_controls["data_confidence_status"],
        "conclusion_guardrails": sanitize_for_snapshot(confidence_controls["conclusion_guardrails"]),
        "reproducibility_packet": sanitize_for_snapshot(
            build_reproducibility_packet(context, data_trust, snapshot_generated_at)
        ),
        "evidence_matrix": sanitize_for_snapshot(evidence_matrix),
        "data_source_notes": sanitize_for_snapshot(dict.get(data, "data_source_notes", [])),
        "deterministic_fallbacks": sanitize_for_snapshot(dict.get(context, "deterministic_fallbacks", [])),
        "report_lint": sanitize_for_snapshot(dict.get(context, "report_lint", {})),
        "content_credibility": sanitize_for_snapshot(dict.get(context, "content_credibility", {})),
        "report_conformance": sanitize_for_snapshot(dict.get(context, "report_conformance", {})),
        "rerun_context": sanitize_rerun_context(context),
        "data": sanitize_for_snapshot(data),
    }
    return apply_snapshot_size_governance(snapshot, max_bytes=max_bytes)


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
