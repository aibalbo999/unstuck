"""Evidence-gate and confidence alignment checks for content credibility."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text
from .text_tokens import is_missing_text_token


HIGH_CONFIDENCE_MIN_SCORE = 8.0


def _normalized_evidence_verdict(value: Any) -> str:
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return "not_recorded"
    return text or "not_recorded"


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


def evaluate_confidence_evidence_alignment(evidence_verdict: Any, confidence_score: float | None) -> dict:
    """Evaluate whether stated confidence is compatible with evidence-gate status."""
    evidence_verdict = _normalized_evidence_verdict(evidence_verdict)
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if evidence_verdict == "rejected" and confidence_score is not None and confidence_score >= HIGH_CONFIDENCE_MIN_SCORE:
        details = {"evidence_verdict": evidence_verdict, "confidence_score": confidence_score}
        issue = _issue(
            "high_confidence_rejected_evidence",
            "證據抽查 rejected，但最終結論仍給出高信心。",
            details,
        )
        blocking.append(issue)
        checks.append(_check("confidence_evidence_alignment", "blocked", issue["message"], details))
    elif evidence_verdict not in {"approved", "not_recorded"}:
        details = {"evidence_verdict": evidence_verdict, "confidence_score": confidence_score}
        warnings.append(_issue("non_approved_evidence_gate", "證據抽查未完全通過，內容可信度需人工確認。", details))
        checks.append(_check("confidence_evidence_alignment", "warning", "證據抽查未完全通過。", details))
    else:
        checks.append(_check(
            "confidence_evidence_alignment",
            "passed",
            "信心與證據抽查狀態未見明顯矛盾。",
            {"evidence_verdict": evidence_verdict},
        ))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}
