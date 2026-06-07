"""Observability API service helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from provider_sla import SLA_CRITICAL_SUCCESS_RATE, SLA_WARNING_SUCCESS_RATE
from job_observability import build_active_jobs_snapshot


VALID_SLA_WINDOWS = {"all", "last_1h", "last_24h", "last_7d"}


def normalize_sla_window(window: str) -> str:
    value = str(window or "all").strip().lower()
    return value if value in VALID_SLA_WINDOWS else "all"


def _alert_fields_for_window(item: dict, window: str) -> dict:
    attempts = int(item.get("attempts") or 0)
    success_rate = float(item.get("success_rate") or 0.0)
    error_count = int(item.get("error_count") or 0)
    last_status = str(item.get("last_status") or "")
    label = "累積" if window == "all" else window

    if attempts >= 3 and (success_rate < SLA_CRITICAL_SUCCESS_RATE or error_count >= 3):
        return {
            "alert_level": "critical",
            "alert_message": f"{item.get('provider')} {label}資料取得率偏低（{success_rate:.0%}），最近狀態：{last_status or 'unknown'}",
            "alert_basis": label,
        }
    if last_status in {"error", "unavailable"} or (attempts >= 3 and success_rate < SLA_WARNING_SUCCESS_RATE):
        return {
            "alert_level": "warning",
            "alert_message": f"{item.get('provider')} 最近有來源異常或 {label}資料取得率低於 {SLA_WARNING_SUCCESS_RATE:.0%}",
            "alert_basis": label,
        }
    return {"alert_level": "ok", "alert_message": "", "alert_basis": label}


def apply_provider_sla_window(providers: list[dict], window: str) -> list[dict]:
    normalized_window = normalize_sla_window(window)
    if normalized_window == "all":
        return [dict(item, selected_window=normalized_window) for item in providers]

    windowed = []
    for item in providers:
        copied = dict(item)
        stats = dict(((item.get("windows") or {}).get(normalized_window)) or {})
        for key in (
            "attempts",
            "success_count",
            "error_count",
            "unavailable_count",
            "skipped_fresh_cache_count",
            "success_rate",
            "avg_duration_ms",
            "total_records",
        ):
            if key in stats:
                copied[key] = stats[key]
        copied["selected_window"] = normalized_window
        copied.update(_alert_fields_for_window(copied, normalized_window))
        windowed.append(copied)
    return windowed


def alerts_from_providers(providers: list[dict]) -> list[dict]:
    return [
        {
            "source": item.get("source"),
            "provider": item.get("provider"),
            "alert_level": item.get("alert_level"),
            "alert_message": item.get("alert_message"),
            "success_rate": item.get("success_rate"),
            "last_status": item.get("last_status"),
            "alert_basis": item.get("alert_basis"),
            "selected_window": item.get("selected_window", "all"),
            "windows": item.get("windows", {}),
        }
        for item in providers
        if item.get("alert_level") in {"warning", "critical"}
    ]


async def build_provider_sla_payload(
    summary_fetcher: Callable[[int], list[dict]],
    alerts_fetcher: Callable[[int], list[dict]],
    limit: int,
    window: str = "all",
) -> dict:
    normalized_window = normalize_sla_window(window)
    providers, cumulative_alerts = await asyncio.gather(
        asyncio.to_thread(summary_fetcher, limit),
        asyncio.to_thread(alerts_fetcher, limit),
    )
    if normalized_window == "all":
        return {"providers": providers, "alerts": cumulative_alerts, "selected_window": normalized_window}

    windowed_providers = apply_provider_sla_window(providers, normalized_window)
    return {
        "providers": windowed_providers,
        "alerts": alerts_from_providers(windowed_providers),
        "selected_window": normalized_window,
    }


async def build_active_jobs_payload(limit: int = 10, event_limit: int = 80) -> dict:
    return await asyncio.to_thread(build_active_jobs_snapshot, limit, event_limit)
