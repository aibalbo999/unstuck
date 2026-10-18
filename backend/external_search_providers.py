"""Alternative web/news search providers for optional enrichment."""

from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import math
import os
import re
from time import monotonic

from config import (
    BING_SEARCH_API_KEY,
    BING_SEARCH_ENDPOINT,
    BRAVE_SEARCH_API_KEY,
    CATALYST_LOOKBACK_DAYS,
    SEARCH_CATALYST_MAX_RESULTS,
    SEARCH_PEER_DISCOVERY_MAX_RESULTS,
    SERPAPI_API_KEY,
    TAVILY_API_KEY,
    WEB_SEARCH_PROVIDER_ORDER,
)
from external_http_client import async_client, log_http_warning
from external_search_provider_clients import fetch_provider_results
from external_search_quality import (
    provider_request_size as _provider_request_size,
    result_source_key as _result_source_key,
    search_quality_satisfied as _search_quality_satisfied,
    select_quality_results as _select_quality_results,
)
from external_search_types import SearchResult
from search_provider_runtime import fetch_search_upstream


# Bing Search APIs retired on 2025-08-11. Keep the implementation available
# only for explicit legacy opt-in, but do not include it in default routing.
# Start with high-yield public RSS feeds. Quota-backed providers remain a
# fallback for searches that do not meet the existing quality threshold; slow,
# inconsistent free endpoints stay at the tail of the bounded waterfall.
DEFAULT_WEB_SEARCH_PROVIDER_ORDER = "google_news_rss,bing_news_rss,duckduckgo_news,gdelt,yahoo_rss"
DEFAULT_WEB_SEARCH_TOTAL_TIMEOUT_SECONDS = 30.0
FREE_NAME_FALLBACK_PROVIDERS = frozenset({
    "google_news_rss", "bing_news_rss", "duckduckgo_news", "gdelt", "yahoo_rss",
})


def _search_deadline(deadline: float | None = None) -> float:
    """Never let a nested query renew the parent's total search allowance."""
    try:
        seconds = float(os.getenv('WEB_SEARCH_TOTAL_TIMEOUT_SECONDS', '30'))
        if not math.isfinite(seconds):
            raise ValueError('non-finite search timeout')
    except (ValueError, TypeError):
        seconds = DEFAULT_WEB_SEARCH_TOTAL_TIMEOUT_SECONDS
    local_deadline = monotonic() + max(1.0, min(seconds, 60.0))
    if deadline is None:
        return local_deadline
    supplied = float(deadline)
    return min(local_deadline, supplied) if math.isfinite(supplied) else local_deadline


def _news_record(result: SearchResult) -> dict:
    return {"date":result.published_at, "title":result.title, "summary":result.snippet,
            "source":result.source, "link":result.link,
            "source_type":f"{result.provider or 'alternative'}_search"}


def _merge_publisher_originals(raw, originals):
    from zoneinfo import ZoneInfo
    from news_record_utils import clean_text, parse_news_datetime
    labels = {'自由財經', '自由時報', '自由時報電子報'}
    def key(row):
        stamp = parse_news_datetime(row.get('date'))
        title = re.sub(r'\s*[-–－]\s*(?:自由財經|自由時報(?:電子報)?)\s*$', '', clean_text(row.get('title'))).casefold()
        return (title, stamp.astimezone(ZoneInfo('Asia/Taipei')).date()) if stamp and row.get('source') in labels else None
    current = {key(v) for v in originals if key(v) is not None}
    replaced = [{'reason':'replaced_by_publisher_original','record':v}
                for v in raw if key(v) is not None and key(v) in current]
    return [v for v in raw if key(v) is None or key(v) not in current] + originals, replaced


