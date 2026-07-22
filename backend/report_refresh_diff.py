"""Data snapshot refresh diff and rerun policy helpers."""

from __future__ import annotations

import json

from data_trust import normalize_data_trust
from mapping_fields import safe_mapping_dict, safe_sequence_items


DECISION_RELEVANT_DATA_KEYS = (
    "current_price", "market_cap_raw", "pe_ratio_raw", "pb_ratio", "ps_ratio", "ev_ebitda",
    "revenue_ttm_raw", "net_income_ttm_raw", "free_cash_flow_raw", "total_debt_raw", "total_cash_raw",
    "years", "revenue_history", "net_income_history", "gross_profit_history", "operating_income_history",
    "fcf_history", "gross_margin_history", "op_margin_history", "net_margin_history", "roe_history",
    "recent_monthly_revenue", "institutional_trading", "pe_river_chart",
)


def _source_status_map(snapshot: dict) -> dict:
    status_map = {}
    snapshot_map = safe_mapping_dict(snapshot) or {}
    entries = safe_sequence_items(dict.get(snapshot_map, "source_audit", []))
    for raw_entry in entries:
        entry = safe_mapping_dict(raw_entry)
        if entry is None:
            continue
        source = str(dict.get(entry, "source") or "unknown")
        provider = str(dict.get(entry, "provider") or "unknown")
        status_map[(source, provider)] = {
            "source": source,
            "provider": provider,
            "status": str(dict.get(entry, "status") or "unknown"),
            "message": str(dict.get(entry, "message") or dict.get(entry, "error_kind") or "")[:160],
        }
    return status_map


def refresh_data_diff(previous_snapshot: dict, refreshed_snapshot: dict) -> dict:
    previous_snapshot_map = safe_mapping_dict(previous_snapshot) or {}
    refreshed_snapshot_map = safe_mapping_dict(refreshed_snapshot) or {}
    before_trust = normalize_data_trust(dict.get(previous_snapshot_map, "data_trust"))
    after_trust = normalize_data_trust(dict.get(refreshed_snapshot_map, "data_trust"))
    before_stale = set(before_trust.get("stale_sources", []) or [])
    after_stale = set(after_trust.get("stale_sources", []) or [])
    before_failures = set(before_trust.get("critical_failures", []) or [])
    after_failures = set(after_trust.get("critical_failures", []) or [])
    before_status = _source_status_map(previous_snapshot)
    after_status = _source_status_map(refreshed_snapshot)
    source_status_changes = []
    for key in sorted(set(before_status) | set(after_status)):
        before = before_status.get(key, {"source": key[0], "provider": key[1], "status": "missing", "message": ""})
        after = after_status.get(key, {"source": key[0], "provider": key[1], "status": "missing", "message": ""})
        if before["status"] != after["status"]:
            source_status_changes.append({
                "source": key[0],
                "provider": key[1],
                "before": before["status"],
                "after": after["status"],
                "message": after.get("message") or before.get("message") or "",
            })

    summary = []
    if before_trust.get("status") != after_trust.get("status"):
        summary.append(f"可信度 {before_trust.get('status')} → {after_trust.get('status')}")
    removed_stale = sorted(before_stale - after_stale)
    added_stale = sorted(after_stale - before_stale)
    removed_failures = sorted(before_failures - after_failures)
    added_failures = sorted(after_failures - before_failures)
    if removed_stale:
        summary.append("解除過期：" + "、".join(removed_stale[:4]))
    if added_stale:
        summary.append("新增過期：" + "、".join(added_stale[:4]))
    if removed_failures:
        summary.append("解除核心異常：" + "、".join(removed_failures[:4]))
    if added_failures:
        summary.append("新增核心異常：" + "、".join(added_failures[:4]))
    if not summary:
        summary.append("資料可信度狀態未變更")

    return {
        "data_trust_status": {
            "before": before_trust.get("status"),
            "after": after_trust.get("status"),
            "changed": before_trust.get("status") != after_trust.get("status"),
        },
        "stale_sources": {"removed": removed_stale, "added": added_stale},
        "critical_failures": {"removed": removed_failures, "added": added_failures},
        "source_status_changes": source_status_changes[:20],
        "summary": summary,
    }


def refresh_requires_analysis_rerun(previous_snapshot: dict, refreshed_snapshot: dict, refresh_diff: dict) -> bool:
    previous_snapshot_map = safe_mapping_dict(previous_snapshot) or {}
    refreshed_snapshot_map = safe_mapping_dict(refreshed_snapshot) or {}
    refresh_diff_map = safe_mapping_dict(refresh_diff) or {}
    if (
        dict.get(previous_snapshot_map, "refreshed_without_analysis_rerun")
        or dict.get(previous_snapshot_map, "decision_validity_status") == "needs_rerun"
    ):
        return True
    before_data = safe_mapping_dict(dict.get(previous_snapshot_map, "data")) or {}
    after_data = safe_mapping_dict(dict.get(refreshed_snapshot_map, "data")) or {}
    for key in DECISION_RELEVANT_DATA_KEYS:
        if _stable_data_value(before_data, key) != _stable_data_value(after_data, key):
            return True

    stale_sources_diff = safe_mapping_dict(dict.get(refresh_diff_map, "stale_sources")) or {}
    if dict.get(stale_sources_diff, "removed") or dict.get(stale_sources_diff, "added"):
        return True
    critical_failures_diff = safe_mapping_dict(dict.get(refresh_diff_map, "critical_failures")) or {}
    if dict.get(critical_failures_diff, "removed") or dict.get(critical_failures_diff, "added"):
        return True

    before_trust = normalize_data_trust(dict.get(previous_snapshot_map, "data_trust"))
    after_trust = normalize_data_trust(dict.get(refreshed_snapshot_map, "data_trust"))
    if _actionable_reason_codes(before_trust) != _actionable_reason_codes(after_trust):
        return True
    if before_trust.get("status") != after_trust.get("status"):
        return not _provider_sla_only_partial(after_trust)
    return False


def _stable_data_value(data: dict, key: str) -> str:
    if key not in data:
        return "__missing__"
    return json.dumps(data.get(key), ensure_ascii=False, sort_keys=True, default=str)


def _actionable_reason_codes(trust: dict) -> set[str]:
    return {
        code for code in (trust.get("reason_codes") or [])
        if str(code).startswith(("source_error:", "source_stale:"))
        or code in {"critical_sources_error", "missing_usable_critical_data"}
    }


def _provider_sla_only_partial(trust: dict) -> bool:
    codes = set(trust.get("reason_codes") or [])
    return (
        trust.get("status") == "partial"
        and "provider_sla_critical" in codes
        and not trust.get("critical_failures")
        and not trust.get("stale_sources")
        and not _actionable_reason_codes(trust)
    )
