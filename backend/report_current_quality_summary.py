"""Summarize read-only current quality projections for indexed reports."""

from __future__ import annotations

from threading import RLock
from time import monotonic
from typing import Any

from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text
from report_history_pagination import collect_all_report_pages
from report_index import query_report_metadata
from report_freshness_summary import report_freshness_bucket


SCHEMA_VERSION = "report_current_quality_summary.v1"
CURRENT_QUALITY_ITEM_LIMIT = 5
CURRENT_QUALITY_CACHE_TTL_SECONDS = 30.0
CONFORMANCE_STATUSES = ("passed", "warning", "blocked", "unknown")
CONTENT_STATUSES = ("passed", "warning", "blocked", "unknown")
EVIDENCE_VERDICTS = ("approved", "caution", "rejected", "unknown")
EVIDENCE_MISMATCH_FRESHNESS_BUCKETS = ("current", "needs_rerun", "unknown")
_SUMMARY_CACHE: dict[tuple[str, int, int, str, str], tuple[float, dict[str, Any]]] = {}
_SUMMARY_CACHE_LOCK = RLock()


def build_indexed_current_quality_summary(
    output_dir: str,
    *,
    page_size: int = 100,
    item_limit: int = CURRENT_QUALITY_ITEM_LIMIT,
) -> dict[str, Any]:
    cache_key = (str(output_dir), max(1, int(page_size)), max(0, safe_int(item_limit, default=CURRENT_QUALITY_ITEM_LIMIT)))
    now = monotonic()
    with _SUMMARY_CACHE_LOCK:
        cached = _SUMMARY_CACHE.get(cache_key)
        if cached is not None and now - cached[0] < CURRENT_QUALITY_CACHE_TTL_SECONDS:
            return cached[1]
    rows = collect_all_report_pages(
        _list_current_quality_rows,
        page_size=page_size,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        include_versions=False,
        output_dir=output_dir,
        sync_metadata=False,
    )
    summary = build_current_quality_summary(
        rows.get("reports", []),
        scope="all_indexed_reports",
        selection_basis="latest_per_ticker_pipeline",
        item_limit=item_limit,
    )
    with _SUMMARY_CACHE_LOCK:
        _SUMMARY_CACHE[cache_key] = (monotonic(), summary)
        if len(_SUMMARY_CACHE) > 4:
            oldest_key = min(_SUMMARY_CACHE, key=lambda key: _SUMMARY_CACHE[key][0])
            _SUMMARY_CACHE.pop(oldest_key, None)
    return summary


def build_filtered_indexed_current_quality_summary(
    output_dir: str,
    *,
    page_size: int = 100,
    q: str = "",
    pipeline: str = "all",
    item_limit: int = 0,
) -> dict[str, Any]:
    """Build the current-quality view for a historical-audit filter.

    This deliberately keeps the latest-version selection and current-rule
    projection separate from the historical persisted-metadata audit.
    """
    normalized_page_size = max(1, int(page_size))
    normalized_query = safe_text(q).strip()
    normalized_pipeline = safe_text(pipeline).strip().lower() or "all"
    normalized_item_limit = max(0, safe_int(item_limit, default=0))
    cache_key = (
        str(output_dir),
        normalized_page_size,
        normalized_item_limit,
        normalized_query,
        normalized_pipeline,
    )
    now = monotonic()
    with _SUMMARY_CACHE_LOCK:
        cached = _SUMMARY_CACHE.get(cache_key)
        if cached is not None and now - cached[0] < CURRENT_QUALITY_CACHE_TTL_SECONDS:
            return cached[1]
    rows = collect_all_report_pages(
        _list_current_quality_rows,
        page_size=normalized_page_size,
        q=normalized_query,
        pipeline=normalized_pipeline,
        recommendation="all",
        data_trust="all",
        include_versions=False,
        output_dir=output_dir,
        sync_metadata=False,
    )
    summary = build_current_quality_summary(
        rows.get("reports", []),
        scope="historical_filter_current_latest",
        selection_basis="latest_per_ticker_pipeline",
        item_limit=normalized_item_limit,
    )
    summary["filters"] = {"q": normalized_query, "pipeline": normalized_pipeline}
    with _SUMMARY_CACHE_LOCK:
        _SUMMARY_CACHE[cache_key] = (monotonic(), summary)
        if len(_SUMMARY_CACHE) > 8:
            oldest_key = min(_SUMMARY_CACHE, key=lambda key: _SUMMARY_CACHE[key][0])
            _SUMMARY_CACHE.pop(oldest_key, None)
    return summary