async def fetch_alternative_search_catalysts_async(
    ticker: str, company_name: str, identity: dict, *,
    max_results: int = SEARCH_CATALYST_MAX_RESULTS, diagnostics: dict | None = None,
    deadline: float | None = None,
    provider_allowlist: set[str] | None = None,
    company_context: dict | None = None,
) -> list[dict]:
    """Bounded company queries expand on eligible evidence shortage, not raw emptiness."""
    from source_content_selection import select_company_records, company_aliases
    started = monotonic()
    deadline = _search_deadline(deadline)
    data = {"ticker":ticker, "company_name":company_name, "company_identity":identity}
    if re.fullmatch(r'\d{4,6}\.(?:TW|TWO)', str(ticker).strip().upper()):
        from company_news_queries import company_search_name
        official_name = company_search_name(data)
    else:
        official_name = str((identity or {}).get("official_name") or company_name or ticker).strip()
    topics = '(法說會 OR 展望 OR 營收 OR earnings OR outlook OR revenue)'
    exchange_name = str((identity or {}).get("official_name") or official_name).strip()
    from company_news_queries import context_bound_search_alias
    exchange_name = context_bound_search_alias(data) or exchange_name
    # Keep a code-anchored shorthand query for issuer news that only uses the
    # exchange label, while the broader topical query uses the precise name.
    queries = [f'{official_name} {topics}',
               f'"{exchange_name}" {ticker.split(".")[0]}']
    google_queries = {}
    bing_queries = {}
    query_provider_allowlists = {}
    matching_company_context = isinstance(company_context, dict) and all(
        company_context.get(key) == data[key] for key in data)
    if re.fullmatch(r'\d{4,6}\.(?:TW|TWO)', str(ticker).strip().upper()):
        from company_news_queries import company_news_query, company_news_brand_fallback_query
        local_query = company_news_query(data, lookback_days=CATALYST_LOOKBACK_DAYS)
        # Reuse the normal Taiwan news identity/time query only on its engine.
        # Other providers keep their own query syntax and the same quality gate.
        anchored_shorthand = f'"{exchange_name.strip("*")}" {ticker.split(".")[0]} when:{CATALYST_LOOKBACK_DAYS}d'
        # Legacy callers omit the original root context. Keep their anchored
        # query; only a matching full context can enable the new brand lookup.
        brand_fallback = ""
        if matching_company_context:
            brand_fallback = company_news_brand_fallback_query(
                company_context, lookback_days=CATALYST_LOOKBACK_DAYS)
        google_queries = {queries[0]: f'{local_query} {topics}',
                          queries[1]: brand_fallback or (anchored_shorthand if exchange_name != official_name else local_query)}
        # Bing RSS returns no items for the topical OR expression on many TW
        # queries. Its exact issuer + code route performs better; local
        # publication-date and issuer checks below remain authoritative.
        bing_queries = {
            queries[0]: anchored_shorthand.removesuffix(f' when:{CATALYST_LOOKBACK_DAYS}d'),
            queries[1]: re.sub(r'\s+when:\d+d\b', '',
                               brand_fallback or anchored_shorthand, flags=re.IGNORECASE).strip(),
        }

        # If the anchored searches still lack enough recent, issuer-matched
        # evidence, allow one exact-name pass over free RSS/search endpoints.
        # The name must come from the same captured equity identity used by
        # selection, and the existing issuer/date/source-quality gates remain
        # authoritative. Never widen the paid-provider route for this fallback.
        identity_row = company_context.get("company_identity") if matching_company_context else None
        query_ticker = str(ticker).strip().upper()
        identity_type = identity_row.get("instrument_type") if isinstance(identity_row, dict) else None
        root_type = company_context.get("instrument_type") if matching_company_context else None
        identity_stock_id = str(identity_row.get("stock_id") or "").strip() if isinstance(identity_row, dict) else ""
        search_name = official_name
        if (matching_company_context and isinstance(identity_row, dict)
                and identity_row.get("ticker") == query_ticker
                and identity_stock_id == query_ticker.split(".")[0]
                and identity_type in (None, "EQUITY") and root_type in (None, "EQUITY")
                and search_name.casefold() in {
                    str(alias).casefold() for alias in company_aliases(company_context)
                }):
            fallback_providers = set(FREE_NAME_FALLBACK_PROVIDERS)
            # Google already received this same name-only query as the second
            # provider-specific query when its bound-brand fallback applied.
            if brand_fallback == f'"{search_name}" when:{CATALYST_LOOKBACK_DAYS}d':
                fallback_providers.discard("google_news_rss")
            if provider_allowlist is not None:
                fallback_providers.intersection_update(provider_allowlist)
            name_only_query = f'"{search_name}"'
            if fallback_providers and name_only_query not in queries:
                queries.append(name_only_query)
                google_queries[name_only_query] = f'"{search_name}" when:{CATALYST_LOOKBACK_DAYS}d'
                bing_queries[name_only_query] = name_only_query
                query_provider_allowlists[name_only_query] = fallback_providers
    raw, selected = [], []
    seen_provider_queries: set[tuple[str, str]] = set()
    queries_started = 0
    cutoff = datetime.now(timezone.utc)
    _, audit = select_company_records([], data, cutoff=cutoff, lookback_days=CATALYST_LOOKBACK_DAYS)
    for query in dict.fromkeys(queries):
        if monotonic() >= deadline:
            break
        observed = []
        queries_started += 1
        provider_query_overrides = {}
        if query in google_queries:
            provider_query_overrides['google_news_rss'] = google_queries[query]
        if query in bing_queries:
            provider_query_overrides['bing_news_rss'] = bing_queries[query]
        results = await fetch_web_search_results_async(
            query, max_results=max_results, lookback_days=CATALYST_LOOKBACK_DAYS,
            require_recent=True, company_context=data, observed_records=observed, deadline=deadline,
            provider_queries=provider_query_overrides or None,
            seen_provider_queries=seen_provider_queries,
            **({'provider_allowlist': query_provider_allowlists.get(query, provider_allowlist)}
               if query_provider_allowlists.get(query, provider_allowlist) is not None else {}),
        )
        raw.extend(_news_record(result) for result in (observed or results))
        selected, audit = select_company_records(raw, data, cutoff=cutoff, lookback_days=CATALYST_LOOKBACK_DAYS)
        candidates = [SearchResult(r['title'],r['summary'],r['link'],r['source'],r['date']) for r in selected]
        if _search_quality_satisfied(candidates,max_results=max_results,query=official_name,
                                     require_recent=True,lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=cutoff):
            break
    candidates = [SearchResult(r['title'],r['summary'],r['link'],r['source'],r['date']) for r in selected]
    publisher_diagnostics = {}
    replaced_wrappers = []
    if (monotonic() < deadline and re.fullmatch(r'\d{4}\.(?:TW|TWO)', ticker)
            and not _search_quality_satisfied(candidates,max_results=max_results,query=official_name,
                                             require_recent=True,lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=cutoff)):
        from data_fetch.market_sources.ltn_stock_news import fetch_ltn_stock_news
        existing = _select_quality_results(candidates,limit=max_results,query=official_name,
                                           require_recent=True,lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=cutoff)
        missing = min(3, max(1, int(max_results)-len(existing)))
        try:
            async with asyncio.timeout(max(.001, deadline-monotonic())):
                originals = await asyncio.to_thread(fetch_ltn_stock_news, data, deadline=deadline,
                                                     diagnostics=publisher_diagnostics,max_records=missing)
        except TimeoutError:
            originals = []
            publisher_diagnostics = {'status':'deadline_exhausted','completion_not_observed':True}
        raw, replaced_wrappers = _merge_publisher_originals(raw, originals)
        selected, audit = select_company_records(raw, data, cutoff=cutoff, lookback_days=CATALYST_LOOKBACK_DAYS)
        candidates = [SearchResult(r['title'],r['summary'],r['link'],r['source'],r['date']) for r in selected]
        if replaced_wrappers:
            audit['source_record_archive'].extend(replaced_wrappers)
            audit['raw_count'] += len(replaced_wrappers)
            audit['rejected_count'] += len(replaced_wrappers)
            audit['rejected_reason_counts']['replaced_by_publisher_original'] = len(replaced_wrappers)
            audit['coverage_status'] = 'partial'
    chosen = _select_quality_results(candidates,limit=max_results,query=official_name,
                                     require_recent=True,lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=cutoff)
    links = {r.link for r in chosen}
    selected = [r for r in selected if r['link'] in links][:max_results]
    audit.update(usable_count=len(selected), quality_status='sufficient_candidates' if _search_quality_satisfied(
        chosen,max_results=max_results,query=official_name,require_recent=True,
        lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=cutoff) else 'insufficient_candidates')
    audit.update(search_budget_exhausted=monotonic() >= deadline,
                 search_queries_started=queries_started,
                 search_duration_ms=max(0, int((monotonic() - started) * 1000)),
                 search_time_budget_seconds=max(0, deadline - started))
    if diagnostics is not None:
        diagnostics.update(audit)
        if publisher_diagnostics:
            diagnostics['ltn_original_news'] = publisher_diagnostics
    return selected


