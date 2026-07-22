"""Build operator repair actions from report quality signals."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list
from provider_impact import build_provider_impact
from report_quality_integrity import snapshot_integrity_repair_item
from report_quality_repair_items import (
    content_credibility_repair_item,
    data_trust_repair_item,
    decision_freshness_repair_item,
    evidence_exit_gate_repair_item,
    report_conformance_repair_item,
)


SCHEMA_VERSION = "report_quality_repair_queue.v1"


def build_report_quality_repair_queue(reports: dict[str, Any] | list[dict[str, Any]], *, limit: int = 5) -> dict[str, Any]:
    """Return prioritized report repair items from already-loaded report rows."""
    report_rows = _report_rows(reports)
    items = [_repair_item(report) for report in report_rows]
    actionable = [item for item in items if item is not None]
    actionable.sort(key=lambda item: (-int(item["priority_score"]), str(item.get("ticker") or ""), str(item.get("filename") or "")))
    limited = actionable[: max(0, safe_int(limit, default=5))]
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "sampled_reports": len(report_rows),
            "action_required": len(actionable),
            "blocked": sum(1 for item in actionable if item["severity"] == "blocked"),
            "warning": sum(1 for item in actionable if item["severity"] == "warning"),
            "notice": sum(1 for item in actionable if item["severity"] == "notice"),
        },
        "items": limited,
    }


def _report_rows(reports: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    envelope = safe_mapping_dict(reports)
    if envelope is not None:
        rows = _field(envelope, "reports")
    else:
        rows = reports
    return safe_dict_list(rows)


def _repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        snapshot_integrity_repair_item(_field(report, "snapshot_integrity")),
        content_credibility_repair_item(report),
        report_conformance_repair_item(report),
        evidence_exit_gate_repair_item(report),
        _provider_sla_item(report),
        data_trust_repair_item(report),
        decision_freshness_repair_item(report),
    ]
    items = [item for item in candidates if item is not None]
    if not items:
        return None
    items.sort(key=lambda item: -int(item["priority_score"]))
    return _base_item(report) | items[0]


def _base_item(report: dict[str, Any]) -> dict[str, Any]:
    filename = _report_filename(report)
    return {
        "type": "report_repair",
        "ticker": _report_ticker(report),
        "filename": filename,
        "report_filename": filename,
        "pipeline_id": _pipeline_id(report),
        "reason_codes": [],
        "blocks_auto_rerun": False,
    }


def _provider_sla_item(report: dict[str, Any]) -> dict[str, Any] | None:
    impact = build_provider_impact(_provider_impact_report(report))
    summary = _dict(_field(impact, "summary"))
    if _field(summary, "recommended_action") != "wait_provider_recovery":
        return None
    codes = _reason_codes(_dict(_field(report, "data_trust")))
    return _item(
        severity="blocked",
        priority=900,
        action="wait_provider_recovery",
        label="等待來源恢復",
        title="核心資料來源不穩",
        detail="provider_sla_critical 影響核心資料，先等待來源恢復或刷新資料，避免盲目重跑。",
        reason_codes=codes,
        blocks_auto_rerun=True,
        extra={"provider_impact": impact},
    )


def _item(
    *,
    severity: str,
    priority: int,
    action: str,
    label: str,
    title: str,
    detail: str,
    reason_codes: list[str],
    blocks_auto_rerun: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "severity": severity,
        "priority_score": priority,
        "recommended_action": action,
        "action_label": label,
        "title": title,
        "detail": detail,
        "reason_codes": reason_codes,
        "blocks_auto_rerun": blocks_auto_rerun,
    }
    if extra:
        item.update(extra)
    return item


def _dict(value: Any) -> dict[str, Any]:
    return safe_mapping_dict(value) or {}


def _field(mapping: dict[str, Any], key: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    return dict.get(mapping, key, default)


def _provider_impact_report(report: dict[str, Any]) -> dict[str, Any]:
    trust = _dict(_field(report, "data_trust"))
    return {
        "ticker": _report_ticker(report),
        "filename": _report_filename(report),
        "report_filename": _report_filename(report),
        "pipeline_id": _pipeline_id(report),
        "data_trust": {
            "reason_codes": _field(trust, "reason_codes"),
            "provider_sla_alerts": _provider_impact_alerts(trust),
        },
    }


def _provider_impact_alerts(trust: dict[str, Any]) -> list[dict[str, Any]]:
    return [_provider_impact_alert(alert) for alert in safe_dict_list(_field(trust, "provider_sla_alerts"))]


def _provider_impact_alert(alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": _field(alert, "source"),
        "provider": _field(alert, "provider"),
        "alert_level": _field(alert, "alert_level"),
        "current_source_has_healthy_entry": _field(alert, "current_source_has_healthy_entry"),
        "current_status": _field(alert, "current_status"),
        "current_record_count": _field(alert, "current_record_count"),
        "current_stale": _field(alert, "current_stale"),
    }


def _report_ticker(report: dict[str, Any]) -> str:
    return _safe_text(_field(report, "ticker")).strip()


def _report_filename(report: dict[str, Any]) -> str:
    filename = _safe_text(_field(report, "filename")).strip()
    return filename or _safe_text(_field(report, "report_filename")).strip()


def _pipeline_id(report: dict[str, Any]) -> str:
    return _safe_text(_field(report, "pipeline_id")).strip() or "v1"


def _safe_text(value: Any) -> str:
    return safe_text(value)


def _reason_codes(trust: dict[str, Any]) -> list[str]:
    return safe_text_list(_field(trust, "reason_codes"))
