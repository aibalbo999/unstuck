from __future__ import annotations

import json

import httpx
import pytest


def payload(rows=None):
    return {
        'status': {'code': '1'},
        'result': {'materials': {'material': rows if rows is not None else [{
            'agentUserName': '2330', 'agentSimpleName': '台積電',
            'eventDate': '2026-07-16 00:00:00.0', 'isValid': True,
            'categoryId': 170, 'guid': 'public-event-id',
            'webLinkPath': 'https://investor.tsmc.com/chinese/quarterly-results/2026/q2',
            'summary': 'DO NOT COPY AI SUMMARY', 'thumbnail': 'DO NOT COPY THUMBNAIL',
        }]}},
        'pagingObject': {'totalCount': len(rows) if rows is not None else 1},
    }


@pytest.fixture
def upstream(monkeypatch):
    import cache_store
    import external_http_client
    import official_financials
    import search_provider_runtime as runtime
    import official_financials_webpro_conference as webpro
    import provider_resilience
    provider_resilience.clear_provider_circuits()
    provider_resilience.clear_provider_throttles()
    state, calls, observations = {}, [], []
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(entries))
    def denied(*args, **kwargs):
        calls.append(('MOPS', kwargs))
        raise runtime.SourceResponseError('access_denied', status_code=200, parser_version='mops-conference-v2')
    def post(url, **kwargs):
        calls.append(('WebPro', kwargs))
        return httpx.Response(200, json=payload(), request=httpx.Request('POST', url))
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', denied)
    monkeypatch.setattr(external_http_client, 'sync_post', post)
    monkeypatch.setattr(webpro, 'sync_post', post)
    return state, calls, observations