async def fetch_alternative_peer_discovery_async(
    ticker: str, company_name: str, sector: str, industry: str, *,
    max_results: int = SEARCH_PEER_DISCOVERY_MAX_RESULTS,
    deadline: float | None = None, company_context: dict | None = None,
    diagnostics: dict | None = None,
) -> list[dict]:
    """Keep US compatibility; Taiwan results require a reported business relation."""
    deadline = _search_deadline(deadline)
    if re.fullmatch(r"\d{4,6}(?:\.(?:TW|TWO))?", str(ticker).strip().upper()):
        from peer_relationship_evidence import PeerRelationshipSelector
        max_results = max(1, min(8, int(max_results)))
        data = dict(company_context or {})
        data.setdefault('ticker', str(ticker).strip().upper())
        data.setdefault('company_name', company_name)
        requested = str(ticker).strip().upper()
        resolved = str(data.get('ticker') or '').strip().upper()
        if ('.' in requested and resolved != requested) or ('.' not in requested and resolved.split('.')[0] != requested):
            data.pop('company_identity', None)
        selector = PeerRelationshipSelector(data, deadline=deadline)
        try:
            if not selector.issuer:
                return []
            from company_news_queries import company_search_name
            name = company_search_name(data)
            for query in (f'{name} 同業', f'{name} 競爭對手'):
                await asyncio.sleep(0)
                if monotonic() >= deadline:
                    break
                observed = []
                selected = await fetch_web_search_results_async(
                    query, max_results=max_results, deadline=deadline,
                    company_context=data, observed_records=observed)
                keys = {(r.link, r.title) for r in selected}
                for item in observed or selected:
                    record = {'title': item.title, 'snippet': item.snippet, 'source': item.source,
                              'link': item.link, 'published_at': item.published_at,
                              'source_type': 'alternative_peer_discovery',
                              'provider': item.provider or 'alternative'}
                    await selector.consider(record, quality_selected=(item.link, item.title) in keys)
                if selector.records:
                    break
            return selector.records[:max_results]
        finally:
            if diagnostics is not None:
                diagnostics.update(selector.audit())
    name = str(company_name or ticker).strip()
    queries = [f"{name} competitors", f"{name} {str(industry or sector).strip()} peers"]
    results = []
    for query in dict.fromkeys(queries):
        if monotonic() >= deadline:
            break
        results = await fetch_web_search_results_async(query, max_results=max_results, deadline=deadline)
        if results:
            break
    return [
        {"title": result.title, "snippet": result.snippet, "source": result.source,
         "link": result.link, "source_type": "alternative_peer_discovery",
         "provider": result.provider or "alternative"}
        for result in results
    ]


