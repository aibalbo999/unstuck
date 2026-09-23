from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

import external_search_providers as search
import external_search_provider_clients as clients
import official_financials_mops_conference as conference
import news_fetchers


@pytest.fixture(autouse=True)
def isolated_cooldowns(monkeypatch):
    import search_provider_runtime as runtime
    state = {}
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: None)
    return state


def test_peer_discovery_retries_with_short_staged_queries(monkeypatch):
    queries = []

    async def fetch(query, **kwargs):
        queries.append(query)
        return []

    monkeypatch.setattr(search, 'fetch_web_search_results_async', fetch)
    assert asyncio.run(search.fetch_alternative_peer_discovery_async('2308.TW', '台達電', 'Technology', 'Power supply')) == []
    assert queries == ['台達電 competitors', '台達電 Power supply peers']


def test_mops_security_page_is_explicit_failure_not_no_announcements(monkeypatch):
    monkeypatch.setattr(conference, '_http_post', lambda *a, **k: SimpleNamespace(text='FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED.', status_code=200))
    with pytest.raises(Exception) as caught:
        conference.fetch_mops_investor_conference_events('2330.TW', year=2026)
    assert getattr(caught.value, 'error_kind', None) == 'access_denied'
    assert getattr(caught.value, 'retryable', None) is False
    assert '2330' not in str(caught.value)  # bounded shape diagnostic, no response echo


def test_mops_unknown_html_is_parse_failure(monkeypatch):
    monkeypatch.setattr(conference, '_http_post', lambda *a, **k: SimpleNamespace(text='<html><body>new page layout</body></html>', status_code=200))
    with pytest.raises(Exception) as caught:
        conference.fetch_mops_investor_conference_events('2330.TW', year=2026)
    assert getattr(caught.value, 'error_kind', None) == 'parse_error'


def test_yahoo_500_is_not_valid_empty(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **k):
            return httpx.Response(500, request=httpx.Request('GET', clients.YAHOO_NEWS_RSS_URL))
    monkeypatch.setattr(clients.httpx, 'AsyncClient', lambda **k: Client())
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(clients.fetch_provider_results(None, 'yahoo_rss', '台積電', max_results=2, lookback_days=30))


@pytest.mark.parametrize('ticker', ['2330.TW', '2330.TWO'])
def test_ptt_normalizes_taiwan_symbol_and_avoids_partial_number(ticker, monkeypatch):
    html = ''.join(f'<div class="r-ent"><div class="title"><a href="/bbs/Stock/{i}.html">{title}</a></div><div class="date">9/23</div></div>' for i, title in enumerate(['[新聞] 2330 法說會', '[新聞] 12330 金額']))
    monkeypatch.setattr(news_fetchers, 'sync_get', lambda *a, **k: SimpleNamespace(text=html))
    records = news_fetchers.fetch_ptt_stock_sentiment(ticker)
    assert [r['title'] for r in records] == ['[新聞] 2330 法說會']


def test_rate_limit_persists_across_scopes_and_recovers_after_deadline(monkeypatch):
    import search_provider_runtime as runtime
    now = [1000.0]
    monkeypatch.setattr(runtime.time, 'time', lambda: now[0])
    monkeypatch.setattr(runtime, 'provider_circuit_state', lambda provider: {})
    called = []
    observations = []
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(entries))

    async def limited():
        called.append('bad')
        r = httpx.Response(429, headers={'Retry-After': '600'}, request=httpx.Request('GET', 'https://example.test/?api_key=never-save'))
        r.raise_for_status()

    async def working():
        called.append('ok')
        return [1]

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(runtime.fetch_search_upstream('tavily', 'key-one', limited))
    assert asyncio.run(runtime.fetch_search_upstream('tavily', 'key-one', working)) == []
    assert asyncio.run(runtime.fetch_search_upstream('tavily', 'key-two', working)) == [1]
    now[0] = 1601.0
    assert asyncio.run(runtime.fetch_search_upstream('tavily', 'key-one', working)) == [1]
    assert called == ['bad', 'ok', 'ok']
    assert [e['event_kind'] for e in observations] == ['http_attempt', 'local_block', 'http_attempt', 'http_attempt']
    assert all('never-save' not in str(e) and 'key-one' not in str(e) for e in observations)


