from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_fetch import FetchRequest, ProviderRegistry  # noqa: E402


def test_alternative_search_uses_free_sources_for_catalysts(monkeypatch):
    import external_search_providers as search

    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss><channel>
      <item>
        <title>TSMC supplier outlook improves</title>
        <link>https://news.example/yahoo</link>
        <description>AI demand supports revenue.</description>
        <pubDate>Sun, 28 Jun 2026 00:00:00 GMT</pubDate>
        <source>Yahoo News</source>
      </item>
    </channel></rss>
    """

    class FakeResponse:
        text = rss

        def raise_for_status(self):
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return FakeResponse()

    async def fake_json_get(_client, url, _params, headers=None):
        assert headers is None
        assert "gdeltproject.org" in url
        return {
            "articles": [
                {
                    "title": "TSMC earnings call points to AI demand",
                    "url": "https://news.example/gdelt",
                    "domain": "news.example",
                    "seendate": "20260628T010000Z",
                }
            ]
        }

    monkeypatch.setattr(search, "WEB_SEARCH_PROVIDER_ORDER", "gdelt,yahoo_rss")
    monkeypatch.setattr(search, "async_client", lambda: FakeClient())
    monkeypatch.setattr(search.httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    monkeypatch.setattr(search, "_async_json_get", fake_json_get)

    records = asyncio.run(search.fetch_alternative_search_catalysts_async("2330.TW", "台積電", {}, max_results=2))

    assert [record["source_type"] for record in records] == ["gdelt_search", "yahoo_rss_search"]
    assert records[0]["title"] == "TSMC earnings call points to AI demand"
    assert records[1]["source"] == "Yahoo News"


def test_alternative_peer_discovery_uses_search_results(monkeypatch):
    import external_search_providers as search

    async def fake_search(query, *, max_results=8, lookback_days=30):
        assert "global competitors" in query
        assert max_results == 8
        return [
            search.SearchResult(
                title="Power peers include Eaton and Schneider",
                snippet="Delta Electronics competes with global power management peers.",
                link="https://news.example/peers",
                source="Brave Search",
                published_at="",
                provider="brave",
            )
        ]

    monkeypatch.setattr(search, "fetch_web_search_results_async", fake_search)

    records = asyncio.run(
        search.fetch_alternative_peer_discovery_async("2308.TW", "台達電", "Technology", "Power supply")
    )

    assert records == [
        {
            "title": "Power peers include Eaton and Schneider",
            "snippet": "Delta Electronics competes with global power management peers.",
            "source": "Brave Search",
            "link": "https://news.example/peers",
            "source_type": "alternative_peer_discovery",
            "provider": "brave",
        }
    ]


def test_google_news_rss_is_available_as_free_fallback(monkeypatch):
    import external_search_providers as search

    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss><channel>
      <item>
        <title>TSMC revenue outlook in focus</title>
        <link>https://news.example/google-news</link>
        <description>Investors watch AI demand.</description>
        <pubDate>Sun, 28 Jun 2026 00:00:00 GMT</pubDate>
        <source>Example Wire</source>
      </item>
    </channel></rss>
    """

    class FakeResponse:
        text = rss

        def raise_for_status(self):
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, params=None):
            assert "news.google.com/rss/search" in url
            assert params["q"]
            return FakeResponse()

    monkeypatch.setattr(search, "WEB_SEARCH_PROVIDER_ORDER", "google_news_rss")
    monkeypatch.setattr(search, "async_client", lambda: FakeClient())

    records = asyncio.run(search.fetch_alternative_search_catalysts_async("2330.TW", "台積電", {}))

    assert records[0]["source_type"] == "google_news_rss_search"
    assert records[0]["source"] == "Example Wire"


def test_catalyst_search_retries_with_broader_company_query(monkeypatch):
    import external_search_providers as search

    calls = []

    async def fake_search(query, *, max_results=8, lookback_days=30):
        assert max_results == 8
        calls.append(query)
        if len(calls) == 1:
            return []
        return [
            search.SearchResult(
                title="TSMC reports monthly revenue",
                snippet="Company update",
                link="https://news.example/revenue",
                source="Google News RSS",
                published_at="",
                provider="google_news_rss",
            )
        ]

    monkeypatch.setattr(search, "fetch_web_search_results_async", fake_search)

    records = asyncio.run(search.fetch_alternative_search_catalysts_async("2330.TW", "台積電", {}))

    assert len(calls) == 2
    assert "earnings outlook" in calls[0]
    assert calls[1] == "台積電 2330.TW"
    assert records[0]["title"] == "TSMC reports monthly revenue"


