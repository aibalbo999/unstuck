"""Small pure helpers for analysis job orchestration."""

from __future__ import annotations

import hashlib


def stable_report_filename(job_id: str, ticker_upper: str, pipeline_id: str) -> str:
    safe_ticker = str(ticker_upper or "").strip().upper().replace(".", "_") or "UNKNOWN"
    digest = hashlib.sha1(f"{job_id}:{pipeline_id}".encode("utf-8")).hexdigest()[:12]
    return f"{safe_ticker}_{pipeline_id}_report_job_{digest}.html"


def build_data_fetch_blocking_notice(data_result) -> dict | None:
    data = data_result.data if isinstance(getattr(data_result, "data", None), dict) else {}
    trust = (
        data_result.data_trust
        if isinstance(getattr(data_result, "data_trust", None), dict)
        else data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
    )
    trust_status = str(trust.get("status") or "unknown")
    has_market_or_financials = bool(
        data.get("current_price")
        or data.get("market_cap_raw")
        or data.get("years")
        or data.get("revenue_history")
    )
    if trust_status == "error":
        return {
            "message": "核心市場或財報來源異常，且沒有足夠可用資料；已停止本次分析，請稍後重試或檢查資料來源設定。",
            "data_trust": trust,
        }
    if data.get("error") and not has_market_or_financials:
        return {
            "message": f"財務資料獲取失敗且沒有可用核心資料：{data.get('error')}",
            "data_trust": trust,
        }
    return None


def build_operator_audit_notice(context: dict) -> dict:
    audit = context.get("final_audit", {}) or {}
    critical = list(audit.get("critical", []) or [])
    blocking = [issue for issue in (context.get("blocking_issues", []) or []) if issue not in critical]
    warnings = list(audit.get("warnings", []) or [])
    corrections = list(audit.get("corrections", []) or [])
    repair_log = list(context.get("audit_repair_log", []) or [])

    if critical or blocking:
        issues = [*critical[:5], *blocking[:3]]
        first_issue = issues[0] if issues else "最終稽核仍有異常"
        return {
            "status": "needs_attention",
            "message": f"最終稽核仍有異常，報告已保留並標示提醒：{first_issue}",
            "issues": issues,
            "repair_log": repair_log[:5],
        }

    if warnings or corrections or repair_log:
        details = [*warnings[:3], *corrections[:3], *repair_log[:3]]
        return {
            "status": "passed_with_notes",
            "message": "最終稽核已通過；系統曾自動修復或套用非阻斷校正。",
            "issues": details,
            "repair_log": repair_log[:5],
        }

    return {"status": "passed", "message": "最終稽核已通過。", "issues": [], "repair_log": []}


__all__ = [
    "build_data_fetch_blocking_notice",
    "build_operator_audit_notice",
    "stable_report_filename",
]
