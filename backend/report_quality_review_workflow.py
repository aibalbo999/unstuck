"""Revision-bound manual review orchestration for report quality gaps."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

import report_quality_audit
from mapping_fields import safe_int, safe_mapping_dict, safe_text
from report_pipeline_identity import resolve_report_pipeline_id
from report_quality_repair_items import quality_metadata_repair_item
from report_quality_review_store import list_review_history, pending_review
from reporting.text_tokens import is_missing_text_token


def report_quality_revision(row: dict[str, Any]) -> str:
    digest = sha256()
    for field in (
        # Index write time and filesystem mtime are refresh signals, not report versions.
        "output_dir", "filename", "pipeline_id",
        "data_snapshot_hash", "html_hash", "markdown_hash", "data_file_hash",
    ):
        digest.update(safe_text(row.get(field)).encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def serialize_quality_review(review: dict[str, Any], revision: str) -> dict[str, Any]:
    payload = {
        "status": safe_text(review.get("status")).strip() or "pending",
        "decision": safe_text(review.get("decision")).strip(),
        "decision_label": safe_text(review.get("decision_label")).strip() or "待人工核對",
        "reviewer_label": safe_text(review.get("reviewer_label")).strip(),
        "note": safe_text(review.get("note")),
        "reviewed_at": review.get("reviewed_at"),
        "event_count": max(0, safe_int(review.get("event_count"), default=0)),
        "report_quality_revision": safe_text(review.get("report_quality_revision")).strip() or revision,
    }
    event_id = safe_int(review.get("event_id"), default=0)
    if event_id > 0:
        payload["event_id"] = event_id
    return payload


def attach_quality_reviews(reports: list[dict[str, Any]], output_dir: str) -> None:
    normalized_output_dir = safe_text(output_dir).strip()
    targets = [
        target
        for report in reports
        for target in [_review_target(report)]
        if target is not None
        if quality_metadata_repair_item(report) is not None and safe_text(report.get("report_quality_revision")).strip()
    ]
    review_history = list_review_history(normalized_output_dir, targets) if normalized_output_dir and targets else {}
    for report in reports:
        if quality_metadata_repair_item(report) is None:
            continue
        target = _review_target(report)
        if target is None:
            continue
        history = review_history.get(target, [])
        report["quality_review_history"] = history
        report["quality_review"] = history[0] if history else pending_review(report_quality_revision=target[2])


def get_indexed_report_quality_review_target(
    output_dir: str,
    *,
    filename: str,
    pipeline_id: str,
) -> dict[str, Any] | None:
    """Load one current indexed quality-gap target for an explicit review."""
    normalized_filename = safe_text(filename).strip()
    requested_pipeline = safe_text(pipeline_id).strip()
    normalized_pipeline = resolve_report_pipeline_id(
        normalized_filename,
        stored_pipeline=requested_pipeline,
    )
    if not normalized_filename:
        return None
    rows, _total = report_quality_audit.query_report_metadata(
        page=1,
        limit=1000,
        q=normalized_filename,
        # Placeholder pipeline values cannot be used as an index filter because
        # the filename is the only remaining identity evidence.
        pipeline="all" if is_missing_text_token(requested_pipeline) else normalized_pipeline,
        recommendation="all",
        data_trust="all",
        include_versions=True,
        output_dir=output_dir,
        sync_metadata=False,
        row_mapper=report_quality_audit._raw_row,
    )
    row = next(
        (
            candidate
            for candidate in rows
            if safe_text(candidate.get("filename")).strip() == normalized_filename
            and resolve_report_pipeline_id(
                normalized_filename,
                stored_pipeline=candidate.get("pipeline_id"),
            ) == normalized_pipeline
        ),
        None,
    )
    if row is None:
        return None
    storage = report_quality_audit.storage_for_existing_output_dir(output_dir, None)
    report = report_quality_audit._report_from_index_row(row, storage)
    report["report_quality_revision"] = report_quality_revision(row)
    item = quality_metadata_repair_item(report)
    if item is None:
        return None
    report["artifact_quality_summary"] = report_quality_audit._read_artifact_quality_summary(storage, normalized_filename)
    target = _review_target(report)
    if target is None:
        return None
    history = list_review_history(output_dir, [target]).get(target, [])
    report["quality_review_history"] = history
    report["quality_review"] = history[0] if history else pending_review(report_quality_revision=target[2])
    return report_quality_audit._audit_item(report, item)


def _review_target(report: dict[str, Any]) -> tuple[str, str, str] | None:
    filename = safe_text(report.get("filename") or report.get("report_filename")).strip()
    revision = safe_text(report.get("report_quality_revision")).strip()
    if not filename or not revision:
        return None
    return (
        filename,
        resolve_report_pipeline_id(filename, stored_pipeline=report.get("pipeline_id")),
        revision,
    )


__all__ = ["attach_quality_reviews", "get_indexed_report_quality_review_target", "report_quality_revision", "serialize_quality_review"]
