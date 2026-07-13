"""Data trust normalization and scoring."""

from __future__ import annotations

from typing import Any, Optional

from data_trust_audit import _safe_bool as safe_bool
from data_trust_audit import source_record_count, string_list
from data_trust_constants import (
    AUDIT_STATUS_DEGRADED_ENRICHMENT,
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_NOT_CONFIGURED,
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
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text


CORE_SOURCE_SET = set(CORE_DATA_SOURCES)


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


def latest_audit_by_source(entries: list) -> dict:
    latest = {}
    for entry in entries:
        entry_map = safe_mapping_dict(entry)
        if entry_map is None:
            continue
        source = _safe_text(dict.get(entry_map, "source")).strip()
        if source:
            latest[source] = entry_map
    return latest


def stale_sources_from(source_freshness: dict, latest_audit: dict) -> list[str]:
    return _stale_sources_from(source_freshness, latest_audit, core_only=True)


def optional_stale_sources_from(source_freshness: dict, latest_audit: dict) -> list[str]:
    return _stale_sources_from(source_freshness, latest_audit, core_only=False)


def _stale_sources_from(source_freshness: dict, latest_audit: dict, *, core_only: bool) -> list[str]:
    sources = set()
    for source, entry in source_freshness.items():
        source_name = _safe_text(source).strip()
        entry_map = safe_mapping_dict(entry)
        if (
            source_name
            and entry_map is not None
            and safe_bool(dict.get(entry_map, "stale"))
            and is_core_source(source_name) == core_only
        ):
            sources.add(source_name)
    for source, entry in latest_audit.items():
        source_name = _safe_text(source).strip()
        entry_map = safe_mapping_dict(entry)
        if (
            source_name
            and entry_map is not None
            and safe_bool(dict.get(entry_map, "stale"))
            and is_core_source(source_name) == core_only
        ):
            sources.add(source_name)
    return sorted(sources)


def is_core_source(source: str) -> bool:
    return _safe_text(source).strip() in CORE_SOURCE_SET


def optional_sources_with_status(latest_audit: dict, status: str) -> list[str]:
    audit = safe_mapping_dict(latest_audit) or {}
    status_text = _safe_text(status).strip()
    return sorted(
        source_name
        for source, entry in audit.items()
        if (source_name := _safe_text(source).strip())
        and not is_core_source(source_name)
        and _audit_status(entry) == status_text
    )


def last_market_data_at(data: dict, source_freshness: dict, latest_audit: dict) -> Optional[str]:
    source_data = safe_mapping_dict(data) or {}
    freshness = safe_mapping_dict(source_freshness) or {}
    audit = safe_mapping_dict(latest_audit) or {}
    market = safe_mapping_dict(dict.get(freshness, "market_data")) or {}
    market_audit = safe_mapping_dict(dict.get(audit, "market_data")) or {}
    for candidate in (
        dict.get(market, "fetched_at"),
        dict.get(source_data, "market_data_fetched_at"),
        dict.get(market_audit, "fetched_at"),
    ):
        timestamp = _safe_text(candidate).strip()
        if timestamp:
            return timestamp
    return None


def _safe_text(value: Any) -> str:
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


def _audit_status(entry: Any) -> str:
    entry_map = safe_mapping_dict(entry)
    if entry_map is None:
        return ""
    return _safe_text(dict.get(entry_map, "status")).strip()


def has_usable_critical_data(data: dict, latest_audit: dict) -> bool:
    source_data = safe_mapping_dict(data) or {}
    audit = safe_mapping_dict(latest_audit) or {}
    market_status = _audit_status(dict.get(audit, "market_data"))
    financial_status = _audit_status(dict.get(audit, "financial_statements"))
    market_ok = (
        market_status in {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}
        or source_record_count("market_data", source_data) > 0
    )
    financial_ok = (
        financial_status in {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}
        or source_record_count("financial_statements", source_data) > 0
    )
    return market_ok and financial_ok


def _score_for_trust(
    *,
    status: str,
    critical_failures: list[str],
    stale_sources: list[str],
    reason_codes: list[str],
) -> tuple[int, list[str]]:
    """Return a compact 0-100 operator-facing trust score."""
    base_scores = {
        TRUST_STATUS_FRESH: 95,
        TRUST_STATUS_PARTIAL: 72,
        TRUST_STATUS_STALE: 62,
        TRUST_STATUS_ERROR: 20,
        TRUST_STATUS_UNKNOWN: 35,
    }
    score = base_scores.get(status, 35)
    reasons: list[str] = []

    if status == TRUST_STATUS_FRESH:
        reasons.append("核心資料新鮮且未見主要來源異常。")
    elif status == TRUST_STATUS_PARTIAL:
        reasons.append("部分來源異常或使用備援資料。")
    elif status == TRUST_STATUS_STALE:
        reasons.append("部分來源超過新鮮度門檻。")
    elif status == TRUST_STATUS_ERROR:
        reasons.append("核心資料來源異常，分析可信度偏低。")
    else:
        reasons.append("缺少完整資料可信度紀錄。")

    if critical_failures:
        penalty = min(30, 12 * len(critical_failures))
        score -= penalty
        reasons.append("核心來源異常：" + "、".join(critical_failures[:4]))
    if stale_sources:
        penalty = min(24, 6 * len(stale_sources))
        score -= penalty
        reasons.append("過期來源：" + "、".join(stale_sources[:4]))

    reason_set = set(reason_codes or [])
    if "data_source_notes_present" in reason_set:
        score -= 4
        reasons.append("含資料口徑或備援補值註記。")
    if "provider_sla_critical" in reason_set:
        score -= 12
        reasons.append("全系統來源健康度曾達 critical。")
    if "provider_sla_warning_note" in reason_set:
        score -= 3
        reasons.append("全系統來源健康度有 warning。")
    if "missing_usable_critical_data" in reason_set:
        score -= 18
        reasons.append("缺少可用核心資料。")
    if "missing_data_trust_snapshot" in reason_set:
        score = min(score, 35)

    return max(0, min(int(round(score)), 100)), reasons[:6]
