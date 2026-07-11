"""Data trust normalization and scoring."""

from __future__ import annotations

from typing import Any, Optional

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


CORE_SOURCE_SET = set(CORE_DATA_SOURCES)


def trust_status_label(status: str) -> str:
    status_text = _safe_text(status).strip()
    return TRUST_STATUS_LABELS.get(status_text, status_text or "unknown")


def normalize_data_trust(value: Any) -> dict:
    if not isinstance(value, dict):
        return unknown_data_trust()

    status = _safe_text(dict.get(value, "status")).strip() or TRUST_STATUS_UNKNOWN
    if status not in TRUST_STATUSES:
        status = TRUST_STATUS_UNKNOWN
    notes = dict.get(value, "notes", [])
    if isinstance(notes, str):
        notes = [notes]
    elif not isinstance(notes, list):
        notes = []

    score = dict.get(value, "score", dict.get(value, "trust_score"))
    try:
        score_value = int(round(float(score)))
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
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
        "last_market_data_at": dict.get(value, "last_market_data_at"),
        "notes": [
            text
            for item in notes
            if (text := _safe_text(item).strip())
        ],
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
        "score": 35,
        "score_reasons": ["未記錄資料快照，僅能以低可信度處理。"],
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
    optional_stale_sources = optional_stale_sources_from(source_freshness, latest_audit)
    latest_error_sources = sorted(
        source
        for source, entry in latest_audit.items()
        if isinstance(entry, dict) and entry.get("status") == AUDIT_STATUS_ERROR
    )
    error_sources = [source for source in latest_error_sources if is_core_source(source)]
    optional_error_sources = [source for source in latest_error_sources if not is_core_source(source)]

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

    if data.get("data_source_notes"):
        notes.append("另有資料口徑或備援補值註記，詳見報告參考資料區。")
        reason_codes.append("data_source_notes_present")

    trust = apply_provider_sla_to_trust(
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
    score, score_reasons = _score_for_trust(
        status=_safe_text(trust.get("status")).strip() or TRUST_STATUS_UNKNOWN,
        critical_failures=string_list(trust.get("critical_failures")),
        stale_sources=string_list(trust.get("stale_sources")),
        reason_codes=string_list(trust.get("reason_codes")),
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
        if not isinstance(entry, dict):
            continue
        source = _safe_text(entry.get("source")).strip()
        if source:
            latest[source] = entry
    return latest


def stale_sources_from(source_freshness: dict, latest_audit: dict) -> list[str]:
    return _stale_sources_from(source_freshness, latest_audit, core_only=True)


def optional_stale_sources_from(source_freshness: dict, latest_audit: dict) -> list[str]:
    return _stale_sources_from(source_freshness, latest_audit, core_only=False)


def _stale_sources_from(source_freshness: dict, latest_audit: dict, *, core_only: bool) -> list[str]:
    sources = set()
    for source, entry in source_freshness.items():
        source_name = _safe_text(source).strip()
        if source_name and isinstance(entry, dict) and entry.get("stale") and is_core_source(source_name) == core_only:
            sources.add(source_name)
    for source, entry in latest_audit.items():
        source_name = _safe_text(source).strip()
        if source_name and isinstance(entry, dict) and entry.get("stale") and is_core_source(source_name) == core_only:
            sources.add(source_name)
    return sorted(sources)


def is_core_source(source: str) -> bool:
    return _safe_text(source).strip() in CORE_SOURCE_SET


def optional_sources_with_status(latest_audit: dict, status: str) -> list[str]:
    return sorted(
        source
        for source, entry in latest_audit.items()
        if not is_core_source(source)
        and isinstance(entry, dict)
        and entry.get("status") == status
    )


def last_market_data_at(data: dict, source_freshness: dict, latest_audit: dict) -> Optional[str]:
    market = source_freshness.get("market_data") if isinstance(source_freshness.get("market_data"), dict) else {}
    return (
        market.get("fetched_at")
        or data.get("market_data_fetched_at")
        or latest_audit.get("market_data", {}).get("fetched_at")
    )


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


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
