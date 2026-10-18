"""Catalyst topics are alternatives while the company stays mandatory."""
import asyncio
from datetime import datetime, timedelta, timezone


def test_initial_query_can_match_a_company_article_with_one_catalyst_topic(monkeypatch):
    import external_search_providers as search
    calls = []

    async def acquire(query, **options):
        calls.append((query, options))
        # The article has a revenue update, not every earnings/outlook synonym.
        assert query.startswith("聯強 ")
        assert "(法說會 OR 展望 OR 營收 OR earnings OR outlook OR revenue)" in query
        assert "2347.TW" not in query
        headlines = ("聯強公布營收", "聯強公布單月營收", "聯強更新營收展望")
        return [search.SearchResult(title=headline, snippet="營收公告",
            link=f"https://example{index}.com/revenue", source=f"Example Wire {index}",
            published_at="2026-09-24", provider="google_news_rss")
            for index, headline in enumerate(headlines)]

    monkeypatch.setattr(search, "fetch_web_search_results_async", acquire)
    records = asyncio.run(search.fetch_alternative_search_catalysts_async("2347.TW", "聯強", {}, max_results=3))
    assert len(calls) == 1 and len(records) == 3
    options = calls[0][1]
    assert options["max_results"] == 3
    assert options["lookback_days"] == search.CATALYST_LOOKBACK_DAYS
    assert options["require_recent"] is True
    assert options["company_context"]["ticker"] == "2347.TW"
    assert options["deadline"] > 0


def test_empty_initial_query_retains_bounded_company_fallback_and_recency(monkeypatch):
    import external_search_providers as search
    calls = []

    async def acquire(query, **options):
        calls.append((query, options))
        return []

    monkeypatch.setattr(search, "fetch_web_search_results_async", acquire)
    assert asyncio.run(search.fetch_alternative_search_catalysts_async("2330.TW", "TSMC", {"official_name": "台積電"})) == []
    assert len(calls) == 2
    assert calls[0][0].startswith("台積電 (") and " OR " in calls[0][0]
    assert calls[1][0] == '"台積電" 2330'
    assert all(options["require_recent"] is True for _, options in calls)


def test_identical_provider_query_is_not_repeated_across_catalyst_passes(monkeypatch):
    import external_search_providers as search
    from data_fetch.market_sources import ltn_stock_news

    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    async def fetch(_client, provider, query, **_options):
        calls.append((provider, query))
        return []

    monkeypatch.setattr(search, "_provider_order", lambda: ["bing_news_rss"])
    monkeypatch.setattr(search, "_provider_configured", lambda _provider: True)
    monkeypatch.setattr(search, "async_client", lambda: FakeClient())
    monkeypatch.setattr(search, "_fetch_provider_results", fetch)
    monkeypatch.setattr(ltn_stock_news, "fetch_ltn_stock_news", lambda *_args, **_kwargs: [])

    identity = {
        "ticker": "2330.TW", "stock_id": "2330", "official_name": "台積電",
        "instrument_type": "EQUITY", "allowed_aliases": ["台積電"],
    }
    result = asyncio.run(search.fetch_alternative_search_catalysts_async(
        "2330.TW", "台積電", identity, max_results=3,
        company_context={"ticker": "2330.TW", "company_name": "台積電",
                         "instrument_type": "EQUITY", "company_identity": identity},
    ))

    assert result == []
    assert calls == [
        ("bing_news_rss", '"台積電" 2330'),
        ("bing_news_rss", '"台積電"'),
    ]


def test_boolean_query_preserves_recency_and_distinct_publisher_gate(monkeypatch):
    import external_search_providers as search
    calls, quality_queries = [], []
    current = datetime.now(timezone.utc)
    recent = current.date().isoformat()
    old = (current - timedelta(days=60)).date().isoformat()
    real_gate = search._search_quality_satisfied

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    async def fetch(client, provider, query, **options):
        calls.append(provider)
        assert " OR " in query  # Providers still receive valid query syntax.
        if len(calls) == 1:
            return [search.SearchResult(title="聯強營收公告", snippet="revenue",
                link=f"https://first.example/{i}", source="First publisher",
                published_at=recent, provider=provider) for i in range(2)] + [
                search.SearchResult(title="聯強舊資料", snippet="outlook",
                    link="https://old.example/news", source="Old publisher",
                    published_at=old, provider=provider)]
        return [search.SearchResult(title="聯強展望", snippet="outlook",
            link="https://second.example/news", source="Second publisher",
            published_at=recent, provider=provider)]

    def check(records, **options):
        quality_queries.append(options["query"])
        return real_gate(records, **options)

    monkeypatch.setattr(search, "async_client", Client)
    monkeypatch.setattr(search, "_provider_order", lambda: ["google_news_rss", "gdelt", "yahoo_rss"])
    monkeypatch.setattr(search, "_fetch_provider_results", fetch)
    monkeypatch.setattr(search, "_search_quality_satisfied", check)
    records = asyncio.run(search.fetch_alternative_search_catalysts_async("2347.TW", "聯強", {}, max_results=2))
    assert calls == ["google_news_rss", "gdelt"]
    assert {record["source"] for record in records} == {"First publisher", "Second publisher"}
    assert all(" OR " not in query for query in quality_queries)
