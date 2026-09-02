"""Provider SLA dashboard alert and source-health projections."""

from __future__ import annotations

from typing import Any

from mapping_fields import mapping_field as _field, safe_mapping_dict, safe_text
from notification_delivery_audit_context import safe_float, safe_int
from provider_sla_payload_shape import finite_float, normalize_provider_sla_windows
from report_freshness_summary import safe_bool


def alerts_from_providers(providers: list[dict]) -> list[dict]:
    alerts = []
    for raw_item in providers:
        item = _payload_dict(raw_item)
        level = safe_text(_field(item, "alert_level")).strip()
        if level not in {"warning", "critical"}:
            continue
        alerts.append({
            "source": _optional_text(_field(item, "source")),
            "provider": _optional_text(_field(item, "provider")),
            "alert_level": level,
            "alert_message": _optional_text(_field(item, "alert_message")),
            "success_rate": _optional_finite_float(_field(item, "success_rate")),
            "last_status": _optional_text(_field(item, "last_status")),
            "alert_basis": _optional_text(_field(item, "alert_basis")),
            "selected_window": safe_text(_field(item, "selected_window")).strip() or "all",
            "windows": normalize_provider_sla_windows(_field(item, "windows")),
        })
    return alerts


def source_health_from_provider_rows(providers: Any) -> dict[str, bool]:
    """Summarize whether each source has usable evidence in the selected window."""
    health: dict[str, bool] = {}
    for item in _provider_rows_or_empty(providers):
        source = safe_text(_field(item, "source")).strip()
        if not source:
            continue
        status = safe_text(_field(item, "last_status")).strip()
        total_records = safe_int(_field(item, "total_records"))
        healthy = status in {"success", "skipped_fresh_cache"} and total_records > 0
        healthy = healthy or status == "degraded_enrichment"
        health[source] = health.get(source, False) or healthy
    return health


def dashboard_provider_alert_payload(
    alert: dict,
    *,
    core_sources: set[str],
    current_source_health: dict[str, bool] | None = None,
) -> dict:
    source = safe_text(_field(alert, "source")).strip()
    source_has_healthy_entry = False
    if current_source_health is not None:
        try:
            source_has_healthy_entry = safe_bool(current_source_health.get(source))
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            source_has_healthy_entry = False
    payload = {
        "source": source,
        "provider": safe_text(_field(alert, "provider")).strip(),
        "alert_level": safe_text(_field(alert, "alert_level")).strip(),
        "alert_message": safe_text(_field(alert, "alert_message")).strip(),
        "success_rate": finite_float(_field(alert, "success_rate")),
        "last_status": safe_text(_field(alert, "last_status")).strip(),
        "alert_basis": safe_text(_field(alert, "alert_basis")).strip(),
        "selected_window": safe_text(_field(alert, "selected_window")).strip() or "all",
        "windows": normalize_provider_sla_windows(_field(alert, "windows")),
        "impact": "core" if source in core_sources else "enrichment",
    }
    if source_has_healthy_entry:
        payload["current_source_has_healthy_entry"] = True
    return payload


def _provider_rows_or_empty(providers: Any) -> list[dict]:
    rows: list[dict] = []
    try:
        iterator = iter(providers)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return rows
    while True:
        try:
            raw_item = next(iterator)
        except StopIteration:
            return rows
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return rows
        item = _payload_dict(raw_item)
        if item:
            rows.append(item)


def _optional_text(value: Any) -> str | None:
    return None if value is None else safe_text(value).strip()


def _optional_finite_float(value: Any) -> float | None:
    return None if value is None else finite_float(value)


def _payload_dict(value: Any) -> dict[Any, Any]:
    return safe_mapping_dict(value) or {}
