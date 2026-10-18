from __future__ import annotations

import json

import httpx
import pytest

# Exercise the existing metadata route with an issuer outside the staged
# published-body profiles. 2330/1229 use tests/test_mops_presentation*.py.


def payload(rows=None):
    return {
        'status': {'code': '1'},
        'result': {'materials': {'material': rows if rows is not None else [{
            'agentUserName': '2324', 'agentSimpleName': '仁寶',
            'eventDate': '2026-07-16 00:00:00.0', 'isValid': True,
            'categoryId': 170, 'guid': 'public-event-id',
            'webLinkPath': 'https://www.compal.com/investor/',
            'summary': 'DO NOT COPY AI SUMMARY', 'thumbnail': 'DO NOT COPY THUMBNAIL',
        }]}},
        'pagingObject': {'totalCount': len(rows) if rows is not None else 1},
    }


@pytest.fixture
def upstream(monkeypatch):
    import cache_store
    import official_financials
    import official_financials_irengage_conference as irengage
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
    def get(url, **kwargs):
        calls.append(('WebPro', kwargs))
        value = payload() if kwargs['params']['categoryId'] == '170' else payload([])
        return httpx.Response(200, json=value, request=httpx.Request('GET', url))
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', denied)
    def irengage_empty(_ticker, *, diagnostics=None, **_kwargs):
        if diagnostics is not None:
            diagnostics.update(actual_provider=irengage.PROVIDER, status='valid_empty',
                               outcome='valid_empty', http_request_sent=False,
                               event_kind='local_block', record_count=0)
        return {}
    monkeypatch.setattr(irengage, 'fetch_irengage_conference_context', irengage_empty)
    monkeypatch.setattr(webpro, 'sync_get', get)
    return state, calls, observations


def test_mops_denial_recovers_metadata_only_and_keeps_upstream_failure(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
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
    assert [name for name, _ in upstream[1]] == ['MOPS', 'WebPro', 'WebPro']


@pytest.mark.parametrize(('cache_hit', 'expected_status'), [
    (False, 'success'), (True, 'skipped_fresh_cache'),
])
def test_mops_timeout_recovers_exact_webpro_event_from_monthly_mops_query(
    monkeypatch, upstream, cache_hit, expected_status,
):
    import official_financials
    import data_fetch.earnings_call_fetcher as flow
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from search_provider_runtime import SourceResponseError

    calls = []
    event = {
        'ticker': '2324', 'company_name': '仁寶', 'date': '2026-07-16',
        'time': '14:00', 'location': '線上', 'title': '仁寶法人說明會',
        'summary': '公司公布營運成果', 'source': 'MOPS investor conference',
        'source_url': 'https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1',
        'materials': [{'label': '簡報檔案', 'url': 'https://mopsov.twse.com.tw/nas/STR/232420260716M001.pdf'}],
    }

    def fetch_mops(ticker, *, year=None, month=None, limit=3, diagnostics=None, **kwargs):
        calls.append((ticker, year, month))
        if month is None:
            if diagnostics is not None:
                diagnostics.update(status='error', error_kind='timeout', http_request_sent=True,
                                   http_request_count=1, http_status=200)
            raise SourceResponseError('timeout', status_code=200)
        assert (ticker, year, month) == ('2324.TW', 2026, 7)
        if diagnostics is not None:
            diagnostics.update(status='success', actual_provider='MOPS investor conference',
                               http_request_sent=not cache_hit,
                               http_request_count=0 if cache_hit else 1,
                               cache_hit=cache_hit, stale=False,
                               fetched_at_epoch=1792210000.0)
        return [event]

    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', fetch_mops)
    monkeypatch.setattr(flow, '_fetch_twse_iih_notice_fallback', lambda *_args, **_kwargs: {})

    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))

    assert result.status == expected_status
    assert result.value['date'] == '2026-07-16'
    assert result.value['summary'] == '公司公布營運成果'
    assert result.value['materials'] == event['materials']
    assert result.value['transcript_available'] is False
    assert result.audit['actual_provider'] == 'MOPS investor conference'
    assert result.audit['component_statuses']['MOPS']['error_kind'] == 'timeout'
    assert result.audit['component_statuses']['MOPS_event_month']['matched_event_date'] == '2026-07-16'
    assert calls == [('2324.TW', None, None), ('2324.TW', 2026, 7)]


