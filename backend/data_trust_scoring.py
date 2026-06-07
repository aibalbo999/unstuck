"""Data trust normalization and scoring."""

from __future__ import annotations

from typing import Any, Optional

from data_trust_audit import source_record_count, string_list
from data_trust_constants import (
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    CORE_DATA_SOURCES,
    CRITICAL_TRUST_SOURCES,
    TRUST_STATUS_ERROR,
    TRUST_STATUS_FRESH,
    TRUST_STATUS_LABELS,
    TRUST_STATUS_PARTIAL,
    TRUST_STATUS_STALE,
    TRUST_STATUS_UNKNOWN,
    TRUST_STATUSES,
)
from data_trust_sla_policy import apply_provider_sla_to_trust


def trust_status_label(status: str) -> str:
    return TRUST_STATUS_LABELS.get(str(status or ""), str(status or "unknown"))


def normalize_data_trust(value: Any) -> dict:
    if not isinstance(value, dict):
        return unknown_data_trust()

    status = str(value.get("status") or TRUST_STATUS_UNKNOWN)
    if status not in TRUST_STATUSES:
        status = TRUST_STATUS_UNKNOWN
    notes = value.get("notes", [])
    if isinstance(notes, str):
        notes = [notes]
    elif not isinstance(notes, list):
        notes = []

    normalized = {
        "status": status,
        "critical_failures": string_list(value.get("critical_failures")),
        "stale_sources": string_list(value.get("stale_sources")),
        "last_market_data_at": value.get("last_market_data_at"),
        "notes": [str(item) for item in notes if str(item).strip()],
        "reason_codes": string_list(value.get("reason_codes")),
    }
    alerts = value.get("provider_sla_alerts")
    if isinstance(alerts, list):
        normalized["provider_sla_alerts"] = [
            item for item in alerts
            if isinstance(item, dict)
        ][:10]
    return normalized


def unknown_data_trust() -> dict:
    return {
        "status": TRUST_STATUS_UNKNOWN,
        "critical_failures": [],
        "stale_sources": [],
        "last_market_data_at": None,
        "notes": ["未記錄資料可信度快照。"],
        "reason_codes": ["missing_data_trust_snapshot"],
    }


def build_data_trust(data: dict) -> dict:
    if not isinstance(data, dict):
        return unknown_data_trust()

    source_freshness = data.get("source_freshness") if isinstance(data.get("source_freshness"), dict) else {}
    audit_entries = data.get("source_audit") if isinstance(data.get("source_audit"), list) else []
    if not source_freshness and not audit_entries:
        return unknown_data_trust()

    latest_audit = latest_audit_by_source(audit_entries)
    critical_failures = [
        source
        for source in CRITICAL_TRUST_SOURCES
        if latest_audit.get(source, {}).get("status") == AUDIT_STATUS_ERROR
    ]
    core_failures = [
        source
        for source in CORE_DATA_SOURCES
        if latest_audit.get(source, {}).get("status") == AUDIT_STATUS_ERROR
    ]
    stale_sources = stale_sources_from(source_freshness, latest_audit)
    error_sources = sorted({
        str(entry.get("source") or "")
        for entry in audit_entries
        if isinstance(entry, dict) and entry.get("status") == AUDIT_STATUS_ERROR and entry.get("source")
    })

    if critical_failures and not has_usable_critical_data(data, latest_audit):
        status = TRUST_STATUS_ERROR
        notes = ["核心市場或財報來源失敗，且沒有足夠可用資料。"]
        reason_codes = ["critical_sources_error", "missing_usable_critical_data"]
    elif critical_failures or core_failures or error_sources:
        status = TRUST_STATUS_PARTIAL
        notes = ["部分來源異常或使用備援資料，請搭配來源審計表檢視。"]
        reason_codes = [f"source_error:{source}" for source in sorted(set(core_failures + error_sources))]
    elif stale_sources:
        status = TRUST_STATUS_STALE
        notes = ["部分資料來源超過新鮮度門檻，分析已保留過期標記。"]
        reason_codes = [f"source_stale:{source}" for source in stale_sources]
    else:
        status = TRUST_STATUS_FRESH
        notes = ["核心資料在新鮮度門檻內，來源審計未見主要異常。"]
        reason_codes = ["fresh_core_sources"]

    if data.get("data_source_notes"):
        notes.append("另有資料口徑或備援補值註記，詳見報告參考資料區。")
        reason_codes.append("data_source_notes_present")

    return apply_provider_sla_to_trust(
        data,
        {
            "status": status,
            "critical_failures": core_failures,
            "stale_sources": stale_sources,
            "last_market_data_at": last_market_data_at(data, source_freshness, latest_audit),
            "notes": notes,
            "reason_codes": reason_codes,
        },
    )


def finalize_data_trust(data: dict) -> dict:
    if isinstance(data, dict):
        data["data_trust"] = build_data_trust(data)
    return data


def latest_audit_by_source(entries: list) -> dict:
    latest = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "")
        if source:
            latest[source] = entry
    return latest


def stale_sources_from(source_freshness: dict, latest_audit: dict) -> list[str]:
    sources = set()
    for source, entry in source_freshness.items():
        if isinstance(entry, dict) and entry.get("stale"):
            sources.add(str(source))
    for source, entry in latest_audit.items():
        if isinstance(entry, dict) and entry.get("stale"):
            sources.add(str(source))
    return sorted(sources)


def last_market_data_at(data: dict, source_freshness: dict, latest_audit: dict) -> Optional[str]:
    market = source_freshness.get("market_data") if isinstance(source_freshness.get("market_data"), dict) else {}
    return (
        market.get("fetched_at")
        or data.get("market_data_fetched_at")
        or latest_audit.get("market_data", {}).get("fetched_at")
    )


def has_usable_critical_data(data: dict, latest_audit: dict) -> bool:
    market_entry = latest_audit.get("market_data", {})
    financial_entry = latest_audit.get("financial_statements", {})
    market_ok = (
        market_entry.get("status") in {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}
        or source_record_count("market_data", data) > 0
    )
    financial_ok = (
        financial_entry.get("status") in {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}
        or source_record_count("financial_statements", data) > 0
    )
    return market_ok and financial_ok