def test_web_search_expands_when_first_provider_lacks_source_diversity(monkeypatch):
    import external_search_providers as search

    calls = []
    requested_sizes = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    async def fake_fetch(_client, provider, _query, *, max_results, lookback_days):
        calls.append(provider)
        requested_sizes[provider] = max_results
        if provider == "tavily":
            return [
                search.SearchResult(
                    title=f"台積電展望 same-source item {index}",
                    snippet="台積電 revenue outlook",
                    link=f"https://same.example/news/{index}",
                    source="Same Source",
                    provider="tavily",
                )
                for index in range(max_results)
            ]
        if provider == "google_news_rss":
            return [
                search.SearchResult(
                    title="台積電展望 fresh independent item",
                    snippet="台積電 revenue outlook",
                    link="https://fresh.example/news",
                    source="Fresh Source",
                    provider="google_news_rss",
                )
            ]
        return []

    monkeypatch.setattr(search, "WEB_SEARCH_PROVIDER_ORDER", "tavily,google_news_rss,brave")
    monkeypatch.setattr(search, "async_client", lambda: FakeClient())
    monkeypatch.setattr(search, "_provider_configured", lambda provider: provider in {"tavily", "google_news_rss"})
    monkeypatch.setattr(search, "_fetch_provider_results", fake_fetch)

    records = asyncio.run(search.fetch_web_search_results_async("台積電 展望", max_results=5))

    assert calls == ["tavily", "google_news_rss"]
    assert requested_sizes["google_news_rss"] == 3
    assert len(records) == 5
    assert "fresh.example" in {search._result_source_key(record) for record in records}


def test_web_search_expands_when_first_provider_lacks_relevant_results(monkeypatch):
    import external_search_providers as search

    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    async def fake_fetch(_client, provider, _query, *, max_results, lookback_days):
        calls.append(provider)
        if provider == "tavily":
            return [
                search.SearchResult(
                    title=f"Unrelated sports item {index}",
                    snippet="stadium match recap",
                    link=f"https://sports-{index}.example/story",
                    source=f"Sports Source {index}",
                    provider="tavily",
                )
                for index in range(max_results)
            ]
        return [
            search.SearchResult(
                title=f"台積電展望 relevant item {index}",
                snippet="台積電 revenue outlook and earnings catalyst",
                link=f"https://finance-{index}.example/news",
                source=f"Finance Source {index}",
                provider=provider,
            )
            for index in range(max_results)
        ]

    monkeypatch.setattr(search, "WEB_SEARCH_PROVIDER_ORDER", "tavily,google_news_rss")
    monkeypatch.setattr(search, "async_client", lambda: FakeClient())
    monkeypatch.setattr(search, "_provider_configured", lambda provider: True)
    monkeypatch.setattr(search, "_fetch_provider_results", fake_fetch)

    records = asyncio.run(search.fetch_web_search_results_async("台積電 展望", max_results=5))

    assert calls == ["tavily", "google_news_rss"]
    assert records
    assert all("sports" not in record.link for record in records[:3])


def test_web_search_stops_when_first_provider_is_full_and_diverse(monkeypatch):
    import external_search_providers as search

    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    async def fake_fetch(_client, provider, _query, *, max_results, lookback_days):
        calls.append(provider)
        return [
            search.SearchResult(
                title=f"台積電展望 diverse item {index}",
                snippet="台積電 revenue outlook",
                link=f"https://source-{index}.example/news",
                source=f"Source {index}",
                provider=provider,
            )
            for index in range(max_results)
        ]

    monkeypatch.setattr(search, "WEB_SEARCH_PROVIDER_ORDER", "tavily,google_news_rss")
    monkeypatch.setattr(search, "async_client", lambda: FakeClient())
    monkeypatch.setattr(search, "_provider_configured", lambda provider: True)
    monkeypatch.setattr(search, "_fetch_provider_results", fake_fetch)

    records = asyncio.run(search.fetch_web_search_results_async("台積電 展望", max_results=5))

    assert calls == ["tavily"]
    assert len(records) == 5


def test_custom_search_json_api_providers_are_not_registered():
    names = ProviderRegistry().provider_names(FetchRequest.from_ticker("2330.TW"), source="recent_catalysts")
    peer_names = ProviderRegistry().provider_names(FetchRequest.from_ticker("2330.TW"), source="peer_discovery")

    assert "Alternative Search" in names
    assert "Google Search" not in names
    assert "Alternative Search" in peer_names
    assert "Google Search" not in peer_names


def test_default_search_provider_order_excludes_retired_bing(monkeypatch):
    import external_search_providers as search

    monkeypatch.setattr(search, "WEB_SEARCH_PROVIDER_ORDER", "")

    assert search._provider_order() == [
        "tavily",
        "serpapi",
        "google_news_rss",
        "gdelt",
        "yahoo_rss",
        "brave",
    ]
    assert "bing" not in search._provider_order()


