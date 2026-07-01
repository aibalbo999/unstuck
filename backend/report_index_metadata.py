"""Metadata extraction helpers for generated report files."""

from __future__ import annotations

import json
import os
import hashlib
import time
from typing import Optional

from data_trust import data_snapshot_filename_for_report, normalize_data_trust, read_data_trust_from_snapshot
from decision_tracking import build_decision_freshness, build_decision_tracking
from report_paths import report_storage_candidates_for_filename
from report_index_parsing import (
    extract_company_name as _extract_company_name,
    is_safe_report_filename,
    normalize_recommendation_label,
    normalize_report_display_date,
    output_dir_key,
    parse_recommendation_summary,
    parse_report_filename,
)


def safe_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def file_sha256(path: str, content: Optional[str] = None) -> str:
    try:
        if content is not None:
            return hashlib.sha256(content.encode("utf-8")).hexdigest()
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def report_index_mtime(output_dir: str, filename: str) -> float:
    html_path = _report_path(output_dir, filename, kind="html")
    md_path = _report_path(output_dir, filename, kind="md")
    data_path = _report_path(output_dir, filename, kind="data")
    return max(safe_mtime(html_path), safe_mtime(md_path), safe_mtime(data_path))


def _report_path(output_dir: str, filename: str, *, kind: str) -> str:
    for key in report_storage_candidates_for_filename(filename, kind=kind):
        candidate = os.path.join(output_dir, key)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(output_dir, report_storage_candidates_for_filename(filename, kind=kind)[0])


def read_snapshot_report_flags(data_snapshot_path: str) -> dict:
    if not os.path.exists(data_snapshot_path):
        return {"analysis_text_stale": False, "analysis_text_stale_message": "", "data_snapshot_hash": ""}
    try:
        with open(data_snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"analysis_text_stale": False, "analysis_text_stale_message": "", "data_snapshot_hash": ""}
    return {
        "analysis_text_stale": bool(snapshot.get("refreshed_without_analysis_rerun")),
        "analysis_text_stale_message": str(snapshot.get("analysis_text_stale_message") or "")[:240],
        "data_snapshot_hash": str(snapshot.get("snapshot_hash") or snapshot.get("content_hash") or ""),
    }


def build_report_metadata(
    filename: str,
    output_dir: Optional[str] = None,
    html_content: Optional[str] = None,
    markdown_content: Optional[str] = None,
    data_trust: Optional[dict] = None,
) -> Optional[dict]:
    if not is_safe_report_filename(filename, ".html"):
        return None

    out_dir = output_dir_key(output_dir)
    html_path = _report_path(out_dir, filename, kind="html")
    md_path = _report_path(out_dir, filename, kind="md")
    if html_content is None and not os.path.exists(html_path):
        return None

    parsed = parse_report_filename(filename)
    html_mtime = safe_mtime(html_path) or time.time()
    file_mtime = max(html_mtime, report_index_mtime(out_dir, filename))

    company_name = _extract_company_name(filename, parsed["ticker"], out_dir, html_content)
    recommendation = parse_recommendation_summary(
        filename,
        output_dir=out_dir,
        markdown_text=markdown_content,
    )
    data_snapshot_filename = data_snapshot_filename_for_report(filename)
    data_snapshot_path = _report_path(out_dir, filename, kind="data")
    report_date = normalize_report_display_date(parsed["date"], snapshot_path=data_snapshot_path, timestamp=html_mtime)
    data_trust_summary = (
        normalize_data_trust(data_trust)
        if data_trust is not None
        else read_data_trust_from_snapshot(data_snapshot_path)
    )
    snapshot_flags = read_snapshot_report_flags(data_snapshot_path)
    decision_tracking = build_decision_tracking(recommendation, data_snapshot_path)
    decision_freshness = build_decision_freshness(data_snapshot_path, report_generated_at=report_date)
    normalized_recommendation = normalize_recommendation_label(recommendation.get("recommendation"))
    search_text = " ".join([
        filename,
        parsed["ticker"],
        company_name,
        str(recommendation.get("recommendation", "")),
    ]).lower()

    return {
        "output_dir": out_dir,
        "filename": filename,
        "md_filename": filename[:-5] + ".md",
        "ticker": parsed["ticker"],
        "company_name": company_name,
        "date": report_date,
        "timestamp": html_mtime,
        "file_mtime": file_mtime,
        "pipeline_id": parsed["pipeline_id"],
        "recommendation": recommendation,
        "data_snapshot_filename": data_snapshot_filename if os.path.exists(data_snapshot_path) else "",
        "data_trust": data_trust_summary,
        "data_trust_status": data_trust_summary.get("status", "unknown"),
        "analysis_text_stale": snapshot_flags["analysis_text_stale"],
        "analysis_text_stale_message": snapshot_flags["analysis_text_stale_message"],
        "data_snapshot_hash": snapshot_flags["data_snapshot_hash"],
        "html_hash": file_sha256(html_path, content=html_content),
        "markdown_hash": file_sha256(md_path, content=markdown_content),
        "data_file_hash": file_sha256(data_snapshot_path),
        "decision_tracking": decision_tracking,
        "decision_freshness": decision_freshness,
        "normalized_recommendation": normalized_recommendation,
        "search_text": search_text,
    }
