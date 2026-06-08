"""Local maintenance routes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, Query, Request


@dataclass(frozen=True)
class MaintenanceRouteDeps:
    require_mutation_authorized: Callable[[Request], None]
    build_storage_summary: Callable[[], dict]
    cleanup_report_index_orphans: Callable[..., dict]
    cleanup_provider_sla_events: Callable[..., dict]
    cleanup_analysis_history: Callable[..., dict]


def create_maintenance_router(deps: MaintenanceRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/maintenance")

    @router.get("/storage-summary")
    async def storage_summary(request: Request):
        deps.require_mutation_authorized(request)
        summary = await asyncio.to_thread(deps.build_storage_summary)
        return {"success": True, "summary": summary}

    @router.post("/cleanup-report-index")
    async def cleanup_report_index(request: Request, write: bool = Query(True)):
        deps.require_mutation_authorized(request)
        result = await asyncio.to_thread(deps.cleanup_report_index_orphans, write=write)
        return _maintenance_result(result)

    @router.post("/cleanup-provider-sla")
    async def cleanup_provider_sla(
        request: Request,
        retention_days: Optional[int] = Query(None, ge=1, le=3650),
    ):
        deps.require_mutation_authorized(request)
        result = await asyncio.to_thread(deps.cleanup_provider_sla_events, retention_days=retention_days)
        return _maintenance_result(result)

    @router.post("/cleanup-analysis-history")
    async def cleanup_job_history(
        request: Request,
        retention_days: Optional[int] = Query(None, ge=1, le=3650),
        keep_recent_jobs: int = Query(20, ge=0, le=500),
        write: bool = Query(True),
    ):
        deps.require_mutation_authorized(request)
        result = await asyncio.to_thread(
            deps.cleanup_analysis_history,
            retention_days=retention_days,
            keep_recent_jobs=keep_recent_jobs,
            write=write,
        )
        return _maintenance_result(result)

    return router


def _maintenance_result(result: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "result": result}