def build_current_quality_summary(
    reports: dict[str, Any] | list[dict[str, Any]],
    *,
    scope: str = "daily_report_sample",
    selection_basis: str | None = None,
    item_limit: int = CURRENT_QUALITY_ITEM_LIMIT,
) -> dict[str, Any]:
    rows = _report_rows(reports)
    scope_text = safe_text(scope).strip() or "daily_report_sample"
    selection_basis_text = safe_text(selection_basis).strip() or (
        "latest_per_ticker_pipeline" if scope_text == "all_indexed_reports" else "caller_supplied_rows"
    )
    conformance = {status: 0 for status in CONFORMANCE_STATUSES}
    content = {status: 0 for status in CONTENT_STATUSES}
    evidence = {verdict: 0 for verdict in EVIDENCE_VERDICTS}
    evidence_failed_count = 0
    evidence_reason_counts: dict[str, int] = {}
    conformance_blocker_counts: dict[str, int] = {}
    content_blocker_counts: dict[str, int] = {}
    evidence_mismatch_claims_by_freshness = {bucket: 0 for bucket in EVIDENCE_MISMATCH_FRESHNESS_BUCKETS}
    evidence_mismatch_reports_by_freshness = {bucket: 0 for bucket in EVIDENCE_MISMATCH_FRESHNESS_BUCKETS}
    non_passed = []
    for report in rows:
        conformance_status = _conformance_status(report.get("report_conformance"))
        content_status = _content_status(report.get("content_credibility"))
        evidence_verdict = _evidence_verdict(report.get("evidence_exit_gate"))
        conformance[conformance_status] += 1
        content[content_status] += 1
        evidence[evidence_verdict] += 1
        report_failed_count = _evidence_failed_count(report.get("evidence_exit_gate"))
        evidence_failed_count += report_failed_count
        if report_failed_count:
            freshness_bucket = report_freshness_bucket(report)
            evidence_mismatch_claims_by_freshness[freshness_bucket] += report_failed_count
            evidence_mismatch_reports_by_freshness[freshness_bucket] += 1
        for reason, count in _evidence_reason_counts(report.get("evidence_exit_gate")).items():
            evidence_reason_counts[reason] = evidence_reason_counts.get(reason, 0) + count
        for blocker_id in _blocker_ids(report.get("report_conformance"), include_decision_tree=True):
            conformance_blocker_counts[blocker_id] = conformance_blocker_counts.get(blocker_id, 0) + 1
        for blocker_id in _blocker_ids(report.get("content_credibility")):
            content_blocker_counts[blocker_id] = content_blocker_counts.get(blocker_id, 0) + 1
        if conformance_status != "passed":
            non_passed.append(_current_quality_item(report, conformance_status, content_status, evidence_verdict))

    non_passed.sort(key=lambda item: (_status_rank(item["report_conformance_status"]), item["filename"]))
    limit = max(0, safe_int(item_limit, default=CURRENT_QUALITY_ITEM_LIMIT))
    items = non_passed[:limit]
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": scope_text,
        "selection_basis": selection_basis_text,
        "audited_reports": len(rows),
        "report_conformance_by_status": conformance,
        "content_credibility_by_status": content,
        "evidence_exit_gate_by_verdict": evidence,
        "evidence_failed_count": evidence_failed_count,
        "evidence_mismatch_claims_by_freshness": evidence_mismatch_claims_by_freshness,
        "evidence_mismatch_reports_by_freshness": evidence_mismatch_reports_by_freshness,
        "evidence_unverifiable_reason_counts": evidence_reason_counts,
        "report_conformance_blocker_counts": dict(sorted(conformance_blocker_counts.items())),
        "content_credibility_blocker_counts": dict(sorted(content_blocker_counts.items())),
        "non_passed_reports": len(non_passed),
        "items_limit": limit,
        "items_total": len(non_passed),
        "items_returned": len(items),
        "items_truncated": len(items) < len(non_passed),
        "items": items,
    }


def build_unavailable_current_quality_summary(
    *,
    scope: str = "all_indexed_reports",
    selection_basis: str = "latest_per_ticker_pipeline",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": scope,
        "selection_basis": selection_basis,
        "status": "unavailable",
        "error_code": "current_quality_summary_unavailable",
    }


def _list_current_quality_rows(*, page: int, limit: int, **filters: Any) -> dict[str, Any]:
    rows, total = query_report_metadata(page=page, limit=limit, **filters)
    return {"reports": rows, "pagination": {"page": page, "limit": limit, "total": total}}


