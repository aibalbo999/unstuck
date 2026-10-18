"""Performance and track record API routes."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from decision_tracking_service import compute_tracking_performance_stats


@dataclass(frozen=True)
class PerformanceRouteDeps:
    get_output_dir: Callable[[], str]
    read_performance: Callable[[str], Awaitable[dict]] | None = None


def create_performance_router(deps: PerformanceRouteDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/api/performance/stats")
    async def get_performance_stats():
        """Get aggregate performance statistics for AI decision reports."""
        if deps.read_performance is not None:
            result = await deps.read_performance(deps.get_output_dir())
            if result.get("status") == "unavailable":
                return JSONResponse(result, status_code=503)
            return result
        return await asyncio.to_thread(compute_tracking_performance_stats, deps.get_output_dir())

    return router
