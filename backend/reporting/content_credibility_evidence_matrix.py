"""Evidence-matrix coverage checks for content credibility."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text
from .text_tokens import is_missing_text_token


_USABLE_EVIDENCE_STATUSES = frozenset({"success", "skipped_fresh_cache", "degraded_enrichment"})


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


def _evidence_claim_row(rows: list, claim: str) -> dict | None:
    for row in rows:
        row_map = _as_dict(row)
        if safe_text(row_map.get("claim")).strip() == claim:
            return row_map
    return None


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

    parsed = _as_dict(context.get("parsed"))
    requirements: list[tuple[str, str, str, str, str]] = []
    if recommendation_present:
        requirements.append((
            "最終投資建議",
            "missing_final_recommendation_evidence",
            "unusable_final_recommendation_evidence",
            "最終投資建議缺少 evidence matrix 覆蓋。",
            "最終投資建議的 evidence matrix 列沒有可用證據狀態或依據，需要人工確認。",
        ))
    if _as_dict(parsed.get("price_targets")):
        requirements.append((
            "估值結論",
            "missing_valuation_evidence",
            "unusable_valuation_evidence",
            "估值結論缺少 evidence matrix 覆蓋。",
            "估值結論的 evidence matrix 列沒有可用證據狀態或依據，需要人工確認。",
        ))
    if _as_dict(parsed.get("moat_scores")):
        requirements.append((
            "護城河評分",
            "missing_moat_evidence",
            "unusable_moat_evidence",
            "護城河評分缺少 evidence matrix 覆蓋。",
            "護城河評分的 evidence matrix 列沒有可用證據狀態或依據，需要人工確認。",
        ))

    for claim, missing_id, unusable_id, missing_message, unusable_message in requirements:
        row = _evidence_claim_row(rows, claim)
        if row is None:
            issue = _issue(missing_id, missing_message, {"required_claim": claim})
        else:
            status = safe_text(row.get("status")).strip().lower() or "unknown"
            basis = safe_text(row.get("basis")).strip()
            basis_present = bool(basis) and not is_missing_text_token(basis)
            if status in _USABLE_EVIDENCE_STATUSES and basis_present:
                checks.append(_check(
                    "evidence_matrix_coverage",
                    "passed",
                    f"{claim}已有可用 evidence matrix 覆蓋。",
                ))
                continue
            issue = _issue(
                unusable_id,
                unusable_message,
                {"required_claim": claim, "status": status, "basis_present": basis_present},
            )
        warnings.append(issue)
        checks.append(_check("evidence_matrix_coverage", "warning", issue["message"], issue["details"]))

    if not requirements:
        checks.append(_check("evidence_matrix_coverage", "passed", "沒有需要檢查的結論 evidence matrix 覆蓋。"))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}
