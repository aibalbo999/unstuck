"""Align content credibility with unresolved final-audit findings."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_text, safe_text_list
from .text_tokens import is_missing_text_token


BLOCKING_FINAL_AUDIT_STATUSES = {"blocked", "failed", "rejected"}


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _status(value: Any) -> str:
    text = safe_text(value).strip().lower()
    return "not_recorded" if is_missing_text_token(text) else text or "not_recorded"


def _issue(issue_id: str, message: str, details: dict) -> dict:
    return {"id": issue_id, "message": message, "details": details}


def _check(check_id: str, status: str, message: str, details: dict) -> dict:
    return {"id": check_id, "status": status, "message": message, "details": details}


def evaluate_final_audit_alignment(final_audit: Any) -> dict:
    """Project unresolved final-audit findings into content-credibility evidence."""
    audit = _as_dict(final_audit)
    if not audit:
        return {
            "blocking_issues": [],
            "warnings": [],
            "checks": [{
                "id": "final_audit_alignment",
                "status": "passed",
                "message": "未提供 final_audit，略過稽核對齊檢查。",
            }],
        }

    status = _status(audit.get("status"))
    critical = safe_text_list(audit.get("critical"))
    warnings = safe_text_list(audit.get("warnings"))
    details = {"status": status, "critical": critical, "warnings": warnings}

    if critical or status in BLOCKING_FINAL_AUDIT_STATUSES:
        issue = _issue(
            "final_audit_critical",
            "最終稽核仍有重大問題，內容可信度不可視為通過。",
            details,
        )
        return {
            "blocking_issues": [issue],
            "warnings": [],
            "checks": [_check("final_audit_alignment", "blocked", issue["message"], details)],
        }

    if warnings or status not in {"passed"}:
        issue = _issue(
            "final_audit_warning",
            "最終稽核仍有警示，內容可信度需人工確認。",
            details,
        )
        return {
            "blocking_issues": [],
            "warnings": [issue],
            "checks": [_check("final_audit_alignment", "warning", issue["message"], details)],
        }

    return {
        "blocking_issues": [],
        "warnings": [],
        "checks": [_check("final_audit_alignment", "passed", "最終稽核未留下未解決問題。", details)],
    }


__all__ = ["evaluate_final_audit_alignment"]