def test_mops_denial_recovers_metadata_only_and_keeps_upstream_failure(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.provider == 'TWSE WebPro conference metadata'
    assert result.value['date'] == '2026-07-16'
    assert result.value['coverage_status'] == 'metadata_only'
    assert result.value['transcript_available'] is False
    assert result.value['transcript_excerpt'] == ''
    assert result.value['summary'] == ''
    assert result.value['materials'] == []
    assert 'DO NOT COPY' not in json.dumps(result.value)
    assert result.audit['coverage_status'] == 'partial'
    assert result.audit['actual_provider'] == result.provider
    assert result.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert result.audit['component_statuses']['MOPS']['status'] == 'error'
    assert [name for name, _ in upstream[1]] == ['MOPS', 'WebPro']


def respond(monkeypatch, value, *, status=200, headers=None):
    import official_financials_webpro_conference as webpro
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(status, json=value, headers=headers, request=httpx.Request('POST', url))
    monkeypatch.setattr(webpro, 'sync_post', post)
    return calls


def test_shared_metadata_cache_preserves_acquisition_time_and_omits_content(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    provider = EarningsCallProvider()
    first = provider.fetch(FetchRequest.from_ticker('2330.TW'))
    second = provider.fetch(FetchRequest.from_ticker('2330.TW'))
    assert second.value == first.value
    assert second.audit['cache_hit'] is True
    assert 'http_request_sent' not in second.audit
    assert second.audit['event_kind'] == 'aggregate'
    assert second.audit['component_statuses']['WebPro']['http_request_sent'] is False
    assert first.audit['fetched_at_epoch'] == second.audit['fetched_at_epoch']
    assert sum(name == 'WebPro' for name, _ in upstream[1]) == 1
    assert 'DO NOT COPY' not in json.dumps(upstream[0])


@pytest.mark.parametrize('changes', [
    {'agentUserName': '2303'}, {'isValid': False}, {'eventDate': '2099-12-01 00:00:00.0'},
])
def test_wrong_company_invalid_and_future_events_do_not_become_latest(monkeypatch, upstream, changes):
    import official_financials_webpro_conference as webpro
    row = payload()['result']['materials']['material'][0]
    respond(monkeypatch, payload([{**row, **changes}]))
    audit = {}
    assert webpro.fetch_webpro_conference_context('2330.TW', diagnostics=audit) == {}
    assert audit['outcome'] == 'valid_empty'


@pytest.mark.parametrize('value', [
    {}, {'status': {'code': '1'}, 'result': {}},
    {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': 1}},
    {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': False}},
    {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': -1}},
    {'status': {'code': '1'}, 'result': {'unexpected': []}, 'pagingObject': {'totalCount': 0}},
    {**payload([]), 'pagingObject': {'totalCount': 2}},
    payload([{'agentUserName': '2330', 'isValid': True, 'categoryId': 170, 'eventDate': '2026-02-30 00:00:00.0'}]),
])
def test_unknown_shapes_and_invalid_calendar_date_are_typed_parse_failure(monkeypatch, upstream, value):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    calls = respond(monkeypatch, value)
    for _ in range(2):
        with pytest.raises(SourceResponseError) as caught:
            webpro.fetch_webpro_conference_context('2330.TW')
        assert caught.value.error_kind == 'parse_error'
        assert caught.value.diagnostic['http_status'] == 200
    assert len(calls) == 1


@pytest.mark.parametrize('link', [
    'http://investor.tsmc.com/q2', 'javascript:alert(1)', 'https://user:pw@example.com/q2',
    'https://127.0.0.1/q2', 'https://localhost/q2', 'https://example.com:444/q2',
    'https://example.com/with space',
])
def test_unsafe_or_non_https_link_is_not_promoted_to_evidence(monkeypatch, upstream, link):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    row = payload()['result']['materials']['material'][0]
    respond(monkeypatch, payload([{**row, 'webLinkPath': link}]))
    with pytest.raises(SourceResponseError) as caught:
        webpro.fetch_webpro_conference_context('2330.TW')
    assert caught.value.error_kind == 'parse_error'


def test_valid_empty_is_index_scope_only_and_has_short_cache(monkeypatch, upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    calls = respond(monkeypatch, payload([]))
    first = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    second = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert first.value == second.value == {}
    assert first.status == 'degraded_enrichment'
    assert first.audit['record_count'] == 0
    assert '不能據此判定公司沒有法說會' in first.audit['message']
    assert first.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert len(calls) == 1
    row = next(v for k, v in upstream[0].items() if k.startswith('shared_provider:'))
    assert 299 <= row['fresh_until_epoch'] - row['fetched_at_epoch'] < 301


def test_official_empty_result_does_not_block_other_companies(monkeypatch, upstream):
    """2321 live response: successful empty envelope omits materials entirely."""
    import official_financials_webpro_conference as webpro
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    calls = []

    def post(url, **kwargs):
        symbol = kwargs['data']['stockCodeOrCompanyName']
        calls.append(symbol)
        value = ({'status': {'code': '1'}, 'result': {},
                  'pagingObject': {'pagingSize': 3, 'totalPage': 0, 'totalCount': 0, 'currentPage': 1}}
                 if symbol == '2321' else payload())
        return httpx.Response(200, json=value, request=httpx.Request('POST', url))

    monkeypatch.setattr(webpro, 'sync_post', post)
    empty = EarningsCallProvider().fetch(FetchRequest.from_ticker('2321.TW'))
    assert empty.status == 'degraded_enrichment'
    assert empty.audit['outcome'] == 'valid_empty'
    assert empty.audit['error_kind'] == ''
    assert empty.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert empty.value == {}
    again = EarningsCallProvider().fetch(FetchRequest.from_ticker('2321.TW'))
    assert again.audit['cache_hit'] is True
    recovered = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert recovered.value['date'] == '2026-07-16'
    assert calls == ['2321', '2330']
    rows = [v for k, v in upstream[0].items() if k.startswith('shared_provider:') and v['value']['events'] == []]
    assert len(rows) == 1
    assert 299 <= rows[0]['fresh_until_epoch'] - rows[0]['fetched_at_epoch'] < 301


def test_both_failures_preserved_and_retry_after_prevents_repeated_http(monkeypatch, upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    calls = respond(monkeypatch, {}, status=429, headers={'Retry-After': '600'})
    for _ in range(2):
        result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
        assert result.value == {}
        assert result.status == 'error'
        assert result.provider == 'TWSE WebPro conference metadata'
        assert result.audit['component_statuses']['WebPro']['http_status'] == 429
        assert result.audit['error_kind'] == 'rate_limited'
        assert result.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
        assert result.audit['component_statuses']['WebPro']['error_kind'] == 'rate_limited'
    assert len(calls) == 1
    assert result.audit['component_statuses']['WebPro']['http_request_sent'] is False
    assert result.audit['component_statuses']['WebPro']['event_kind'] == 'local_block'


def test_primary_valid_empty_does_not_start_fallback(monkeypatch, upstream):
    import official_financials
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    calls = []
    def empty(*args, **kwargs):
        calls.append(kwargs)
        return []
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', empty)
    assert fetch_free_earnings_call_context('2330.TW') == {}
    assert len(calls) == 2  # existing current/previous-year valid-empty behavior
    assert not upstream[1]


def test_non_taiwan_symbols_never_query_either_index(upstream):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    assert fetch_free_earnings_call_context('TSM') == {}
    assert fetch_free_earnings_call_context('2330.US') == {}
    assert not upstream[1]


def test_old_mops_outer_circuit_cannot_block_metadata_backup(monkeypatch, upstream):
    import provider_resilience as resilience
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    original = resilience._check_provider_state
    checked = []
    def check(provider):
        checked.append(provider)
        if provider == 'MOPS investor conference':
            raise resilience.ProviderCircuitOpenError('old MOPS circuit')
        return original(provider)
    monkeypatch.setattr(resilience, '_check_provider_state', check)
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.value['source'] == 'TWSE WebPro conference metadata'
    assert 'MOPS / TWSE WebPro investor conference' in checked


def test_real_http_observation_not_duplicated_by_workflow_audit_projection(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.workflow import _audit_entries_from_provider_results
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    projected = _audit_entries_from_provider_results([result])
    entries = upstream[2] + projected
    http_entries = [entry for entry in entries if entry.get('event_kind') == 'http_attempt']
    assert len(http_entries) == 1
    assert http_entries[0]['provider'] == 'TWSE WebPro conference metadata'
    assert result.audit['event_kind'] == 'aggregate'
    assert 'http_request_sent' not in result.audit
    assert all(entry['provider'] != 'MOPS investor conference' or entry['status'] != 'success' for entry in entries)


@pytest.mark.parametrize('value', [
    {'status': {}, 'result': {}},
    payload([{'agentUserName': '2330', 'categoryId': 170, 'eventDate': '2026-07-16 00:00:00.0'}]),
])
def test_missing_required_response_fields_cannot_be_valid_empty(monkeypatch, upstream, value):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    respond(monkeypatch, value)
    with pytest.raises(SourceResponseError) as caught:
        webpro.fetch_webpro_conference_context('2330.TW')
    assert caught.value.error_kind == 'parse_error'


def test_persisted_mops_cooldown_uses_backup_without_mops_http(monkeypatch, upstream):
    import time
    import official_financials
    import official_financials_mops_conference as mops
    import search_provider_runtime as runtime
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    upstream[0][runtime.scope_key('MOPS', endpoint='investor_conference')] = {
        'error_kind': 'access_denied', 'http_status': 200, 'retry_at': time.time() + 1800,
    }
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', mops.fetch_mops_investor_conference_events)
    monkeypatch.setattr(mops, '_http_post', lambda *a, **k: pytest.fail('Cooling MOPS must not receive HTTP'))
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.value['source'] == 'TWSE WebPro conference metadata'
    assert result.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert [(row['provider'], row['event_kind']) for row in upstream[2]] == [
        ('MOPS', 'local_block'), ('TWSE WebPro conference metadata', 'http_attempt')]


def test_confirmed_etf_scope_remains_outside_earnings_call_plan(upstream):
    from data_fetch.optional_provider_plan import collect_optional_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import FetchRequest
    data = {'ticker': '0050.TW', 'quote_type': 'ETF'}
    providers, refresh = collect_optional_providers(FetchRequest.from_ticker('0050.TW'), ProviderRegistry(), data, '0050.TW')
    assert refresh['earnings_call'] is False
    assert not any(provider.source == 'earnings_call' for provider in providers)
    assert not upstream[1]


def test_merge_keeps_partial_metadata_and_single_http_observation(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    data = {'ticker': '2330.TW', 'quote_type': 'EQUITY', 'source_audit': [result.audit]}
    merged = _merge_optional_http_bundle(data, {'earnings_call': result.value}, refreshed_sources=('earnings_call',))
    audit = merged['source_audit'][-1]
    assert merged['earnings_call']['transcript_available'] is False
    assert audit['status'] == 'degraded_enrichment'
    assert audit['actual_provider'] == 'TWSE WebPro conference metadata'
    assert audit['coverage_status'] == 'partial'
    assert audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert audit['provider'] == 'TWSE WebPro conference metadata'
    assert audit['event_kind'] == 'aggregate'
    assert 'http_request_sent' not in audit
    all_entries = upstream[2] + merged['source_audit']
    assert sum(entry.get('event_kind') == 'http_attempt' for entry in all_entries) == 1


def test_transport_failure_does_not_inherit_previous_request_http_status(monkeypatch, upstream):
    from types import SimpleNamespace
    import official_financials_webpro_conference as webpro
    import search_provider_runtime as runtime
    runtime.observe_http_response(SimpleNamespace(status_code=200))
    def fail(*args, **kwargs):
        raise httpx.ConnectTimeout('timeout')
    monkeypatch.setattr(webpro, 'sync_post', fail)
    try:
        with pytest.raises(runtime.SourceResponseError) as caught:
            webpro.fetch_webpro_conference_context('2330.TW')
        assert caught.value.error_kind == 'timeout'
        assert caught.value.diagnostic['http_status'] is None
    finally:
        runtime.observe_http_response(None)


def test_legacy_sync_bundle_preserves_webpro_provenance_and_partial_coverage(monkeypatch, upstream):
    import data_fetch.yfinance_sync_enrichment as legacy
    for name in ('fetch_finmind_news_catalysts', 'fetch_yfinance_news_catalysts',
                 'fetch_fmp_news_catalysts', 'fetch_institutional_trading_trend',
                 'fetch_dynamic_peer_metrics', 'build_pe_river_chart_data'):
        monkeypatch.setattr(legacy, name, lambda *a, **k: [])
    bundle = legacy.fetch_sync_enrichment_bundle(
        ticker='2330.TW', stock=None, company_name='台積電', sector='Technology',
        industry='Semiconductors', company_identity={'instrument_type': 'EQUITY'},
        years=[], net_income_history=[], shares_outstanding=None, skip_optional_http=False,
    )
    assert bundle['earnings_call']['source'] == 'TWSE WebPro conference metadata'
    audit = next(entry for entry in bundle['audit'] if entry['source'] == 'earnings_call')
    assert audit['provider'] == 'TWSE WebPro conference metadata'
    assert audit['status'] == 'degraded_enrichment'
    assert audit['coverage_status'] == 'partial'
    assert audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert audit['event_kind'] == 'aggregate'
    assert sum(entry.get('event_kind') == 'http_attempt' for entry in upstream[2] + bundle['audit']) == 1
