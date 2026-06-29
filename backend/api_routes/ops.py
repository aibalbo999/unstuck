"""Operations dashboard compatibility routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Query

import api_observability_service


@dataclass(frozen=True)
class OpsRouteDeps:
    get_provider_sla_summary: Callable[[int], list[dict]]
    get_provider_sla_alerts: Callable[[int], list[dict]]
    get_task_queue: Callable[[], Any]


def create_ops_router(deps: OpsRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/ops")

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
