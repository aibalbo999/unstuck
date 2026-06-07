"""Observability routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter, Query

import api_observability_service


@dataclass(frozen=True)
class ObservabilityRouteDeps:
    get_provider_sla_summary: Callable[[int], list[dict]]
    get_provider_sla_alerts: Callable[[int], list[dict]]


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

    return router

