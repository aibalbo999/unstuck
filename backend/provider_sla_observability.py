"""Provider SLA observability payload helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from mapping_fields import mapping_field as _field, safe_mapping_dict, safe_text
from notification_delivery_audit_context import safe_float, safe_int
from provider_sla import SLA_CRITICAL_SUCCESS_RATE, SLA_WARNING_SUCCESS_RATE
from provider_sla_dashboard_payload import alerts_from_providers, dashboard_provider_alert_payload, source_health_from_provider_rows
from provider_sla_payload_shape import normalize_provider_sla_numeric_fields, provider_sla_numeric_value


VALID_SLA_WINDOWS = {"all", "last_1h", "last_24h", "last_7d"}


def normalize_sla_window(window: str) -> str:
    value = safe_text(window).strip().lower() or "all"
    return value if value in VALID_SLA_WINDOWS else "all"


def provider_rows_or_empty(providers: Any) -> list[dict]:
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


def _fetch_provider_payload_rows_or_empty(fetcher: Callable[[int], Any], limit: int) -> Any:
    try:
        return fetcher(limit)
    except Exception:
        return []


def _alert_fields_for_window(item: dict, window: str) -> dict:
    attempts = safe_int(_field(item, "availability_attempts", _field(item, "attempts")))
    success_rate = safe_float(_field(item, "success_rate"))
    error_count = safe_int(_field(item, "error_count"))
    last_status = safe_text(_field(item, "last_status")).strip()
    provider = safe_text(_field(item, "provider")).strip() or "unknown"
    label = "累積" if window == "all" else window

    if window != "all" and attempts == 0:
        return {"alert_level": "ok", "alert_message": "", "alert_basis": label}
    if attempts >= 3 and (success_rate < SLA_CRITICAL_SUCCESS_RATE or error_count >= 3):
        return {
            "alert_level": "critical",
            "alert_message": f"{provider} {label}資料取得率偏低（{success_rate:.0%}），最近狀態：{last_status or 'unknown'}",
            "alert_basis": label,
        }
    if last_status in {"error", "unavailable"} or (attempts >= 3 and success_rate < SLA_WARNING_SUCCESS_RATE):
        return {
            "alert_level": "warning",
            "alert_message": f"{provider} 最近有來源異常或 {label}資料取得率低於 {SLA_WARNING_SUCCESS_RATE:.0%}",
            "alert_basis": label,
        }
    return {"alert_level": "ok", "alert_message": "", "alert_basis": label}


def apply_provider_sla_window(providers: list[dict], window: str) -> list[dict]:
    normalized_window = normalize_sla_window(window)
    if normalized_window == "all":
        return [dict(normalize_provider_sla_numeric_fields(item), selected_window=normalized_window) for item in providers]

    windowed = []
    for item in providers:
        copied = normalize_provider_sla_numeric_fields(item)
        stats = _payload_dict(_field(_payload_dict(_field(copied, "windows")), normalized_window))
        for key in (
            "attempts",
            "availability_attempts",
            "success_count",
            "error_count",
            "unavailable_count",
            "skipped_fresh_cache_count",
            "not_configured_count",
            "degraded_enrichment_count",
            "success_rate",
            "avg_duration_ms",
            "total_records",
        ):
            if key in stats:
                copied[key] = provider_sla_numeric_value(key, stats[key])
        copied["selected_window"] = normalized_window
        copied.update(_alert_fields_for_window(copied, normalized_window))
        windowed.append(copied)
    return windowed


async def build_provider_sla_payload(
    summary_fetcher: Callable[[int], list[dict]],
    alerts_fetcher: Callable[[int], list[dict]],
    limit: int,
    window: str = "all",
) -> dict:
    normalized_window = normalize_sla_window(window)
    providers, cumulative_alerts = await asyncio.gather(
        asyncio.to_thread(_fetch_provider_payload_rows_or_empty, summary_fetcher, limit),
        asyncio.to_thread(_fetch_provider_payload_rows_or_empty, alerts_fetcher, limit),
    )
    windowed_providers = [normalize_provider_sla_numeric_fields(item) for item in providers]
    if normalized_window == "all":
        return {"providers": windowed_providers, "alerts": alerts_from_providers(cumulative_alerts), "selected_window": normalized_window}

    windowed_providers = apply_provider_sla_window(windowed_providers, normalized_window)
    return {
        "providers": windowed_providers,
        "alerts": alerts_from_providers(windowed_providers),
        "selected_window": normalized_window,
    }

def _payload_dict(value: Any) -> dict[Any, Any]:
    return safe_mapping_dict(value) or {}
