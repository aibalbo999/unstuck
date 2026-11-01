"""Decision tracking routes for operator-selected tickers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import decision_tracking_service
import maintenance_guard


MAINTENANCE_MESSAGE = "系統維護中或維護狀態尚未確認，暫停變更及刷新決策追蹤；既有資料仍可查詢。"


@dataclass(frozen=True)
class DecisionTrackingRouteDeps:
    get_output_dir: Callable[[], str]
    get_refresh_service: Callable[[], Any]
    require_mutation_authorized: Callable[[Request], None]
    read_tracking: Callable[[str], Awaitable[dict]] | None = None


def create_decision_tracking_router(deps: DecisionTrackingRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/decision-tracking")

    @router.get("")
    async def get_decision_tracking():
        try:
            if deps.read_tracking is not None:
                result = await deps.read_tracking(deps.get_output_dir())
                return JSONResponse(result, status_code=503) if result.get("status") == "unavailable" else result
            return await asyncio.to_thread(decision_tracking_service.list_decision_tracking, deps.get_output_dir())
        except maintenance_guard.MaintenanceError:
            return await asyncio.to_thread(decision_tracking_service.list_decision_tracking,
                deps.get_output_dir(), sync_metadata=False)

    @router.post("")
    async def upsert_decision_tracking_item(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        try:
            return await asyncio.to_thread(decision_tracking_service.upsert_tracking_item, payload, deps.get_output_dir())
        except maintenance_guard.MaintenanceError:
            raise HTTPException(status_code=503, detail=MAINTENANCE_MESSAGE) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/{ticker}")
    async def delete_decision_tracking_item(request: Request, ticker: str):
        deps.require_mutation_authorized(request)
        try:
            return await asyncio.to_thread(decision_tracking_service.delete_tracking_item, ticker, deps.get_output_dir())
        except maintenance_guard.MaintenanceError:
            raise HTTPException(status_code=503, detail=MAINTENANCE_MESSAGE) from None

    @router.post("/refresh")
    async def refresh_decision_tracking(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json() if request.headers.get("content-length") not in {"", "0", None} else {}
        tickers = payload.get("tickers") if isinstance(payload, dict) else None
        try:
            return await decision_tracking_service.refresh_tracking_items(
                output_dir=deps.get_output_dir(),
                refresh_service=deps.get_refresh_service(),
                tickers=tickers if isinstance(tickers, list) else None,
            )
        except maintenance_guard.MaintenanceError:
            raise HTTPException(status_code=503, detail=MAINTENANCE_MESSAGE) from None

    return router
