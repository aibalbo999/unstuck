"""Report-level provider SLA impact ledger."""

from __future__ import annotations

from typing import Any

from data_trust_constants import AUDIT_STATUS_SKIPPED_FRESH_CACHE, AUDIT_STATUS_SUCCESS, CORE_DATA_SOURCES


SCHEMA_VERSION = "provider_impact.v1"
LEDGER_SCHEMA_VERSION = "provider_impact_ledger.v1"
CORE_SOURCES = set(CORE_DATA_SOURCES)
HEALTHY_STATUSES = {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}
SEVERITY_RANK = {"none": 0, "notice": 1, "warning": 2, "critical": 3}


def build_provider_impact(report: dict[str, Any]) -> dict[str, Any]:
    """Return provider impact for one report row."""
    trust = _dict(_field(report, "data_trust"))
    codes = _reason_codes(trust)
    impacts = [_impact_for_alert(alert, codes) for alert in _alerts(trust)]
    impacts = [impact for impact in impacts if impact is not None]
    summary = _summary(impacts, codes)
    return {
        "schema_version": SCHEMA_VERSION,
        "ticker": _report_ticker(report),
        "filename": _report_filename(report),
        "pipeline_id": _pipeline_id(report),
        "reason_codes": codes,
        "summary": summary,
        "impacts": impacts,
    }


def build_provider_impact_ledger(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Return provider impact rows for report collections."""
    report_rows = _safe_dict_list(reports)
    items = []
    for report in report_rows:
        impact = build_provider_impact(report)
        if impact["impacts"]:
            items.append(impact)
    items.sort(key=_ledger_sort_key)
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "summary": {
            "sampled_reports": len(report_rows),
            "reports_with_impacts": len(items),
            "blocked_reports": sum(1 for item in items if _field(_dict(item["summary"]), "blocks_auto_rerun")),
            "monitor_reports": sum(1 for item in items if _field(_dict(item["summary"]), "recommended_action") == "monitor_provider"),
        },
        "items": items,
    }


def _impact_for_alert(alert: dict[str, Any], reason_codes: list[str]) -> dict[str, Any] | None:
    if not isinstance(alert, dict):
        return None
    source = _safe_text(_field(alert, "source")).strip() or "unknown"
    provider = _safe_text(_field(alert, "provider")).strip() or "unknown"
    level = (_safe_text(_field(alert, "alert_level")).strip() or "warning").lower()
    current_healthy = _current_fetch_healthy(alert)
    source_scope = "core" if source in CORE_SOURCES else "optional"
    affects_core = source_scope == "core" and not current_healthy and "provider_sla_critical" in reason_codes
    severity = _severity(level, source_scope, current_healthy, reason_codes)
    if severity == "none":
        return None
    return {
        "source": source,
        "provider": provider,
        "alert_level": level,
        "source_scope": source_scope,
        "affects_core_data": affects_core,
        "current_fetch_healthy": current_healthy,
        "severity": severity,
        "recommended_action": "wait_provider_recovery" if affects_core else "monitor_provider",
        "message": _message(source, provider, severity, affects_core, current_healthy),
    }


def _summary(impacts: list[dict[str, Any]], reason_codes: list[str]) -> dict[str, Any]:
    max_severity = _max_severity([impact["severity"] for impact in impacts])
    blocks = any(_field(impact, "affects_core_data") for impact in impacts)
    action = "wait_provider_recovery" if blocks else ("monitor_provider" if impacts else "none")
    return {
        "max_severity": max_severity,
        "recommended_action": action,
        "blocks_auto_rerun": blocks,
        "reason_codes": reason_codes,
        "core_impacts": sum(1 for impact in impacts if _field(impact, "source_scope") == "core"),
        "optional_impacts": sum(1 for impact in impacts if _field(impact, "source_scope") == "optional"),
    }


def _severity(level: str, source_scope: str, current_healthy: bool, reason_codes: list[str]) -> str:
    if source_scope == "core" and level == "critical" and not current_healthy and "provider_sla_critical" in reason_codes:
        return "critical"
    if level == "critical":
        return "notice"
    if level == "warning":
        return "warning"
    return "none"


def _message(source: str, provider: str, severity: str, affects_core: bool, current_healthy: bool) -> str:
    if affects_core:
        return f"{source}/{provider} critical 且本次核心資料未健康，先等待來源恢復或刷新資料。"
    if current_healthy:
        return f"{source}/{provider} 有 SLA 警示，但本次抓取健康，列為監控提醒。"
    if severity == "notice":
        return f"{source}/{provider} 影響補充或非阻斷資料，列為監控提醒。"
    return f"{source}/{provider} 有來源穩定度警示。"


def _ledger_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    summary = _dict(_field(item, "summary"))
    severity_rank = SEVERITY_RANK.get(_safe_text(_field(summary, "max_severity")).strip(), 0)
    return (-severity_rank, _safe_text(_field(item, "ticker")).strip())


def _report_ticker(report: dict[str, Any]) -> str:
    return _safe_text(_field(report, "ticker")).strip()


def _report_filename(report: dict[str, Any]) -> str:
    filename = _safe_text(_field(report, "filename")).strip()
    if filename:
        return filename
    return _safe_text(_field(report, "report_filename")).strip()


def _pipeline_id(report: dict[str, Any]) -> str:
    return _safe_text(_field(report, "pipeline_id")).strip() or "v1"


def _current_fetch_healthy(alert: dict[str, Any]) -> bool:
    if _safe_bool(_field(alert, "current_source_has_healthy_entry")):
        return True
    status = _safe_text(_field(alert, "current_status")).strip()
    record_count = _safe_int(_field(alert, "current_record_count"))
    return status in HEALTHY_STATUSES and record_count > 0 and not _safe_bool(_field(alert, "current_stale"))


def _max_severity(values: list[str]) -> str:
    if not values:
        return "none"
    return max(values, key=lambda value: SEVERITY_RANK.get(value, 0))


def _alerts(trust: dict[str, Any]) -> list[dict[str, Any]]:
    return _safe_dict_list(_field(trust, "provider_sla_alerts"))


def _reason_codes(trust: dict[str, Any]) -> list[str]:
    return _safe_text_list(_field(trust, "reason_codes"))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    rows = []
    iterator = _sequence_iterator(value)
    if iterator is None:
        return rows
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            if rows or used_native:
                break
            iterator = _native_sequence_iterator(value)
            if iterator is None:
                break
            used_native = True
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False


def _safe_int(value: Any) -> int:
    try:
        return int(0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0


def _safe_text(value: Any) -> str:
    try:
        return "" if value is None else str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


def _safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    texts = []
    iterator = _sequence_iterator(value)
    if iterator is None:
        return texts
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            if texts or used_native:
                break
            iterator = _native_sequence_iterator(value)
            if iterator is None:
                break
            used_native = True
            continue
        text = _safe_text(item).strip()
        if text:
            texts.append(text)
    return texts


def _sequence_iterator(value: list[Any] | tuple[Any, ...]):
    try:
        return iter(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return _native_sequence_iterator(value)
    return None


def _native_sequence_iterator(value: list[Any] | tuple[Any, ...]):
    try:
        if isinstance(value, list):
            return list.__iter__(value)
        if isinstance(value, tuple):
            return tuple.__iter__(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    return None


def _field(mapping: dict[str, Any], key: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    return dict.get(mapping, key, default)


__all__ = ["SCHEMA_VERSION", "LEDGER_SCHEMA_VERSION", "build_provider_impact", "build_provider_impact_ledger"]
