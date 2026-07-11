"""Provider SLA payload shaping helpers."""

from __future__ import annotations

from typing import Any

from notification_delivery_audit_context import safe_dict, safe_float, safe_int, safe_text


PROVIDER_SLA_INT_FIELDS = {
    "attempts",
    "availability_attempts",
    "success_count",
    "error_count",
    "unavailable_count",
    "skipped_fresh_cache_count",
    "not_configured_count",
    "degraded_enrichment_count",
    "total_records",
}
PROVIDER_SLA_FLOAT_FIELDS = {"success_rate", "avg_duration_ms"}
PROVIDER_SLA_WINDOW_KEYS = {"last_1h", "last_24h", "last_7d"}


def finite_float(value: Any) -> float:
    number = safe_float(value)
    return 0.0 if number != number or number in {float("inf"), float("-inf")} else number


def provider_sla_numeric_value(key: str, value: Any) -> int | float | Any:
    if key in PROVIDER_SLA_FLOAT_FIELDS:
        return finite_float(value)
    if key in PROVIDER_SLA_INT_FIELDS:
        return safe_int(value)
    return value


def normalize_provider_sla_windows(windows: Any) -> dict:
    normalized = {}
    for raw_window, raw_stats in safe_dict(windows).items():
        window = safe_text(raw_window).strip().lower()
        if window in PROVIDER_SLA_WINDOW_KEYS:
            normalized[window] = normalize_provider_sla_numeric_fields(safe_dict(raw_stats))
    return normalized


def normalize_provider_sla_numeric_fields(row: Any) -> dict:
    copied = safe_dict(row)
    for key in PROVIDER_SLA_INT_FIELDS | PROVIDER_SLA_FLOAT_FIELDS:
        if key in copied:
            copied[key] = provider_sla_numeric_value(key, copied[key])
    if "windows" in copied:
        copied["windows"] = normalize_provider_sla_windows(copied["windows"])
    return copied
