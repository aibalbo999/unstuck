"""Evidence-matrix coverage checks for content credibility."""

from __future__ import annotations

from typing import Any
from mapping_fields import safe_text

from .content_credibility_evidence_matrix_support import (
    USABLE_EVIDENCE_STATUSES,
    as_dict,
    check,
    evidence_claim_row,
    evidence_matrix_rows,
    issue,
    usable_basis,
)


def evaluate_evidence_matrix_coverage(
    *,
    context: dict,
    snapshot: dict,
    recommendation_present: bool,
) -> dict:
    """Evaluate whether the final recommendation has evidence-matrix coverage."""
    context = as_dict(context)
    snapshot = as_dict(snapshot)
    rows = evidence_matrix_rows(context, snapshot)
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    parsed = as_dict(context.get("parsed"))
    requirements: list[tuple[str, str, str, str, str]] = []
    if recommendation_present:
        requirements.append((
            "最終投資建議",
            "missing_final_recommendation_evidence",
            "unusable_final_recommendation_evidence",
            "最終投資建議缺少 evidence matrix 覆蓋。",
            "最終投資建議的 evidence matrix 列沒有可用證據狀態或依據，需要人工確認。",
        ))
    if as_dict(parsed.get("price_targets")):
        requirements.append((
            "估值結論",
            "missing_valuation_evidence",
            "unusable_valuation_evidence",
            "估值結論缺少 evidence matrix 覆蓋。",
            "估值結論的 evidence matrix 列沒有可用證據狀態或依據，需要人工確認。",
        ))
    if as_dict(parsed.get("moat_scores")):
        requirements.append((
            "護城河評分",
            "missing_moat_evidence",
            "unusable_moat_evidence",
            "護城河評分缺少 evidence matrix 覆蓋。",
            "護城河評分的 evidence matrix 列沒有可用證據狀態或依據，需要人工確認。",
        ))

    for claim, missing_id, unusable_id, missing_message, unusable_message in requirements:
        row = evidence_claim_row(rows, claim)
        if row is None:
            current_issue = issue(missing_id, missing_message, {"required_claim": claim})
        else:
            status, basis_present = usable_basis(row)
            if status in USABLE_EVIDENCE_STATUSES and basis_present:
                checks.append(check(
                    "evidence_matrix_coverage",
                    "passed",
                    f"{claim}已有可用 evidence matrix 覆蓋。",
                ))
                continue
            current_issue = issue(
                unusable_id,
                unusable_message,
                {"required_claim": claim, "status": status, "basis_present": basis_present},
            )
        warnings.append(current_issue)
        checks.append(check("evidence_matrix_coverage", "warning", current_issue["message"], current_issue["details"]))

    if not requirements:
        checks.append(check("evidence_matrix_coverage", "passed", "沒有需要檢查的結論 evidence matrix 覆蓋。"))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}
