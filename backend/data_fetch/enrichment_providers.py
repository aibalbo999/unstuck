"""HTTP/news/peer enrichment providers."""

from __future__ import annotations

import math
import re
import time

from source_audit import audited_fetch, audited_fetch_async
from search_provider_runtime import SourceResponseError
from report_freshness_summary import safe_bool

from .earnings_call_fetcher import FREE_EARNINGS_CALL_PROVIDER_NAME, apply_earnings_call_audit, fetch_free_earnings_call_context
from .enrichment_search_providers import AlternativePeerDiscoveryProvider, AlternativeSearchProvider
from .market_sources.common import first_number
from .provider_base import DataProvider, not_configured_provider_result, provider_result_from_audited
from .types import FetchRequest, ProviderResult


class FreeNewsWaterfallProvider(DataProvider):
    name = "Free news waterfall"
    source = "recent_catalysts"
    cost_tier, capabilities = "free", {"news", "recent_catalysts"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS
        from external_data_client import ExternalDataClient

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = str((context or {}).get("original_ticker") or data.get("ticker") or request.ticker).strip().upper()
        from company_news_queries import company_news_query
        from config import CATALYST_LOOKBACK_DAYS, SEARCH_CATALYST_MAX_RESULTS
        from news_freshness_policy import apply_news_freshness, apply_news_only_freshness, news_cutoff
        from source_content_selection import select_company_records
        from external_search_quality import result_source_key, search_quality_satisfied
        from external_search_types import SearchResult
        company_data = {**data, "ticker": ticker}
        query = company_news_query(company_data, lookback_days=CATALYST_LOOKBACK_DAYS)
        cutoff = news_cutoff()
        def select_candidates(candidates):
            # Search delivery does not turn direct forum/overview URLs into
            # editorial news. Both free engines use the aggregate role gate.
            candidates = [dict(r, source_type='free_news_search') for r in candidates]
            return select_company_records(candidates, company_data, cutoff=cutoff,
                                          lookback_days=CATALYST_LOOKBACK_DAYS)

        def sufficient(candidates):
            eligible, _ = select_candidates(candidates)
            selected = apply_news_only_freshness(dict(company_data), records=eligible, cutoff=cutoff,
                lookback_days=CATALYST_LOOKBACK_DAYS, limit=SEARCH_CATALYST_MAX_RESULTS)
            results = [SearchResult(r['title'], r['summary'], r['link'], r['source'], r['date'])
                       for r in selected['recent_catalysts']]
            return search_quality_satisfied(results, max_results=SEARCH_CATALYST_MAX_RESULTS,
                query=query, lookback_days=CATALYST_LOOKBACK_DAYS, require_recent=True, cutoff=cutoff)
        client = ExternalDataClient()
        # Search ranking may put old/unrelated hits first. Apply the unchanged
        # company/date gate to the bounded pool before retaining the configured
        # evidence capacity used by the downstream search gate.
        records = client.get_news(query, ticker=ticker, limit=20, sufficient=sufficient)
        records, selection = select_candidates(records)
        selected = apply_news_freshness(dict(company_data), records=records, cutoff=cutoff,
                                        lookback_days=CATALYST_LOOKBACK_DAYS, limit=SEARCH_CATALYST_MAX_RESULTS)
        records = selected["recent_catalysts"]
        # Capacity exclusions are eligible evidence, not company/date failures.
        selection["news_selection"] = selected["news_selection"]
        selection["additional_recent_catalysts"] = selected["additional_recent_catalysts"]
        final_results = [SearchResult(r.get('title', ''), r.get('summary') or '', r.get('link', ''),
                                      str(r.get('publisher') or r.get('source') or ''), str(r.get('date') or ''))
                         for r in records]
        result_quality_satisfied = search_quality_satisfied(
            final_results, max_results=SEARCH_CATALYST_MAX_RESULTS, query=query,
            lookback_days=CATALYST_LOOKBACK_DAYS, require_recent=True, cutoff=cutoff)
        result_publisher_count = len({result_source_key(result) for result in final_results if result_source_key(result)})
        status = AUDIT_STATUS_SUCCESS if result_quality_satisfied else AUDIT_STATUS_DEGRADED_ENRICHMENT
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=status,
            value=records,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": status,
                "record_count": len(records),
                "result_quality_satisfied": result_quality_satisfied,
                "result_publisher_count": result_publisher_count,
                "qualified_result_status": "sufficient_qualified_results" if result_quality_satisfied else "insufficient_search_quality",
                "cache_hit": safe_bool(data.get("_cache_hit")),
                "stale": False,
                "message": "免費新聞 waterfall 已回傳近期催化劑。" if records else "未取得公司相符且在時間窗內的新聞；不代表沒有催化劑。",
                "related_entries": list(client.last_news_audit),
                **selection,
            },
        )


