"""Provider SLA alert matching helpers for data trust policy."""

from __future__ import annotations

from contextlib import suppress
import sqlite3

from config import (
    PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS,
    PROVIDER_SLA_WARNING_MIN_ATTEMPTS,
)
from data_trust_constants import AUDIT_STATUS_SKIPPED_FRESH_CACHE, AUDIT_STATUS_SUCCESS
from mapping_fields import safe_text as _mapping_safe_text


SLA_WARNING_MIN_ATTEMPTS = PROVIDER_SLA_WARNING_MIN_ATTEMPTS
SLA_CRITICAL_MIN_ATTEMPTS = PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS
CURRENT_FETCH_OK_STATUSES = {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}
_SAFE_EXCEPTIONS = (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError)
_FETCH_ALERT_EXCEPTIONS = (ImportError, sqlite3.Error, OSError) + _SAFE_EXCEPTIONS


def current_provider_pairs(data: dict) -> set[tuple[str, str]]:
    return set(current_provider_entries(data).keys())


def current_provider_entries(data: dict) -> dict[tuple[str, str], dict]:
    data = safe_dict(data)
    pairs = {}
    for entry in safe_dict_rows(data.get("source_audit")):
        source = safe_text(entry.get("source")).strip()
        provider = safe_text(entry.get("provider")).strip().lower()
        if source and provider:
            pairs[(source, provider)] = entry
    return pairs


def current_source_health(data: dict) -> dict[str, bool]:
    health: dict[str, bool] = {}
    for entry in current_provider_entries(data).values():
        if not isinstance(entry, dict):
            continue
        source = safe_text(entry.get("source")).strip()
        if source:
            health[source] = health.get(source, False) or audit_entry_is_healthy(entry)
    return health


def matched_provider_sla_alerts(data: dict, alerts: list[dict] | None = None) -> list[dict]:
    provider_entries = current_provider_entries(data)
    if not provider_entries:
        return []
    source_health = current_source_health(data)
    if alerts is None:
        alerts = fetch_provider_sla_alerts()
    matched = []
    for alert in safe_dict_rows(alerts):
        source = safe_text(alert.get("source")).strip()
        provider = safe_text(alert.get("provider")).strip().lower()
        level = safe_text(alert.get("alert_level")).strip().lower()
        if level not in {"warning", "critical"}:
            continue
        if not has_enough_sla_evidence(alert, level):
            continue
        current_entry = provider_entries.get((source, provider))
        if current_entry is not None:
            matched.append(
                compact_alert(
                    alert,
                    current_entry=current_entry,
                    source_has_healthy_entry=source_health.get(source, False),
                )
            )
    return matched


def current_fetch_is_healthy(alert: dict) -> bool:
    if safe_bool(alert.get("current_source_has_healthy_entry")):
        return True
    status = safe_text(alert.get("current_status")).strip()
    record_count = safe_int(alert.get("current_record_count"))
    return status in CURRENT_FETCH_OK_STATUSES and record_count > 0 and not safe_bool(alert.get("current_stale"))


def audit_entry_is_healthy(entry: dict) -> bool:
    status = safe_text(entry.get("status")).strip()
    record_count = safe_int(entry.get("record_count"))
    return status in CURRENT_FETCH_OK_STATUSES and record_count > 0 and not safe_bool(entry.get("stale"))


def safe_int(value: object) -> int:
    try:
        return int(0 if value is None else value)
    except _SAFE_EXCEPTIONS:
        return 0


def safe_text(value: object) -> str:
    return _mapping_safe_text(value)


def safe_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        text = safe_text(value).strip()
        return [text] if text else []
    iterator = safe_iterator(value)
    if iterator is None:
        return []
    texts = []
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            return texts
        except _SAFE_EXCEPTIONS:
            if texts or used_native:
                return texts
            iterator = native_sequence_iterator(value)
            if iterator is None:
                return texts
            used_native = True
            continue
        if text := safe_text(item).strip():
            texts.append(text)


def safe_dict(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    try:
        return dict(value)
    except _SAFE_EXCEPTIONS:
        try:
            return {key: child for key, child in dict.items(value)}
        except _SAFE_EXCEPTIONS:
            return {}


def safe_dict_rows(value: object) -> list[dict]:
    if value is None or isinstance(value, (str, bytes, dict)):
        return []
    iterator = safe_iterator(value)
    if iterator is None:
        return []
    rows = []
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            return rows
        except _SAFE_EXCEPTIONS:
            if rows or used_native:
                return rows
            iterator = native_sequence_iterator(value)
            if iterator is None:
                return rows
            used_native = True
            continue
        if isinstance(item, dict):
            rows.append(safe_dict(item))


def safe_iterator(value: object):
    try:
        return iter(value)
    except _SAFE_EXCEPTIONS:
        return native_sequence_iterator(value)
    return None


def native_sequence_iterator(value: object):
    try:
        if isinstance(value, list):
            return list.__iter__(value)
        if isinstance(value, tuple):
            return tuple.__iter__(value)
    except _SAFE_EXCEPTIONS:
        return None
    return None


def fetch_provider_sla_alerts() -> object:
    with suppress(*_FETCH_ALERT_EXCEPTIONS):
        from provider_sla import get_provider_sla_alerts

        return get_provider_sla_alerts(limit=100)
    return []


def safe_bool(value: object) -> bool:
    try:
        return bool(value)
    except _SAFE_EXCEPTIONS:
        return False


def has_enough_sla_evidence(alert: dict, level: str) -> bool:
    attempts = evidence_attempts(alert)
    if level == "critical":
        return attempts >= SLA_CRITICAL_MIN_ATTEMPTS
    return attempts >= SLA_WARNING_MIN_ATTEMPTS


def evidence_attempts(alert: dict) -> int:
    basis = safe_text(alert.get("alert_basis")).strip()
    windows = safe_dict(alert.get("windows"))
    window = safe_dict(windows.get(basis)) if basis else {}
    if window:
        return safe_int(window.get("attempts"))
    return safe_int(alert.get("attempts"))


def compact_alert(
    alert: dict,
    *,
    current_entry: dict | None = None,
    source_has_healthy_entry: bool = False,
) -> dict:
    compact = {
        "source": safe_text(alert.get("source")).strip() or "unknown",
        "provider": safe_text(alert.get("provider")).strip() or "unknown",
        "alert_level": safe_text(alert.get("alert_level")).strip() or "warning",
        "alert_message": safe_text(alert.get("alert_message")).strip()[:180],
        "success_rate": alert.get("success_rate"),
        "last_status": alert.get("last_status"),
        "alert_basis": alert.get("alert_basis"),
        "evidence_attempts": evidence_attempts(alert),
    }
    if isinstance(current_entry, dict):
        compact["current_status"] = safe_text(current_entry.get("status")).strip() or "unknown"
        compact["current_record_count"] = safe_int(current_entry.get("record_count"))
        compact["current_stale"] = safe_bool(current_entry.get("stale"))
        compact["current_source_has_healthy_entry"] = safe_bool(source_has_healthy_entry)
    return compact
