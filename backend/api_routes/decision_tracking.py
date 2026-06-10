"""Decision tracking routes for operator-selected tickers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request

import decision_tracking_service


@dataclass(frozen=True)
class DecisionTrackingRouteDeps:
    get_output_dir: Callable[[], str]
    get_refresh_service: Callable[[], Any]
    require_mutation_authorized: Callable[[Request], None]


def create_decision_tracking_router(deps: DecisionTrackingRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/decision-tracking")

    @router.get("")
    async def get_decision_tracking():
        return await asyncio.to_thread(decision_tracking_service.list_decision_tracking, deps.get_output_dir())

    @router.post("")
    async def upsert_decision_tracking_item(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        try:
            return await asyncio.to_thread(decision_tracking_service.upsert_tracking_item, payload, deps.get_output_dir())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/{ticker}")
    async def delete_decision_tracking_item(request: Request, ticker: str):
        deps.require_mutation_authorized(request)
        return await asyncio.to_thread(decision_tracking_service.delete_tracking_item, ticker, deps.get_output_dir())

    @router.post("/refresh")
    async def refresh_decision_tracking(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json() if request.headers.get("content-length") not in {"", "0", None} else {}
        tickers = payload.get("tickers") if isinstance(payload, dict) else None
        return await decision_tracking_service.refresh_tracking_items(
            output_dir=deps.get_output_dir(),
            refresh_service=deps.get_refresh_service(),
            tickers=tickers if isinstance(tickers, list) else None,
        )

    return router
