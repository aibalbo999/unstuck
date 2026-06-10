"""Provider SLA alert policy helpers."""

from __future__ import annotations


SLA_WARNING_SUCCESS_RATE = 0.8
SLA_CRITICAL_SUCCESS_RATE = 0.5


def provider_alert_fields(item: dict) -> dict:
    basis = alert_basis(item)
    attempts = int(basis.get("availability_attempts", basis.get("attempts")) or 0)
    success_rate = float(basis.get("success_rate") or 0.0)
    error_count = int(basis.get("error_count") or 0)
    last_status = str(item.get("last_status") or "")
    basis_label = basis.get("label") or "累積"
    if attempts >= 3 and (success_rate < SLA_CRITICAL_SUCCESS_RATE or error_count >= 3):
        return {
            "alert_level": "critical",
            "alert_message": f"{item.get('provider')} {basis_label}資料取得率偏低（{success_rate:.0%}），最近狀態：{last_status or 'unknown'}",
            "alert_basis": basis_label,
        }
    if last_status in {"error", "unavailable"} or (attempts >= 3 and success_rate < SLA_WARNING_SUCCESS_RATE):
        return {
            "alert_level": "warning",
            "alert_message": f"{item.get('provider')} 最近有來源異常或 {basis_label}資料取得率低於 {SLA_WARNING_SUCCESS_RATE:.0%}",
            "alert_basis": basis_label,
        }
    return {"alert_level": "ok", "alert_message": "", "alert_basis": basis_label}


def alert_basis(item: dict) -> dict:
    windows = item.get("windows") if isinstance(item.get("windows"), dict) else {}
    for label in ("last_1h", "last_24h", "last_7d"):
        stats = dict(windows.get(label) or {})
        if int(stats.get("availability_attempts", stats.get("attempts")) or 0) >= 3:
            stats["label"] = label
            return stats
    return {
        "label": "累積",
        "attempts": int(item.get("attempts") or 0),
        "availability_attempts": int(item.get("availability_attempts", item.get("attempts")) or 0),
        "success_rate": float(item.get("success_rate") or 0.0),
        "error_count": int(item.get("error_count") or 0),
    }
