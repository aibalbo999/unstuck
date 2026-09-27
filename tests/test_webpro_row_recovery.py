"""Real 2892 index: one allowed HTTPS link survives two rejected HTTP rows."""
from copy import deepcopy
import json
from pathlib import Path
import time

import httpx
import pytest

FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/webpro170_2892_20260927.json'
EMPTY = {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': 0}}


@pytest.fixture
def upstream(monkeypatch):
    import cache_store
    import official_financials
    import official_financials_webpro_conference as webpro
    import search_provider_runtime as runtime
    import provider_resilience
    provider_resilience.clear_provider_circuits()
    provider_resilience.clear_provider_throttles()
    state, calls, observations = {}, [], []
    responses = {170: json.loads(FIXTURE.read_text()), 148: deepcopy(EMPTY)}
    for module in (cache_store, runtime):
        monkeypatch.setattr(module, 'get_cache_json', lambda key: state.get(key))
        monkeypatch.setattr(module, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, deepcopy(value)))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(deepcopy(entries)))
    def post(url, **kwargs):
        assert url == webpro.LIST_URL  # Never dereference any event link.
        assert kwargs['data']['pageNumber'] == '1' and kwargs['data']['pagingSize'] == '3'
        category = int(kwargs['data']['categoryId'])
        calls.append((url, category, kwargs['data']['stockCodeOrCompanyName']))
        return httpx.Response(200, json=responses[category], request=httpx.Request('POST', url))
    def denied(*args, **kwargs):
        raise runtime.SourceResponseError('access_denied', status_code=200)
    monkeypatch.setattr(webpro, 'sync_post', post)
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', denied)
    return responses, state, calls, observations


def test_real_mixed_page_recovers_old_metadata_with_partial_counts_and_archive(upstream):
    import official_financials_webpro_conference as webpro
    from prompt_evidence import prompt_evidence_copy
    diagnostic = {}
    context = webpro.fetch_webpro_conference_context('2892.TW', diagnostics=diagnostic)
    assert context['date'] == '2023-11-30'
    assert context['event_url'] == 'https://www.zucast.com/event/Lws1OOSP/subscribe/create'
    assert context['coverage_status'] == 'metadata_only'
    assert context['selection_status'] == 'partial'
    assert context['summary'] == context['transcript_excerpt'] == ''
    assert context['transcript_available'] is False and context['materials'] == []
    assert diagnostic['outcome'] == 'partial'
    assert [diagnostic[k] for k in ('raw_count','usable_count','rejected_count')] == [3,1,2]
    assert diagnostic['rejected_reason_counts'] == {'unusable_event_link':2}
    assert context['rejected_count'] == 2
    rejected = context['source_record_archive']
    assert [r['record']['webLinkPath'] for r in rejected] == [r['webLinkPath'] for r in upstream[0][170]['result']['materials']['material'][1:]]
    prompt = prompt_evidence_copy(context)
    assert 'source_record_archive' not in prompt
    assert 'http://www.zucast.com' not in json.dumps(prompt)
    assert len(upstream[2]) == 2
    assert webpro.COOLDOWN_KEY not in upstream[1]
    assert [(r['status'],r['outcome'],r['record_count']) for r in upstream[3]] == [('degraded_enrichment','partial',1), ('degraded_enrichment','valid_empty',0)]


def test_all_bad_links_are_partial_zero_not_empty_or_global_failure(upstream):
    import official_financials_webpro_conference as webpro
    rows = upstream[0][170]['result']['materials']['material']
    rows[0]['webLinkPath'] = rows[0]['webLinkPath'].replace('https:', 'http:')
    diagnostic = {}
    assert webpro.fetch_webpro_conference_context('2892.TW', diagnostics=diagnostic) == {}
    assert diagnostic['outcome'] == 'partial'
    assert [diagnostic[k] for k in ('raw_count','usable_count','rejected_count')] == [3,0,3]
    assert [r['outcome'] for r in diagnostic['category_observations']] == ['partial','valid_empty']
    assert len(diagnostic['source_record_archive']) == 3
    assert webpro.COOLDOWN_KEY not in upstream[1]
    assert upstream[3][0]['status'] == 'degraded_enrichment'
    assert upstream[3][0]['outcome'] == 'partial' and upstream[3][0]['record_count'] == 0
    assert [r[1] for r in upstream[2]] == [170,148]


