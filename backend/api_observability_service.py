"""Observability API service helpers."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from api_observability_prometheus import _labels, _metric_bool, _metric_int, _metric_number
from api_quota_service import build_api_quota_payload as _build_api_quota_payload
from data_trust_constants import CORE_DATA_SOURCES
from free_mode_contract import build_free_mode_contract
from job_observability import build_active_jobs_snapshot, build_ops_dashboard_snapshot
from mapping_fields import safe_mapping_dict, safe_mapping_items, safe_text, safe_text_list
from notification_delivery_audit import get_delivery_audit_summary
from notification_delivery_audit_context import safe_dict, safe_int
from notification_delivery_observability import (
    notification_delivery_attention_required,
    notification_delivery_dashboard_summary,
    notification_delivery_prometheus_lines,
)
from provider_sla_observability import (
    alerts_from_providers,
    apply_provider_sla_window,
    build_provider_sla_payload,
    dashboard_provider_alert_payload,
    normalize_sla_window,
    provider_rows_or_empty,
)
from queue_dashboard_payload import normalize_ops_queue_payload
from queue_observability import snapshot_task_queue


CORE_PROVIDER_ALERT_SOURCES = set(CORE_DATA_SOURCES)

async def build_active_jobs_payload(limit: int = 10, event_limit: int = 80) -> dict:
    return await asyncio.to_thread(build_active_jobs_snapshot, limit, event_limit)


async def build_api_quota_payload(summary_fetcher: Callable[[int], list[dict]]) -> dict:
    try:
        return await asyncio.to_thread(_build_api_quota_payload, summary_fetcher)
    except Exception:
        return {"services": []}


async def build_prometheus_metrics(
    summary_fetcher: Callable[[int], list[dict]],
    *,
    task_queue: Any,
    provider_limit: int = 1000,
) -> str:
    providers, queue, notification_delivery = await asyncio.gather(
        asyncio.to_thread(_provider_summary_or_empty, summary_fetcher, provider_limit),
        asyncio.to_thread(_queue_snapshot_or_empty, task_queue),
        asyncio.to_thread(_notification_delivery_summary_or_empty),
    )
    providers = provider_rows_or_empty(providers)
    queue = normalize_ops_queue_payload(queue)
    lines = [
        "# HELP stock_agent_provider_sla_success_rate Provider success rate by source.",
        "# TYPE stock_agent_provider_sla_success_rate gauge",
    ]
    for item in providers:
        labels = _labels(source=item.get("source"), provider=item.get("provider"))
        lines.append(f"stock_agent_provider_sla_success_rate{labels} {_metric_number(item.get('success_rate')):g}")
    lines.extend([
        "# HELP stock_agent_provider_sla_attempts_total Provider attempts by source.",
        "# TYPE stock_agent_provider_sla_attempts_total counter",
    ])
    for item in providers:
        labels = _labels(source=item.get("source"), provider=item.get("provider"))
        lines.append(f"stock_agent_provider_sla_attempts_total{labels} {_metric_int(item.get('attempts'))}")
    lines.extend([
        "# HELP stock_agent_provider_sla_errors_total Provider error count by source.",
        "# TYPE stock_agent_provider_sla_errors_total counter",
    ])
    for item in providers:
        labels = _labels(source=item.get("source"), provider=item.get("provider"))
        lines.append(f"stock_agent_provider_sla_errors_total{labels} {_metric_int(item.get('error_count'))}")
    lines.extend([
        "# HELP stock_agent_provider_sla_alert Provider alert state; 1 means active warning or critical.",
        "# TYPE stock_agent_provider_sla_alert gauge",
    ])
    for item in providers:
        level = safe_text(item.get("alert_level")).strip() or "ok"
        labels = _labels(source=item.get("source"), provider=item.get("provider"), level=level)
        lines.append(f"stock_agent_provider_sla_alert{labels} {1 if level in {'warning', 'critical'} else 0}")

    backend = safe_text(queue.get("backend")).strip() or "unknown"
    queue_name = safe_text(queue.get("queue_name")).strip() or backend
    lines.extend([
        "# HELP stock_agent_queue_available Queue backend availability.",
        "# TYPE stock_agent_queue_available gauge",
        f"stock_agent_queue_available{_labels(backend=backend)} {1 if _metric_bool(queue.get('available')) else 0}",
        "# HELP stock_agent_queue_depth Number of queued jobs.",
        "# TYPE stock_agent_queue_depth gauge",
        f"stock_agent_queue_depth{_labels(queue=queue_name)} {_metric_int(queue.get('depth'))}",
    ])
    for name, details in safe_mapping_items(_payload_dict(queue.get("queues"))):
        lines.append(f"stock_agent_queue_depth{_labels(queue=name)} {_metric_int(_payload_dict(details).get('depth'))}")

    lines.extend(notification_delivery_prometheus_lines(notification_delivery, _labels))
    lines.append("")
    return "\n".join(lines)


def _provider_summary_or_empty(summary_fetcher: Callable[[int], list[dict]], provider_limit: int) -> list[dict]:
    try: return summary_fetcher(provider_limit)
    except Exception: return []


def _queue_snapshot_or_empty(task_queue: Any) -> dict:
    try:
        return snapshot_task_queue(task_queue)
    except Exception:
        return {"backend": "unknown", "available": False, "queue_name": "unknown", "depth": 0, "queues": {}}


def _notification_delivery_summary_or_empty() -> dict:
    try: return get_delivery_audit_summary()
    except Exception: return {}


def _ops_dashboard_snapshot_or_empty(**kwargs: Any) -> dict:
    try: return build_ops_dashboard_snapshot(**kwargs)
    except Exception: return {"observability_unavailable": True}


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
    jobs, providers, api_quotas, queue, notification_delivery = await asyncio.gather(
        asyncio.to_thread(
            _ops_dashboard_snapshot_or_empty,
            completed_limit=completed_limit,
            telemetry_limit=telemetry_limit,
            stuck_after_seconds=stuck_after_seconds,
        ),
        build_provider_sla_payload(summary_fetcher, alerts_fetcher, provider_limit, window="last_24h"),
        build_api_quota_payload(summary_fetcher),
        asyncio.to_thread(_queue_snapshot_or_empty, task_queue),
        asyncio.to_thread(_notification_delivery_summary_or_empty),
    )
    jobs = _payload_dict(jobs) or {"observability_unavailable": True}
    queue = normalize_ops_queue_payload(queue)
    providers = _payload_dict(providers) or {"selected_window": "last_24h", "alerts": []}
    api_quotas = _payload_dict(api_quotas) or {"services": []}
    api_quotas["services"] = provider_rows_or_empty(api_quotas.get("services"))
    alerts = [_with_provider_alert_impact(alert) for alert in provider_rows_or_empty(providers.get("alerts"))]
    notification_delivery_summary = notification_delivery_dashboard_summary(notification_delivery)
    status = _dashboard_status(
        jobs=jobs,
        queue=queue,
        provider_alerts=alerts,
        notification_delivery=notification_delivery_summary,
    )
    provider_counts = _provider_alert_counts(alerts)
    return {
        "status": status,
        "generated_at": time.time(),
        "free_mode": _free_mode_dashboard_summary(),
        "jobs": _payload_dict(jobs.get("jobs")),
        "job_latency": _payload_dict(jobs.get("job_latency")),
        "stuck_jobs": _stuck_jobs_payload(jobs.get("stuck_jobs")),
        "node_telemetry": _payload_dict(jobs.get("node_telemetry")),
        "model_route_budget": _payload_dict(jobs.get("model_route_budget")),
        "queue": queue,
        "providers": {
            "selected_window": safe_text(providers.get("selected_window")).strip() or "last_24h",
            **provider_counts,
            "alerts": alerts,
        },
        "api_quotas": api_quotas,
        "notification_delivery": notification_delivery_summary,
    }


def _free_mode_dashboard_summary() -> dict:
    contract = _payload_dict(build_free_mode_contract()); providers = provider_rows_or_empty(contract.get("providers"))
    by_cost_tier: dict[str, int] = {}
    for provider in providers:
        tier = safe_text(provider.get("cost_tier")).strip() or "unknown"
        by_cost_tier[tier] = by_cost_tier.get(tier, 0) + 1
    return {
        "enabled": _metric_bool(contract.get("enabled")),
        "can_run_without_paid_keys": _metric_bool(contract.get("can_run_without_paid_keys")),
        "provider_count": len(providers),
        "providers_by_cost_tier": by_cost_tier,
        "violations": safe_text_list(contract.get("violations")),
    }


def _dashboard_status(
    *,
    jobs: dict,
    queue: dict,
    provider_alerts: list[dict],
    notification_delivery: dict | None = None,
) -> str:
    if not queue.get("available"):
        return "critical"
    if any(
        alert.get("alert_level") == "critical" and alert.get("impact") == "core"
        for alert in provider_alerts
    ):
        return "critical"
    if _metric_bool(jobs.get("observability_unavailable")):
        return "warning"
    if _stuck_job_count(jobs.get("stuck_jobs")) > 0:
        return "warning"
    if provider_alerts:
        return "warning"
    if notification_delivery_attention_required(notification_delivery or {}):
        return "warning"
    return "ok"


def _with_provider_alert_impact(alert: dict) -> dict:
    return dashboard_provider_alert_payload(alert, core_sources=CORE_PROVIDER_ALERT_SOURCES)

def _provider_alert_counts(alerts: list[dict]) -> dict:
    critical = [alert for alert in alerts if alert.get("alert_level") == "critical"]
    warning = [alert for alert in alerts if alert.get("alert_level") == "warning"]
    core = [alert for alert in alerts if alert.get("impact") == "core"]
    enrichment = [alert for alert in alerts if alert.get("impact") != "core"]
    core_critical = [alert for alert in core if alert.get("alert_level") == "critical"]
    enrichment_critical = [alert for alert in enrichment if alert.get("alert_level") == "critical"]
    return {
        "alert_count": len(alerts),
        "critical_count": len(critical),
        "warning_count": len(warning),
        "core_alert_count": len(core),
        "core_critical_count": len(core_critical),
        "enrichment_alert_count": len(enrichment),
        "enrichment_critical_count": len(enrichment_critical),
    }


def _stuck_jobs_payload(value: Any) -> dict:
    payload = _payload_dict(value)
    if "count" in payload:
        payload["count"] = _strict_count(payload.get("count"))
    return payload


def _stuck_job_count(value: Any) -> int:
    return _strict_count(_payload_dict(value).get("count"))


def _strict_count(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)


def _payload_dict(value: Any) -> dict[Any, Any]:
    return safe_mapping_dict(value) or {}
