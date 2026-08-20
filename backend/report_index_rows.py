"""SQLite row mapping for report metadata index."""

from __future__ import annotations

import json
import os
from typing import Any

from data_trust import normalize_data_trust, unknown_data_trust
from data_trust_snapshot import verify_data_snapshot_integrity
from decision_tracking import build_decision_freshness, build_decision_tracking
from mapping_fields import safe_mapping_dict
from pipeline_modes import get_pipeline_definition
from recommendation_calibration import calibrate_recommendation_summary
from recommendation_labels import normalize_recommendation_label
from report_index_parsing import normalize_report_display_date, parse_recommendation_summary
from report_index_repair import recommendation_needs_rebuild
from report_history_storage import storage_for_existing_output_dir
from report_paths import report_storage_candidates_for_filename
from report_preview import build_report_preview, extract_trade_setup
from report_quality_evidence import read_artifact_quality_summary
from report_quality_metadata_repair import (
    quality_metadata_provenance_from_reason_codes,
    quality_metadata_repair_item,
)
from reporting.content_credibility import evaluate_content_credibility
from reporting.content_credibility_final_audit import align_content_credibility_with_final_audit
from reporting.content_credibility_projection import merge_content_credibility_results, project_content_credibility_with_current_evidence
from reporting.evidence_exit_gate_projection import evidence_exit_gate_projection_metadata, project_evidence_exit_gate
from reporting.report_conformance_projection import project_report_conformance, report_conformance_projection_metadata


def _row_file_path(row, *, kind: str) -> str:
    try:
        filename = row["filename"]
        output_dir = row["output_dir"]
    except (KeyError, IndexError):
        return ""
    for key in report_storage_candidates_for_filename(filename, kind=kind):
        candidate = os.path.join(output_dir, key)
        if os.path.exists(candidate):
            return candidate
    return ""


def _snapshot_path(row) -> str:
    path = _row_file_path(row, kind="data")
    if path:
        return path
    try:
        filename = row["data_snapshot_filename"] if "data_snapshot_filename" in row.keys() else ""
        output_dir = row["output_dir"]
    except (KeyError, IndexError):
        return ""
    if not filename:
        return ""
    candidate = os.path.join(output_dir, filename)
    return candidate if os.path.exists(candidate) else ""


def _read_snapshot(row) -> dict:
    path = _snapshot_path(row)
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (OSError, TypeError, json.JSONDecodeError):
        return {}
    return snapshot if isinstance(snapshot, dict) else {}


def _snapshot_integrity(row, *, snapshot: dict | None = None) -> dict:
    snapshot = snapshot if isinstance(snapshot, dict) else _read_snapshot(row)
    if not snapshot:
        return {
            "status": "unverified",
            "valid": None,
            "hash": "",
            "expected_hash": "",
            "errors": ["snapshot unavailable"],
        }

    integrity = verify_data_snapshot_integrity(snapshot)
    expected_hash = str(integrity.get("expected_hash") or "").strip()
    if not expected_hash:
        return {
            "status": "unverified",
            "valid": None,
            "hash": str(integrity.get("hash") or ""),
            "expected_hash": "",
            "errors": ["snapshot_hash missing"],
        }

    return {
        "status": "verified" if integrity.get("valid") else "invalid",
        "valid": bool(integrity.get("valid")),
        "hash": str(integrity.get("hash") or ""),
        "expected_hash": expected_hash,
        "errors": [str(error) for error in integrity.get("errors", []) if str(error)],
    }


def _company_name(row, *, snapshot: dict | None = None) -> str:
    try:
        ticker = str(row["ticker"] or "")
        stored = str(row["company_name"] or "").strip()
    except (KeyError, IndexError):
        ticker = ""
        stored = ""
    if stored and stored != ticker:
        return stored
    snapshot = snapshot if isinstance(snapshot, dict) else _read_snapshot(row)
    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    for source in (snapshot, data):
        candidate = str(source.get("company_name") or source.get("raw_company_name") or "").strip()
        if candidate and candidate not in {ticker, "N/A"}:
            return candidate
    return stored or ticker


