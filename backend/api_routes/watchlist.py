"""Watchlist routes for scheduled batch analysis."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

import watchlist_service


@dataclass(frozen=True)
class WatchlistRouteDeps:
    get_task_queue: Callable[[], Any]
    run_stock_analysis_job: Callable[[str, str, str], str]
    create_job: Callable[[str, str], str]
    find_active_job: Callable[[str, str], dict]
    require_mutation_authorized: Callable[[Request], None]


def create_watchlist_router(deps: WatchlistRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/watchlist")

    @router.get("")
    async def get_watchlist():
        return await asyncio.to_thread(watchlist_service.list_watchlist)

    @router.post("")
    async def upsert_watchlist_item(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        try:
            return await asyncio.to_thread(watchlist_service.upsert_watchlist_item, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/{ticker}")
    async def delete_watchlist_item(
        request: Request,
        ticker: str,
        pipeline: str = Query("all", max_length=24),
    ):
        deps.require_mutation_authorized(request)
        return await asyncio.to_thread(watchlist_service.delete_watchlist_item, ticker, pipeline)

    @router.get("/due")
    async def get_due_watchlist_items():
        return {"items": await asyncio.to_thread(watchlist_service.due_watchlist_items)}

    @router.post("/run")
    async def run_watchlist_items(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        requested = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(requested, list):
            requested = [
                item for item in watchlist_service.list_watchlist().get("items", [])
                if item.get("enabled")
            ]
        return await asyncio.to_thread(
            watchlist_service.enqueue_watchlist_items,
            requested,
            create_job=deps.create_job,
            find_active_job=deps.find_active_job,
            task_queue=deps.get_task_queue(),
            run_stock_analysis_job=deps.run_stock_analysis_job,
        )

    return router
