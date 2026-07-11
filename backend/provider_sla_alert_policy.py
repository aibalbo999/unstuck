"""Provider SLA alert policy helpers."""

from __future__ import annotations

from notification_delivery_audit_context import safe_dict, safe_float, safe_int, safe_text


SLA_WARNING_SUCCESS_RATE = 0.8
SLA_CRITICAL_SUCCESS_RATE = 0.5


def provider_alert_fields(item: dict) -> dict:
    item = safe_dict(item)
    basis = alert_basis(item)
    attempts = safe_int(basis.get("availability_attempts", basis.get("attempts")))
    success_rate = safe_float(basis.get("success_rate"))
    error_count = safe_int(basis.get("error_count"))
    last_status = safe_text(item.get("last_status")).strip()
    basis_label = safe_text(basis.get("label")).strip() or "累積"
    provider = safe_text(item.get("provider")).strip() or "unknown"
    if attempts >= 3 and (success_rate < SLA_CRITICAL_SUCCESS_RATE or error_count >= 3):
        return {
            "alert_level": "critical",
            "alert_message": f"{provider} {basis_label}資料取得率偏低（{success_rate:.0%}），最近狀態：{last_status or 'unknown'}",
            "alert_basis": basis_label,
        }
    if last_status in {"error", "unavailable"} or (attempts >= 3 and success_rate < SLA_WARNING_SUCCESS_RATE):
        return {
            "alert_level": "warning",
            "alert_message": f"{provider} 最近有來源異常或 {basis_label}資料取得率低於 {SLA_WARNING_SUCCESS_RATE:.0%}",
            "alert_basis": basis_label,
        }
    return {"alert_level": "ok", "alert_message": "", "alert_basis": basis_label}


def alert_basis(item: dict) -> dict:
    item = safe_dict(item)
    windows = safe_dict(item.get("windows"))
    for label in ("last_1h", "last_24h", "last_7d"):
        stats = safe_dict(windows.get(label))
        if safe_int(stats.get("availability_attempts", stats.get("attempts"))) >= 3:
            stats["label"] = label
            return stats
    return {
        "label": "累積",
        "attempts": safe_int(item.get("attempts")),
        "availability_attempts": safe_int(item.get("availability_attempts", item.get("attempts"))),
        "success_rate": safe_float(item.get("success_rate")),
        "error_count": safe_int(item.get("error_count")),
    }