@pytest.mark.parametrize('change', [{'ticker': '2303'}, {'date': '2026-07-17'}])
def test_monthly_mops_fallback_does_not_promote_wrong_company_or_date(monkeypatch, upstream, change):
    import official_financials
    import data_fetch.earnings_call_fetcher as flow
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from search_provider_runtime import SourceResponseError

    event = {
        'ticker': '2324', 'company_name': '仁寶', 'date': '2026-07-16',
        'title': '仁寶法人說明會', 'summary': '官方摘要',
        'source': 'MOPS investor conference',
        'source_url': 'https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1',
        'materials': [],
    }

    def fetch_mops(ticker, *, month=None, diagnostics=None, **kwargs):
        if month is None:
            raise SourceResponseError('timeout', status_code=200)
        return [{**event, **change}]

    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', fetch_mops)
    monkeypatch.setattr(flow, '_fetch_twse_iih_notice_fallback', lambda *_args, **_kwargs: {})
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.value['coverage_status'] == 'metadata_only'
    assert result.audit['component_statuses']['MOPS_event_month']['matched_event_date'] is None


def respond(monkeypatch, value, *, status=200, headers=None):
    import official_financials_webpro_conference as webpro
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(status, json=value, headers=headers, request=httpx.Request('GET', url))
    monkeypatch.setattr(webpro, 'sync_get', get)
    return calls


