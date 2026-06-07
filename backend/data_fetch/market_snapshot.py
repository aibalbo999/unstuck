"""Core market/financial snapshot fetch boundary."""

from __future__ import annotations

import asyncio

from .yfinance_core_fetch import fetch_stock_data


async def fetch_market_snapshot_async(ticker: str) -> dict:
    """Fetch the blocking core payload without optional HTTP enrichment."""
    return await asyncio.to_thread(fetch_stock_data, ticker, True)


def fetch_market_snapshot(ticker: str, skip_optional_http: bool = True) -> dict:
    return fetch_stock_data(ticker, skip_optional_http)
