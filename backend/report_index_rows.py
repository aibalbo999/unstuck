"""SQLite row mapping for report metadata index."""

from __future__ import annotations

import json
import os

from data_trust import normalize_data_trust, unknown_data_trust
from decision_tracking import build_decision_freshness, build_decision_tracking
from pipeline_modes import get_pipeline_definition
from report_index_parsing import parse_recommendation_summary


def _snapshot_path(row) -> str:
    try:
        filename = row["data_snapshot_filename"] if "data_snapshot_filename" in row.keys() else ""
        output_dir = row["output_dir"]
    except (KeyError, IndexError):
        return ""
    return os.path.join(output_dir, filename) if filename else ""


def _decision_tracking(row, recommendation: dict) -> dict:
    return build_decision_tracking(recommendation, _snapshot_path(row))


def _temporal_memory(row) -> dict:
    path = _snapshot_path(row)
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (OSError, TypeError, json.JSONDecodeError):
        return {}
    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    memory = data.get("temporal_memory") if isinstance(data.get("temporal_memory"), dict) else {}
    return memory


def row_to_report(row) -> dict:
    try:
        recommendation = json.loads(row["recommendation_json"])
    except (TypeError, json.JSONDecodeError):
        recommendation = parse_recommendation_summary(row["filename"], output_dir=row["output_dir"])
    try:
        data_trust = normalize_data_trust(json.loads(row["data_trust_json"]))
    except (KeyError, TypeError, json.JSONDecodeError):
        data_trust = unknown_data_trust()
    decision_tracking = _decision_tracking(row, recommendation)
    decision_freshness = build_decision_freshness(
        _snapshot_path(row),
        report_generated_at=row["report_date"] if "report_date" in row.keys() else "",
    )

    pipeline_id = row["pipeline_id"] or "v1"
    return {
        "filename": row["filename"],
        "ticker": row["ticker"],
        "company_name": row["company_name"],
        "date": row["report_date"],
        "timestamp": row["timestamp"],
        "pipeline_id": pipeline_id,
        "pipeline_label": get_pipeline_definition(pipeline_id)["short_label"],
        "recommendation": recommendation,
        "decision_tracking": decision_tracking,
        "decision_freshness": decision_freshness,
        "temporal_memory": _temporal_memory(row),
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
