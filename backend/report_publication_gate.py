"""Reject explicitly blocked analysis output before canonical publication."""
from mapping_fields import safe_mapping_dict, safe_text, safe_text_list
from reporting.content_credibility_final_audit import evaluate_final_audit_alignment


BLOCKING_STATUSES = {"blocked", "failed", "rejected"}


class ReportPublicationBlockedError(Exception):
    def __init__(self, issues):
        self.issues = list(dict.fromkeys(issues))
        super().__init__("報告品質檢查未通過，本次報告未發布：" + "；".join(self.issues[:5]))


def assert_report_publishable(payload):
    """Share the existing audit semantics; warnings/caution remain publishable."""
    value = safe_mapping_dict(payload) or {}
    issues = safe_text_list(value.get("blocking_issues"))
    if safe_text(value.get("status")).strip().lower() in BLOCKING_STATUSES:
        issues.append("分析工作流仍有阻斷問題")
    audit = safe_mapping_dict(value.get("final_audit")) or {}
    alignment = evaluate_final_audit_alignment(audit)
    if alignment["blocking_issues"]:
        issues.extend(safe_text_list(audit.get("critical")) or ["最終稽核未通過"])
    for key, label, field in (
        ("report_lint", "報告格式檢查", "status"),
        ("content_credibility", "內容可信度", "status"),
        ("report_conformance", "報告契約檢查", "status"),
        ("evidence_exit_gate", "證據檢查", "verdict"),
    ):
        section = safe_mapping_dict(value.get(key)) or {}
        if safe_text(section.get(field)).strip().lower() in BLOCKING_STATUSES:
            issues.append(f"{label}未通過")
    if issues:
        raise ReportPublicationBlockedError(issues)


def publication_blocked_event(exc, **context):
    issues = getattr(exc, "issues", None) or [str(exc)]
    message = str(exc) if isinstance(exc, ReportPublicationBlockedError) else str(ReportPublicationBlockedError(issues))
    return {"type": "error", "phase": "report_quality_blocked", "level": "error",
            "message": message, "issues": issues[:8], "retry_scheduled": False, **context}