def test_shared_metadata_cache_preserves_acquisition_time_and_omits_content(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    provider = EarningsCallProvider()
    first = provider.fetch(FetchRequest.from_ticker('2324.TW'))
    second = provider.fetch(FetchRequest.from_ticker('2324.TW'))
    assert second.value == first.value
    assert second.audit['cache_hit'] is True
    assert 'http_request_sent' not in second.audit
    assert second.audit['event_kind'] == 'aggregate'
    assert second.audit['component_statuses']['WebPro']['http_request_sent'] is False
    assert first.audit['fetched_at_epoch'] == second.audit['fetched_at_epoch']
    assert sum(name == 'WebPro' for name, _ in upstream[1]) == 2
    assert 'DO NOT COPY' not in json.dumps(upstream[0])


@pytest.mark.parametrize('changes', [
    {'agentUserName': '2303'}, {'isValid': False}, {'eventDate': '2099-12-01 00:00:00.0'},
])
def test_wrong_company_invalid_and_future_events_do_not_become_latest(monkeypatch, upstream, changes):
    import official_financials_webpro_conference as webpro
    row = payload()['result']['materials']['material'][0]
    def get(url, **kwargs):
        value = payload([{**row, **changes, 'categoryId': int(kwargs['params']['categoryId'])}])
        return httpx.Response(200, json=value, request=httpx.Request('GET', url))
    monkeypatch.setattr(webpro, 'sync_get', get)
    audit = {}
    assert webpro.fetch_webpro_conference_context('2324.TW', diagnostics=audit) == {}
    assert audit['outcome'] == 'valid_empty'


@pytest.mark.parametrize('value', [
    {}, {'status': {'code': '1'}, 'result': {}},
    {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': 1}},
    {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': False}},
    {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': -1}},
    {'status': {'code': '1'}, 'result': {'unexpected': []}, 'pagingObject': {'totalCount': 0}},
    {**payload([]), 'pagingObject': {'totalCount': 2}},
    payload([{'agentUserName': '2324', 'isValid': True, 'categoryId': 170, 'eventDate': '2026-02-30 00:00:00.0'}]),
])
def test_unknown_shapes_and_invalid_calendar_date_are_typed_parse_failure(monkeypatch, upstream, value):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    calls = respond(monkeypatch, value)
    for _ in range(2):
        with pytest.raises(SourceResponseError) as caught:
            webpro.fetch_webpro_conference_context('2324.TW')
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
    row = payload()['result']['materials']['material'][0]
    def get(url, **kwargs):
        value = payload([{**row, 'webLinkPath': link, 'categoryId': int(kwargs['params']['categoryId'])}])
        return httpx.Response(200, json=value, request=httpx.Request('GET', url))
    monkeypatch.setattr(webpro, 'sync_get', get)
    diagnostic = {}
    assert webpro.fetch_webpro_conference_context('2324.TW', diagnostics=diagnostic) == {}
    assert diagnostic['outcome'] == 'partial'
    assert diagnostic['usable_count'] == 0 and diagnostic['rejected_count'] == 2
    assert all(item['record']['webLinkPath'] == link for item in diagnostic['source_record_archive'])
    assert webpro.COOLDOWN_KEY not in upstream[0]
    assert all(item['status'] == 'degraded_enrichment' for item in upstream[2])


def test_valid_empty_is_index_scope_only_and_has_short_cache(monkeypatch, upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    calls = respond(monkeypatch, payload([]))
    first = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
    second = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
    assert first.value == second.value == {}
    assert first.status == 'degraded_enrichment'
    assert first.audit['record_count'] == 0
    assert '不能據此判定公司沒有法說會' in first.audit['message']
    assert first.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert len(calls) == 2
    row = next(v for k, v in upstream[0].items() if k.startswith('shared_provider:'))
    assert 299 <= row['fresh_until_epoch'] - row['fetched_at_epoch'] < 301


def test_official_empty_result_does_not_block_other_companies(monkeypatch, upstream):
    """2322 live response: successful empty envelope omits materials entirely."""
    import official_financials_webpro_conference as webpro
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    calls = []

    def get(url, **kwargs):
        symbol = kwargs['params']['companyCode']
        calls.append(symbol)
        value = ({'status': {'code': '1'}, 'result': {},
                  'pagingObject': {'pagingSize': webpro.PAGE_SIZE, 'totalPage': 0, 'totalCount': 0, 'currentPage': 1}}
                 if symbol == '2322' else payload([{**row, 'categoryId': int(kwargs['params']['categoryId'])}
                                                   for row in payload()['result']['materials']['material']]))
        return httpx.Response(200, json=value, request=httpx.Request('GET', url))

    monkeypatch.setattr(webpro, 'sync_get', get)
    empty = EarningsCallProvider().fetch(FetchRequest.from_ticker('2322.TW'))
    assert empty.status == 'degraded_enrichment'
    assert empty.audit['outcome'] == 'valid_empty'
    assert empty.audit['error_kind'] == ''
    assert empty.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert empty.value == {}
    again = EarningsCallProvider().fetch(FetchRequest.from_ticker('2322.TW'))
    assert again.audit['cache_hit'] is True
    recovered = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
    assert recovered.value['date'] == '2026-07-16'
    assert calls == ['2322', '2322', '2324', '2324']
    rows = [v for k, v in upstream[0].items() if k.startswith('shared_provider:') and v['value']['events'] == []]
    assert len(rows) == 2
    assert 299 <= rows[0]['fresh_until_epoch'] - rows[0]['fetched_at_epoch'] < 301


def test_valid_empty_mops_uses_company_scoped_webpro_before_secondary_sources(monkeypatch):
    import official_financials
    import official_financials_webpro_conference as webpro
    import data_fetch.earnings_call_fetcher as flow

    mops_calls, webpro_calls = [], []

    def empty_mops(ticker, *, year=None, diagnostics=None, **kwargs):
        mops_calls.append((ticker, year))
        if diagnostics is not None:
            diagnostics.update(status='success', outcome='valid_empty', actual_provider='MOPS',
                               http_request_sent=True, http_request_count=1,
                               fetched_at_epoch=1792220000.0)
        return []

    recovered = {
        'ticker': '2610.TW', 'date': '2026-08-20', 'period': '2026-08-20',
        'title': '華航法人說明會（索引）', 'summary': '', 'transcript_excerpt': '',
        'transcript_available': False, 'materials': [], 'source': webpro.PROVIDER,
        'source_url': 'https://webpro.twse.com.tw/WebPortal/vod/101/?categoryId=148',
        'event_url': 'https://irconference.twse.com.tw/2610_30_20260820_ch.mp4',
        'category_id': 148, 'coverage_status': 'metadata_only',
    }

    def webpro_context(ticker, *, diagnostics=None, **kwargs):
        webpro_calls.append(ticker)
        if diagnostics is not None:
            diagnostics.update(status='success', outcome='results', actual_provider=webpro.PROVIDER,
                               http_request_sent=True, http_request_count=1,
                               coverage_status='metadata_only', fetched_at_epoch=1792220000.0)
        return dict(recovered)

    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', empty_mops)
    monkeypatch.setattr(webpro, 'fetch_webpro_conference_context', webpro_context)
    monkeypatch.setattr(flow, '_fetch_twse_iih_notice_fallback',
                        lambda *_args, **_kwargs: pytest.fail('WebPro already recovered the official event'))
    monkeypatch.setattr(flow, '_fetch_irengage_fallback',
                        lambda *_args, **_kwargs: pytest.fail('WebPro already recovered the official event'))

    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2610.TW'))
    context = result.value
    diagnostics = result.audit

    assert result.status == 'success'
    assert context['date'] == '2026-08-20'
    assert context['event_url'].endswith('/2610_30_20260820_ch.mp4')
    assert mops_calls == [('2610.TW', None), ('2610.TW', 2025), ('2610.TW', 2026)]
    assert webpro_calls == ['2610.TW']
    assert diagnostics['record_count'] > 0
    assert diagnostics['provider'] == webpro.PROVIDER
    assert diagnostics['component_statuses']['MOPS']['status'] == 'valid_empty'
    assert diagnostics['component_statuses']['WebPro']['outcome'] == 'results'


def test_valid_empty_mops_and_webpro_remain_empty_before_secondary_recovery(monkeypatch):
    import official_financials
    import official_financials_webpro_conference as webpro
    import data_fetch.earnings_call_fetcher as flow

    calls = []

    def empty_mops(ticker, *, year=None, diagnostics=None, **kwargs):
        if diagnostics is not None:
            diagnostics.update(status='success', outcome='valid_empty', actual_provider='MOPS',
                               http_request_sent=True, http_request_count=1,
                               fetched_at_epoch=1792220000.0)
        return []

    def empty_webpro(ticker, *, diagnostics=None, **kwargs):
        calls.append(('WebPro', ticker))
        if diagnostics is not None:
            diagnostics.update(status='valid_empty', outcome='valid_empty', actual_provider=webpro.PROVIDER,
                               http_request_sent=True, http_request_count=2,
                               fetched_at_epoch=1792220000.0)
        return {}

    def empty_iih(ticker, diagnostics, *, components=None, **kwargs):
        calls.append(('IIH', ticker))
        diagnostics['component_statuses'] = dict(components or {})
        diagnostics['component_statuses']['TWSE_IIH_MOPS_notice'] = {'status': 'valid_empty'}
        return {}

    def empty_irengage(ticker, context, diagnostics, **kwargs):
        calls.append(('IR Engage', ticker))
        return context

    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', empty_mops)
    monkeypatch.setattr(webpro, 'fetch_webpro_conference_context', empty_webpro)
    monkeypatch.setattr(flow, '_fetch_twse_iih_notice_fallback', empty_iih)
    monkeypatch.setattr(flow, '_fetch_irengage_fallback', empty_irengage)

    diagnostics = {}
    assert flow._fetch_official_index_context('2322.TW', diagnostics=diagnostics) == {}
    assert calls == [('WebPro', '2322.TW'), ('IIH', '2322.TW'), ('IR Engage', '2322.TW')]
    assert diagnostics['component_statuses']['WebPro']['outcome'] == 'valid_empty'


def test_both_failures_preserved_and_retry_after_prevents_repeated_http(monkeypatch, upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    calls = respond(monkeypatch, {}, status=429, headers={'Retry-After': '600'})
    for _ in range(2):
        result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
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


def test_primary_valid_empty_uses_official_webpro_company_fallback(monkeypatch, upstream):
    import official_financials
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    calls = []
    def empty(*args, **kwargs):
        calls.append(kwargs)
        return []
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', empty)
    context = fetch_free_earnings_call_context('2324.TW')
    assert len(calls) == 3  # annual empty results, then the verified event month
    assert calls[-1]['year'] == 2026 and calls[-1]['month'] == 7
    assert context['date'] == '2026-07-16'
    assert context['source'] == 'TWSE WebPro conference metadata'
    assert len(upstream[1]) == 2


def test_non_taiwan_symbols_never_query_either_index(upstream):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    assert fetch_free_earnings_call_context('TSM') == {}
    assert fetch_free_earnings_call_context('2324.US') == {}
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
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
    assert result.value['source'] == 'TWSE WebPro conference metadata'
    assert 'MOPS / TWSE WebPro investor conference' in checked


def test_real_http_observation_not_duplicated_by_workflow_audit_projection(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.workflow import _audit_entries_from_provider_results
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
    projected = _audit_entries_from_provider_results([result])
    entries = upstream[2] + projected
    http_entries = [entry for entry in entries if entry.get('event_kind') == 'http_attempt']
    assert len(http_entries) == 2
    assert http_entries[0]['provider'] == 'TWSE WebPro conference metadata'
    assert result.audit['event_kind'] == 'aggregate'
    assert 'http_request_sent' not in result.audit
    assert all(entry['provider'] != 'MOPS investor conference' or entry['status'] != 'success' for entry in entries)


@pytest.mark.parametrize('value', [
    {'status': {}, 'result': {}},
    payload([{'agentUserName': '2324', 'categoryId': 170, 'eventDate': '2026-07-16 00:00:00.0'}]),
])
def test_missing_required_response_fields_cannot_be_valid_empty(monkeypatch, upstream, value):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    respond(monkeypatch, value)
    with pytest.raises(SourceResponseError) as caught:
        webpro.fetch_webpro_conference_context('2324.TW')
    assert caught.value.error_kind == 'parse_error'


def test_persisted_mops_cooldown_uses_backup_without_mops_http(monkeypatch, upstream):
    import time
    import official_financials
    import official_financials_mops_conference as mops
    import search_provider_runtime as runtime
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    upstream[0][runtime.scope_key('MOPS', endpoint='mopsov_investor_conference')] = {
        'error_kind': 'access_denied', 'http_status': 200, 'retry_at': time.time() + 1800,
    }
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', mops.fetch_mops_investor_conference_events)
    monkeypatch.setattr(mops, '_http_post', lambda *a, **k: pytest.fail('Cooling MOPS must not receive HTTP'))
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.value['source'] == 'TWSE WebPro conference metadata'
    assert result.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert [(row['provider'], row['event_kind']) for row in upstream[2]] == [
        ('MOPS', 'local_block'), ('TWSE WebPro conference metadata', 'http_attempt'),
        ('TWSE WebPro conference metadata', 'http_attempt')]


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
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2324.TW'))
    data = {'ticker': '2324.TW', 'quote_type': 'EQUITY', 'source_audit': [result.audit]}
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
    assert sum(entry.get('event_kind') == 'http_attempt' for entry in all_entries) == 2


def test_transport_failure_does_not_inherit_previous_request_http_status(monkeypatch, upstream):
    from types import SimpleNamespace
    import official_financials_webpro_conference as webpro
    import search_provider_runtime as runtime
    runtime.observe_http_response(SimpleNamespace(status_code=200))
    def fail(*args, **kwargs):
        raise httpx.ConnectTimeout('timeout')
    monkeypatch.setattr(webpro, 'sync_get', fail)
    try:
        with pytest.raises(runtime.SourceResponseError) as caught:
            webpro.fetch_webpro_conference_context('2324.TW')
        assert caught.value.error_kind == 'timeout'
        assert caught.value.diagnostic['http_status'] is None
    finally:
        runtime.observe_http_response(None)


def test_legacy_sync_bundle_preserves_webpro_provenance_and_partial_coverage(monkeypatch, upstream):
    import data_fetch.yfinance_sync_enrichment as legacy
    import official_institutional_source
    # This test isolates the conference flow, including the newer institutional
    # fallback that can otherwise issue an unrelated public-source attempt.
    monkeypatch.setattr(official_institutional_source, 'recover_institutional_observations',
                        lambda ticker, value, **kwargs: (value, {}))
    for name in ('fetch_finmind_news_catalysts', 'fetch_yfinance_news_catalysts',
                 'fetch_fmp_news_catalysts', 'fetch_institutional_trading_trend',
                 'fetch_dynamic_peer_metrics', 'build_pe_river_chart_data'):
        monkeypatch.setattr(legacy, name, lambda *a, **k: [])
    bundle = legacy.fetch_sync_enrichment_bundle(
        ticker='2324.TW', stock=None, company_name='仁寶', sector='Technology',
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
    assert sum(entry.get('event_kind') == 'http_attempt' for entry in upstream[2] + bundle['audit']) == 2
