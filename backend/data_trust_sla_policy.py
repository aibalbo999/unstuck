"""Provider SLA policy integration for data trust scoring."""

from __future__ import annotations

from contextlib import suppress

from config import (
    PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS,
    PROVIDER_SLA_DEGRADE_LEVELS,
    PROVIDER_SLA_WARNING_MIN_ATTEMPTS,
)
from data_trust_constants import TRUST_STATUS_ERROR, TRUST_STATUS_PARTIAL, TRUST_STATUS_UNKNOWN


SLA_WARNING_MIN_ATTEMPTS = PROVIDER_SLA_WARNING_MIN_ATTEMPTS
SLA_CRITICAL_MIN_ATTEMPTS = PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS
SLA_DEGRADE_LEVELS = {str(item).strip().lower() for item in PROVIDER_SLA_DEGRADE_LEVELS}


def current_provider_pairs(data: dict) -> set[tuple[str, str]]:
    entries = data.get("source_audit") if isinstance(data.get("source_audit"), list) else []
    pairs = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "").strip()
        provider = str(entry.get("provider") or "").strip().lower()
        if source and provider:
            pairs.add((source, provider))
    return pairs


def matched_provider_sla_alerts(data: dict, alerts: list[dict] | None = None) -> list[dict]:
    pairs = current_provider_pairs(data)
    if not pairs:
        return []
    if alerts is None:
        with suppress(Exception):
            from provider_sla import get_provider_sla_alerts

            alerts = get_provider_sla_alerts(limit=100)
    matched = []
    for alert in alerts or []:
        if not isinstance(alert, dict):
            continue
        source = str(alert.get("source") or "").strip()
        provider = str(alert.get("provider") or "").strip().lower()
        level = str(alert.get("alert_level") or "").strip().lower()
        if level not in {"warning", "critical"}:
            continue
        if not _has_enough_sla_evidence(alert, level):
            continue
        if (source, provider) in pairs:
            matched.append(_compact_alert(alert))
    return matched


def apply_provider_sla_to_trust(data: dict, trust: dict, alerts: list[dict] | None = None) -> dict:
    matched = matched_provider_sla_alerts(data, alerts=alerts)
    if not matched:
        return trust

    trust = dict(trust)
    trust["provider_sla_alerts"] = matched
    reason_codes = list(trust.get("reason_codes") or [])
    notes = list(trust.get("notes") or [])
    alert_summary = "；".join(
        f"{item['source']}/{item['provider']}={item['alert_level']}({item.get('evidence_attempts', 0)}次)"
        for item in matched[:3]
    )
    if any(item.get("alert_level") in SLA_DEGRADE_LEVELS for item in matched):
        notes.append(f"來源健康度警示：{alert_summary}；critical provider SLA 已調降資料可信度。")
        reason_codes.append("provider_sla_critical")
    else:
        notes.append(f"來源健康度觀察：{alert_summary}；warning 僅列入提醒，未單獨調降可信度。")
        reason_codes.append("provider_sla_warning_note")
    trust["notes"] = notes
    trust["reason_codes"] = sorted(set(str(code) for code in reason_codes if str(code).strip()))
    trust["status"] = _downgraded_status(str(trust.get("status") or TRUST_STATUS_UNKNOWN), matched)
    return trust


def _downgraded_status(status: str, alerts: list[dict]) -> str:
    if status in {TRUST_STATUS_ERROR, TRUST_STATUS_UNKNOWN}:
        return status
    if any(item.get("alert_level") in SLA_DEGRADE_LEVELS for item in alerts):
        return TRUST_STATUS_PARTIAL
    return status


def _has_enough_sla_evidence(alert: dict, level: str) -> bool:
    attempts = _evidence_attempts(alert)
    if level == "critical":
        return attempts >= SLA_CRITICAL_MIN_ATTEMPTS
    return attempts >= SLA_WARNING_MIN_ATTEMPTS


def _evidence_attempts(alert: dict) -> int:
    basis = str(alert.get("alert_basis") or "").strip()
    windows = alert.get("windows") if isinstance(alert.get("windows"), dict) else {}
    window = windows.get(basis) if basis else None
    if isinstance(window, dict):
        return int(window.get("attempts") or 0)
    return int(alert.get("attempts") or 0)


def _compact_alert(alert: dict) -> dict:
    evidence_attempts = _evidence_attempts(alert)
    return {
        "source": str(alert.get("source") or "unknown"),
        "provider": str(alert.get("provider") or "unknown"),
        "alert_level": str(alert.get("alert_level") or "warning"),
        "alert_message": str(alert.get("alert_message") or "")[:180],
        "success_rate": alert.get("success_rate"),
        "last_status": alert.get("last_status"),
        "alert_basis": alert.get("alert_basis"),
        "evidence_attempts": evidence_attempts,
    }
