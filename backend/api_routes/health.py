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
    build_runtime_identity_payload: Callable[[], dict] | None = None


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

    @router.get("/api/runtime-identity")
    async def runtime_identity():
        if deps.build_runtime_identity_payload is None:
            return {"schema_version": "stock-agent.runtime-identity.v1", "commit": None, "dirty": None}
        return deps.build_runtime_identity_payload()

    return router
