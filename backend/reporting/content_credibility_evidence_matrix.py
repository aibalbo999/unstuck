"""Evidence-matrix coverage checks for content credibility."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _issue(issue_id: str, message: str, details: dict | None = None) -> dict:
    issue = {"id": issue_id, "message": message}
    if details:
        issue["details"] = details
    return issue


def _check(check_id: str, status: str, message: str, details: dict | None = None) -> dict:
    result = {"id": check_id, "status": status, "message": message}
    if details:
        result["details"] = details
    return result


def _evidence_matrix_rows(context: dict, snapshot: dict) -> list:
    if "evidence_matrix" in snapshot:
        return safe_sequence_items(snapshot.get("evidence_matrix"))
    try:
        from .evidence_matrix import build_evidence_matrix_rows

        return build_evidence_matrix_rows(context)
    except Exception:
        return []


def _has_evidence_claim(rows: list, claim: str) -> bool:
    for row in rows:
        row_map = _as_dict(row)
        if safe_text(row_map.get("claim")).strip() == claim:
            return True
    return False


def evaluate_evidence_matrix_coverage(
    *,
    context: dict,
    snapshot: dict,
    recommendation_present: bool,
) -> dict:
    """Evaluate whether the final recommendation has evidence-matrix coverage."""
    context = _as_dict(context)
    snapshot = _as_dict(snapshot)
    rows = _evidence_matrix_rows(context, snapshot)
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if recommendation_present and not _has_evidence_claim(rows, "最終投資建議"):
        issue = _issue(
            "missing_final_recommendation_evidence",
            "最終投資建議缺少 evidence matrix 覆蓋。",
            {"required_claim": "最終投資建議"},
        )
        warnings.append(issue)
        checks.append(_check("evidence_matrix_coverage", "warning", issue["message"], issue["details"]))
    else:
        checks.append(_check("evidence_matrix_coverage", "passed", "最終投資建議已有 evidence matrix 覆蓋。"))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}
