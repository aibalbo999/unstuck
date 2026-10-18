"""The verified 5314 issuer name must outrank its ambiguous exchange shorthand."""

import asyncio
from datetime import datetime, timezone

import external_search_providers as search
from alternative_data_fetcher import recruitment_company_name
from company_news_queries import company_news_query
from source_content_selection import issuer_match


CONTEXT = {
    "ticker": "5314.TWO",
    "company_name": "世紀* / Myson Century, Inc.",
    "quote_type": "EQUITY",
    "exchange": "TWO",
    "company_identity": {
        "ticker": "5314.TWO",
        "stock_id": "5314",
        "official_name": "世紀*",
        "instrument_type": "EQUITY",
        "english_names": ["Myson Century, Inc."],
    },
}


def test_verified_search_anchor_replaces_ambiguous_shorthand():
    assert company_news_query(CONTEXT) == '"世紀民生" 5314 when:30d'
    assert recruitment_company_name(CONTEXT["company_name"], CONTEXT) == "世紀民生"


def test_full_issuer_name_is_admitted_but_ambiguous_shorthand_alone_is_not():
    stamp = datetime.now(timezone.utc).isoformat()
    assert issuer_match({"title": "世紀民生發表新產品", "date": stamp}, CONTEXT) == "世紀民生"
    assert issuer_match({"title": "世紀之星河輪推出新航線", "date": stamp}, CONTEXT) is None
    assert issuer_match({"title": "[標的] 5314 世紀除權", "date": stamp}, CONTEXT)


def test_peer_search_uses_full_issuer_name_without_relaxing_selection(monkeypatch):
    queries = []

    async def empty(query, **_kwargs):
        queries.append(query)
        return []

    monkeypatch.setattr(search, "fetch_web_search_results_async", empty)
    result = asyncio.run(search.fetch_alternative_peer_discovery_async(
        "5314.TWO", CONTEXT["company_name"], "Technology", "Semiconductors",
        company_context=CONTEXT,
    ))
    assert result == []
    assert queries == ["世紀民生 同業", "世紀民生 競爭對手"]


def test_catalyst_search_preserves_full_primary_issuer_and_explicit_engine_queries(monkeypatch):
    queries = []

    async def empty(query, **_kwargs):
        queries.append((query, _kwargs.get('provider_queries')))
        return []

    monkeypatch.setattr(search, "fetch_web_search_results_async", empty)
    result = asyncio.run(search.fetch_alternative_search_catalysts_async(
        "5314.TWO", CONTEXT["company_name"], CONTEXT["company_identity"],
    ))
    assert result == []
    assert [query for query, _providers in queries] == [
        "世紀民生 (法說會 OR 展望 OR 營收 OR earnings OR outlook OR revenue)",
        '"世紀*" 5314',
    ]
    assert queries[0][1] == {'google_news_rss': '"世紀民生" 5314 when:30d '
                            '(法說會 OR 展望 OR 營收 OR earnings OR outlook OR revenue)',
                            'bing_news_rss': '"世紀" 5314'}
    assert queries[1][1] == {'google_news_rss': '"世紀" 5314 when:30d', 'bing_news_rss': '"世紀" 5314'}
