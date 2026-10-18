"""Search-backed enrichment providers."""

from __future__ import annotations

import time
import math

from data_trust import build_source_audit_entry
from source_audit import audited_fetch_async
from report_freshness_summary import safe_bool

from .provider_base import DataProvider, provider_result_from_audited
from .types import FetchRequest, ProviderResult


class AlternativeSearchProvider(DataProvider):
    name = "Alternative Search"
    source = "recent_catalysts"
    cost_tier, capabilities = "free", {"search", "recent_catalysts"}

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from external_search_providers import fetch_alternative_search_catalysts_async

        context = context or {}
        data = context.get("data", {}) or {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        company_name = str(data.get("company_name") or ticker).strip()
        identity = data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {}
        cache_hit = safe_bool(data.get("_cache_hit"))
        diagnostics = {}
        supplied_deadline = context.get("catalyst_search_deadline")
        def budget_skip(reason):
            return ProviderResult(self.source,self.name,"unavailable",value=[],audit={
                "source":self.source,"provider":self.name,"status":"unavailable",
                "event_kind":"local_block","http_request_sent":False,"record_count":0,
                "cache_hit":False,"stale":False,"reason_code":reason,
                "message":"skip: 原搜尋期限已用盡或無法確認，未發送額外請求。",**diagnostics})
        if "catalyst_search_deadline" in context:
            try:
                if type(supplied_deadline) not in (int,float):
                    raise ValueError("invalid deadline")
                supplied_deadline=float(supplied_deadline)
                if not math.isfinite(supplied_deadline):
                    raise ValueError("invalid deadline")
            except (ValueError,TypeError,OverflowError):
                return budget_skip("catalyst_search_deadline_invalid")
            if time.monotonic()>=supplied_deadline:
                return budget_skip("catalyst_search_deadline_exhausted")
        async def acquire():
            kwargs = {"diagnostics": diagnostics}
            from company_news_queries import company_news_brand_fallback_query
            if company_news_brand_fallback_query(data):
                kwargs['company_context'] = data
            if context.get('free_sources_only') is True:
                kwargs['provider_allowlist'] = {'google_news_rss', 'bing_news_rss', 'duckduckgo_news', 'gdelt', 'yahoo_rss'}
            if "catalyst_search_deadline" in context:
                if time.monotonic()>=supplied_deadline:
                    diagnostics.update(search_budget_exhausted=True,search_queries_started=0)
                    return []
                kwargs["deadline"] = supplied_deadline
            return await fetch_alternative_search_catalysts_async(ticker, company_name, identity, **kwargs)
        result = await audited_fetch_async(
            self.source, self.name, acquire, default=[], cache_hit=cache_hit,
            empty_status="degraded_enrichment", unavailable_message="未取得足量公司相符的近期催化劑。",
        )
        if (supplied_deadline is not None and diagnostics.get("search_budget_exhausted") is True
                and diagnostics.get("search_queries_started") == 0 and not result.get("value")):
            return budget_skip("catalyst_search_deadline_exhausted")
        result['audit'].update(diagnostics)
        if diagnostics.get('quality_status') == 'insufficient_candidates' and result['audit'].get('status') == 'success':
            result['audit']['status'] = 'degraded_enrichment'
        return provider_result_from_audited(result, self.source, self.name)



class AlternativePeerDiscoveryProvider(DataProvider):
    name = "Alternative Search"
    source = "peer_discovery"
    cost_tier, capabilities = "free", {"peer_discovery", "search"}

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from external_search_providers import fetch_alternative_peer_discovery_async

        context = context or {}
        data = context.get("data", {}) or {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        company_name = str(data.get("company_name") or ticker).strip()
        sector = str(data.get("sector") or "")
        industry = str(data.get("industry") or "")
        cache_hit = safe_bool(data.get("_cache_hit"))
        from peer_relationship_evidence import peer_selection_diagnostics
        diagnostics = peer_selection_diagnostics(ticker)
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_alternative_peer_discovery_async,
            (ticker, company_name, sector, industry),
            kwargs={"company_context": data, "diagnostics": diagnostics},
            default=[],
            cache_hit=cache_hit,
            empty_status="degraded_enrichment",
            unavailable_message="Alternative Search 未回傳同業搜尋結果。",
        )
        result["audit"].update(diagnostics)
        return provider_result_from_audited(result, self.source, self.name)


class YahooPublishedPeerRankingProvider(DataProvider):
    """Read a dated published cohort; never certify business comparability."""

    name = "Yahoo Taiwan published industry ranking"
    source = "peer_discovery"
    markets = {"tw"}
    cost_tier, capabilities = "free", {"peer_discovery", "published_industry_candidates"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from shared_provider_cache import shared_fetch
        from .market_sources.yahoo_peer_ranking import (
            POLICY, _specific_categories, _today, fetch_published_industry_peers,
            validate_stored_ranking_body, RankingError,
        )
        from .market_sources.peer_recovery import load_peer_stock_master

        started = time.time()
        data = (context or {}).get("data") or {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        today = _today()
        try:
            master = load_peer_stock_master()
            categories = _specific_categories(ticker, master, today)
        except Exception:
            master, categories = [], set()
        if not categories:
            audit = build_source_audit_entry(
                self.source, self.name, "unavailable", started_at_epoch=started,
                finished_at_epoch=time.time(), record_count=0,
                message="沒有可核對的當期細分產業，未抓取 Yahoo 同業排名。",
            )
            audit.update(selection_policy=POLICY, event_kind="local_block",
                         http_request_sent=False, reason_code="specific_industry_unavailable")
            return ProviderResult(self.source, self.name, "unavailable", value=[], audit=audit)

        value, meta = shared_fetch(
            f"yahoo-published-peer-ranking:v1:{ticker}:{today.isoformat()}",
            lambda: fetch_published_industry_peers(ticker, today=today, master_rows=master),
            freshness_seconds=4 * 3600, retention_seconds=4 * 3600,
            result_ttl=lambda result: 4 * 3600 if result.get("records") else 900,
            error_retry_seconds=300, lock_wait_seconds=1,
        )
        value = value if isinstance(value, dict) else {}
        receipt_error = ""
        try:
            validate_stored_ranking_body(value, ticker, master, today=today)
        except RankingError:
            receipt_error = "source_receipt_invalid"
        rows = value.get("records") if isinstance(value.get("records"), list) else []
        if receipt_error:
            rows = []
        stale = bool(meta.get("stale"))
        cache_hit = bool(meta.get("cache_hit"))
        actual_request = not cache_hit and not meta.get("cooldown") and meta.get("error_kind") != "single_flight_busy"
        if receipt_error:
            status = "error"
        elif meta.get("error_kind"):
            status = "degraded_enrichment" if stale and rows else "error"
        elif cache_hit:
            status = "skipped_fresh_cache" if rows else "unavailable"
        else:
            status = "success" if rows else "unavailable"
        audit = build_source_audit_entry(
            self.source, self.name, status,
            fetched_at_epoch=meta.get("fetched_at_epoch"),
            started_at_epoch=started, finished_at_epoch=time.time(),
            record_count=len(rows), cache_hit=cache_hit, stale=stale,
            error_kind=str(meta.get("error_kind") or receipt_error),
            message=("已取得日期與主檔可核對的產業候選名單；業務及數值可比性未驗證。"
                     if rows else "Yahoo 同業排名未回傳可核對的細分產業候選名單。"),
        )
        audit.update(selection_policy=POLICY, source_url=value.get("source_url"),
                     observed_at=value.get("observed_at"), publisher_industry=value.get("publisher_industry"),
                     response_sha256=value.get("response_sha256"),
                     raw_count=value.get("raw_count", 0), usable_count=len(rows),
                     http_request_sent=actual_request,
                     event_kind="http_request" if actual_request else "cache_hit" if cache_hit else "local_block")
        if isinstance(value.get("raw_http_receipt"), dict):
            # Preserve the original acquisition receipt through warm cache
            # reads without inserting raw bodies or local paths into candidates.
            audit["raw_http_receipt"] = value["raw_http_receipt"]
        if receipt_error:
            audit["receipt_validation_error"] = receipt_error
        return ProviderResult(self.source, self.name, status, value=rows, audit=audit)


class MoneyDjPublishedPeerCohortProvider(DataProvider):
    """Recover 5314's dated food-biotech cohort as candidate evidence only."""

    name = "MoneyDJ published food-biotech cohort"
    source = "peer_discovery"
    markets = {"tw"}
    cost_tier, capabilities = "free", {"peer_discovery", "published_industry_candidates"}

    def supports(self, request: FetchRequest) -> bool:
        return request.ticker.strip().upper() == "5314.TWO"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.moneydj_peer_cohort import (
            POLICY, URL, _current_identity, _today, acquire_published_cohort, cohort_source_audit,
        )
        from .market_sources.peer_recovery import load_peer_stock_master

        started = time.time()
        ticker = str(((context or {}).get("data") or {}).get("ticker") or request.ticker).strip().upper()
        today = _today()
        try:
            master = load_peer_stock_master()
            identity = _current_identity("5314", master, today)
        except Exception:
            master, identity = [], None
        if ticker != "5314.TWO" or identity != ("世紀*", "tpex"):
            audit = build_source_audit_entry(
                self.source, self.name, "unavailable", started_at_epoch=started,
                finished_at_epoch=time.time(), record_count=0,
                message="沒有可核對的當期 5314 公司身分，未抓取 MoneyDJ 同業名單。",
            )
            audit.update(selection_policy=POLICY, event_kind="local_block",
                         http_request_sent=False, reason_code="current_issuer_identity_unavailable")
            return ProviderResult(self.source, self.name, "unavailable", value=[], audit=audit)

        value, meta = acquire_published_cohort(ticker,master,today=today)
        value = value if isinstance(value, dict) else {}
        rows = value.get("records") if isinstance(value.get("records"), list) else []
        audit=cohort_source_audit(value,meta,started_at_epoch=started)
        return ProviderResult(self.source, self.name, audit["status"], value=rows, audit=audit)


class MedicalPublishedPeerCohortProvider(DataProvider):
    """Publish verified medical leads without asserting whole-business similarity."""

    name='MoneyDJ/TWSE published medical cohort'
    source='peer_discovery'
    markets={'tw'}
    cost_tier,capabilities='free',{'peer_discovery','published_industry_candidates'}

    def supports(self,request:FetchRequest)->bool:
        return request.ticker.strip().upper()=='9103.TW'

    def fetch(self,request:FetchRequest,context:dict|None=None)->ProviderResult:
        from .market_sources.moneydj_medical_peer_cohort import (
            POLICY,_context_valid,_today,get_medical_cohort_candidates,medical_discovery_records,is_medical_peer_record,
        )
        from .market_sources.peer_recovery import load_peer_stock_master
        started=time.time();data=(context or {}).get('data') or {};today=_today()
        ticker=str(data.get('ticker') or request.ticker).strip().upper()
        identity=data.get('company_identity')
        if (not self.supports(request) or ticker!=request.ticker.strip().upper()
                or not _context_valid(ticker,identity)
                or str(data.get('industry')or'').strip().casefold()!='medical instruments & supplies'):
            audit=build_source_audit_entry(self.source,self.name,'unavailable',record_count=0,
                started_at_epoch=started,finished_at_epoch=time.time(),message='沒有可核對的美德醫療公司context，未抓取醫材名單。')
            audit.update(selection_policy=POLICY,event_kind='local_block',http_request_sent=False)
            return ProviderResult(self.source,self.name,audit['status'],value=[],audit=audit)
        result=get_medical_cohort_candidates(ticker,identity,load_peer_stock_master(),today=today)
        rows=[r for r in medical_discovery_records(result) if is_medical_peer_record(r,ticker,today=today)]
        audit={**result['source_audit'],'record_count':len(rows),'usable_count':len(rows)}
        if not rows and audit['status'] in {'success','skipped_fresh_cache'}:
            audit.update(status='unavailable',error_kind='medical_discovery_receipt_invalid')
        return ProviderResult(self.source,self.name,audit['status'],value=rows,audit=audit)


class OfficialSegmentDiscoveryProvider(DataProvider):
    """Recover missing leads from exact official issuer/segment memberships."""

    name = 'TPEx official segment discovery'
    source = 'peer_discovery'
    markets = {'tw'}
    cost_tier, capabilities = 'free', {'peer_discovery', 'official_segment_candidates'}

    def supports(self, request: FetchRequest) -> bool:
        from .market_sources.official_segment_discovery import PROFILES
        return request.ticker.strip().upper() in PROFILES

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.official_segment_discovery import POLICY, PROFILES, fetch_segment_discovery
        from .market_sources.peer_recovery import load_peer_stock_master

        data = (context or {}).get('data') or {}
        ticker = request.ticker.strip().upper()
        identity = data.get('company_identity')
        profile = PROFILES.get(ticker, {})
        if (not self.supports(request) or str(data.get('ticker') or '').strip().upper() != ticker
                or not isinstance(identity, dict) or identity.get('ticker') != ticker
                or identity.get('stock_id') != ticker[:4]
                or identity.get('official_name') != profile.get('name')
                or identity.get('instrument_type') != 'EQUITY'):
            audit = {'source': self.source, 'provider': self.name, 'status': 'unavailable',
                     'selection_policy': POLICY, 'event_kind': 'local_block',
                     'http_request_sent': False, 'cache_hit': False, 'stale': False,
                     'record_count': 0, 'reason_code': 'current_issuer_context_unverified',
                     'message': '無法核對請求與目前公司身分，未抓取官方產業鏈。'}
            return ProviderResult(self.source, self.name, audit['status'], value=[], audit=audit)
        result = fetch_segment_discovery(ticker, load_peer_stock_master())
        return ProviderResult(self.source, self.name, result['audit']['status'],
                              value=result['records'], audit=result['audit'])
