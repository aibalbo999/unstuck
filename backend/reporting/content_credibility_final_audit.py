"""Align content credibility with unresolved final-audit findings."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text, safe_text_list
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


def final_audit_from_conformance(report_conformance: Any) -> dict:
    """Recover the final-audit status already recorded in conformance output."""
    conformance = _as_dict(report_conformance)
    for step in safe_dict_list(conformance.get("decision_tree")):
        if safe_text(step.get("id")).strip().lower() != "final_audit":
            continue
        status = _status(step.get("status"))
        details = safe_text_list(step.get("details"))
        if not details:
            message = safe_text(step.get("message")).strip()
            if message:
                details = [message]
        if status in BLOCKING_FINAL_AUDIT_STATUSES:
            return {"status": status, "critical": details, "warnings": [], "corrections": []}
        if status != "passed":
            return {"status": status, "critical": [], "warnings": details, "corrections": []}
        return {"status": "passed", "critical": [], "warnings": [], "corrections": []}
    return {}


def align_content_credibility_with_final_audit(content_credibility: Any, final_audit: Any) -> dict:
    """Prevent a recorded passed gate from hiding a later final-audit failure."""
    content = _as_dict(content_credibility)
    content_status = _status(content.get("status"))
    if content_status not in {"passed", "warning", "blocked", "failed", "rejected"}:
        return content

    audit = _as_dict(final_audit)
    if "decision_tree" in audit:
        audit = final_audit_from_conformance(audit)
    aligned = evaluate_final_audit_alignment(audit)
    blocking = aligned["blocking_issues"]
    warnings = aligned["warnings"]
    if not blocking and not warnings:
        return content

    result = dict(content)
    result["blocking_issues"] = _merge_issues(content.get("blocking_issues"), blocking)
    result["warnings"] = _merge_issues(content.get("warnings"), warnings)
    result["checks"] = _merge_issues(content.get("checks"), aligned["checks"])
    if blocking and content_status not in {"blocked", "failed", "rejected"}:
        result["status"] = "blocked"
    elif warnings and content_status == "passed":
        result["status"] = "warning"
    if result.get("status") == "blocked":
        result["summary"] = "報告關鍵結論與資料或證據存在阻斷矛盾。"
    elif result.get("status") == "warning":
        result["summary"] = "報告關鍵結論未見阻斷矛盾，但仍有可信度警示。"
    return result


def _merge_issues(existing: Any, additions: list[dict]) -> list[dict]:
    merged = safe_dict_list(existing)
    known = {
        (safe_text(issue.get("id")), safe_text(issue.get("message")))
        for issue in merged
    }
    for issue in additions:
        key = (safe_text(issue.get("id")), safe_text(issue.get("message")))
        if key not in known:
            merged.append(issue)
            known.add(key)
    return merged


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


__all__ = [
    "align_content_credibility_with_final_audit",
    "evaluate_final_audit_alignment",
    "final_audit_from_conformance",
]
