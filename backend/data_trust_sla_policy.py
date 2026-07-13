"""Provider SLA policy integration for data trust scoring."""

from __future__ import annotations

from contextlib import suppress
import sqlite3

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
from mapping_fields import safe_text


SLA_WARNING_MIN_ATTEMPTS = PROVIDER_SLA_WARNING_MIN_ATTEMPTS
SLA_CRITICAL_MIN_ATTEMPTS = PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS
SLA_DEGRADE_LEVELS = {str(item).strip().lower() for item in PROVIDER_SLA_DEGRADE_LEVELS}
CORE_PROVIDER_SLA_SOURCES = set(CORE_DATA_SOURCES)
CURRENT_FETCH_OK_STATUSES = {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}


def current_provider_pairs(data: dict) -> set[tuple[str, str]]:
    return set(current_provider_entries(data).keys())


def current_provider_entries(data: dict) -> dict[tuple[str, str], dict]:
    data = _safe_dict(data)
    pairs = {}
    for entry in _safe_dict_rows(data.get("source_audit")):
        source = _safe_text(entry.get("source")).strip()
        provider = _safe_text(entry.get("provider")).strip().lower()
        if source and provider:
            pairs[(source, provider)] = entry
    return pairs


def current_source_health(data: dict) -> dict[str, bool]:
    health: dict[str, bool] = {}
    for entry in current_provider_entries(data).values():
        if not isinstance(entry, dict):
            continue
        source = _safe_text(entry.get("source")).strip()
        if source:
            health[source] = health.get(source, False) or _audit_entry_is_healthy(entry)
    return health


def matched_provider_sla_alerts(data: dict, alerts: list[dict] | None = None) -> list[dict]:
    provider_entries = current_provider_entries(data)
    if not provider_entries:
        return []
    source_health = current_source_health(data)
    if alerts is None:
        alerts = _fetch_provider_sla_alerts()
    matched = []
    for alert in _safe_dict_rows(alerts):
        source = _safe_text(alert.get("source")).strip()
        provider = _safe_text(alert.get("provider")).strip().lower()
        level = _safe_text(alert.get("alert_level")).strip().lower()
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
    reason_codes = _safe_text_list(trust.get("reason_codes"))
    notes = _safe_text_list(trust.get("notes"))
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
    trust["reason_codes"] = sorted(set(code for code in reason_codes if code))
    trust["status"] = _downgraded_status(_safe_text(trust.get("status")).strip() or TRUST_STATUS_UNKNOWN, degrading_alerts)
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
    return _safe_text(source).strip() in CORE_PROVIDER_SLA_SOURCES


def _current_fetch_is_healthy(alert: dict) -> bool:
    if _safe_bool(alert.get("current_source_has_healthy_entry")):
        return True
    status = _safe_text(alert.get("current_status")).strip()
    record_count = _safe_int(alert.get("current_record_count"))
    return status in CURRENT_FETCH_OK_STATUSES and record_count > 0 and not _safe_bool(alert.get("current_stale"))


def _audit_entry_is_healthy(entry: dict) -> bool:
    status = _safe_text(entry.get("status")).strip()
    record_count = _safe_int(entry.get("record_count"))
    return status in CURRENT_FETCH_OK_STATUSES and record_count > 0 and not _safe_bool(entry.get("stale"))


def _safe_int(value: object) -> int:
    try:
        return int(0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return 0


def _safe_text(value: object) -> str:
    return safe_text(value)


def _safe_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        text = _safe_text(value).strip()
        return [text] if text else []
    iterator = _safe_iterator(value)
    if iterator is None:
        return []
    texts = []
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            return texts
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            if texts or used_native:
                return texts
            iterator = _native_sequence_iterator(value)
            if iterator is None:
                return texts
            used_native = True
            continue
        if text := _safe_text(item).strip():
            texts.append(text)


def _safe_dict(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    try:
        return dict(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        try:
            return {key: child for key, child in dict.items(value)}
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return {}


def _safe_dict_rows(value: object) -> list[dict]:
    if value is None or isinstance(value, (str, bytes, dict)):
        return []
    iterator = _safe_iterator(value)
    if iterator is None:
        return []
    rows = []
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            return rows
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            if rows or used_native:
                return rows
            iterator = _native_sequence_iterator(value)
            if iterator is None:
                return rows
            used_native = True
            continue
        if isinstance(item, dict):
            rows.append(_safe_dict(item))


def _safe_iterator(value: object):
    try:
        return iter(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return _native_sequence_iterator(value)
    return None


def _native_sequence_iterator(value: object):
    try:
        if isinstance(value, list):
            return list.__iter__(value)
        if isinstance(value, tuple):
            return tuple.__iter__(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    return None


def _fetch_provider_sla_alerts() -> object:
    with suppress(
        ImportError,
        sqlite3.Error,
        TypeError,
        ValueError,
        ArithmeticError,
        RuntimeError,
        AttributeError,
        OSError,
    ):
        from provider_sla import get_provider_sla_alerts

        return get_provider_sla_alerts(limit=100)
    return []


def _safe_bool(value: object) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return False


def _has_enough_sla_evidence(alert: dict, level: str) -> bool:
    attempts = _evidence_attempts(alert)
    if level == "critical":
        return attempts >= SLA_CRITICAL_MIN_ATTEMPTS
    return attempts >= SLA_WARNING_MIN_ATTEMPTS


def _evidence_attempts(alert: dict) -> int:
    basis = _safe_text(alert.get("alert_basis")).strip()
    windows = _safe_dict(alert.get("windows"))
    window = _safe_dict(windows.get(basis)) if basis else {}
    if window:
        return _safe_int(window.get("attempts"))
    return _safe_int(alert.get("attempts"))


def _compact_alert(
    alert: dict,
    *,
    current_entry: dict | None = None,
    source_has_healthy_entry: bool = False,
) -> dict:
    evidence_attempts = _evidence_attempts(alert)
    compact = {
        "source": _safe_text(alert.get("source")).strip() or "unknown",
        "provider": _safe_text(alert.get("provider")).strip() or "unknown",
        "alert_level": _safe_text(alert.get("alert_level")).strip() or "warning",
        "alert_message": _safe_text(alert.get("alert_message")).strip()[:180],
        "success_rate": alert.get("success_rate"),
        "last_status": alert.get("last_status"),
        "alert_basis": alert.get("alert_basis"),
        "evidence_attempts": evidence_attempts,
    }
    if isinstance(current_entry, dict):
        compact["current_status"] = _safe_text(current_entry.get("status")).strip() or "unknown"
        compact["current_record_count"] = _safe_int(current_entry.get("record_count"))
        compact["current_stale"] = _safe_bool(current_entry.get("stale"))
        compact["current_source_has_healthy_entry"] = _safe_bool(source_has_healthy_entry)
    return compact
