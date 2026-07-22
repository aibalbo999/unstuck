"""Data-confidence target-price guardrails for content credibility."""

from __future__ import annotations

from data_trust_scoring import trust_status_label
from mapping_fields import safe_text
from report_reproducibility import (
    EXPLICIT_TARGET_PRICE_MIN_SCORE,
    data_confidence_score,
    detect_explicit_target_price_fields,
)

from .text_tokens import is_missing_text_token


def _data_trust_status(value: object) -> str:
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return "unknown"
    return text or "unknown"


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


def evaluate_data_confidence_target_guardrail(context: dict, data_trust: dict) -> dict:
    """Evaluate whether target-price claims are allowed by data confidence."""
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []
    explicit_target_fields = detect_explicit_target_price_fields(context)
    score = data_confidence_score(data_trust)
    trust_status = _data_trust_status(data_trust.get("status"))

    if explicit_target_fields and score < EXPLICIT_TARGET_PRICE_MIN_SCORE:
        details = {
            "data_confidence_score": score,
            "min_data_confidence_score": EXPLICIT_TARGET_PRICE_MIN_SCORE,
            "detected_fields": explicit_target_fields,
            "data_trust_status": trust_status,
        }
        issue = _issue(
            "explicit_target_price_low_data_confidence",
            "資料信心低於明確目標價門檻，但報告仍含明確目標價欄位。",
            details,
        )
        blocking.append(issue)
        checks.append(_check("data_confidence_target_guardrail", "blocked", issue["message"], details))
    elif trust_status != "fresh":
        details = {
            "data_trust_status": trust_status,
            "data_trust_label": trust_status_label(trust_status),
        }
        warnings.append(_issue("non_fresh_data_trust", "資料可信度不是 fresh，內容可信度需保留限制。", details))
        checks.append(_check("data_confidence_target_guardrail", "warning", "資料可信度不是 fresh。", details))
    else:
        checks.append(_check(
            "data_confidence_target_guardrail",
            "passed",
            "資料信心達到明確目標價門檻。",
            {"data_confidence_score": score},
        ))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}
