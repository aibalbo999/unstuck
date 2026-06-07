"""Canonical stock data service facade."""

from __future__ import annotations

import time
from contextlib import suppress
from typing import Awaitable, Callable, Optional

from provider_sla import record_source_audit_entries

from .provider_registry import ProviderRegistry
from .types import FetchRequest, FetchResult, ProviderResult
from .workflow import fetch_payload_async


FetchAsyncCallable = Callable[[FetchRequest], Awaitable[dict]]


class StockDataService:
    """Canonical entrypoint for stock data payload generation."""

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        fetcher: Optional[FetchAsyncCallable] = None,
    ):
        self.registry = registry or ProviderRegistry()
        self._fetcher = fetcher

    async def fetch_async(self, request: FetchRequest) -> FetchResult:
        started = time.time()
        normalized_request = FetchRequest.from_ticker(
            request.ticker.strip().upper(),
            skip_optional_http=request.options.skip_optional_http,
            force_refresh=request.options.force_refresh,
            include_provider_results=request.options.include_provider_results,
            record_provider_sla=request.options.record_provider_sla,
        )

        if self._fetcher is not None:
            data = await self._fetcher(normalized_request)
        else:
            data = await fetch_payload_async(normalized_request, registry=self.registry)

        duration_ms = max(0, int(round((time.time() - started) * 1000)))
        return self._build_result(normalized_request, data or {}, duration_ms)

    def fetch(self, request: FetchRequest) -> FetchResult:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.fetch_async(request))
        raise RuntimeError("StockDataService.fetch() cannot run inside an active event loop; use fetch_async().")

    def _build_result(self, request: FetchRequest, data: dict, duration_ms: int) -> FetchResult:
        audit_entries = data.get("source_audit", []) if isinstance(data.get("source_audit"), list) else []
        import sqlite3
        if request.options.record_provider_sla:
            with suppress(sqlite3.Error):
                record_source_audit_entries(audit_entries)
        provider_results = []
        if request.options.include_provider_results:
            provider_results = [
                ProviderResult(
                    source=str(entry.get("source") or "unknown"),
                    provider=str(entry.get("provider") or ""),
                    status=str(entry.get("status") or "unknown"),
                    audit=dict(entry),
                    duration_ms=int(entry.get("duration_ms") or 0),
                )
                for entry in audit_entries
                if isinstance(entry, dict)
            ]
        return FetchResult(
            request=request,
            data=data,
            source_audit=list(audit_entries),
            data_trust=data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {},
            provider_results=provider_results,
            cache_hit=bool(data.get("_cache_hit")),
            duration_ms=duration_ms,
            warnings=list(data.get("data_source_notes", []) or []),
        )


DEFAULT_STOCK_DATA_SERVICE = StockDataService()


async def fetch_stock_data_async(request: FetchRequest) -> FetchResult:
    return await DEFAULT_STOCK_DATA_SERVICE.fetch_async(request)