async def fetch_web_search_results_async(
    query: str,
    *,
    max_results: int = SEARCH_CATALYST_MAX_RESULTS,
    lookback_days: int = 30,
    require_recent: bool = False,
    company_context: dict | None = None,
    observed_records: list | None = None,
    deadline: float | None = None,
    provider_queries: dict[str, str] | None = None,
    provider_allowlist: set[str] | None = None,
    seen_provider_queries: set[tuple[str, str]] | None = None,
) -> list[SearchResult]:
    """Run providers within one deadline, retaining evidence obtained before expiry."""
    deadline = _search_deadline(deadline)
    cleaned_query = str(query or "").strip()
    if not cleaned_query or monotonic() >= deadline:
        return []
    target_results = max(1, int(max_results))
    # Boolean syntax is not a relevance term ("OR" would match "reports").
    quality_query = re.sub(r"\bOR\b", " ", cleaned_query)

    cutoff = datetime.now(timezone.utc)
    results: list[SearchResult] = []
    async with async_client() as client:
        for provider in _provider_order():
            if provider_allowlist is not None and provider not in provider_allowlist:
                continue
            if monotonic() >= deadline:
                break
            selected = _select_quality_results(
                results,
                limit=target_results,
                query=quality_query,
                lookback_days=lookback_days,
                require_recent=require_recent, cutoff=cutoff, company_context=company_context,
            )
            if _search_quality_satisfied(
                selected,
                max_results=target_results,
                query=quality_query,
                lookback_days=lookback_days,
                require_recent=require_recent, cutoff=cutoff,
            ):
                break
            if not _provider_configured(provider):
                continue
            provider_query = (provider_queries or {}).get(provider)
            provider_query = provider_query.strip() if isinstance(provider_query, str) else ''
            request_query = provider_query or cleaned_query
            seen_key = (provider, request_query)
            if seen_provider_queries is not None and seen_key in seen_provider_queries:
                continue
            remaining = target_results - len(selected)
            request_size = _provider_request_size(remaining, max_results=target_results)
            if (provider in {'google_news_rss', 'bing_news_rss'}
                    and require_recent and company_context is not None
                    and 1 <= target_results <= 8):
                # RSS already delivers the whole feed. Preserve bounded
                # candidate headroom before issuer/date/dedup selection; the
                # accepted result limit and publisher gate remain unchanged.
                request_size = max(request_size, min(20, target_results * 3))
            remaining_seconds = deadline - monotonic()
            if remaining_seconds <= 0:
                break
            try:
                # Enforce the remaining *total* allowance in addition to the
                # endpoint callback's own cap. Caller cancellation propagates.
                async with asyncio.timeout(remaining_seconds):
                    fetched = await _fetch_provider_results(
                        client,
                        provider,
                        request_query,
                        max_results=request_size,
                        lookback_days=lookback_days,
                    )
            except Exception as exc:
                if seen_provider_queries is not None:
                    seen_provider_queries.add(seen_key)
                log_http_warning("Alternative Search", provider, exc)
                continue
            if seen_provider_queries is not None:
                seen_provider_queries.add(seen_key)
            results.extend(fetched)
            if observed_records is not None:
                observed_records.extend(fetched)

    return _select_quality_results(
        results,
        limit=target_results,
        query=quality_query,
        lookback_days=lookback_days,
        require_recent=require_recent, cutoff=cutoff, company_context=company_context,
    )


