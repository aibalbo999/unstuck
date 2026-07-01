"""Provider SLA policy integration for data trust scoring."""

from __future__ import annotations

from contextlib import suppress

from config import (
    PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS,
    PROVIDER_SLA_DEGRADE_LEVELS,
    PROVIDER_SLA_WARNING_MIN_ATTEMPTS,
)
from data_trust_constants import (
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    CORE_DATA_SOURCES,
    TRUST_STATUS_ERROR,
    TRUST_STATUS_PARTIAL,
    TRUST_STATUS_UNKNOWN,
)


SLA_WARNING_MIN_ATTEMPTS = PROVIDER_SLA_WARNING_MIN_ATTEMPTS
SLA_CRITICAL_MIN_ATTEMPTS = PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS
SLA_DEGRADE_LEVELS = {str(item).strip().lower() for item in PROVIDER_SLA_DEGRADE_LEVELS}
CORE_PROVIDER_SLA_SOURCES = set(CORE_DATA_SOURCES)
CURRENT_FETCH_OK_STATUSES = {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}


def current_provider_pairs(data: dict) -> set[tuple[str, str]]:
    return set(current_provider_entries(data).keys())


def current_provider_entries(data: dict) -> dict[tuple[str, str], dict]:
    entries = data.get("source_audit") if isinstance(data.get("source_audit"), list) else []
    pairs = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "").strip()
        provider = str(entry.get("provider") or "").strip().lower()
        if source and provider:
            pairs[(source, provider)] = entry
    return pairs


def current_source_health(data: dict) -> dict[str, bool]:
    health: dict[str, bool] = {}
    for entry in current_provider_entries(data).values():
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "").strip()
        if source:
            health[source] = health.get(source, False) or _audit_entry_is_healthy(entry)
    return health


def matched_provider_sla_alerts(data: dict, alerts: list[dict] | None = None) -> list[dict]:
    provider_entries = current_provider_entries(data)
    if not provider_entries:
        return []
    source_health = current_source_health(data)
    if alerts is None:
        import sqlite3
        with suppress(ImportError, sqlite3.Error):
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
        current_entry = provider_entries.get((source, provider))
        if current_entry is not None:
            matched.append(
                _compact_alert(
                    alert,
                    current_entry=current_entry,
                    source_has_healthy_entry=source_health.get(source, False),
                )
            )
    return matched


def apply_provider_sla_to_trust(data: dict, trust: dict, alerts: list[dict] | None = None) -> dict:
    matched = matched_provider_sla_alerts(data, alerts=alerts)
    if not matched:
        return trust

    trust = dict(trust)
    trust["provider_sla_alerts"] = matched
    reason_codes = list(trust.get("reason_codes") or [])
    notes = list(trust.get("notes") or [])
    degrading_alerts = [
        item for item in matched
        if item.get("alert_level") in SLA_DEGRADE_LEVELS and _is_core_sla_source(item.get("source"))
    ]
    optional_degrading_alerts = [
        item for item in matched
        if item.get("alert_level") in SLA_DEGRADE_LEVELS and not _is_core_sla_source(item.get("source"))
    ]
    core_health_notice_alerts = [
        item for item in matched
        if item.get("alert_level") in SLA_DEGRADE_LEVELS
        and _is_core_sla_source(item.get("source"))
        and _current_fetch_is_healthy(item)
    ]
    degrading_alerts = [item for item in degrading_alerts if not _current_fetch_is_healthy(item)]
    warning_alerts = [item for item in matched if item.get("alert_level") not in SLA_DEGRADE_LEVELS]
    if degrading_alerts:
        notes.append(f"來源健康度警示：{_alert_summary(degrading_alerts)}；critical provider SLA 已調降資料可信度。")
        reason_codes.append("provider_sla_critical")
    if core_health_notice_alerts:
        notes.append(f"核心來源健康度警示：{_alert_summary(core_health_notice_alerts)}；本次資料抓取成功，未調降本報告核心資料可信度。")
        reason_codes.append("provider_sla_core_health_notice")
    if optional_degrading_alerts:
        notes.append(f"補充來源健康度警示：{_alert_summary(optional_degrading_alerts)}；未調降核心資料可信度。")
        reason_codes.append("provider_sla_optional_critical")
    if warning_alerts and not degrading_alerts and not optional_degrading_alerts:
        notes.append(f"來源健康度觀察：{_alert_summary(warning_alerts)}；warning 僅列入提醒，未單獨調降可信度。")
        reason_codes.append("provider_sla_warning_note")
    trust["notes"] = notes
    trust["reason_codes"] = sorted(set(str(code) for code in reason_codes if str(code).strip()))
    trust["status"] = _downgraded_status(str(trust.get("status") or TRUST_STATUS_UNKNOWN), degrading_alerts)
    return trust


def _alert_summary(alerts: list[dict]) -> str:
    return "；".join(
        f"{item['source']}/{item['provider']}={item['alert_level']}({item.get('evidence_attempts', 0)}次)"
        for item in alerts[:3]
    )


def _downgraded_status(status: str, degrading_alerts: list[dict]) -> str:
    if status in {TRUST_STATUS_ERROR, TRUST_STATUS_UNKNOWN}:
        return status
    if degrading_alerts:
        return TRUST_STATUS_PARTIAL
    return status


def _is_core_sla_source(source: object) -> bool:
    return str(source or "") in CORE_PROVIDER_SLA_SOURCES


def _current_fetch_is_healthy(alert: dict) -> bool:
    if bool(alert.get("current_source_has_healthy_entry")):
        return True
    status = str(alert.get("current_status") or "").strip()
    record_count = _safe_int(alert.get("current_record_count"))
    return status in CURRENT_FETCH_OK_STATUSES and record_count > 0 and not bool(alert.get("current_stale"))


def _audit_entry_is_healthy(entry: dict) -> bool:
    status = str(entry.get("status") or "").strip()
    record_count = _safe_int(entry.get("record_count"))
    return status in CURRENT_FETCH_OK_STATUSES and record_count > 0 and not bool(entry.get("stale"))


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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


def _compact_alert(
    alert: dict,
    *,
    current_entry: dict | None = None,
    source_has_healthy_entry: bool = False,
) -> dict:
    evidence_attempts = _evidence_attempts(alert)
    compact = {
        "source": str(alert.get("source") or "unknown"),
        "provider": str(alert.get("provider") or "unknown"),
        "alert_level": str(alert.get("alert_level") or "warning"),
        "alert_message": str(alert.get("alert_message") or "")[:180],
        "success_rate": alert.get("success_rate"),
        "last_status": alert.get("last_status"),
        "alert_basis": alert.get("alert_basis"),
        "evidence_attempts": evidence_attempts,
    }
    if isinstance(current_entry, dict):
        compact["current_status"] = str(current_entry.get("status") or "unknown")
        compact["current_record_count"] = _safe_int(current_entry.get("record_count"))
        compact["current_stale"] = bool(current_entry.get("stale"))
        compact["current_source_has_healthy_entry"] = bool(source_has_healthy_entry)
    return compact