def test_unknown_432_is_not_declared_quota(monkeypatch):
    import search_provider_runtime as runtime
    response = httpx.Response(432, request=httpx.Request('POST', 'https://example.test'))
    exc = httpx.HTTPStatusError('rejected', request=response.request, response=response)
    state = runtime.remember_failure(runtime.scope_key('tavily', 'key'), exc)
    assert state['error_kind'] == 'provider_rejected'
    assert state['http_status'] == 432


def test_conference_rejection_does_not_probe_previous_year(monkeypatch):
    import data_fetch.earnings_call_fetcher as earnings
    import official_financials
    import search_provider_runtime as runtime
    calls = []
    def rejected(ticker, **kwargs):
        calls.append(kwargs)
        raise runtime.SourceResponseError('access_denied', status_code=200)
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', rejected)
    import official_financials_webpro_conference as webpro
    monkeypatch.setattr(webpro, 'fetch_webpro_conference_context', lambda *a, **k: (_ for _ in ()).throw(runtime.SourceResponseError('access_denied')))
    with pytest.raises(runtime.SourceResponseError):
        earnings.fetch_free_earnings_call_context('2330.TW')
    assert len(calls) == 1


def test_mops_explicit_no_data_is_valid_empty(monkeypatch):
    monkeypatch.setattr(conference, '_http_post', lambda *a, **k: SimpleNamespace(text='<html>查無資料</html>', status_code=200))
    assert conference.fetch_mops_investor_conference_events('2330.TW', year=2026) == []


def test_conference_parse_failure_not_retried_by_resilience(monkeypatch):
    import provider_resilience as resilience
    import search_provider_runtime as runtime
    calls = []
    def parse_failure():
        calls.append(1)
        raise runtime.SourceResponseError('parse_error')
    monkeypatch.setattr(resilience, '_check_provider_state', lambda *a: None)
    monkeypatch.setattr(resilience, 'enforce_provider_throttle', lambda *a: None)
    with pytest.raises(runtime.SourceResponseError):
        resilience.call_provider_with_resilience('MOPS test', parse_failure)
    assert calls == [1]


def test_search_malformed_payload_cannot_become_empty(monkeypatch):
    async def invalid(*a, **k): return {'unexpected': 'changed schema'}
    monkeypatch.setattr(clients, '_async_json_get', invalid)
    with pytest.raises(Exception) as caught:
        asyncio.run(clients.fetch_provider_results(None, 'serpapi', 'test', max_results=2, lookback_days=30))
    assert getattr(caught.value, 'error_kind', '') == 'parse_error'


def test_cooldown_survives_sqlite_backend_reopen(tmp_path, monkeypatch):
    import search_provider_runtime as runtime
    from cache_backends import SqliteCacheBackend
    path = tmp_path / 'isolated.sqlite3'
    first = SqliteCacheBackend(str(path))
    monkeypatch.setattr(runtime, 'set_cache_json', first.set_json)
    response = httpx.Response(403, request=httpx.Request('GET', 'https://example.test'))
    key = runtime.scope_key('brave', 'credential')
    runtime.remember_failure(key, httpx.HTTPStatusError('rejected', request=response.request, response=response))
    first.close()
    second = SqliteCacheBackend(str(path))
    monkeypatch.setattr(runtime, 'get_cache_json', second.get_json)
    try:
        state = runtime.cooldown_state(key)
        assert state['error_kind'] == 'access_denied'
        assert state['http_status'] == 403
    finally:
        second.close()


def test_ptt_no_results_and_transport_failure_have_distinct_observations(monkeypatch):
    import search_provider_runtime as runtime
    observations = []
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(entries))
    monkeypatch.setattr(news_fetchers, 'sync_get', lambda *a, **k: SimpleNamespace(text='<html><div class="r-ent"></div></html>', status_code=200))
    assert news_fetchers.fetch_ptt_stock_sentiment('2330.TW') == []
    def fail(*a, **k): raise httpx.ConnectTimeout('endpoint timed out')
    monkeypatch.setattr(news_fetchers, 'sync_get', fail)
    assert news_fetchers.fetch_ptt_stock_sentiment('2330.TW') == []
    assert [(e['outcome'], e['status']) for e in observations] == [('valid_empty', 'degraded_enrichment'), ('failure', 'unavailable')]
    assert observations[1]['error_kind'] == 'timeout'


def test_telemetry_failure_preserves_results(monkeypatch):
    import search_provider_runtime as runtime
    monkeypatch.setattr(runtime, 'provider_circuit_state', lambda provider: {})
    def storage_down(entries): raise RuntimeError('storage unavailable')
    monkeypatch.setattr(runtime, 'record_source_audit_entries', storage_down)
    async def working(): return [1]
    assert asyncio.run(runtime.fetch_search_upstream('public', '', working)) == [1]