def test_partial_cache_preserves_original_time_counts_and_rejections(upstream, monkeypatch):
    import official_financials_webpro_conference as webpro
    now = [time.time()]
    monkeypatch.setattr(webpro.time,'time',lambda: now[0])
    first_audit = {}
    first = webpro.fetch_webpro_conference_context('2892.TW',diagnostics=first_audit)
    now[0] += 301
    audit = {}
    second = webpro.fetch_webpro_conference_context('2892.TW',diagnostics=audit)
    assert second == first
    assert len(upstream[2]) == 2 and len(upstream[3]) == 2
    assert audit['outcome'] == 'partial' and audit['rejected_count'] == 2
    assert audit['cache_hit'] is True and audit['http_request_sent'] is False
    assert audit['fetched_at_epoch'] == first_audit['fetched_at_epoch']
    assert audit['source_record_archive'] == first_audit['source_record_archive']


def test_partial_empty_category_cache_remains_partial(upstream):
    import official_financials_webpro_conference as webpro
    upstream[0][170]['result']['materials']['material'][0]['webLinkPath'] = 'http://example.com/event'
    for _ in range(2):
        audit = {}
        assert webpro.fetch_webpro_conference_context('2892.TW',diagnostics=audit) == {}
        assert audit['outcome'] == 'partial' and audit['rejected_count'] == 3
    assert len(upstream[2]) == 2 and len(upstream[3]) == 2
    assert audit['cache_hit'] is True
    assert all(row['fresh_until_epoch']-row['fetched_at_epoch'] < 301
               for key,row in upstream[1].items() if key.startswith('shared_provider:'))


