"""Observability routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Query

import api_observability_service


@dataclass(frozen=True)
class ObservabilityRouteDeps:
    get_provider_sla_summary: Callable[[int], list[dict]]
    get_provider_sla_alerts: Callable[[int], list[dict]]
    get_task_queue: Callable[[], Any]


def create_observability_router(deps: ObservabilityRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/observability")

    @router.get("/provider-sla")
    async def provider_sla_summary(
        limit: int = Query(100, ge=1, le=1000),
        window: str = Query("all", max_length=24),
    ):
        return await api_observability_service.build_provider_sla_payload(
            deps.get_provider_sla_summary,
            deps.get_provider_sla_alerts,
            limit,
            window=window,
        )

    @router.get("/active-jobs")
    async def active_jobs(
        limit: int = Query(10, ge=1, le=50),
        event_limit: int = Query(80, ge=1, le=300),
    ):
        return await api_observability_service.build_active_jobs_payload(limit, event_limit)

    @router.get("/api-quotas")
    async def api_quotas():
        return await api_observability_service.build_api_quota_payload(
            deps.get_provider_sla_summary
        )

    @router.get("/model-routes")
    async def model_routes(
        telemetry_limit: int = Query(5000, ge=1, le=50000),
    ):
        return await api_observability_service.build_model_route_budget_payload(
            telemetry_limit=telemetry_limit,
        )

    @router.get("/dashboard")
    async def dashboard(
        provider_limit: int = Query(100, ge=1, le=1000),
        completed_limit: int = Query(500, ge=1, le=5000),
        telemetry_limit: int = Query(5000, ge=1, le=50000),
        stuck_after_seconds: int = Query(15 * 60, ge=60, le=24 * 60 * 60),
    ):
        return await api_observability_service.build_ops_dashboard_payload(
            deps.get_provider_sla_summary,
            deps.get_provider_sla_alerts,
            task_queue=deps.get_task_queue(),
            provider_limit=provider_limit,
            completed_limit=completed_limit,
            telemetry_limit=telemetry_limit,
            stuck_after_seconds=stuck_after_seconds,
        )

    return router
