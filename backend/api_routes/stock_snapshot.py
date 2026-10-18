"""Consumer stock snapshot routes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException

from data_fetch.types import FetchRequest
from data_fetch.service import fetch_stock_data_async
from stock_snapshot_service import build_stock_snapshot


@dataclass(frozen=True)
class StockSnapshotRouteDeps:
    fetch_payload: Callable[[FetchRequest], Awaitable[dict]]


async def _fetch_snapshot_payload(request: FetchRequest) -> dict:
    result = await fetch_stock_data_async(request)
    return result.data


def create_stock_snapshot_router(deps: StockSnapshotRouteDeps | None = None) -> APIRouter:
    deps = deps or StockSnapshotRouteDeps(fetch_payload=_fetch_snapshot_payload)
    router = APIRouter(prefix="/api/stocks")

    @router.get("/{ticker}/snapshot")
    async def stock_snapshot(ticker: str):
        normalized_ticker = str(ticker or "").strip().upper()
        if not normalized_ticker:
            raise HTTPException(status_code=400, detail="Ticker is required")
        data = await deps.fetch_payload(FetchRequest.from_ticker(normalized_ticker, skip_optional_http=False))
        if not isinstance(data, dict) or data.get("error"):
            raise HTTPException(status_code=502, detail=str((data or {}).get("error") or "Stock data unavailable"))
        return build_stock_snapshot(data)

    return router