def _report_date(row) -> str:
    try:
        parsed_date = row["report_date"] if "report_date" in row.keys() else ""
        timestamp = float(row["timestamp"] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        parsed_date = ""
        timestamp = 0.0
    return normalize_report_display_date(parsed_date, snapshot_path=_snapshot_path(row), timestamp=timestamp)


def _decision_tracking(row, recommendation: dict, *, snapshot: dict | None = None) -> dict:
    return build_decision_tracking(recommendation, _snapshot_path(row), snapshot=snapshot)


def _normalize_recommendation_summary(recommendation: dict) -> dict:
    if not isinstance(recommendation, dict):
        return {}
    normalized = dict(recommendation)
    normalized["recommendation"] = normalize_recommendation_label(normalized.get("recommendation"))
    return normalized


def _temporal_memory(row, *, snapshot: dict | None = None) -> dict:
    snapshot = snapshot if isinstance(snapshot, dict) else _read_snapshot(row)
    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    memory = data.get("temporal_memory") if isinstance(data.get("temporal_memory"), dict) else {}
    return memory


def _evidence_exit_gate(row, *, snapshot: dict | None = None) -> dict:
    snapshot = snapshot if isinstance(snapshot, dict) else _read_snapshot(row)
    gate = snapshot.get("evidence_exit_gate") if isinstance(snapshot, dict) else {}
    return gate if isinstance(gate, dict) else {}


def _report_conformance(row, *, snapshot: dict | None = None) -> dict:
    snapshot = snapshot if isinstance(snapshot, dict) else _read_snapshot(row)
    conformance = snapshot.get("report_conformance") if isinstance(snapshot, dict) else {}
    return conformance if isinstance(conformance, dict) else {}


_UNSET = object()


def _content_credibility(
    row,
    *,
    pipeline_id: str,
    markdown_text: str,
    snapshot: dict | None = None,
    projected: Any = _UNSET,
) -> dict:
    snapshot = snapshot if isinstance(snapshot, dict) else _read_snapshot(row)
    credibility = snapshot.get("content_credibility") if isinstance(snapshot, dict) else {}
    credibility = credibility if isinstance(credibility, dict) else {}
    final_audit_or_conformance = {}
    if isinstance(snapshot, dict):
        final_audit_or_conformance = snapshot.get("final_audit") or snapshot.get("report_conformance", {})
    credibility = align_content_credibility_with_final_audit(
        credibility,
        final_audit_or_conformance,
    )
    evidence_only_projection, projected = (projected, None) if isinstance(projected, dict) and projected.get("_projection_scope") == "evidence_confidence" else (None, projected)
    if projected is _UNSET:
        projected = project_content_credibility(snapshot)
    if projected is not None and _recorded_content_credibility(credibility):
        return merge_content_credibility_results(credibility, projected)
    if pipeline_id != "v4":
        return {key: value for key, value in projected.items() if key != "_projection_scope"} if projected is not None else (merge_content_credibility_results(credibility, evidence_only_projection) if evidence_only_projection and _recorded_content_credibility(credibility) else credibility)
    checks = credibility.get("checks") if isinstance(credibility.get("checks"), list) else []
    if any(isinstance(check, dict) and check.get("id") == "trade_setup_alignment" for check in checks):
        return merge_content_credibility_results(credibility, evidence_only_projection) if evidence_only_projection and _recorded_content_credibility(credibility) else credibility
    trade_setup = extract_trade_setup(snapshot, markdown_text)
    if not trade_setup:
        return merge_content_credibility_results(credibility, evidence_only_projection) if evidence_only_projection and _recorded_content_credibility(credibility) else credibility
    if not _recorded_content_credibility(credibility):
        return credibility

    data = safe_mapping_dict(snapshot.get("data")) or {}
    context = {
        "pipeline_id": "v4",
        "data": data,
        "parsed": {"trade_setup": trade_setup},
        "evidence_exit_gate": safe_mapping_dict(snapshot.get("evidence_exit_gate")) or {},
    }
    projected = evaluate_content_credibility(context, snapshot, markdown=markdown_text)
    if not _recorded_content_credibility(credibility):
        return projected
    return merge_content_credibility_results(evidence_only_projection, projected) if evidence_only_projection else merge_content_credibility_results(credibility, projected)


def _recorded_content_credibility(credibility: dict) -> bool:
    return str(credibility.get("status") or "").strip().lower() in {"passed", "warning", "blocked", "failed", "rejected"}


def _markdown_text(row) -> str:
    path = _row_file_path(row, kind="md")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _snapshot_text(row, key: str, *, snapshot: dict | None = None) -> str:
    snapshot = snapshot if isinstance(snapshot, dict) else _read_snapshot(row)
    value = snapshot.get(key)
    return str(value or "").strip()


def _quality_evidence(row, report: dict) -> dict:
    item = quality_metadata_repair_item(report)
    if item is None:
        return {}
    storage = storage_for_existing_output_dir(str(row["output_dir"]), None)
    return {
        "missing_quality_fields": item["missing_quality_fields"],
        "quality_metadata_provenance": quality_metadata_provenance_from_reason_codes(item["reason_codes"]),
        "refreshed_from_report": report.get("refreshed_from_report", ""),
        "snapshot_refreshed_at": report.get("snapshot_refreshed_at", ""),
        "artifact_quality_summary": read_artifact_quality_summary(storage, report.get("filename")),
    }


def row_to_report(row) -> dict:
    try:
        data_trust = normalize_data_trust(json.loads(row["data_trust_json"]))
    except (KeyError, TypeError, json.JSONDecodeError):
        data_trust = unknown_data_trust()
    try:
        recommendation = json.loads(row["recommendation_json"])
    except (TypeError, json.JSONDecodeError):
        recommendation = parse_recommendation_summary(row["filename"], output_dir=row["output_dir"])
    if recommendation_needs_rebuild(recommendation):
        rebuilt_recommendation = parse_recommendation_summary(row["filename"], output_dir=row["output_dir"])
        if not recommendation_needs_rebuild(rebuilt_recommendation):
            recommendation = rebuilt_recommendation
    recommendation = calibrate_recommendation_summary(
        recommendation,
        data_trust=data_trust,
        analysis_text_stale=bool(row["analysis_text_stale"]) if "analysis_text_stale" in row.keys() else False,
        pipeline_id=row["pipeline_id"] if "pipeline_id" in row.keys() else "",
    )
    recommendation = _normalize_recommendation_summary(recommendation)
    snapshot_path = _snapshot_path(row)
    snapshot = _read_snapshot(row)
    decision_tracking = _decision_tracking(row, recommendation, snapshot=snapshot)
    report_date = _report_date(row)
    decision_freshness = build_decision_freshness(
        snapshot_path,
        report_generated_at=report_date,
        snapshot=snapshot,
    )
    pipeline_id = row["pipeline_id"] or "v1"
    markdown_text = _markdown_text(row)
    stored_evidence_exit_gate = _evidence_exit_gate(row, snapshot=snapshot)
    projected_evidence_exit_gate = project_evidence_exit_gate(snapshot, markdown_text)
    stored_content_credibility = snapshot.get("content_credibility") if isinstance(snapshot.get("content_credibility"), dict) else {}
    stored_content_credibility = align_content_credibility_with_final_audit(
        stored_content_credibility,
        snapshot.get("final_audit") or snapshot.get("report_conformance", {}),
    )
    projected_content_credibility = project_content_credibility_with_current_evidence(snapshot, stored_content_credibility, evidence_projection=projected_evidence_exit_gate, recommendation=recommendation)
    preview = build_report_preview(
        pipeline_id,
        row["ticker"],
        recommendation,
        markdown_text=markdown_text,
        snapshot_path=snapshot_path,
        snapshot=snapshot,
    )

    report = {
        "filename": row["filename"],
        "ticker": row["ticker"],
        "company_name": _company_name(row, snapshot=snapshot),
        "date": report_date,
        "timestamp": row["timestamp"],
        "pipeline_id": pipeline_id,
        "pipeline_label": get_pipeline_definition(pipeline_id)["short_label"],
        "recommendation": recommendation,
        "preview": preview,
        "decision_tracking": decision_tracking,
        "decision_freshness": decision_freshness,
        "temporal_memory": _temporal_memory(row, snapshot=snapshot),
        "evidence_exit_gate": projected_evidence_exit_gate or stored_evidence_exit_gate,
        "report_conformance": project_report_conformance(_report_conformance(row, snapshot=snapshot), projected_evidence_exit_gate, projected_content_credibility),
        "content_credibility": _content_credibility(
            row,
            pipeline_id=pipeline_id,
            markdown_text=markdown_text,
            snapshot=dict(snapshot, evidence_exit_gate=projected_evidence_exit_gate) if projected_evidence_exit_gate is not None else snapshot,
            projected=projected_content_credibility,
        ),
        "snapshot_integrity": _snapshot_integrity(row, snapshot=snapshot),
        "data_snapshot_filename": row["data_snapshot_filename"] if "data_snapshot_filename" in row.keys() else "",
        "data_trust": data_trust,
        "data_trust_status": row["data_trust_status"] if "data_trust_status" in row.keys() else data_trust.get("status", "unknown"),
        "analysis_text_stale": bool(row["analysis_text_stale"]) if "analysis_text_stale" in row.keys() else False,
        "analysis_text_stale_message": row["analysis_text_stale_message"] if "analysis_text_stale_message" in row.keys() else "",
        "data_snapshot_hash": row["data_snapshot_hash"] if "data_snapshot_hash" in row.keys() else "",
        "html_hash": row["html_hash"] if "html_hash" in row.keys() else "",
        "markdown_hash": row["markdown_hash"] if "markdown_hash" in row.keys() else "",
        "data_file_hash": row["data_file_hash"] if "data_file_hash" in row.keys() else "",
    }
    quality_refresh_provenance = snapshot.get("quality_metadata_refresh_provenance")
    if isinstance(quality_refresh_provenance, dict) and quality_refresh_provenance:
        report["quality_metadata_refresh_provenance"] = quality_refresh_provenance
    if projected_content_credibility is not None:
        report["content_credibility_projection"] = {
            "status": "projected" if _recorded_content_credibility(stored_content_credibility) else "available",
            "source": "snapshot.current_evidence" if projected_content_credibility.get("_projection_scope") == "evidence_confidence" else "snapshot.recommendation_context" if projected_content_credibility.get("_projection_scope") == "recommendation_context" else "snapshot.rerun_context",
            "persisted_status": str(stored_content_credibility.get("status") or "").strip().lower(),
        }
    if projected_evidence_exit_gate is not None:
        report["evidence_exit_gate_projection"] = evidence_exit_gate_projection_metadata(
            projected_evidence_exit_gate, stored_evidence_exit_gate
        )
    report.update({"report_conformance_projection": projection_metadata} if (projection_metadata := report_conformance_projection_metadata(_report_conformance(row, snapshot=snapshot), report.get("report_conformance"))) else {})
    report["refreshed_from_report"] = _snapshot_text(row, "refreshed_from_report", snapshot=snapshot)
    report["snapshot_refreshed_at"] = _snapshot_text(row, "snapshot_refreshed_at", snapshot=snapshot)
    report.update(_quality_evidence(row, {**report, "report_conformance": _report_conformance(row, snapshot=snapshot), "evidence_exit_gate": stored_evidence_exit_gate}))
    if not report.get("missing_quality_fields"):
        report.pop("refreshed_from_report", None)
        report.pop("snapshot_refreshed_at", None)
    return report
