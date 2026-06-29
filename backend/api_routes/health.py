"""Runtime health and readiness routes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class HealthRouteDeps:
    build_health_payload: Callable[[], dict]
    build_readiness_payload: Callable[[], dict]


def create_health_router(deps: HealthRouteDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz():
        return deps.build_health_payload()

    @router.get("/readyz")
    async def readyz():
        payload = await asyncio.to_thread(deps.build_readiness_payload)
        status_code = 200 if payload.get("status") == "ready" else 503
        return JSONResponse(payload, status_code=status_code)

    return router
