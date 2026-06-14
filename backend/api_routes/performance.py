"""Performance and track record API routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter

from decision_tracking_service import compute_tracking_performance_stats


@dataclass(frozen=True)
class PerformanceRouteDeps:
    get_output_dir: Callable[[], str]


def create_performance_router(deps: PerformanceRouteDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/api/performance/stats")
    def get_performance_stats():
        """Get aggregate performance statistics for AI decision reports."""
        return compute_tracking_performance_stats(deps.get_output_dir())

    return router