class TwseCompanyHistoryProvider(DataProvider):
    """Recent exchange announcements, with original issuer text verified."""

    name = "TWSE company announcement history"
    source = "recent_catalysts"
    markets = {"tw"}
    cost_tier, capabilities = "free", {"official_announcements", "recent_catalysts"}
    freshness_seconds = 1800
    primary_source_provider = False
    cache_prefix = "twse-company-announcements:v3"

    def supports(self, request: FetchRequest) -> bool:
        return bool(re.fullmatch(r"[1-9]\d{3,5}(?:\.TW)?", str(request.ticker or "").upper()))

    def _ticker_allowed(self, ticker: str) -> bool:
        return bool(re.fullmatch(r"[1-9]\d{3,5}\.TW", ticker))

    def _fetch_records(self, ticker: str):
        from .market_sources.twse_company_history import fetch_recent_company_announcements
        return fetch_recent_company_announcements(ticker)

    @staticmethod
    def _progress_seconds(diagnostic):
        expiry = diagnostic.get('progress_fresh_until_epoch')
        try:
            return max(0., expiry - time.time()) if type(expiry) in (int, float) and math.isfinite(expiry) else 0.
        except OverflowError:
            return 0.

    def _result_ttl(self, item):
        records, diagnostic = item
        ttl = 1800 if records else 300
        if records and isinstance(diagnostic, dict) and 'progress_fresh_until_epoch' in diagnostic:
            ttl = min(ttl, self._progress_seconds(diagnostic))
            if diagnostic.get('progress_resume_possible') is True:
                ttl = min(ttl, 60)
        return ttl

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from shared_provider_cache import shared_fetch
        from .market_sources.mops_json_company_history import TICKERS, validate_json_context

        started = time.time()
        data = (context or {}).get("data") if isinstance((context or {}).get("data"), dict) else {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        if not self._ticker_allowed(ticker):
            return ProviderResult(self.source, self.name, "not_applicable", value=[],
                                  audit={"source": self.source, "provider": self.name,
                                         "status": "not_applicable", "record_count": 0})
        if ticker in TICKERS:
            try:
                validate_json_context({**data, 'ticker': ticker}, ticker)
            except ValueError:
                return ProviderResult(self.source,self.name,'not_applicable',value=[],audit={
                    'source':self.source,'provider':self.name,'status':'not_applicable','record_count':0,
                    'http_request_sent':False,'http_request_count':0,'event_kind':'local_block'})
        prefix = ('tdr-mops-announcements:v1' if ticker == '9103.TW' else
                  'json-mops-announcements:v1' if ticker in TICKERS else self.cache_prefix)
        value, meta = shared_fetch(
            f"{prefix}:{ticker}",
            lambda: self._fetch_records(ticker),
            freshness_seconds=self.freshness_seconds, retention_seconds=self.freshness_seconds,
            result_ttl=self._result_ttl,
            error_retry_seconds=120, lock_wait_seconds=1,
        )
        records, diagnostic = value if isinstance(value, (list, tuple)) and len(value) == 2 else ([], {})
        records = records if isinstance(records, list) else []
        diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
        if (records and 'progress_fresh_until_epoch' in diagnostic
                and self._progress_seconds(diagnostic) <= 0):
            # A retained aggregate cannot make its original bodies fresh again,
            # including a failed refresh or shared_fetch's minimum one-second TTL.
            records = []
            diagnostic = {**diagnostic, 'status': 'degraded_enrichment',
                          'coverage_status': 'partial', 'progress_resume_possible': False,
                          'error_kind': 'original_progress_expired'}
            meta = {**meta, 'stale': True}
        status = ("error" if meta.get("error_kind") else diagnostic.get("status") or "error")
        if meta.get("cache_hit") and not meta.get("stale") and status == "success":
            status = "skipped_fresh_cache"
        elif meta.get("stale") and records:
            status = "degraded_enrichment"
        audit = {**diagnostic, **meta, "source": self.source, "provider": self.name,
                 "status": status, "record_count": len(records),
                 "event_kind": "cache_hit" if meta.get("cache_hit") else "aggregate",
                 "http_request_sent": diagnostic.get("http_request_sent", True) and not meta.get("cache_hit") and not meta.get("cooldown")
                                      and meta.get("error_kind") != "single_flight_busy",
                 "duration_ms": max(0, int((time.time() - started) * 1000))}
        if (status in {'success', 'skipped_fresh_cache'} and diagnostic.get('body_cache_hit') is True
                and diagnostic.get('detail_new_body_count') == 0):
            # A new index validates cached bodies but does not reacquire them.
            # Retain actual index HTTP attempts while excluding a new-body success.
            status = 'skipped_fresh_cache'
            audit.update(status=status, cache_hit=True, event_kind='cache_hit',
                         fetched_at_epoch=diagnostic.get('body_fetched_at_epoch'))
        if meta.get("cache_hit"):
            # The saved original receipts describe acquisition history. This
            # observation reused them and sent no current HTTP request.
            audit["http_request_count"] = 0
            if 'request_observations' in audit:
                audit['request_observations'] = []
        return ProviderResult(self.source, self.name, status, value=records, audit=audit,
                              duration_ms=audit["duration_ms"])


class TpexCompanyHistoryProvider(TwseCompanyHistoryProvider):
    name = "TPEx MOPS company announcement history"
    cache_prefix = "tpex-company-announcements:v1"

    def supports(self, request: FetchRequest) -> bool:
        return bool(re.fullmatch(r"[1-9]\d{3,5}\.TWO", str(request.ticker or "").upper()))

    def _ticker_allowed(self, ticker: str) -> bool:
        return self.supports(FetchRequest.from_ticker(ticker))

    def _fetch_records(self, ticker: str):
        from .market_sources.tpex_company_history import fetch_recent_tpex_announcements
        return fetch_recent_tpex_announcements(ticker)


class YahooProvider(DataProvider):
    name = "Yahoo Finance"
    source = "recent_catalysts"
    cost_tier, capabilities = "free", {"news", "recent_catalysts"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.http_enrichment import fetch_yfinance_news_catalysts

        context = context or {}
        data = context.get("data") if isinstance(context.get("data"), dict) else {}
        from .market_sources.yahoo_taiwan_news import (
            TRANSPORT, PARSER_VERSION, regional_ticker, source_url,
            fetch_yahoo_taiwan_news, annotate_regional_result,
        )
        resolved = regional_ticker(request.ticker, data)
        if resolved:
            diagnostic = {"transport": TRANSPORT, "actual_provider": "Yahoo Taiwan",
                          "source_url": source_url(resolved), "parser_version": PARSER_VERSION,
                          "http_request_sent": False}
            result = audited_fetch(
                self.source, "Yahoo Finance news", fetch_yahoo_taiwan_news, (resolved,),
                {"diagnostics": diagnostic}, default=[], empty_status="degraded_enrichment",
                unavailable_message="Yahoo 台灣個股頁未回傳新聞；不代表沒有事件。",
            )
            return annotate_regional_result(
                provider_result_from_audited(result, self.source, self.name),
                {**data, "ticker": resolved}, diagnostic,
            )
        stock = context.get("stock") or (context.get("market_snapshot") or {}).get("stock")
        if stock is None:
            import yfinance as yf
            data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}
            ticker = str(data.get("ticker") or request.ticker).strip().upper()
            stock = yf.Ticker(ticker)
        result = audited_fetch(
            self.source,
            "Yahoo Finance news",
            fetch_yfinance_news_catalysts,
            (stock,),
            default=[],
            empty_status="degraded_enrichment",
            unavailable_message="Yahoo Finance 未回傳近期新聞。",
        )
        from source_content_selection import annotate_result
        return annotate_result(provider_result_from_audited(result, self.source, self.name),
                               {**((context or {}).get("data") or {}), "ticker": request.ticker})


class FmpNewsProvider(DataProvider):
    name = "FMP news"
    source = "recent_catalysts"
    markets = {"us"}
    cost_tier, capabilities, requires_env = "free_with_key", {"news", "recent_catalysts"}, ("FMP_API_KEY",)

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from config import FMP_API_KEY
        from .market_sources.http_enrichment import fetch_fmp_news_catalysts_async

        if not FMP_API_KEY:
            return not_configured_provider_result(
                self.source,
                self.name,
                "FMP_API_KEY 未設定，略過 FMP news enrichment。",
            )
        context = context or {}
        data = context.get("data", {}) or {}
        ticker = str(context.get("original_ticker") or data.get("ticker") or request.ticker).strip().upper()
        cache_hit = safe_bool(data.get("_cache_hit"))
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_fmp_news_catalysts_async,
            (ticker,),
            default=[],
            cache_hit=cache_hit,
            empty_status="degraded_enrichment",
            unavailable_message="FMP news 未回傳近期新聞。",
        )
        from source_content_selection import annotate_result
        return annotate_result(provider_result_from_audited(result, self.source, self.name),
                               {**((context or {}).get("data") or {}), "ticker": request.ticker})


