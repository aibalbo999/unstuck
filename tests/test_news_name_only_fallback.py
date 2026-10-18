from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture(autouse=True)
def disable_ltn_network(monkeypatch):
    from data_fetch.market_sources import ltn_stock_news

    monkeypatch.setattr(ltn_stock_news, "fetch_ltn_stock_news", lambda *args, **kwargs: [])


def _issuer_context():
    identity = {
        "ticker": "5314.TWO",
        "stock_id": "5314",
        "instrument_type": "EQUITY",
        "official_name": "世紀民生",
        "legal_name": "世紀民生科技股份有限公司",
        "allowed_aliases": ["世紀民生", "世紀民生科技股份有限公司", "5314.TWO", "5314"],
        "forbidden_aliases": [],
    }
    context = {
        "ticker": "5314.TWO",
        "company_name": "世紀民生",
        "company_identity": identity,
        "instrument_type": "EQUITY",
    }
    return identity, context


def _recent_results(search, hosts=8):
    published_at = datetime.now(timezone.utc).date().isoformat()
    return [
        search.SearchResult(
            title=f"世紀民生營運消息第 {index}",
            snippet="世紀民生公司營運與營收資訊",
            link=f"https://publisher{index}.example/news/{index}",
            source=f"Publisher {index}",
            published_at=published_at,
            provider="google_news_rss",
        )
        for index in range(hosts)
    ]


def test_name_only_search_runs_after_anchored_queries_remain_insufficient(monkeypatch):
    import external_search_providers as search

    identity, context = _issuer_context()
    calls = []

    async def fake_search(query, *, observed_records=None, **kwargs):
        calls.append((query, kwargs.get("provider_queries"), kwargs.get("provider_allowlist")))
        results = _recent_results(search) if len(calls) == 3 else []
        if observed_records is not None:
            observed_records.extend(results)
        return results

    monkeypatch.setattr(search, "fetch_web_search_results_async", fake_search)
    diagnostics = {}
    records = asyncio.run(search.fetch_alternative_search_catalysts_async(
        "5314.TWO", "世紀民生", identity, company_context=context, diagnostics=diagnostics,
    ))

    assert len(calls) == 3
    assert calls[2][0] == '"世紀民生"'
    assert calls[2][1] == {
        "google_news_rss": '"世紀民生" when:30d',
        "bing_news_rss": '"世紀民生"',
    }
    assert calls[2][2] == {"google_news_rss", "bing_news_rss", "duckduckgo_news", "gdelt", "yahoo_rss"}
    assert len(records) == 8
    assert diagnostics["quality_status"] == "sufficient_candidates"


def test_name_only_search_is_not_enabled_for_missing_or_mismatched_context(monkeypatch):
    import external_search_providers as search

    identity, context = _issuer_context()
    calls = []

    async def fake_search(query, *, observed_records=None, **kwargs):
        calls.append(query)
        return []

    monkeypatch.setattr(search, "fetch_web_search_results_async", fake_search)
    mismatched_context = {**context, "ticker": "5315.TWO"}
    for supplied_context in (None, mismatched_context):
        calls.clear()
        asyncio.run(search.fetch_alternative_search_catalysts_async(
            "5314.TWO", "世紀民生", identity, company_context=supplied_context,
        ))
        assert len(calls) == 2


def test_name_only_search_honors_caller_provider_allowlist(monkeypatch):
    import external_search_providers as search

    identity, context = _issuer_context()
    calls = []

    async def fake_search(query, *, observed_records=None, **kwargs):
        calls.append((query, kwargs.get("provider_allowlist")))
        results = _recent_results(search) if len(calls) == 3 else []
        if observed_records is not None:
            observed_records.extend(results)
        return results

    monkeypatch.setattr(search, "fetch_web_search_results_async", fake_search)
    records = asyncio.run(search.fetch_alternative_search_catalysts_async(
        "5314.TWO", "世紀民生", identity,
        company_context=context, provider_allowlist={"google_news_rss", "tavily"},
    ))

    assert len(records) == 8
    assert calls[2] == ('"世紀民生"', {"google_news_rss"})


def test_name_only_search_is_skipped_when_existing_queries_are_sufficient(monkeypatch):
    import external_search_providers as search

    identity, context = _issuer_context()
    calls = []

    async def fake_search(query, *, observed_records=None, **kwargs):
        calls.append(query)
        results = _recent_results(search) if len(calls) == 2 else []
        if observed_records is not None:
            observed_records.extend(results)
        return results

    monkeypatch.setattr(search, "fetch_web_search_results_async", fake_search)
    records = asyncio.run(search.fetch_alternative_search_catalysts_async(
        "5314.TWO", "世紀民生", identity, company_context=context,
    ))

    assert len(calls) == 2
    assert len(records) == 8
