"""Observability API service helpers."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from provider_sla import SLA_CRITICAL_SUCCESS_RATE, SLA_WARNING_SUCCESS_RATE
from api_quota_service import build_api_quota_payload as _build_api_quota_payload
from job_observability import build_active_jobs_snapshot, build_ops_dashboard_snapshot
from queue_observability import snapshot_task_queue


VALID_SLA_WINDOWS = {"all", "last_1h", "last_24h", "last_7d"}


def normalize_sla_window(window: str) -> str:
    value = str(window or "all").strip().lower()
    return value if value in VALID_SLA_WINDOWS else "all"


def _alert_fields_for_window(item: dict, window: str) -> dict:
    attempts = int(item.get("availability_attempts", item.get("attempts")) or 0)
    success_rate = float(item.get("success_rate") or 0.0)
    error_count = int(item.get("error_count") or 0)
    last_status = str(item.get("last_status") or "")
    label = "累積" if window == "all" else window

    if window != "all" and attempts == 0:
        return {"alert_level": "ok", "alert_message": "", "alert_basis": label}
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


async def build_api_quota_payload(summary_fetcher: Callable[[int], list[dict]]) -> dict:
    return await asyncio.to_thread(_build_api_quota_payload, summary_fetcher)


async def build_ops_dashboard_payload(
    summary_fetcher: Callable[[int], list[dict]],
    alerts_fetcher: Callable[[int], list[dict]],
    *,
    task_queue: Any,
    provider_limit: int = 100,
    completed_limit: int = 500,
    telemetry_limit: int = 5000,
    stuck_after_seconds: int = 15 * 60,
) -> dict:
    jobs, providers, api_quotas, queue = await asyncio.gather(
        asyncio.to_thread(
            build_ops_dashboard_snapshot,
            completed_limit=completed_limit,
            telemetry_limit=telemetry_limit,
            stuck_after_seconds=stuck_after_seconds,
        ),
        build_provider_sla_payload(summary_fetcher, alerts_fetcher, provider_limit, window="last_24h"),
        build_api_quota_payload(summary_fetcher),
        asyncio.to_thread(snapshot_task_queue, task_queue),
    )
    alerts = providers.get("alerts", [])
    status = _dashboard_status(jobs=jobs, queue=queue, provider_alerts=alerts)
    return {
        "status": status,
        "generated_at": time.time(),
        "jobs": jobs.get("jobs", {}),
        "job_latency": jobs.get("job_latency", {}),
        "stuck_jobs": jobs.get("stuck_jobs", {}),
        "node_telemetry": jobs.get("node_telemetry", {}),
        "queue": queue,
        "providers": {
            "selected_window": providers.get("selected_window"),
            "alert_count": len(alerts),
            "alerts": alerts,
        },
        "api_quotas": api_quotas,
    }


def _dashboard_status(*, jobs: dict, queue: dict, provider_alerts: list[dict]) -> str:
    if not queue.get("available"):
        return "critical"
    if any(alert.get("alert_level") == "critical" for alert in provider_alerts):
        return "critical"
    if int((jobs.get("stuck_jobs") or {}).get("count") or 0) > 0:
        return "warning"
    if provider_alerts:
        return "warning"
    return "ok"
