"""SQLite row mapping for report metadata index."""

from __future__ import annotations

import json
import os

from data_trust import normalize_data_trust, unknown_data_trust
from data_trust_snapshot import verify_data_snapshot_integrity
from decision_tracking import build_decision_freshness, build_decision_tracking
from pipeline_modes import get_pipeline_definition
from recommendation_calibration import calibrate_recommendation_summary
from recommendation_labels import normalize_recommendation_label
from report_index_parsing import normalize_report_display_date, parse_recommendation_summary
from report_index_repair import recommendation_needs_rebuild
from report_paths import report_storage_candidates_for_filename
from report_preview import build_report_preview


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


def _snapshot_integrity(row) -> dict:
    snapshot = _read_snapshot(row)
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


def _company_name(row) -> str:
    try:
        ticker = str(row["ticker"] or "")
        stored = str(row["company_name"] or "").strip()
    except (KeyError, IndexError):
        ticker = ""
        stored = ""
    if stored and stored != ticker:
        return stored
    snapshot = _read_snapshot(row)
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


def _decision_tracking(row, recommendation: dict) -> dict:
    return build_decision_tracking(recommendation, _snapshot_path(row))


def _normalize_recommendation_summary(recommendation: dict) -> dict:
    if not isinstance(recommendation, dict):
        return {}
    normalized = dict(recommendation)
    normalized["recommendation"] = normalize_recommendation_label(normalized.get("recommendation"))
    return normalized


def _temporal_memory(row) -> dict:
    snapshot = _read_snapshot(row)
    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    memory = data.get("temporal_memory") if isinstance(data.get("temporal_memory"), dict) else {}
    return memory


def _evidence_exit_gate(row) -> dict:
    snapshot = _read_snapshot(row)
    gate = snapshot.get("evidence_exit_gate") if isinstance(snapshot, dict) else {}
    return gate if isinstance(gate, dict) else {}


def _report_conformance(row) -> dict:
    snapshot = _read_snapshot(row)
    conformance = snapshot.get("report_conformance") if isinstance(snapshot, dict) else {}
    return conformance if isinstance(conformance, dict) else {}


def _content_credibility(row) -> dict:
    snapshot = _read_snapshot(row)
    credibility = snapshot.get("content_credibility") if isinstance(snapshot, dict) else {}
    return credibility if isinstance(credibility, dict) else {}


def _markdown_text(row) -> str:
    path = _row_file_path(row, kind="md")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


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
    decision_tracking = _decision_tracking(row, recommendation)
    report_date = _report_date(row)
    decision_freshness = build_decision_freshness(
        _snapshot_path(row),
        report_generated_at=report_date,
    )

    pipeline_id = row["pipeline_id"] or "v1"
    markdown_text = _markdown_text(row)
    preview = build_report_preview(
        pipeline_id,
        row["ticker"],
        recommendation,
        markdown_text=markdown_text,
        snapshot_path=_snapshot_path(row),
    )

    return {
        "filename": row["filename"],
        "ticker": row["ticker"],
        "company_name": _company_name(row),
        "date": report_date,
        "timestamp": row["timestamp"],
        "pipeline_id": pipeline_id,
        "pipeline_label": get_pipeline_definition(pipeline_id)["short_label"],
        "recommendation": recommendation,
        "preview": preview,
        "decision_tracking": decision_tracking,
        "decision_freshness": decision_freshness,
        "temporal_memory": _temporal_memory(row),
        "evidence_exit_gate": _evidence_exit_gate(row),
        "report_conformance": _report_conformance(row),
        "content_credibility": _content_credibility(row),
        "snapshot_integrity": _snapshot_integrity(row),
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
