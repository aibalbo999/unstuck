"""Actual RSS regression: retain recent company evidence within the same budget."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import external_search_providers as search
from external_search_payloads import parse_news_rss_payload
from source_content_selection import select_company_records

FIXTURES = ROOT / 'tests/fixtures/source_acquisition'
NOW = datetime(2026, 9, 27, 9, 16, 0, tzinfo=timezone.utc)
DATA = {'ticker': '5314.TWO', 'company_name': '世紀* / Myson Century, Inc.',
        'company_identity': {'official_name': '世紀*', 'allowed_aliases': ['世紀*', 'Myson Century, Inc.']}}
TOPICS = '(法說會 OR 展望 OR 營收 OR earnings OR outlook OR revenue)'
EMPTY = '<rss><channel/></rss>'


@pytest.fixture(autouse=True)
def isolated_search(monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(search, 'datetime', FrozenDatetime)
    monkeypatch.setattr(search, 'WEB_SEARCH_PROVIDER_ORDER', 'google_news_rss')
    async def guarded_fake(_provider, _credential, callback, **kwargs):
        assert kwargs['admission_wait_seconds'] == 2.0
        return await callback()
    monkeypatch.setattr(search, 'fetch_search_upstream', guarded_fake)


def records(xml):
    return [{'date': r.published_at, 'title': r.title, 'summary': r.snippet,
             'link': r.link, 'source': r.source}
            for r in parse_news_rss_payload(xml, provider='google_news_rss', fallback_source='Google News RSS')[:8]]


def install_client(monkeypatch, payload_for_query):
    calls = []
    class Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return None
        async def get(self, url, *, params):
            calls.append(dict(params))
            return httpx.Response(200, text=payload_for_query(params['q']), request=httpx.Request('GET', url))
    monkeypatch.setattr(search, 'async_client', Client)
    return calls


def test_real_rss_recovers_eight_recent_records_in_one_existing_query_budget(monkeypatch):
    old = (FIXTURES / 'news5314_current_20260927.xml').read_text()
    recent = (FIXTURES / 'news5314_recent_20260927.xml').read_text()
    old_selected, old_audit = select_company_records(records(old), DATA, cutoff=NOW)
    assert len(old_selected) == 2 and old_audit['rejected_reason_counts'] == {'historical': 6}
    expected_query = f'"世紀" 5314 when:30d {TOPICS}'
    calls = install_client(monkeypatch, lambda query: recent if query == expected_query else old if TOPICS in query else EMPTY)
    audit = {}
    selected = asyncio.run(search.fetch_alternative_search_catalysts_async(
        DATA['ticker'], DATA['company_name'], DATA['company_identity'], max_results=8, diagnostics=audit))
    assert len(selected) == 8
    assert len(calls) == 1 and calls[0]['q'] == expected_query
    assert audit['raw_count'] == 8 and audit['usable_count'] == 8
    assert audit['rejected_count'] == 0 and audit['source_record_archive'] == []
    assert audit['quality_status'] == 'sufficient_candidates'
    assert len({row['source'] for row in selected}) >= 3
    assert all(row['issuer_match'] and row['content_coverage'] == 'headline_or_snippet' for row in selected)


def test_google_override_does_not_change_other_provider_queries(monkeypatch):
    monkeypatch.setattr(search, 'WEB_SEARCH_PROVIDER_ORDER', 'tavily,google_news_rss,yahoo_rss')
    monkeypatch.setattr(search, '_provider_configured', lambda _name: True)
    calls = []
    async def provider(_client, name, query, **_kwargs):
        calls.append((name, query))
        return []
    monkeypatch.setattr(search, '_fetch_provider_results', provider)
    install_client(monkeypatch, lambda _q: EMPTY)
    overrides = {'google_news_rss': 'company 5314 when:30d'}
    assert asyncio.run(search.fetch_web_search_results_async('original topic', provider_queries=overrides)) == []
    assert calls == [('tavily', 'original topic'), ('google_news_rss', overrides['google_news_rss']), ('yahoo_rss', 'original topic')]
    assert overrides == {'google_news_rss': 'company 5314 when:30d'}


@pytest.mark.parametrize('ticker', ['5314.TW', '5314.TWO'])
def test_tw_queries_remain_bounded_and_use_configured_lookback(monkeypatch, ticker):
    monkeypatch.setattr(search, 'CATALYST_LOOKBACK_DAYS', 7)
    calls = install_client(monkeypatch, lambda _q: EMPTY)
    result = asyncio.run(search.fetch_alternative_search_catalysts_async(
        ticker, DATA['company_name'], DATA['company_identity'], max_results=8))
    assert result == [] and len(calls) == 2
    assert [row['q'] for row in calls] == [f'"世紀" 5314 when:7d {TOPICS}', '"世紀" 5314 when:7d']


def test_us_catalysts_keep_existing_queries(monkeypatch):
    calls = install_client(monkeypatch, lambda _q: EMPTY)
    asyncio.run(search.fetch_alternative_search_catalysts_async('AAPL', 'Apple', {'official_name': 'Apple'}, max_results=8))
    assert [row['q'] for row in calls] == [f'Apple {TOPICS}', '"Apple" AAPL']


def test_explicitly_unrestricted_peer_query_has_no_implicit_time_or_ticker_rewrite(monkeypatch):
    calls = install_client(monkeypatch, lambda _q: EMPTY)
    assert asyncio.run(search.fetch_web_search_results_async('雙鴻 同業', require_recent=False)) == []
    assert [row['q'] for row in calls] == ['雙鴻 同業']


def test_upstream_time_hint_does_not_bypass_local_evidence_gates(monkeypatch):
    samples = [('世紀*(5314) 舊聞', 'Tue, 01 Jan 2019 00:00:00 GMT'),
               ('世紀*(5314) 未來消息', 'Mon, 28 Sep 2026 00:00:00 GMT'),
               ('無關公司營收', 'Fri, 25 Sep 2026 00:00:00 GMT'),
               ('世紀*(5314) 未知日期', '')]
    xml = '<rss><channel>' + ''.join(
        f'<item><title>{title}</title><link>https://example.test/{i}</link><pubDate>{date}</pubDate></item>'
        for i, (title, date) in enumerate(samples)) + '</channel></rss>'
    calls = install_client(monkeypatch, lambda _q: xml)
    audit = {}
    assert asyncio.run(search.fetch_alternative_search_catalysts_async(
        DATA['ticker'], DATA['company_name'], DATA['company_identity'], diagnostics=audit)) == []
    assert len(calls) == 2 and all('when:30d' in row['q'] for row in calls)
    assert set(audit['rejected_reason_counts']) == {'historical', 'future', 'issuer_unverified', 'unknown_date'}
    assert audit['rejected_count'] == len(audit['source_record_archive']) == 8
    assert audit['coverage_status'] == 'partial' and audit['quality_status'] == 'insufficient_candidates'


def test_expired_total_deadline_sends_no_query(monkeypatch):
    calls = install_client(monkeypatch, lambda _q: EMPTY)
    assert asyncio.run(search.fetch_alternative_search_catalysts_async(
        DATA['ticker'], DATA['company_name'], DATA['company_identity'], deadline=search.monotonic() - 1)) == []
    assert calls == []


@pytest.mark.parametrize('overrides', [{}, {'google_news_rss': ''}, {'google_news_rss': None}, {'unknown_engine': 'unused'}])
def test_empty_or_unused_override_keeps_original_route_and_query(monkeypatch, overrides):
    calls = install_client(monkeypatch, lambda _q: EMPTY)
    assert asyncio.run(search.fetch_web_search_results_async('original', provider_queries=overrides)) == []
    assert [row['q'] for row in calls] == ['original']


def test_cancellation_stops_before_the_second_query(monkeypatch):
    seen = []
    async def cancel(_client, provider, query, **kwargs):
        seen.append((provider, query))
        raise asyncio.CancelledError()
    install_client(monkeypatch, lambda _q: EMPTY)
    monkeypatch.setattr(search, '_fetch_provider_results', cancel)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(search.fetch_alternative_search_catalysts_async(
            DATA['ticker'], DATA['company_name'], DATA['company_identity']))
    assert seen == [('google_news_rss', f'"世紀" 5314 when:30d {TOPICS}')]