async def _fetch_provider_results(
    client,
    provider: str,
    query: str,
    *,
    max_results: int,
    lookback_days: int,
) -> list[SearchResult]:
    credential = {"brave": BRAVE_SEARCH_API_KEY, "bing": BING_SEARCH_API_KEY,
                  "tavily": TAVILY_API_KEY, "serpapi": SERPAPI_API_KEY}.get(provider, "")
    return await fetch_search_upstream(provider, credential or "", lambda: fetch_provider_results(
        client, provider, query, max_results=max_results, lookback_days=lookback_days,
    ), admission_wait_seconds=2.0)


def _provider_order() -> list[str]:
    raw = WEB_SEARCH_PROVIDER_ORDER or DEFAULT_WEB_SEARCH_PROVIDER_ORDER
    allowed = {"brave", "bing", "tavily", "serpapi", "gdelt", "google_news_rss", "bing_news_rss", "duckduckgo_news", "yahoo_rss"}
    providers = []
    for item in str(raw).replace(";", ",").split(","):
        provider = item.strip().lower().replace("-", "_")
        if provider in allowed and provider not in providers:
            providers.append(provider)
    return providers or DEFAULT_WEB_SEARCH_PROVIDER_ORDER.split(",")


def _provider_configured(provider: str) -> bool:
    if provider in {"gdelt", "google_news_rss", "bing_news_rss", "duckduckgo_news", "yahoo_rss"}:
        return True
    if provider == "brave":
        return bool(BRAVE_SEARCH_API_KEY)
    if provider == "bing":
        return bool(BING_SEARCH_API_KEY and BING_SEARCH_ENDPOINT)
    if provider == "tavily":
        return bool(TAVILY_API_KEY)
    if provider == "serpapi":
        return bool(SERPAPI_API_KEY)
    return False