def test_bing_requires_explicit_provider_order_opt_in(monkeypatch):
    import external_search_providers as search

    monkeypatch.setattr(search, "WEB_SEARCH_PROVIDER_ORDER", "bing,google_news_rss")

    assert search._provider_order() == ["bing", "google_news_rss"]


def test_alternative_search_provider_fetches_catalysts(monkeypatch):
    from data_fetch.enrichment_providers import AlternativeSearchProvider

    async def fake_fetch(ticker, company_name, identity):
        assert ticker == "2330.TW"
        assert company_name == "台積電"
        assert identity == {"official_name": "Taiwan Semiconductor"}
        return [{"title": "Alternative catalyst"}]

    monkeypatch.setattr("external_search_providers.fetch_alternative_search_catalysts_async", fake_fetch)

    result = asyncio.run(
        AlternativeSearchProvider().fetch_async(
            FetchRequest.from_ticker("2330.TW"),
            {
                "data": {
                    "ticker": "2330.TW",
                    "company_name": "台積電",
                    "company_identity": {"official_name": "Taiwan Semiconductor"},
                }
            },
        )
    )

    assert result.provider == "Alternative Search"
    assert result.status == "success"
    assert result.value == [{"title": "Alternative catalyst"}]


def test_alternative_peer_provider_fetches_peer_discovery(monkeypatch):
    from data_fetch.enrichment_providers import AlternativePeerDiscoveryProvider

    async def fake_fetch(ticker, company_name, sector, industry):
        assert ticker == "2308.TW"
        assert company_name == "台達電"
        assert sector == "Technology"
        assert industry == "Power"
        return [{"title": "Alternative peer"}]

    monkeypatch.setattr("external_search_providers.fetch_alternative_peer_discovery_async", fake_fetch)

    result = asyncio.run(
        AlternativePeerDiscoveryProvider().fetch_async(
            FetchRequest.from_ticker("2308.TW"),
            {
                "data": {
                    "ticker": "2308.TW",
                    "company_name": "台達電",
                    "sector": "Technology",
                    "industry": "Power",
                }
            },
        )
    )

    assert result.provider == "Alternative Search"
    assert result.status == "success"
    assert result.value == [{"title": "Alternative peer"}]


def test_legacy_optional_enrichment_merges_alternative_search(monkeypatch):
    import data_fetch.optional_enrichment as optional_enrichment

    async def empty(*_args, **_kwargs):
        return []

    async def alternative_catalysts(*_args, **_kwargs):
        return [{"title": "Alternative catalyst", "link": "https://example.test/catalyst"}]

    async def alternative_peers(*_args, **_kwargs):
        return [{"title": "Alternative peer", "link": "https://example.test/peer"}]

    monkeypatch.setattr(optional_enrichment, "fetch_alternative_search_catalysts_async", alternative_catalysts)
    monkeypatch.setattr(optional_enrichment, "fetch_alternative_peer_discovery_async", alternative_peers)
    monkeypatch.setattr(optional_enrichment, "fetch_fmp_news_catalysts_async", empty)
    monkeypatch.setattr(optional_enrichment, "cache_financial_payload", lambda *_args, **_kwargs: None)

    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "company_identity": {},
        "sector": "Technology",
        "industry": "Semiconductor",
        "source_audit": [],
        "source_freshness": {},
    }

    result = asyncio.run(optional_enrichment.enrich_optional_http_async("2330", data))

    assert result["recent_catalysts"][0]["title"] == "Alternative catalyst"
    assert result["peer_discovery_results"][0]["title"] == "Alternative peer"
    assert {"Alternative Search", "Recent catalysts providers", "Peer discovery providers"} <= {
        entry["provider"] for entry in result["source_audit"]
    }


def test_optional_http_bundle_excludes_custom_search_json_api(monkeypatch):
    import external_data_clients as clients

    async def empty(*_args, **_kwargs):
        return []

    monkeypatch.setattr(clients, "fetch_alternative_search_catalysts_async", empty)
    monkeypatch.setattr(clients, "fetch_alternative_peer_discovery_async", empty)
    monkeypatch.setattr(clients, "fetch_fmp_news_catalysts_async", empty)

    bundle = asyncio.run(
        clients.fetch_optional_http_data_bundle(
            "2330.TW",
            "台積電",
            {"official_name": "台積電"},
            sector="Technology",
            industry="Semiconductor",
        )
    )

    assert "google_catalysts" not in bundle
    assert "google_peer_discovery" not in bundle