class EarningsCallProvider(DataProvider):
    name = FREE_EARNINGS_CALL_PROVIDER_NAME
    source, markets = "earnings_call", {"tw"}
    cost_tier, capabilities = "free", {"earnings_call"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = str((context or {}).get("original_ticker") or data.get("ticker") or request.ticker).strip().upper()
        diagnostic = {}
        from .market_sources.taiwanmobile_conference import supports as supports_twm, validate_context as validate_twm, PROVIDER as TWM_PROVIDER
        if supports_twm(request.ticker) or supports_twm(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_twm(data, requested)):
                return ProviderResult(self.source, TWM_PROVIDER, 'unavailable', value={}, audit={
                    'source':self.source, 'provider':TWM_PROVIDER, 'status':'unavailable', 'event_kind':'local_block',
                    'record_count':0, 'http_request_sent':False, 'http_request_count':0,
                    'error_kind':'context_unverified', 'message':'股票與台灣大哥大官方逐字稿來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = TWM_PROVIDER
        from .market_sources.zdt_conference import supports_zdt, validate_context as validate_zdt_context, PROVIDER as ZDT_PROVIDER
        if supports_zdt(request.ticker) or supports_zdt(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_zdt_context(data, requested)):
                return ProviderResult(self.source, ZDT_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': ZDT_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與臻鼎簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = ZDT_PROVIDER
        from .market_sources.getac_conference import supports_getac, validate_context as validate_getac_context, PROVIDER as GETAC_PROVIDER
        if supports_getac(request.ticker) or supports_getac(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_getac_context(data, requested)):
                return ProviderResult(self.source, GETAC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': GETAC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與神基簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = GETAC_PROVIDER
        from .market_sources.npc_conference import supports_npc, validate_context as validate_npc_context, PROVIDER as NPC_PROVIDER
        if supports_npc(request.ticker) or supports_npc(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_npc_context(data, requested)):
                return ProviderResult(self.source, NPC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': NPC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與南亞簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = NPC_PROVIDER
        from .market_sources.sinbon_conference import supports_sinbon, validate_context as validate_sinbon_context, PROVIDER as SINBON_PROVIDER
        if supports_sinbon(request.ticker) or supports_sinbon(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_sinbon_context(data, requested)):
                return ProviderResult(self.source, SINBON_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': SINBON_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與信邦公開申報簡報法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = SINBON_PROVIDER
        from .market_sources.fubon_conference import supports_fubon, validate_context as validate_fubon_context, PROVIDER as FUBON_PROVIDER
        if supports_fubon(request.ticker) or supports_fubon(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_fubon_context(data, requested)):
                return ProviderResult(self.source, FUBON_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': FUBON_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與富邦金公開申報簡報法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = FUBON_PROVIDER
        from .market_sources.voltronic_conference import supports_voltronic, validate_context as validate_voltronic_context, PROVIDER as VOLTRONIC_PROVIDER
        if supports_voltronic(request.ticker) or supports_voltronic(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_voltronic_context(data, requested)):
                return ProviderResult(self.source, VOLTRONIC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': VOLTRONIC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與旭隼公開申報簡報法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = VOLTRONIC_PROVIDER
        from .market_sources.macronix_conference import supports_macronix, validate_context as validate_macronix_context, PROVIDER as MACRONIX_PROVIDER
        if supports_macronix(request.ticker) or supports_macronix(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_macronix_context(data, requested)):
                return ProviderResult(self.source, MACRONIX_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': MACRONIX_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與旺宏簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = MACRONIX_PROVIDER
        from .market_sources.tecom_conference import supports_tecom, validate_context as validate_tecom_context, PROVIDER as TECOM_PROVIDER
        if supports_tecom(request.ticker) or supports_tecom(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_tecom_context(data, requested)):
                return ProviderResult(self.source, TECOM_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': TECOM_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與東訊簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = TECOM_PROVIDER
        from .market_sources.eikei_conference import supports_eikei, validate_context as validate_eikei_context, PROVIDER as EIKEI_PROVIDER
        if supports_eikei(request.ticker) or supports_eikei(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_eikei_context(data, requested)):
                return ProviderResult(self.source, EIKEI_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': EIKEI_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與榮惠簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = EIKEI_PROVIDER
        from .market_sources.nanyapcb_conference import supports_nanyapcb, validate_context as validate_nanyapcb_context, PROVIDER as NANYAPCB_PROVIDER
        if supports_nanyapcb(request.ticker) or supports_nanyapcb(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_nanyapcb_context(data, requested)):
                return ProviderResult(self.source, NANYAPCB_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': NANYAPCB_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與南電簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = NANYAPCB_PROVIDER
        from .market_sources.wahlee_conference import supports_wahlee, validate_context as validate_wahlee_context, PROVIDER as WAHLEE_PROVIDER
        if supports_wahlee(request.ticker) or supports_wahlee(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_wahlee_context(data, requested)):
                return ProviderResult(self.source, WAHLEE_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': WAHLEE_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與華立簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = WAHLEE_PROVIDER
        from .market_sources.chroma_conference import supports_chroma, validate_context as validate_chroma_context, PROVIDER as CHROMA_PROVIDER
        if supports_chroma(request.ticker) or supports_chroma(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_chroma_context(data, requested)):
                return ProviderResult(self.source, CHROMA_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': CHROMA_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與致茂簡報官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = CHROMA_PROVIDER
        from .market_sources.chb_conference import supports_chb, validate_context as validate_chb_context, PROVIDER as CHB_PROVIDER
        if supports_chb(request.ticker) or supports_chb(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_chb_context(data, requested)):
                return ProviderResult(self.source, CHB_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': CHB_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與彰銀問答官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = CHB_PROVIDER
        from .market_sources.innocare_conference import supports_innocare, validate_context as validate_innocare_context, PROVIDER as INNOCARE_PROVIDER
        if supports_innocare(request.ticker) or supports_innocare(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_innocare_context(data, requested)):
                return ProviderResult(self.source, INNOCARE_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': INNOCARE_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與睿生光電官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = INNOCARE_PROVIDER
        from .market_sources.walsin_conference import supports_walsin, validate_context as validate_walsin_context, PROVIDER as WALSIN_PROVIDER
        if supports_walsin(request.ticker) or supports_walsin(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_walsin_context(data, requested)):
                return ProviderResult(self.source, WALSIN_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': WALSIN_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與華新官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = WALSIN_PROVIDER
        from .market_sources.lienhwa_conference import supports_lienhwa, validate_context as validate_lienhwa_context, PROVIDER as LIENHWA_PROVIDER
        if supports_lienhwa(request.ticker) or supports_lienhwa(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_lienhwa_context(data, requested)):
                return ProviderResult(self.source, LIENHWA_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': LIENHWA_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與聯華官網法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = LIENHWA_PROVIDER
        from .market_sources.mops_presentation import supports as supports_material, validate_context as validate_material_context, PROVIDER as MATERIAL_PROVIDER
        if (supports_material(request.ticker) or supports_material(ticker)) and not supports_lienhwa(ticker) and not supports_walsin(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_material_context(data, requested)):
                return ProviderResult(self.source, MATERIAL_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': MATERIAL_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與 MOPS 簡報來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = MATERIAL_PROVIDER
        from .market_sources.cht_conference import supports_cht, validate_context as validate_cht_context, PROVIDER as CHT_PROVIDER
        if supports_cht(request.ticker) or supports_cht(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_cht_context(data, requested)):
                return ProviderResult(self.source, CHT_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': CHT_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與中華電法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = CHT_PROVIDER
        from .market_sources.allis_conference import supports_allis, validate_context as validate_allis_context, PROVIDER as ALLIS_PROVIDER
        if supports_allis(request.ticker) or supports_allis(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_allis_context(data, requested)):
                return ProviderResult(self.source, ALLIS_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': ALLIS_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與亞力法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = ALLIS_PROVIDER
        from .market_sources.gce_conference import supports_gce, validate_context as validate_gce_context, PROVIDER as GCE_PROVIDER
        if supports_gce(request.ticker) or supports_gce(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_gce_context(data, requested)):
                return ProviderResult(self.source, GCE_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': GCE_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與金像電法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = GCE_PROVIDER
        from .market_sources.hiwin_conference import supports_hiwin, validate_context as validate_hiwin_context, PROVIDER as HIWIN_PROVIDER
        if supports_hiwin(request.ticker) or supports_hiwin(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_hiwin_context(data, requested)):
                return ProviderResult(self.source, HIWIN_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': HIWIN_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與上銀法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = HIWIN_PROVIDER
        from .market_sources.kinik_conference import supports_kinik, validate_context as validate_kinik_context, PROVIDER as KINIK_PROVIDER
        if supports_kinik(request.ticker) or supports_kinik(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_kinik_context(data, requested)):
                return ProviderResult(self.source, KINIK_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': KINIK_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與中砂法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = KINIK_PROVIDER
        from .market_sources.csc_conference import supports_csc, validate_context as validate_csc_context, PROVIDER as CSC_PROVIDER
        if supports_csc(request.ticker) or supports_csc(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_csc_context(data, requested)):
                return ProviderResult(self.source, CSC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': CSC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與中鋼法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = CSC_PROVIDER
        from .market_sources.sti_conference import supports_sti, validate_context as validate_sti_context, PROVIDER as STI_PROVIDER
        if supports_sti(request.ticker) or supports_sti(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_sti_context(data, requested)):
                return ProviderResult(self.source, STI_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': STI_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與敦陽科法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = STI_PROVIDER
        from .market_sources.sigurd_conference import supports_sigurd, validate_context as validate_sigurd_context, PROVIDER as SIGURD_PROVIDER
        if supports_sigurd(request.ticker) or supports_sigurd(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_sigurd_context(data, requested)):
                return ProviderResult(self.source, SIGURD_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': SIGURD_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與矽格法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = SIGURD_PROVIDER
        from .market_sources.winbond_conference import supports_winbond, validate_context as validate_winbond_context, PROVIDER as WINBOND_PROVIDER
        if supports_winbond(request.ticker) or supports_winbond(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_winbond_context(data, requested)):
                return ProviderResult(self.source, WINBOND_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': WINBOND_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與華邦電法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = WINBOND_PROVIDER
        from .market_sources.chipmos_conference import supports_chipmos, validate_context as validate_chipmos_context, PROVIDER as CHIPMOS_PROVIDER
        if supports_chipmos(request.ticker) or supports_chipmos(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_chipmos_context(data, requested)):
                return ProviderResult(self.source, CHIPMOS_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': CHIPMOS_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與南茂法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = CHIPMOS_PROVIDER
        from .market_sources.unitech_conference import supports_unitech, validate_context as validate_unitech_context, PROVIDER as UNITECH_PROVIDER
        if supports_unitech(request.ticker) or supports_unitech(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_unitech_context(data, requested)):
                return ProviderResult(self.source, UNITECH_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': UNITECH_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與燿華法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = UNITECH_PROVIDER
        from .market_sources.tewc_conference import supports_tewc, validate_context as validate_tewc_context, PROVIDER as TEWC_PROVIDER
        if supports_tewc(request.ticker) or supports_tewc(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_tewc_context(data, requested)):
                return ProviderResult(self.source, TEWC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': TEWC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與大東電法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = TEWC_PROVIDER
        from .market_sources.delta_conference import supports_delta, validate_context as validate_delta_context, PROVIDER as DELTA_PROVIDER
        if supports_delta(request.ticker) or supports_delta(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_delta_context(data, requested)):
                return ProviderResult(self.source, DELTA_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': DELTA_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與台達電逐字稿來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = DELTA_PROVIDER
        from .market_sources.jentech_conference import supports_jentech, validate_context as validate_jentech, PROVIDER as JENTECH_PROVIDER
        if supports_jentech(request.ticker) or supports_jentech(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_jentech(data, requested)):
                return ProviderResult(self.source, JENTECH_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': JENTECH_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與健策法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = JENTECH_PROVIDER
        from .market_sources.eclat_conference import supports_eclat, validate_context as validate_eclat, PROVIDER as ECLAT_PROVIDER
        if supports_eclat(request.ticker) or supports_eclat(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_eclat(data, requested)):
                return ProviderResult(self.source, ECLAT_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': ECLAT_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與儒鴻法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = ECLAT_PROVIDER
        from .market_sources.pcsc_conference import supports_pcsc, validate_context as validate_pcsc, PROVIDER as PCSC_PROVIDER
        if supports_pcsc(request.ticker) or supports_pcsc(ticker):
            requested = str(request.ticker).strip().upper()
            if (requested != ticker
                    or context is not None and 'data' in context and not isinstance(context['data'], dict)
                    or data and not validate_pcsc(data, requested)):
                return ProviderResult(self.source, PCSC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': PCSC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與統一超商法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = PCSC_PROVIDER
        from .market_sources.guc_conference import supports_guc, validate_context as validate_guc, PROVIDER as GUC_PROVIDER
        if supports_guc(request.ticker) or supports_guc(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_guc(data, requested)):
                return ProviderResult(self.source, GUC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': GUC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與創意法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = GUC_PROVIDER
        from .market_sources.seec_conference import supports_seec, validate_context as validate_seec, PROVIDER as SEEC_PROVIDER
        if supports_seec(request.ticker) or supports_seec(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_seec(data, requested)):
                return ProviderResult(self.source, SEEC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': SEEC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與士電法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = SEEC_PROVIDER
        from .market_sources.kingslide_conference import supports_kingslide, validate_context as validate_kingslide, PROVIDER as KINGSLIDE_PROVIDER
        if supports_kingslide(request.ticker) or supports_kingslide(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_kingslide(data, requested)):
                return ProviderResult(self.source, KINGSLIDE_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': KINGSLIDE_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與川湖法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = KINGSLIDE_PROVIDER
        from .market_sources.promate_conference import supports_promate, validate_context as validate_promate, PROVIDER as PROMATE_PROVIDER
        if supports_promate(request.ticker) or supports_promate(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_promate(data, requested)):
                return ProviderResult(self.source, PROMATE_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': PROMATE_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與豐藝法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = PROMATE_PROVIDER
        from .market_sources.auras_conference import supports_auras, validate_context as validate_auras_context, PROVIDER as AURAS_PROVIDER
        if supports_auras(request.ticker) or supports_auras(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_auras_context(data, requested)):
                return ProviderResult(self.source, AURAS_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': AURAS_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與雙鴻法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = AURAS_PROVIDER
        from .market_sources.tcfhc_conference import supports_tcfhc, validate_context as validate_tcfhc_context, PROVIDER as TCFHC_PROVIDER
        if supports_tcfhc(request.ticker) or supports_tcfhc(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_tcfhc_context(data, requested)):
                return ProviderResult(self.source, TCFHC_PROVIDER, 'unavailable', value={}, audit={
                    'source': self.source, 'provider': TCFHC_PROVIDER, 'status': 'unavailable', 'event_kind': 'local_block',
                    'record_count': 0, 'http_request_sent': False, 'http_request_count': 0,
                    'error_kind': 'context_unverified', 'message': '股票與合庫金控問答來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = TCFHC_PROVIDER
        from .market_sources.psc_conference import supports_psc, validate_context as validate_psc_context, PROVIDER as PSC_PROVIDER
        if supports_psc(request.ticker) or supports_psc(ticker):
            requested = str(request.ticker).strip().upper()
            if requested != ticker or (data and not validate_psc_context(data, requested)):
                return ProviderResult(self.source, PSC_PROVIDER, 'unavailable', value={}, audit={
                    'source':self.source,'provider':PSC_PROVIDER,'status':'unavailable','event_kind':'local_block',
                    'record_count':0,'http_request_sent':False,'http_request_count':0,
                    'error_kind':'context_unverified','message':'股票與統一證券法說來源身分不一致，未抓取。'})
            diagnostic['actual_provider'] = PSC_PROVIDER
        from company_conference_content import supports_company, PROVIDER as ISSUER_PROVIDER
        audit_provider = ISSUER_PROVIDER if supports_company(ticker) else "MOPS / TWSE WebPro investor conference"
        def fetch_context():
            try:
                return fetch_free_earnings_call_context(ticker, diagnostics=diagnostic,
                    **({'force_refresh':True} if request.options.force_refresh else {}),
                    **({'source_context':data} if ticker == '2317.TW' and (context or {}).get('source_only_recovery') is True else {}))
            except SourceResponseError as exc:
                diagnostic.update(exc.diagnostic, status="error", message=str(exc))
                return {}

        result = audited_fetch(
            self.source,
            audit_provider,
            fetch_context,
            default={},
            empty_status="degraded_enrichment",
            unavailable_message="免費法說會資料未回傳。",
        )
        apply_earnings_call_audit(result, diagnostic)
        if supports_company(ticker):
            from company_conference_content import AGGREGATE_MESSAGE
            result['audit']['message'] = AGGREGATE_MESSAGE
        return provider_result_from_audited(result, self.source, self.name)


class GlobalMarketContextProvider(DataProvider):
    name = "yfinance global context"
    source = "global_market_context"
    cost_tier, capabilities = "free", {"global_market_context"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.global_context import fetch_global_market_context

        context = context or {}
        data = context.get("data", {}) or {}
        cache_hit = safe_bool(data.get("_cache_hit"))
        result = audited_fetch(
            self.source,
            self.name,
            fetch_global_market_context,
            (
                str(data.get("ticker") or request.ticker).strip().upper(),
                str(data.get("company_name") or request.ticker),
                str(data.get("sector") or ""),
                str(data.get("industry") or ""),
            ),
            default={"lookback_days": 5, "items": [], "coverage_notes": ["全球市場脈絡暫無可用資料。"]},
            record_counter=lambda value: len(value.get("items", [])) if isinstance(value, dict) else 0,
            cache_hit=cache_hit,
            empty_status="degraded_enrichment",
            unavailable_message="yfinance global context 未回傳全球市場脈絡。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class InternationalNewsContextProvider(DataProvider):
    name = "GDELT / Google News RSS"
    source = "international_news_context"
    cost_tier, capabilities = "free", {"international_news_context", "news"}

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from external_data_gdelt import fetch_gdelt_international_news_context

        context = context or {}
        data = context.get("data", {}) or {}
        cache_hit = safe_bool(data.get("_cache_hit"))
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_gdelt_international_news_context,
            (
                str(data.get("sector") or ""),
                str(data.get("industry") or ""),
            ),
            default={"lookback_days": 7, "topics": [], "coverage_notes": ["國際新聞脈絡暫無可用資料。"]},
            record_counter=lambda value: len(value.get("topics", [])) if isinstance(value, dict) else 0,
            cache_hit=cache_hit,
            empty_status="degraded_enrichment",
            unavailable_message="GDELT 未回傳國際新聞脈絡。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class DynamicPeerMetricsProvider(DataProvider):
    name = "FinMind/yfinance"
    source = "dynamic_peer_metrics"
    cost_tier, capabilities = "free", {"peer_metrics"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.peers import fetch_dynamic_peer_metrics_with_diagnostics

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        result = audited_fetch(
            self.source,
            self.name,
            fetch_dynamic_peer_metrics_with_diagnostics,
            (
                str(data.get("ticker") or request.ticker).strip().upper(),
                str(data.get("company_name") or request.ticker),
                str(data.get("sector") or ""),
                str(data.get("industry") or ""),
                data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {},
            ),
            default={"peers":[],"audit":{}},
            record_counter=lambda value: value.get("audit",{}).get("usable_count",0),
            empty_status="degraded_enrichment",
            unavailable_message="同業指標暫無可用資料。",
        )
        payload = result.get('value') or {}
        result['audit'].update(payload.get('audit') or {})
        result['value'] = payload.get('peers') or []
        if result['audit'].get('coverage_status') not in {'success', 'complete'} and result['audit'].get('status') == 'success':
            result['audit']['status'] = 'degraded_enrichment'
        return provider_result_from_audited(result, self.source, self.name)


class PeRiverChartProvider(DataProvider):
    name = "FinMind/default multiples"
    source = "pe_river_chart"
    cost_tier, capabilities = "free", {"valuation"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.valuation import build_pe_river_chart_data

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        from .financial_history_basis import is_ordinary_individual_basis
        if is_ordinary_individual_basis(data):
            from .provider_base import unavailable_provider_result
            result = unavailable_provider_result(self.source,self.name,'個別本期損益未證明可換算集團每股盈餘；不生成 P/E 河流圖。')
            result.audit.update(event_kind='local_block',http_request_sent=False,http_request_count=0,
                                error_kind='ordinary_individual_group_basis_unverified')
            return result
        value = data.get("shares_raw", data.get("shares_outstanding"))
        shares = first_number(value)
        result = audited_fetch(
            self.source,
            self.name,
            build_pe_river_chart_data,
            (
                str(data.get("ticker") or request.ticker).strip().upper(),
                list(data.get("years") or []),
                list(data.get("net_income_history") or []),
                shares,
            ),
            default={"years": list(data.get("years") or []), "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"},
            unavailable_message="P/E 河流圖資料暫無可用資料。",
        )
        return provider_result_from_audited(result, self.source, self.name)
