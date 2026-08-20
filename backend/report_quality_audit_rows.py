"""Snapshot and artifact row hydration for the report-quality audit."""

from __future__ import annotations

import json
from typing import Any, Callable

from mapping_fields import safe_text
from pipeline_modes import get_pipeline_definition, get_structured_agent_num
from report_rerun_context import parse_agent_sections_from_markdown
from reporting.content_credibility_final_audit import align_content_credibility_with_final_audit
from reporting.content_credibility_projection import merge_content_credibility_results, project_content_credibility


def hydrate_report_from_index_row(
    row: dict[str, Any],
    storage: Any,
    *,
    load_item: Callable[..., Any],
    verify_snapshot_integrity: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    filename = safe_text(row.get("filename")).strip()
    snapshot = _load_snapshot(storage, filename, load_item)
    integrity = snapshot_integrity(snapshot, verify_snapshot_integrity=verify_snapshot_integrity)
    stored = align_content_credibility_with_final_audit(
        snapshot.get("content_credibility", {}),
        snapshot.get("final_audit") or snapshot.get("report_conformance", {}),
    )
    projected = project_content_credibility(snapshot)
    recorded = safe_text(stored.get("status")).strip().lower() in {
        "passed", "warning", "blocked", "failed", "rejected",
    }
    return {
        "ticker": safe_text(row.get("ticker")).strip(),
        "filename": filename,
        "report_date": safe_text(row.get("report_date") or row.get("date")).strip(),
        "pipeline_id": safe_text(row.get("pipeline_id")).strip() or "v1",
        "snapshot_integrity": integrity,
        "refreshed_from_report": safe_text(snapshot.get("refreshed_from_report")).strip(),
        "snapshot_refreshed_at": safe_text(snapshot.get("snapshot_refreshed_at")).strip(),
        "refreshed_without_analysis_rerun": bool(snapshot.get("refreshed_without_analysis_rerun")),
        "decision_validity_status": safe_text(snapshot.get("decision_validity_status")).strip(),
        "rerun_context": snapshot.get("rerun_context", {}),
        "report_conformance": snapshot.get("report_conformance", {}),
        "evidence_exit_gate": snapshot.get("evidence_exit_gate", {}),
        "content_credibility": merge_content_credibility_results(stored, projected) if projected and recorded else stored,
        "content_credibility_projection": _projection_metadata(projected, stored, recorded),
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
    return {
        "status": "verified" if integrity.get("valid") else "invalid",
        "valid": bool(integrity.get("valid")),
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
        markdown = raw_content.decode("utf-8", errors="replace") if isinstance(raw_content, bytes) else safe_text(raw_content)
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


def _projection_metadata(projected: dict[str, Any] | None, stored: dict[str, Any], recorded: bool) -> dict[str, str]:
    return {
        "status": ("projected" if recorded else "available") if projected else "unavailable",
        "source": "snapshot.rerun_context",
        "persisted_status": safe_text(stored.get("status")).strip().lower(),
    }


__all__ = ["hydrate_report_from_index_row", "read_artifact_rerun_context_status", "snapshot_integrity"]
