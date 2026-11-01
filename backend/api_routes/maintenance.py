"""Local maintenance routes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request

import maintenance_guard


def _run_action(action, *, write, **kwargs):
    if not write:
        return action(write=write, **kwargs)
    # This context lives in the actual action thread, not the request Task.
    with maintenance_guard.admission():
        return action(write=write, **kwargs)


async def _maintenance_action(action, **kwargs):
    try:
        return await asyncio.to_thread(_run_action, action, **kwargs)
    except maintenance_guard.MaintenanceError:
        raise HTTPException(status_code=503,
            detail="系統維護中或維護狀態尚未確認，暫停執行清理；仍可預覽及查詢狀態。") from None


@dataclass(frozen=True)
class MaintenanceRouteDeps:
    require_mutation_authorized: Callable[[Request], None]
    build_storage_summary: Callable[[], dict]
    cleanup_failed_queue: Callable[..., dict]
    cleanup_report_index_orphans: Callable[..., dict]
    cleanup_provider_sla_events: Callable[..., dict]
    cleanup_analysis_history: Callable[..., dict]
    run_sqlite_maintenance: Callable[..., dict]


def create_maintenance_router(deps: MaintenanceRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/maintenance")

    @router.get("/storage-summary")
    async def storage_summary(request: Request):
        deps.require_mutation_authorized(request)
        summary = await asyncio.to_thread(deps.build_storage_summary)
        return {"success": True, "summary": summary}

    @router.post("/cleanup-failed-queue")
    async def cleanup_failed_queue(
        request: Request,
        stale_after_seconds: int = Query(7 * 24 * 60 * 60, ge=60, le=3650 * 24 * 60 * 60),
        write: bool = Query(False),
    ):
        deps.require_mutation_authorized(request)
        result = await _maintenance_action(
            deps.cleanup_failed_queue,
            stale_after_seconds=stale_after_seconds,
            write=write,
        )
        return _maintenance_result(result)

    @router.post("/cleanup-report-index")
    async def cleanup_report_index(request: Request, write: bool = Query(False)):
        deps.require_mutation_authorized(request)
        result = await _maintenance_action(deps.cleanup_report_index_orphans, write=write)
        return _maintenance_result(result)

    @router.post("/cleanup-provider-sla")
    async def cleanup_provider_sla(
        request: Request,
        retention_days: Optional[int] = Query(None, ge=1, le=3650),
        write: bool = Query(False),
    ):
        deps.require_mutation_authorized(request)
        result = await _maintenance_action(deps.cleanup_provider_sla_events, retention_days=retention_days, write=write)
        return _maintenance_result(result)

    @router.post("/cleanup-analysis-history")
    async def cleanup_job_history(
        request: Request,
        retention_days: Optional[int] = Query(None, ge=1, le=3650),
        keep_recent_jobs: int = Query(20, ge=0, le=500),
        write: bool = Query(False),
    ):
        deps.require_mutation_authorized(request)
        result = await _maintenance_action(
            deps.cleanup_analysis_history,
            retention_days=retention_days,
            keep_recent_jobs=keep_recent_jobs,
            write=write,
        )
        return _maintenance_result(result)

    @router.post("/sqlite-maintenance")
    async def sqlite_maintenance(request: Request, write: bool = Query(False)):
        deps.require_mutation_authorized(request)
        result = await _maintenance_action(deps.run_sqlite_maintenance, write=write)
        return _maintenance_result(result)

    return router


def _maintenance_result(result: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "result": result}
