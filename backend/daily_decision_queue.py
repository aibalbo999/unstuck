"""Prioritized daily operator decision queue."""

from __future__ import annotations

from datetime import date
from typing import Any

from daily_decision_queue_notifications import notification_delivery_items
from daily_decision_report_actions import backtest_due_items, rerun_items
from daily_decision_queue_summary import SOURCE_ORDER, queue_response
from daily_decision_provider_items import provider_impact_items
from daily_decision_report_keys import report_key
from daily_decision_route_warnings import route_warning_items
from mapping_fields import mapping_field as _field
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list
from operator_action_contract import navigation_context
from report_freshness_summary import safe_bool
from report_pipeline_identity import resolve_report_pipeline_id

SCHEMA_VERSION = "daily_decision_queue.v1"


def build_daily_decision_queue(
    *,
    reports: list[dict[str, Any]],
    repair_items: list[dict[str, Any]],
    quality_audit_items: list[dict[str, Any]] | None = None,
    rerun_reports: list[dict[str, Any]],
    high_priority_watchlist: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    performance: dict[str, Any],
    free_mode: dict[str, Any],
    provider_impact_ledger: dict[str, Any] | None = None,
    ops: dict[str, Any] | None = None,
    limit: int = 5,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Return one sorted queue across report, tracking, provider, and ops signals."""
    repair_actions = [_repair_action_payload(item) for item in safe_dict_list(repair_items)]
    repair_keys = {report_key(item) for item in repair_actions if report_key(item)}
    quality_audit_actions = [_repair_action_payload(item, source="report_quality_audit")
        for item in safe_dict_list(quality_audit_items)
        if report_key(item) not in repair_keys
    ]
    blocking_repair_keys = {
        report_key(item)
        for item in repair_actions
        if report_key(item) and _field(item, "type") != "rerun_report"
    }
    blocking_quality_audit_keys = {report_key(item)
        for item in quality_audit_actions
        if report_key(item) and _field(item, "type") != "rerun_report"
    }
    report_action_keys = repair_keys | {report_key(item) for item in quality_audit_actions if report_key(item)}
    blocking_report_action_keys = blocking_repair_keys | blocking_quality_audit_keys
    ops_payload = safe_mapping_dict(ops) or {}
    provider_ledger = safe_mapping_dict(provider_impact_ledger) or {}
    items = []
    items.extend(_free_mode_items(free_mode))
    items.extend(repair_actions)
    items.extend(quality_audit_actions)
    items.extend(provider_impact_items(provider_ledger, skip_keys=report_action_keys))
    items.extend(notification_delivery_items(ops_payload))
    items.extend(backtest_due_items(reports, performance, as_of=as_of or date.today(), skip_keys=blocking_report_action_keys))
    items.extend(rerun_items(rerun_reports, skip_keys=report_action_keys))
    items.extend(route_warning_items(ops_payload))
    items.extend(_watchlist_items(high_priority_watchlist))
    items.extend(_candidate_items(candidates))
    actionable = [item for item in items if item]
    return queue_response(actionable, limit=limit, schema_version=SCHEMA_VERSION)


def _free_mode_items(free_mode: dict[str, Any]) -> list[dict[str, Any]]:
    if safe_bool(_field(free_mode, "can_run_without_paid_keys", True)):
        return []
    violations = safe_text_list(_field(free_mode, "violations"))
    return [{
        "source": "free_mode",
        "type": "fix_free_mode",
        "priority_score": 980,
        "title": "免費模式有付費依賴缺口",
        "detail": "先查看 provider contract，避免報告流程依賴付費來源。",
        "violations": violations,
    }]

def _watchlist_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = safe_dict_list(items)
    if not rows:
        return []
    samples = "、".join(ticker for item in rows[:3] if (ticker := safe_text(_field(item, "ticker")).strip()))
    return [{
        "source": "watchlist",
        "type": "run_watchlist",
        "priority_score": 560,
        "title": f"{len(rows)} 檔 watchlist 待分析",
        "detail": samples,
    }]


def _candidate_items(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = safe_dict_list(candidates)
    if not rows:
        return []
    candidate = rows[0]
    ticker = safe_text(_field(candidate, "ticker")).strip()
    company_name = safe_text(_field(candidate, "company_name")).strip()
    reason = safe_text(_field(candidate, "reason")).strip()
    return [{
        "source": "screener",
        "type": "review_candidate",
        "priority_score": 420,
        "title": " ".join(part for part in (ticker, company_name) if part),
        "detail": reason or "市場掃描候選",
        "reason": reason,
        "company_name": company_name,
        "score": _field(candidate, "score"),
        "ticker": ticker,
    }]


def _repair_action_payload(item: dict[str, Any], *, source: str = "report_repair") -> dict[str, Any]:
    recommended = safe_text(_field(item, "recommended_action")).strip() or "manual_review"
    action_type = {
        "rerun_analysis": "rerun_report",
        "refresh_data_snapshot": "refresh_data_snapshot",
        "wait_provider_recovery": "wait_provider_recovery",
        "manual_review": "manual_review",
    }.get(recommended, "manual_review")
    ticker = safe_text(_field(item, "ticker")).strip() or "報告"
    filename = safe_text(_field(item, "filename")).strip() or safe_text(_field(item, "report_filename")).strip() or None
    pipeline_id = resolve_report_pipeline_id(
        filename or "",
        stored_pipeline=_field(item, "pipeline_id"),
    )
    title = safe_text(_field(item, "title")).strip() or "報告需處理"
    action_payload = {
        "source": source,
        "type": action_type,
        "priority_score": _int(_field(item, "priority_score")) or 700,
        "title": f"{ticker} {pipeline_id} {title}",
        "detail": safe_text(_field(item, "detail")),
        "ticker": ticker,
        "filename": filename,
        "report_filename": filename,
        "pipeline_id": pipeline_id,
        "severity": safe_text(_field(item, "severity")).strip() or None,
        "recommended_action": recommended,
        "action_label": safe_text(_field(item, "action_label")).strip() or None,
        "blocks_auto_rerun": safe_bool(_field(item, "blocks_auto_rerun")),
        "reason_codes": safe_text_list(_field(item, "reason_codes")),
    }
    for key in ("operator_action", "operator_action_label", "target_panel", "target_tab"):
        value = safe_text(_field(item, key)).strip()
        if value:
            action_payload[key] = value
    if filename:
        action_payload.update(navigation_context(action_payload))
    return action_payload


def _int(value: Any) -> int:
    return safe_int(value)


__all__ = ["SCHEMA_VERSION", "build_daily_decision_queue"]
