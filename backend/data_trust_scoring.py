"""Data trust normalization and scoring."""

from __future__ import annotations

from typing import Any

from data_trust_audit import string_list
from data_trust_constants import (
    AUDIT_STATUS_DEGRADED_ENRICHMENT,
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_NOT_CONFIGURED,
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
from data_trust_score_policy import score_for_trust as _score_for_trust
from data_trust_source_status import (
    audit_status as _audit_status,
    has_usable_critical_data,
    is_core_source,
    last_market_data_at,
    latest_audit_by_source,
    optional_sources_with_status,
    optional_stale_sources_from,
    stale_sources_from,
)
from data_trust_sla_policy import apply_provider_sla_to_trust
from data_trust_values import has_value
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number


def trust_status_label(status: str) -> str:
    status_text = _safe_text(status).strip()
    return TRUST_STATUS_LABELS.get(status_text, status_text or "unknown")


def normalize_data_trust(value: Any) -> dict:
    value_map = safe_mapping_dict(value)
    if value_map is None:
        return unknown_data_trust()
    value = value_map

    status = _safe_text(dict.get(value, "status")).strip() or TRUST_STATUS_UNKNOWN
    if status not in TRUST_STATUSES:
        status = TRUST_STATUS_UNKNOWN
    notes = string_list(dict.get(value, "notes"))
    last_market_data_at = _safe_text(dict.get(value, "last_market_data_at")).strip() or None

    score = dict.get(value, "score", dict.get(value, "trust_score"))
    try:
        if isinstance(score, bool):
            raise TypeError("boolean score is not numeric evidence")
        score_value = int(round(float(score)))
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        score_value = _score_for_trust(
            status=status,
            critical_failures=string_list(dict.get(value, "critical_failures")),
            stale_sources=string_list(dict.get(value, "stale_sources")),
            reason_codes=string_list(dict.get(value, "reason_codes")),
        )[0]
    normalized = {
        "status": status,
        "critical_failures": string_list(dict.get(value, "critical_failures")),
        "stale_sources": string_list(dict.get(value, "stale_sources")),
        "last_market_data_at": last_market_data_at,
        "notes": notes,
        "reason_codes": string_list(dict.get(value, "reason_codes")),
        "score": max(0, min(score_value, 100)),
        "score_reasons": string_list(dict.get(value, "score_reasons")) or _score_for_trust(
            status=status,
            critical_failures=string_list(dict.get(value, "critical_failures")),
            stale_sources=string_list(dict.get(value, "stale_sources")),
            reason_codes=string_list(dict.get(value, "reason_codes")),
        )[1],
    }
    alerts = dict.get(value, "provider_sla_alerts")
    if isinstance(alerts, (list, tuple)):
        normalized["provider_sla_alerts"] = safe_dict_list(alerts)[:10]
    return normalized


def unknown_data_trust() -> dict:
    return {
        "status": TRUST_STATUS_UNKNOWN,
        "critical_failures": [],
        "stale_sources": [],
        "last_market_data_at": None,
        "notes": ["未記錄資料可信度快照。"],
        "reason_codes": ["missing_data_trust_snapshot"],
        "score": 35,
        "score_reasons": ["未記錄資料快照，僅能以低可信度處理。"],
    }


def build_data_trust(data: dict) -> dict:
    source_data = safe_mapping_dict(data)
    if source_data is None:
        return unknown_data_trust()

    source_freshness = _safe_mapping_children(dict.get(source_data, "source_freshness"))
    audit_entries = safe_dict_list(dict.get(source_data, "source_audit"))
    if not source_freshness and not audit_entries:
        return unknown_data_trust()

    latest_audit = latest_audit_by_source(audit_entries)
    critical_failures = [
        source
        for source in CRITICAL_TRUST_SOURCES
        if _audit_status(dict.get(latest_audit, source)) == AUDIT_STATUS_ERROR
    ]
    core_failures = [
        source
        for source in CORE_DATA_SOURCES
        if _audit_status(dict.get(latest_audit, source)) == AUDIT_STATUS_ERROR
    ]
    stale_sources = stale_sources_from(source_freshness, latest_audit)
    optional_stale_sources = optional_stale_sources_from(source_freshness, latest_audit)
    latest_error_sources = sorted(
        source
        for source, entry in latest_audit.items()
        if _audit_status(entry) == AUDIT_STATUS_ERROR
    )
    error_sources = [source for source in latest_error_sources if is_core_source(source)]
    optional_error_sources = [source for source in latest_error_sources if not is_core_source(source)]

    if critical_failures and not has_usable_critical_data(source_data, latest_audit):
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

    optional_not_configured = optional_sources_with_status(latest_audit, AUDIT_STATUS_NOT_CONFIGURED)
    optional_degraded = optional_sources_with_status(latest_audit, AUDIT_STATUS_DEGRADED_ENRICHMENT)
    if optional_not_configured:
        notes.append("補充來源未設定，系統已略過該 enrichment，不影響核心資料可信度。")
        reason_codes.extend(f"optional_source_not_configured:{source}" for source in optional_not_configured)
    if optional_degraded:
        notes.append("補充來源降級，核心市場與財報資料仍按既有可信度處理。")
        reason_codes.extend(f"optional_source_degraded:{source}" for source in optional_degraded)
    if optional_stale_sources:
        notes.append("補充來源超過新鮮度門檻，已保留提醒，不影響核心資料可信度。")
        reason_codes.extend(f"optional_source_stale:{source}" for source in optional_stale_sources)
    if optional_error_sources:
        notes.append("補充來源異常，核心市場與財報資料仍按既有可信度處理。")
        reason_codes.extend(f"optional_source_error:{source}" for source in optional_error_sources)

    if _data_source_notes(dict.get(source_data, "data_source_notes")):
        notes.append("另有資料口徑或備援補值註記，詳見報告參考資料區。")
        reason_codes.append("data_source_notes_present")

    base_trust = {
        "status": status,
        "critical_failures": core_failures,
        "stale_sources": stale_sources,
        "last_market_data_at": last_market_data_at(source_data, source_freshness, latest_audit),
        "notes": notes,
        "reason_codes": reason_codes,
    }
    provider_sla_trust = {
        **base_trust,
        "critical_failures": list(core_failures),
        "stale_sources": list(stale_sources),
        "notes": list(notes),
        "reason_codes": list(reason_codes),
    }
    try:
        trust = safe_mapping_dict(apply_provider_sla_to_trust(source_data, provider_sla_trust)) or dict(base_trust)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        trust = dict(base_trust)
    status_text = _safe_text(dict.get(trust, "status")).strip() or TRUST_STATUS_UNKNOWN
    if status_text not in TRUST_STATUSES:
        status_text = TRUST_STATUS_UNKNOWN
    trust["status"] = status_text
    critical_failure_list = string_list(dict.get(trust, "critical_failures"))
    stale_source_list = string_list(dict.get(trust, "stale_sources"))
    note_list = string_list(dict.get(trust, "notes"))
    reason_code_list = string_list(dict.get(trust, "reason_codes"))
    trust["critical_failures"] = critical_failure_list
    trust["stale_sources"] = stale_source_list
    trust["notes"] = note_list
    trust["reason_codes"] = reason_code_list
    last_market_data_at_text = _safe_text(dict.get(trust, "last_market_data_at")).strip() or None
    trust["last_market_data_at"] = last_market_data_at_text
    provider_sla_alert_rows = safe_dict_list(dict.get(trust, "provider_sla_alerts"))[:10]
    if provider_sla_alert_rows:
        trust["provider_sla_alerts"] = provider_sla_alert_rows
    else:
        trust.pop("provider_sla_alerts", None)
    score, score_reasons = _score_for_trust(
        status=status_text,
        critical_failures=critical_failure_list,
        stale_sources=stale_source_list,
        reason_codes=reason_code_list,
    )
    trust["score"] = score
    trust["score_reasons"] = score_reasons
    return trust


def finalize_data_trust(data: dict) -> dict:
    if isinstance(data, dict):
        data["data_trust"] = build_data_trust(data)
    return data


def _safe_text(value: Any) -> str:
    if is_non_finite_number(value):
        return ""
    if isinstance(value, str) and not has_value(value):
        return ""
    return safe_text(value)


def _safe_mapping_children(value: Any) -> dict:
    rows = safe_mapping_dict(value) or {}
    normalized = {}
    for key, child in rows.items():
        child_map = safe_mapping_dict(child)
        if child_map is not None:
            normalized[key] = child_map
    return normalized


def _data_source_notes(value: Any) -> list[str]:
    if not isinstance(value, (str, list, tuple)):
        return []
    return string_list(value)