def test_generic_provider_circuit_cannot_block_replacement_credential(monkeypatch):
    import search_provider_runtime as runtime
    inspected = []
    def circuit(provider):
        inspected.append(provider)
        return {'open': True, 'opened_until': runtime.time.time() + 600} if provider == 'tavily' else {}
    monkeypatch.setattr(runtime, 'provider_circuit_state', circuit)
    async def working(): return [1]
    assert asyncio.run(runtime.fetch_search_upstream('tavily', 'replacement', working)) == [1]
    assert inspected == [runtime.scope_key('tavily', 'replacement')]


def test_earnings_provider_preserves_typed_failure_in_report_audit(monkeypatch):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    import data_fetch.enrichment_providers as providers
    import search_provider_runtime as runtime
    calls = []
    def rejected(ticker, **kwargs):
        calls.append(ticker)
        raise runtime.SourceResponseError('access_denied', status_code=200, response_text='security refusal', parser_version='mops-conference-v2')
    monkeypatch.setattr(providers, 'fetch_free_earnings_call_context', rejected)
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.value == {}
    assert result.status == 'error'
    assert result.audit['error_kind'] == 'access_denied'
    assert result.audit['http_status'] == 200
    assert result.audit['parser_version'] == 'mops-conference-v2'
    assert len(result.audit['response_sha256']) == 64
    assert calls == ['2330.TW']
    assert 'security refusal' not in str(result.audit)
    assert result.audit['response_bytes'] == len('security refusal'.encode())
    assert '拒絕存取' in result.audit['message']
    assert 'response_bytes' not in result.audit['message']

    from reporting.source_audit import build_source_audit_markdown
    from evidence_exit_gate import extract_numeric_claims
    markdown = build_source_audit_markdown({'source_audit': [result.audit]})
    assert not extract_numeric_claims(markdown)


def test_ptt_unknown_html_is_not_valid_empty(monkeypatch):
    import search_provider_runtime as runtime
    observations = []
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(entries))
    monkeypatch.setattr(news_fetchers, 'sync_get', lambda *a, **k: SimpleNamespace(text='<html>Unexpected page</html>', status_code=200))
    assert news_fetchers.fetch_ptt_stock_sentiment('2330.TW') == []
    assert observations[0]['outcome'] == 'failure'
    assert observations[0]['error_kind'] == 'parse_error'


def test_search_http_status_survives_success_and_json_parse_failure(monkeypatch):
    import search_provider_runtime as runtime
    observations = []
    monkeypatch.setattr(runtime, 'provider_circuit_state', lambda provider: {})
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(entries))
    class Client:
        async def get(self, url, **kwargs):
            return httpx.Response(200, json={'web': {'results': []}}, request=httpx.Request('GET', url))
    assert asyncio.run(runtime.fetch_search_upstream('brave', 'valid', lambda: clients.fetch_provider_results(Client(), 'brave', 'query', max_results=2, lookback_days=30))) == []
    assert observations[-1]['http_status'] == 200
    class InvalidClient:
        async def get(self, url, **kwargs):
            return httpx.Response(200, text='<html>not JSON</html>', request=httpx.Request('GET', url))
    with pytest.raises(Exception):
        asyncio.run(runtime.fetch_search_upstream('brave', 'invalid', lambda: clients.fetch_provider_results(InvalidClient(), 'brave', 'query', max_results=2, lookback_days=30)))
    assert observations[-1]['http_status'] == 200
    assert observations[-1]['error_kind'] == 'parse_error'


def test_legacy_facade_seam_restores_observed_http_after_override(monkeypatch):
    import external_data_clients as facade
    import search_response_validation as validation
    forwarded = []
    async def observed(client, url, params, headers=None):
        forwarded.append('observed')
        return {}
    async def fake(client, url, params, headers=None):
        forwarded.append('fake')
        return {}
    monkeypatch.setattr(validation, 'observed_json_get', observed)
    original_client_seam = clients._async_json_get
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(facade, '_async_json_get', fake)
            facade._sync_source_seams()
            asyncio.run(clients._async_json_get(None, 'https://example.test', {}))
        asyncio.run(clients._async_json_get(None, 'https://example.test', {}))
        assert forwarded == ['fake', 'observed']
    finally:
        clients._async_json_get = original_client_seam