def test_provider_partial_handoff_and_snapshot_keep_rejections(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from prompt_evidence import prompt_evidence_copy
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2892.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.audit['coverage_status'] == 'partial'
    assert result.audit['outcome'] == 'partial'
    assert result.audit['rejected_count'] == 2
    assert result.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    data = {'ticker':'2892.TW','source_audit':[result.audit]}
    merged = _merge_optional_http_bundle(data,{'earnings_call':result.value},refreshed_sources=['earnings_call'])
    assert merged['source_audit'][-1]['status'] == 'degraded_enrichment'
    assert merged['source_audit'][-1]['rejected_count'] == 2
    assert merged['earnings_call']['date'] == '2023-11-30'
    assert 'http://www.zucast.com' not in json.dumps(prompt_evidence_copy(merged))


@pytest.mark.parametrize('change', [{'agentUserName':'2330'}, {'eventDate':'2099-01-01 00:00:00.0'}, {'isValid':False}])
def test_same_id_cannot_override_company_date_or_validity(upstream,change):
    import official_financials_webpro_conference as webpro
    rows = upstream[0][170]['result']['materials']['material']
    extra = {**deepcopy(rows[0]),**change}
    rows.insert(0,extra)
    upstream[0][170]['pagingObject']['totalCount'] = 9
    context = webpro.fetch_webpro_conference_context('2892.TW')
    assert context['date'] == '2023-11-30'
    assert context['event_id'] == rows[1]['guid']
    assert context['rejected_count'] == 2


def test_partial_page_does_not_cool_down_another_company(upstream):
    import official_financials_webpro_conference as webpro
    assert webpro.fetch_webpro_conference_context('2892.TW')['selection_status'] == 'partial'
    valid = deepcopy(upstream[0][170]['result']['materials']['material'][0])
    valid.update(agentUserName='2330',agentSimpleName='台積電')
    upstream[0][170]['result']['materials']['material'] = [valid]
    assert webpro.fetch_webpro_conference_context('2330.TW')['ticker'] == '2330'
    assert [r[2] for r in upstream[2]] == ['2892','2892','2330','2330']


def test_partial_observation_is_degraded_with_explicit_outcome(upstream):
    import search_provider_runtime as runtime
    runtime.record_observation('test',time.monotonic(),outcome='partial',count=0,source='earnings_call',details={'rejected_count':3})
    assert upstream[3][0]['status'] == 'degraded_enrichment'
    assert upstream[3][0]['outcome'] == 'partial'
    assert upstream[3][0]['record_count'] == 0


def test_first_partial_then_second_positive_preserves_combined_selection(upstream,monkeypatch):
    import official_financials_webpro_conference as webpro
    now = [time.time()]
    monkeypatch.setattr(webpro.time,'time',lambda: now[0])
    original = upstream[0][170]['result']['materials']['material']
    good = {**deepcopy(original[0]),'categoryId':148}
    original[0]['webLinkPath'] = 'http://example.com/rejected'
    second = deepcopy(upstream[0][170])
    second['result']['materials']['material'] = [good]
    upstream[0][148] = second
    audit = {}
    context = webpro.fetch_webpro_conference_context('2892.TW',diagnostics=audit)
    assert context['category_id'] == 148 and context['selection_status'] == 'partial'
    assert [audit[k] for k in ('raw_count','usable_count','rejected_count')] == [4,1,3]
    assert audit['outcome'] == 'partial'
    assert [row['outcome'] for row in audit['category_observations']] == ['partial','results']
    original_times = [row['fetched_at_epoch'] for row in audit['category_observations']]
    now[0] += 301
    cached_audit = {}
    assert webpro.fetch_webpro_conference_context('2892.TW',diagnostics=cached_audit) == context
    assert [row['fetched_at_epoch'] for row in cached_audit['category_observations']] == original_times
    assert cached_audit['outcome'] == 'partial' and cached_audit['cache_hit'] is True
    assert len(upstream[2]) == 2 and len(upstream[3]) == 2


def test_first_partial_then_second_hard_error_keeps_rejected_originals(upstream):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    upstream[0][170]['result']['materials']['material'][0]['webLinkPath'] = 'http://example.com/rejected'
    upstream[0][148] = {}
    with pytest.raises(SourceResponseError) as caught:
        webpro.fetch_webpro_conference_context('2892.TW')
    assert caught.value.error_kind == 'parse_error'
    categories = caught.value.diagnostic['category_observations']
    assert categories[0]['outcome'] == 'partial' and categories[0]['rejected_count'] == 3
    assert len(categories[0]['source_record_archive']) == 3
    assert categories[1]['error_kind'] == 'parse_error'
    assert webpro.COOLDOWN_KEY in upstream[1]
    assert [row['status'] for row in upstream[3]] == ['degraded_enrichment','error']


def test_all_rejected_provider_handoff_is_partial_zero(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    upstream[0][170]['result']['materials']['material'][0]['webLinkPath'] = 'http://example.com/rejected'
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2892.TW'))
    assert result.value == {} and result.status == 'degraded_enrichment'
    assert result.audit['outcome'] == 'partial' and result.audit['record_count'] == 0
    assert result.audit['quality_status'] == 'partial_row_rejection'
    assert result.audit['rejected_count'] == 3
    assert len(result.audit['source_record_archive']) == 3


def test_existing_endpoint_cooldown_blocks_new_parser_without_http(upstream):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    upstream[1][webpro.COOLDOWN_KEY] = {'error_kind':'parse_error','http_status':200,
                                      'retry_at':time.time()+2400,'parser_version':'webpro-conference-metadata-v2'}
    with pytest.raises(SourceResponseError):
        webpro.fetch_webpro_conference_context('2892.TW')
    assert upstream[2] == []
    assert upstream[3][0]['http_request_sent'] is False
    assert upstream[3][0]['event_kind'] == 'local_block'


@pytest.mark.parametrize('outcome,count,sent,error,expected', [
    ('results',1,True,'','success'),
    ('valid_empty',0,True,'','degraded_enrichment'),
    ('failure',0,True,'parse_error','error'),
    ('failure',0,True,'timeout','unavailable'),
    ('cooldown',0,False,'rate_limited','unavailable'),
])
def test_observation_other_outcomes_keep_status_contract(upstream,outcome,count,sent,error,expected):
    import search_provider_runtime as runtime
    runtime.record_observation('test',time.monotonic(),outcome=outcome,count=count,sent=sent,details={'error_kind':error})
    assert upstream[3][0]['status'] == expected
    assert upstream[3][0]['http_request_sent'] is sent
