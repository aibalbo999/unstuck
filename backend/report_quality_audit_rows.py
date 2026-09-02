"""Snapshot and artifact row hydration for the report-quality audit."""

from __future__ import annotations

import json
from typing import Any, Callable

from mapping_fields import safe_mapping_dict, safe_text
from decision_tracking import build_decision_freshness
from pipeline_modes import get_pipeline_definition, get_structured_agent_num
from report_artifact_text import decode_utf8_artifact_text
from report_rerun_context import parse_agent_sections_from_markdown
from reporting.content_credibility_final_audit import align_content_credibility_with_final_audit
from reporting.content_credibility_projection import merge_content_credibility_results, project_content_credibility
from reporting.evidence_exit_gate_projection import evidence_exit_gate_projection_metadata, project_evidence_exit_gate
from report_freshness_summary import safe_bool


def hydrate_report_from_index_row(
    row: dict[str, Any],
    storage: Any,
    *,
    load_item: Callable[..., Any],
    verify_snapshot_integrity: Callable[[dict[str, Any]], dict[str, Any]],
    project_current_quality: bool = True,
) -> dict[str, Any]:
    filename = safe_text(row.get("filename")).strip()
    snapshot = _load_snapshot(storage, filename, load_item)
    integrity = snapshot_integrity(snapshot, verify_snapshot_integrity=verify_snapshot_integrity)
    stored = align_content_credibility_with_final_audit(
        snapshot.get("content_credibility", {}),
        snapshot.get("final_audit") or snapshot.get("report_conformance", {}),
    )
    stored_evidence = safe_mapping_dict(snapshot.get("evidence_exit_gate")) or {}
    recorded_evidence = safe_text(stored_evidence.get("verdict")).strip().lower() in {
        "approved", "caution", "rejected",
    }
    recorded = safe_text(stored.get("status")).strip().lower() in {
        "passed", "warning", "blocked", "failed", "rejected",
    }
    projected = project_content_credibility(snapshot) if project_current_quality and recorded else None
    projected_evidence = None
    if project_current_quality and recorded_evidence:
        projected_evidence = project_evidence_exit_gate(
            snapshot,
            _load_markdown(storage, filename, load_item),
        )
    return {
        "ticker": safe_text(row.get("ticker")).strip(),
        "filename": filename,
        "report_date": safe_text(row.get("report_date") or row.get("date")).strip(),
        "pipeline_id": safe_text(row.get("pipeline_id")).strip() or "v1",
        "snapshot_integrity": integrity,
        "refreshed_from_report": safe_text(snapshot.get("refreshed_from_report")).strip(),
        "snapshot_refreshed_at": safe_text(snapshot.get("snapshot_refreshed_at")).strip(),
        "decision_freshness": build_decision_freshness(
            report_generated_at=safe_text(row.get("report_date") or row.get("date")).strip(),
            snapshot=snapshot,
        ),
        "quality_metadata_refresh_provenance": snapshot.get("quality_metadata_refresh_provenance", {}),
        "refreshed_without_analysis_rerun": safe_bool(snapshot.get("refreshed_without_analysis_rerun")),
        "decision_validity_status": safe_text(snapshot.get("decision_validity_status")).strip(),
        "rerun_context": snapshot.get("rerun_context", {}),
        "report_conformance": snapshot.get("report_conformance", {}),
        "evidence_exit_gate": projected_evidence or stored_evidence,
        "content_credibility": merge_content_credibility_results(stored, projected) if projected and recorded else stored,
        "content_credibility_projection": _projection_metadata(projected, stored, recorded),
        **(
            {
                "evidence_exit_gate_projection": evidence_exit_gate_projection_metadata(
                    projected_evidence,
                    stored_evidence,
                )
            }
            if projected_evidence is not None
            else {}
        ),
    }


def snapshot_integrity(
    snapshot: dict[str, Any],
    *,
    verify_snapshot_integrity: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    if not snapshot:
        return {"status": "unverified", "valid": None, "errors": ["snapshot unavailable"]}
    try:
        integrity = verify_snapshot_integrity(snapshot)
    except Exception:
        return {"status": "unverified", "valid": None, "errors": ["snapshot integrity check failed"]}
    expected_hash = safe_text(integrity.get("expected_hash")).strip()
    if not expected_hash:
        return {"status": "unverified", "valid": None, "errors": ["snapshot_hash missing"]}
    valid = safe_bool(integrity.get("valid"))
    return {
        "status": "verified" if valid else "invalid",
        "valid": valid,
        "errors": [safe_text(error) for error in integrity.get("errors", []) if safe_text(error)],
    }


def read_artifact_rerun_context_status(
    storage: Any,
    filename: Any,
    pipeline_id: Any,
    *,
    load_item: Callable[..., Any],
) -> str:
    if not storage or not safe_text(filename).strip():
        return "unavailable"
    try:
        item = load_item(storage, safe_text(filename).strip(), kind="md")
    except Exception:
        return "unavailable"
    if item is None:
        return "unavailable"
    try:
        raw_content = item.content
        markdown = decode_utf8_artifact_text(raw_content)
        if markdown is None:
            return "unavailable"
        sections = parse_agent_sections_from_markdown(markdown)
        pipeline = get_pipeline_definition(safe_text(pipeline_id).strip() or "v1")
        final_agent = get_structured_agent_num("recommendation", pipeline["id"])
        if final_agent is None:
            return "unavailable"
        required_agents = [agent for agent in pipeline["agents"] if agent < final_agent]
        if all(agent in sections for agent in required_agents):
            return "present"
        return "partial" if sections else "missing"
    except Exception:
        return "unavailable"


def _load_snapshot(storage: Any, filename: str, load_item: Callable[..., Any]) -> dict[str, Any]:
    try:
        item = load_item(storage, filename, kind="data") if storage and filename else None
    except Exception:
        item = None
    if item is None:
        return {}
    try:
        snapshot = json.loads(item.content)
    except Exception:
        return {}
    return snapshot if isinstance(snapshot, dict) else {}


def _load_markdown(storage: Any, filename: str, load_item: Callable[..., Any]) -> str:
    try:
        item = load_item(storage, filename, kind="md") if storage and filename else None
    except Exception:
        item = None
    if item is None:
        return ""
    try:
        raw_content = item.content
        return decode_utf8_artifact_text(raw_content) or ""
    except Exception:
        return ""


def _projection_metadata(projected: dict[str, Any] | None, stored: dict[str, Any], recorded: bool) -> dict[str, str]:
    return {
        "status": "projected" if projected else ("unavailable" if recorded else "available"),
        "source": "snapshot.rerun_context",
        "persisted_status": safe_text(stored.get("status")).strip().lower(),
    }


__all__ = ["hydrate_report_from_index_row", "read_artifact_rerun_context_status", "snapshot_integrity"]
