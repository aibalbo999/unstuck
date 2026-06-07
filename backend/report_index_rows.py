"""SQLite row mapping for report metadata index."""

from __future__ import annotations

import json

from data_trust import normalize_data_trust, unknown_data_trust
from pipeline_modes import get_pipeline_definition
from report_index_parsing import parse_recommendation_summary


def row_to_report(row) -> dict:
    try:
        recommendation = json.loads(row["recommendation_json"])
    except (TypeError, json.JSONDecodeError):
        recommendation = parse_recommendation_summary(row["filename"], output_dir=row["output_dir"])
    try:
        data_trust = normalize_data_trust(json.loads(row["data_trust_json"]))
    except (KeyError, TypeError, json.JSONDecodeError):
        data_trust = unknown_data_trust()

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
        "data_snapshot_filename": row["data_snapshot_filename"] if "data_snapshot_filename" in row.keys() else "",
        "data_trust": data_trust,
        "data_trust_status": row["data_trust_status"] if "data_trust_status" in row.keys() else data_trust.get("status", "unknown"),
        "analysis_text_stale": bool(row["analysis_text_stale"]) if "analysis_text_stale" in row.keys() else False,
        "analysis_text_stale_message": row["analysis_text_stale_message"] if "analysis_text_stale_message" in row.keys() else "",
        "data_snapshot_hash": row["data_snapshot_hash"] if "data_snapshot_hash" in row.keys() else "",
    }