def _report_rows(reports: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(reports, dict):
        return safe_dict_list(reports.get("reports"))
    return safe_dict_list(reports)


def _conformance_status(value: Any) -> str:
    status = safe_text((safe_mapping_dict(value) or {}).get("status")).strip().lower()
    if status in {"blocked", "failed", "rejected"}:
        return "blocked"
    return status if status in {"passed", "warning"} else "unknown"


def _content_status(value: Any) -> str:
    status = safe_text((safe_mapping_dict(value) or {}).get("status")).strip().lower()
    if status in {"blocked", "failed", "rejected"}:
        return "blocked"
    return status if status in {"passed", "warning"} else "unknown"


def _evidence_verdict(value: Any) -> str:
    verdict = safe_text((safe_mapping_dict(value) or {}).get("verdict")).strip().lower()
    return verdict if verdict in {"approved", "caution", "rejected"} else "unknown"


def _evidence_reason_counts(value: Any) -> dict[str, int]:
    gate = safe_mapping_dict(value) or {}
    raw_counts = safe_mapping_dict(gate.get("unverifiable_reason_counts")) or {}
    return {
        reason: count
        for raw_reason, raw_count in raw_counts.items()
        if (reason := safe_text(raw_reason).strip())
        and (count := safe_int(raw_count, default=0)) > 0
    }


def _evidence_failed_count(value: Any) -> int:
    gate = safe_mapping_dict(value) or {}
    return max(0, safe_int(gate.get("failed_count"), default=0))


def _blocker_ids(value: Any, *, include_decision_tree: bool = False) -> set[str]:
    gate = safe_mapping_dict(value) or {}
    blocker_ids = {
        safe_text(issue.get("id")).strip() or "unknown"
        for issue in safe_dict_list(gate.get("blocking_issues"))
    }
    if include_decision_tree:
        blocker_ids.update(
            safe_text(step.get("id")).strip() or "unknown"
            for step in safe_dict_list(gate.get("decision_tree"))
            if safe_text(step.get("status")).strip().lower() in {"blocked", "failed", "rejected"}
        )
    elif not blocker_ids:
        blocker_ids.update(
            safe_text(check.get("id")).strip() or "unknown"
            for check in safe_dict_list(gate.get("checks"))
            if safe_text(check.get("status")).strip().lower() in {"blocked", "failed", "rejected"}
        )
    return blocker_ids


def _current_quality_item(
    report: dict[str, Any],
    conformance_status: str,
    content_status: str,
    evidence_verdict: str,
) -> dict[str, Any]:
    conformance = safe_mapping_dict(report.get("report_conformance")) or {}
    evidence_failed_count = _evidence_failed_count(report.get("evidence_exit_gate"))
    evidence_reason_counts = _evidence_reason_counts(report.get("evidence_exit_gate"))
    issues = safe_dict_list(conformance.get("blocking_issues")) + safe_dict_list(conformance.get("warnings"))
    reason = next(
        (
            safe_text(issue.get("message") or issue.get("detail")).strip()
            for issue in issues
            if safe_text(issue.get("message") or issue.get("detail")).strip()
        ),
        "目前品質狀態需要人工查看。",
    )
    payload = {
        "ticker": safe_text(report.get("ticker")).strip(),
        "pipeline_id": safe_text(report.get("pipeline_id")).strip() or "v1",
        "filename": safe_text(report.get("filename") or report.get("report_filename")).strip(),
        "report_date": safe_text(report.get("date") or report.get("report_date")).strip(),
        "report_conformance_status": conformance_status,
        "content_credibility_status": content_status,
        "evidence_exit_gate_verdict": evidence_verdict,
        "evidence_failed_count": evidence_failed_count,
        "evidence_unverifiable_reason_counts": evidence_reason_counts,
        "reason": reason,
    }
    if evidence_failed_count:
        payload["evidence_mismatch_freshness_status"] = report_freshness_bucket(report)
    return payload


def _status_rank(status: str) -> int:
    return {"blocked": 0, "warning": 1, "unknown": 2, "passed": 3}.get(status, 2)


__all__ = [
    "CONFORMANCE_STATUSES",
    "CONTENT_STATUSES",
    "CURRENT_QUALITY_ITEM_LIMIT",
    "CURRENT_QUALITY_CACHE_TTL_SECONDS",
    "EVIDENCE_VERDICTS",
    "EVIDENCE_MISMATCH_FRESHNESS_BUCKETS",
    "SCHEMA_VERSION",
    "build_current_quality_summary",
    "build_filtered_indexed_current_quality_summary",
    "build_indexed_current_quality_summary",
    "build_unavailable_current_quality_summary",
]
