"""Canonical stock data service facade."""

from __future__ import annotations

import time
import re
from contextlib import suppress
from typing import Awaitable, Callable, Optional

from provider_sla import record_source_audit_entries
from report_freshness_summary import safe_bool
from provider_correlation import correlate_fetch, current_audit_correlation

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

    @correlate_fetch
    async def fetch_async(self, request: FetchRequest) -> FetchResult:
        started = time.time()
        normalized_request = FetchRequest.from_ticker(
            request.ticker.strip().upper(),
            skip_optional_http=request.options.skip_optional_http,
            force_refresh=request.options.force_refresh,
            include_provider_results=request.options.include_provider_results,
            record_provider_sla=request.options.record_provider_sla,
            radar_refresh=request.options.radar_refresh,
        )

        if self._fetcher is not None:
            data = await self._fetcher(normalized_request)
        else:
            data = await fetch_payload_async(normalized_request, registry=self.registry)

        duration_ms = max(0, int(round((time.time() - started) * 1000)))
        return self._build_result(normalized_request, data or {}, duration_ms)

    @correlate_fetch
    async def fetch_radar_async(self, request: FetchRequest, sources: tuple[str, ...]) -> FetchResult:
        if "full" in sources or self._fetcher is not None:
            return await self.fetch_async(request)
        from .radar import fetch_radar_payload
        started = time.time()
        data = await fetch_radar_payload(request, sources, self.registry)
        return self._build_result(request, data, max(0, int((time.time() - started) * 1000)))

    @correlate_fetch
    async def fetch_source_async(self, request: FetchRequest, source: str, *, context: dict | None = None) -> FetchResult:
        """Acquire one optional source, including its unsuccessful observations."""
        if source not in {"instrument_identity", "financial_statements", "annual_workforce", "earnings_call", "recent_catalysts", "issuer_news", "tdr_announcements", "official_announcements", "philjobnet_jobs", "dynamic_peer_metrics", "institutional_trading", "alternative_data"} or self._fetcher is not None:
            raise RuntimeError("指定來源刷新不支援此資料計畫")
        if source == 'instrument_identity':
            from .security_identity_provider import SecurityIdentityProvider
            provider = SecurityIdentityProvider()
            canonical_source = 'taiwan_open_data'
        elif source == 'financial_statements':
            from .annual_financial_source_provider import AnnualFinancialSourceProvider
            provider = AnnualFinancialSourceProvider()
            canonical_source = source
        elif source == 'recent_catalysts':
            from copy import deepcopy
            from recent_catalyst_source_refresh import validate_recent_refresh_context
            validate_recent_refresh_context((context or {}).get('data'), request.ticker)
            context = deepcopy(context or {})
            context['data']['_cache_hit'] = False
            context['free_sources_only'] = True
            candidates = [p for p in self.registry.for_request(request, source)
                          if p.name == 'Alternative Search']
            provider = candidates[0] if len(candidates) == 1 else None
            canonical_source = source
        elif source == 'dynamic_peer_metrics':
            from peer_source_refresh import validate_peer_refresh_context
            policy = validate_peer_refresh_context((context or {}).get('data'), request.ticker)
            if policy == 'ncc' and request.options.force_refresh:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail='NCC 同業來源僅接受保留正常快取的流程')
            candidates = [p for p in self.registry.for_request(request, source) if p.name == 'FinMind/yfinance']
            provider = candidates[0] if len(candidates) == 1 else None
            canonical_source = source
        elif source == 'institutional_trading':
            from institutional_source_refresh import validate_institutional_refresh_context, institutional_refresh_session
            validate_institutional_refresh_context((context or {}).get('data'), request.ticker)
            institutional_refresh_session(request.ticker)
            candidates = [p for p in self.registry.for_request(request, source) if p.name == 'FinMind']
            provider = candidates[0] if len(candidates) == 1 else None
            canonical_source = source
        elif source == 'alternative_data':
            from copy import deepcopy
            from alternative_source_refresh import validate_alternative_refresh_context, PROVIDER
            validate_alternative_refresh_context((context or {}).get('data'), request.ticker)
            context = deepcopy(context or {})
            candidates = [p for p in self.registry.for_request(request, source)
                          if p.name == PROVIDER and p.cost_tier == 'free']
            provider = candidates[0] if len(candidates) == 1 else None
            canonical_source = source
        elif source == 'philjobnet_jobs':
            if request.ticker != '9103.TW':
                raise RuntimeError('此雇主入口尚未驗證此股票')
            from .agent_context_providers import PhilJobNetJobObservationProvider
            provider = PhilJobNetJobObservationProvider()
            canonical_source = 'alternative_data'
        elif source in {"issuer_news", "tdr_announcements", "official_announcements"}:
            if source == 'official_announcements':
                from official_announcement_source_refresh import supports as supports_ordinary
                if supports_ordinary(request.ticker):
                    from official_announcement_source_refresh import validate_context as validate_json_context
                else:
                    from .market_sources.mops_json_company_history import validate_json_context
                try:
                    validate_json_context((context or {}).get('data'), request.ticker)
                except ValueError as exc:
                    raise RuntimeError('此新版公告入口或原股票身分尚未通過核對') from exc
            if source == "tdr_announcements" and request.ticker != "9103.TW":
                raise RuntimeError("此公告入口尚未驗證此股票")
            provider_name = "TWSE company announcement history" if source in {"tdr_announcements", "official_announcements"} else "Verified issuer news"
            candidates = [p for p in self.registry.for_request(request, "recent_catalysts")
                          if p.name == provider_name]
            provider = candidates[0] if len(candidates) == 1 else None
            canonical_source = "recent_catalysts"
        else:
            provider = self.registry.first_provider(request, source)
            canonical_source = source
        if provider is None:
            raise RuntimeError("指定來源未設定")
        started = time.time()
        material_context = False
        if source == 'earnings_call':
            from .market_sources.mops_presentation import supports as supports_material
            material_context = supports_material(request.ticker)
        result = await provider.fetch_async(request, context if material_context or source in {'financial_statements', 'recent_catalysts', 'official_announcements', 'dynamic_peer_metrics', 'alternative_data'} or source == 'issuer_news' and request.ticker in {'2201.TW', '5880.TW', '2206.TW'} or source == 'earnings_call' and (request.ticker in {'1476.TW', '3653.TW', '2912.TW', '3443.TW', '1503.TW', '2059.TW', '2367.TW', '8150.TW', '2344.TW', '6257.TW', '2480.TW', '2330.TW', '1229.TW', '1605.TW', '2002.TW', '2412.TW', '1514.TW', '2368.TW', '2049.TW', '1560.TW'} or request.ticker == '2317.TW' and isinstance(context,dict)and context.get('source_only_recovery')is True or re.fullmatch(r'[1-9]\d{3,5}\.TWO',request.ticker) is not None) else {"original_ticker": request.ticker})
        if source == 'recent_catalysts':
            from recent_catalyst_source_refresh import guard_recent_source_result
            result = guard_recent_source_result(result, context['data'])
        if source == 'official_announcements':
            from official_announcement_source_refresh import supports as supports_ordinary
            if supports_ordinary(request.ticker):
                from official_announcement_source_refresh import guard_result as guard_json_result
            else:
                from .market_sources.mops_json_company_history import guard_json_result
            result = guard_json_result(result, context['data'])
        if source == 'dynamic_peer_metrics':
            from peer_source_refresh import guard_peer_result
            result = guard_peer_result(result, context['data'], request.ticker)
        if source == 'alternative_data':
            from alternative_source_refresh import guard_alternative_result, record_related_alternative_attempts
            result = guard_alternative_result(result, context['data'])
            if request.options.record_provider_sla:
                record_related_alternative_attempts(result)
        # Build the canonical result before the caller rejects a failure. Radar
        # intentionally raises early and cannot retain this failure observation.
        source_audits = [result.audit]
        if source in {'financial_statements', 'annual_workforce'}:
            related = result.audit.get('related_entries') if isinstance(result.audit,dict) else None
            if isinstance(related,list):
                source_audits.extend(entry for entry in related if isinstance(entry,dict))
        data = {"ticker": request.ticker, canonical_source: result.value, "source_audit": source_audits}
        if source == 'alternative_data':
            from alternative_source_refresh import IDENTITY_FIELDS
            data.update({k: deepcopy(context['data'][k]) for k in IDENTITY_FIELDS if k in context['data']})
        return self._build_result(request, data, max(0, int((time.time() - started) * 1000)))

    def fetch(self, request: FetchRequest) -> FetchResult:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.fetch_async(request))
        raise RuntimeError("StockDataService.fetch() cannot run inside an active event loop; use fetch_async().")

    def _build_result(self, request: FetchRequest, data: dict, duration_ms: int) -> FetchResult:
        from source_applicability import apply_source_applicability
        from data_trust import finalize_data_trust
        apply_source_applicability(data)
        finalize_data_trust(data)
        audit_entries = data.get("source_audit", []) if isinstance(data.get("source_audit"), list) else []
        # Unstamped/manual provider entries are current fetch-result aggregates,
        # not proof that every retained source record was fetched by this job.
        audit_entries = [dict(entry) if any(entry.get(key) for key in ("job_id", "fetch_id", "operation_id"))
                         else {**current_audit_correlation(), **entry}
                         for entry in audit_entries if isinstance(entry, dict)]
        data["source_audit"] = audit_entries
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
            cache_hit=safe_bool(data.get("_cache_hit")),
            duration_ms=duration_ms,
            warnings=list(data.get("data_source_notes", []) or []),
        )


DEFAULT_STOCK_DATA_SERVICE = StockDataService()


async def fetch_stock_data_async(request: FetchRequest) -> FetchResult:
    return await DEFAULT_STOCK_DATA_SERVICE.fetch_async(request)
