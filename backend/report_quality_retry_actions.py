"""Recognize report-quality findings that are safe to retry."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text, safe_text_list


FINAL_AUDIT_RETRY_MARKERS = ("輸出為失敗訊息", "缺少 Agent 輸出", "仍含佔位文字")


def final_audit_retry_detail(gate: Any) -> str | None:
    issues = safe_dict_list(_field(gate, "blocking_issues"))
    return next((detail for issue in issues if _status(_field(issue, "id")) == "final_audit" for detail in _issue_details(issue) if _is_retry_detail(detail)), None)


def content_final_audit_retry_detail(gate: Any) -> str | None:
    issues = safe_dict_list(_field(gate, "blocking_issues"))
    if not issues or any(_status(_field(issue, "id")) != "final_audit_critical" for issue in issues):
        return None
    details = [detail for issue in issues for detail in _issue_details(issue)]
    return details[0] if details and all(_is_retry_detail(detail) for detail in details) else None


def _field(mapping: Any, key: str, default: Any = None) -> Any:
    return dict.get(mapping, key, default) if isinstance(mapping, dict) else default


def _status(value: Any) -> str:
    return safe_text(value).strip().lower()


def _issue_details(issue: dict[str, Any]) -> list[str]:
    raw_details = _field(issue, "details")
    details = safe_mapping_dict(raw_details)
    return safe_text_list(_field(details, "critical")) if details else safe_text_list(raw_details) or [safe_text(raw_details).strip()]


def _is_retry_detail(detail: str) -> bool:
    return any(marker in detail for marker in FINAL_AUDIT_RETRY_MARKERS)
