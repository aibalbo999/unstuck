"""Build operator repair actions from report quality signals."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_int, safe_text_list
from provider_impact import build_provider_impact


SCHEMA_VERSION = "report_quality_repair_queue.v1"


def build_report_quality_repair_queue(reports: dict[str, Any] | list[dict[str, Any]], *, limit: int = 5) -> dict[str, Any]:
    """Return prioritized report repair items from already-loaded report rows."""
    report_rows = _report_rows(reports)
    items = [_repair_item(report) for report in report_rows]
    actionable = [item for item in items if item is not None]
    actionable.sort(key=lambda item: (-int(item["priority_score"]), str(item.get("ticker") or ""), str(item.get("filename") or "")))
    limited = actionable[: max(0, safe_int(limit))]
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
    if isinstance(reports, dict):
        rows = _field(reports, "reports")
    else:
        rows = reports
    return safe_dict_list(rows)


def _repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        _content_credibility_item(report),
        _report_conformance_item(report),
        _evidence_exit_gate_item(report),
        _provider_sla_item(report),
        _data_trust_item(report),
        _decision_freshness_item(report),
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


def _content_credibility_item(report: dict[str, Any]) -> dict[str, Any] | None:
    gate = _dict(_field(report, "content_credibility"))
    status = _status(_field(gate, "status"))
    if status == "blocked":
        return _item(
            severity="blocked",
            priority=1000,
            action="manual_review",
            label="人工審核",
            title="內容可信度未通過",
            detail=_summary(gate, "報告建議、目標價或資料限制互相矛盾。"),
            reason_codes=["content_credibility_blocked"],
            blocks_auto_rerun=True,
        )
    if status == "warning":
        return _item(
            severity="warning",
            priority=780,
            action="manual_review",
            label="人工審核",
            title="內容可信度需確認",
            detail=_summary(gate, "報告內容可信度有警示，採用前需人工確認。"),
            reason_codes=["content_credibility_warning"],
        )
    return None


def _report_conformance_item(report: dict[str, Any]) -> dict[str, Any] | None:
    conformance = _dict(_field(report, "report_conformance"))
    status = _status(_field(conformance, "status"))
    if status == "blocked":
        return _item(
            severity="blocked",
            priority=960,
            action="manual_review",
            label="人工審核",
            title="報告符合性未通過",
            detail=_summary(conformance, "報告未符合輸出契約。"),
            reason_codes=["report_conformance_blocked"],
            blocks_auto_rerun=True,
        )
    if status == "warning":
        return _item(
            severity="warning",
            priority=740,
            action="manual_review",
            label="人工審核",
            title="報告符合性需確認",
            detail=_summary(conformance, "報告符合主要契約，但仍需人工確認。"),
            reason_codes=["report_conformance_warning"],
        )
    return None


def _evidence_exit_gate_item(report: dict[str, Any]) -> dict[str, Any] | None:
    gate = _dict(_field(report, "evidence_exit_gate"))
    verdict = _status(_field(gate, "verdict"))
    if verdict == "rejected":
        return _item(
            severity="blocked",
            priority=940,
            action="manual_review",
            label="人工審核",
            title="證據抽查未通過",
            detail=_summary(gate, "報告數字未能對上資料快照。"),
            reason_codes=["evidence_exit_gate_rejected"],
            blocks_auto_rerun=True,
        )
    if verdict == "caution":
        return _item(
            severity="warning",
            priority=720,
            action="manual_review",
            label="人工審核",
            title="數字證據需核對",
            detail=_summary(gate, "部分報告數字需人工確認。"),
            reason_codes=["evidence_exit_gate_caution"],
        )
    return None


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


def _data_trust_item(report: dict[str, Any]) -> dict[str, Any] | None:
    trust = _dict(_field(report, "data_trust"))
    status = _status(_field(trust, "status"))
    codes = _reason_codes(trust)
    if status == "error" or any(code.startswith("source_error:") for code in codes):
        return _item(
            severity="blocked",
            priority=860,
            action="manual_review",
            label="查看報告",
            title="資料來源異常",
            detail="資料來源錯誤，採用或重跑前需先確認來源審計。",
            reason_codes=codes or ["data_trust_error"],
            blocks_auto_rerun=True,
        )
    if status == "stale" or _has_stale_source(trust, codes):
        return _item(
            severity="warning",
            priority=620,
            action="refresh_data_snapshot",
            label="刷新資料",
            title="資料快照過期",
            detail="先刷新資料快照，再判斷是否需要完整重跑。",
            reason_codes=codes or ["data_trust_stale"],
        )
    return None


def _decision_freshness_item(report: dict[str, Any]) -> dict[str, Any] | None:
    freshness = _dict(_field(report, "decision_freshness"))
    if not (
        _safe_bool(_field(freshness, "requires_rerun"))
        or _safe_bool(_field(report, "requires_rerun"))
        or _safe_bool(_field(report, "analysis_text_stale"))
    ):
        return None
    detail = _first_text(
        _field(freshness, "requires_rerun_reason"),
        _field(report, "analysis_text_stale_message"),
        _field(report, "requires_rerun_reason"),
        fallback="資料快照與結論不同步，舊 Markdown 不應視為最新判斷。",
    )
    return _item(
        severity="warning",
        priority=700,
        action="rerun_analysis",
        label="完整重跑",
        title="結論需完整重跑",
        detail=detail,
        reason_codes=["decision_freshness_needs_rerun"],
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
    return value if isinstance(value, dict) else {}


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


def _status(value: Any) -> str:
    return _safe_text(value).strip().lower()


def _report_ticker(report: dict[str, Any]) -> str:
    return _safe_text(_field(report, "ticker")).strip()


def _report_filename(report: dict[str, Any]) -> str:
    filename = _safe_text(_field(report, "filename")).strip()
    return filename or _safe_text(_field(report, "report_filename")).strip()


def _pipeline_id(report: dict[str, Any]) -> str:
    return _safe_text(_field(report, "pipeline_id")).strip() or "v1"


def _safe_text(value: Any) -> str:
    try:
        return "" if value is None else str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False


def _summary(payload: dict[str, Any], fallback: str) -> str:
    summary = _safe_text(_field(payload, "summary")).strip()
    if summary:
        return summary
    message = _safe_text(_field(payload, "message")).strip()
    if message:
        return message
    return fallback


def _first_text(*values: Any, fallback: str) -> str:
    for value in values:
        text = _safe_text(value).strip()
        if text:
            return text
    return fallback


def _reason_codes(trust: dict[str, Any]) -> list[str]:
    return safe_text_list(_field(trust, "reason_codes"))


def _has_stale_source(trust: dict[str, Any], codes: list[str]) -> bool:
    return bool(safe_text_list(_field(trust, "stale_sources"))) or any(code.startswith("source_stale:") for code in codes)


__all__ = ["build_report_quality_repair_queue"]
