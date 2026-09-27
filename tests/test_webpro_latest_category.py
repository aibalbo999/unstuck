"""Compare both bounded WebPro categories using captured 2892 responses."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

import httpx
import pytest

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'
EMPTY = {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': 0}}


@pytest.fixture
def source(monkeypatch):
    import cache_store
    import official_financials_webpro_conference as webpro
    import search_provider_runtime as runtime
    state, calls, observations, writes = {}, [], [], []
    now = [time.time()]
    monkeypatch.setattr(webpro.time, 'time', lambda: now[0])
    responses = {category: json.loads((FIXTURES / f'webpro{category}_2892_20260927.json').read_bytes())
                 for category in (170, 148)}
    def set_cache(key, value, ttl_seconds):
        state[key] = deepcopy(value)
        writes.append((key, deepcopy(value), ttl_seconds))
    for module in (cache_store, runtime):
        monkeypatch.setattr(module, 'get_cache_json', lambda key: deepcopy(state.get(key)))
        monkeypatch.setattr(module, 'set_cache_json', set_cache)
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(deepcopy(entries)))
    def post(url, **kwargs):
        assert url == webpro.LIST_URL  # Never fetch event links or content.
        data = kwargs['data']
        assert data['pageNumber'] == '1' and data['pagingSize'] == '3'
        assert data['stockCodeOrCompanyName'] == '2892'
        category = int(data['categoryId'])
        calls.append(category)
        assert len(calls) <= 2, 'No extra category or page budget'
        value = responses[category]
        if isinstance(value, Exception):
            raise value
        now[0] += 1
        return httpx.Response(200, json=value, request=httpx.Request('POST', url))
    monkeypatch.setattr(webpro, 'sync_post', post)
    return responses, state, calls, observations, writes, now


def test_real_older_partial170_cannot_hide_newer148_metadata(source):
    import official_financials_webpro_conference as webpro
    from prompt_evidence import prompt_evidence_copy
    audit = {}
    context = webpro.fetch_webpro_conference_context('2892.TW', diagnostics=audit)
    assert context['date'] == '2026-08-27'
    assert context['category_id'] == 148
    assert context['source_url'].endswith('categoryId=148')
    assert context['event_url'] == 'https://irconference.twse.com.tw/2892_173_20260827_ch.mp4'
    assert context['ticker'] == '2892'
    assert context['coverage_status'] == 'metadata_only'
    assert context['transcript_available'] is False
    assert context['summary'] == context['transcript_excerpt'] == '' and context['materials'] == []
    assert context['selection_policy'] == 'latest_eligible_category_v2'
    assert source[2] == [170, 148]
    assert [row['outcome'] for row in audit['category_observations']] == ['partial', 'results']
    assert audit['outcome'] == context['selection_status'] == 'partial'
    assert [audit[key] for key in ('raw_count', 'usable_count', 'rejected_count')] == [6, 4, 2]
    assert len(context['source_record_archive']) == 2
    assert context['fetched_at_epoch'] == audit['category_observations'][1]['fetched_at_epoch']
    assert context['category_observations'] == audit['category_observations']
    assert [(row['status'], row['record_count']) for row in source[3]] == [('degraded_enrichment', 1), ('success', 3)]
    assert 'http://www.zucast.com' not in json.dumps(prompt_evidence_copy(context))


@pytest.mark.parametrize('date148, expected', [('2023-11-30', 170), ('2023-10-01', 170), ('2024-01-01', 148)])
def test_event_date_order_and_stable170_tie(source, date148, expected):
    import official_financials_webpro_conference as webpro
    for row in source[0][148]['result']['materials']['material']:
        row['eventDate'] = date148 + ' 00:00:00.0'
    context = webpro.fetch_webpro_conference_context('2892.TW')
    assert context['category_id'] == expected
    assert source[2] == [170, 148]


@pytest.mark.parametrize('failure', [{}, httpx.ConnectTimeout('bounded timeout')])
def test_second_category_failure_retains_first_with_short_incomplete_cache(source, failure):
    import official_financials_webpro_conference as webpro
    source[0][148] = failure
    audit = {}
    context = webpro.fetch_webpro_conference_context('2892.TW', diagnostics=audit)
    assert source[2] == [170, 148]
    assert context['date'] == '2023-11-30' and context['category_id'] == 170
    assert context['selection_status'] == audit['outcome'] == 'partial'
    assert context['quality_status'] == audit['quality_status'] == 'incomplete_category'
    assert audit['incomplete_categories'] == context['incomplete_categories'] == [148]
    assert audit['recency_comparison_complete'] is False
    assert audit['rejected_count'] == 2 and len(context['source_record_archive']) == 2
    assert audit['category_observations'][1]['error_kind'] in ('parse_error', 'timeout')
    assert context['category_observations'][1] == audit['category_observations'][1]
    assert [row['status'] for row in source[3]] == ['degraded_enrichment', 'error' if isinstance(failure, dict) else 'unavailable']
    stored = source[1]['webpro-conference-context:v2:2892']
    original = deepcopy(stored)
    assert 0 < stored['fresh_until_epoch'] - source[5][0] <= 300
    assert stored['fresh_until_epoch'] <= context['fetched_at_epoch'] + 86400
    source[5][0] += 120
    cached_audit = {}
    assert webpro.fetch_webpro_conference_context('2892.TW', diagnostics=cached_audit) == context
    assert cached_audit['outcome'] == 'partial' and cached_audit['cache_hit'] is True
    assert source[1]['webpro-conference-context:v2:2892'] == original
    assert len(source[3]) == 2 and len(source[2]) == 2


def test_incomplete_cache_expiry_rechecks_original_guard_without_http(source):
    import official_financials_webpro_conference as webpro
    source[0][148] = {}
    # A prior expired failure makes the normal second failure cooldown 600s.
    source[1][webpro.COOLDOWN_KEY] = {'retry_at': source[5][0] - 1,
                                     'consecutive_failures': 1, 'error_kind': 'parse_error'}
    first = webpro.fetch_webpro_conference_context('2892.TW')
    source[5][0] += 301
    audit = {}
    second = webpro.fetch_webpro_conference_context('2892.TW', diagnostics=audit)
    assert second['date'] == first['date']
    assert second['fetched_at_epoch'] == first['fetched_at_epoch']
    assert second['selection_status'] == 'partial'
    assert audit['category_observations'][1]['event_kind'] == 'local_block'
    assert source[2] == [170, 148]
    assert source[3][-1]['http_request_sent'] is False


def test_missing_first_and_second_error_still_raises_with_both_diagnostics(source):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    source[0][170] = deepcopy(EMPTY)
    source[0][148] = {}
    with pytest.raises(SourceResponseError) as caught:
        webpro.fetch_webpro_conference_context('2892.TW')
    assert [row['category_id'] for row in caught.value.diagnostic['category_observations']] == [170, 148]
    assert caught.value.diagnostic['category_observations'][0]['outcome'] == 'valid_empty'
    assert not any(key.startswith('webpro-conference-context:') for key in source[1])


def test_first_failure_never_proceeds_to148_or_bypasses_existing_guard(source):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    source[0][170] = {}
    with pytest.raises(SourceResponseError):
        webpro.fetch_webpro_conference_context('2892.TW')
    assert source[2] == [170]
    with pytest.raises(SourceResponseError):
        webpro.fetch_webpro_conference_context('2892.TW')
    assert source[2] == [170]


def test_all_empty_is_valid_empty_without_positive_context(source):
    import official_financials_webpro_conference as webpro
    source[0].update({170: deepcopy(EMPTY), 148: deepcopy(EMPTY)})
    audit = {}
    assert webpro.fetch_webpro_conference_context('2892.TW', diagnostics=audit) == {}
    assert audit['outcome'] == 'valid_empty'
    assert audit['recency_comparison_complete'] is True
    assert source[2] == [170, 148]
    assert all(row['status'] == 'degraded_enrichment' for row in source[3])
    assert 'webpro-conference-context:v2:2892' not in source[1]


def test_old_context_policy_ignored_unchanged_and_v3_category_cache_reused(source):
    import official_financials_webpro_conference as webpro
    old = {'context': {'date': '2023-11-30'}, 'diagnostic': {}, 'fresh_until_epoch': source[5][0] + 86400}
    source[1]['webpro-conference-context:v1:2892'] = deepcopy(old)
    webpro._fetch_category('2892', 170)
    webpro._fetch_category('2892', 148)
    first_acquisitions = source[5][0]
    source[5][0] += 100
    audit = {}
    context = webpro.fetch_webpro_conference_context('2892.TW', diagnostics=audit)
    assert context['date'] == '2026-08-27'
    assert source[1]['webpro-conference-context:v1:2892'] == old
    assert source[2] == [170, 148] and len(source[3]) == 2
    assert audit['cache_hit'] is True
    assert context['fetched_at_epoch'] == first_acquisitions
    assert source[1]['webpro-conference-context:v2:2892']['fresh_until_epoch'] == min(row['fetched_at_epoch'] for row in audit['category_observations']) + 86400
    for raw in ('webpro-conference-metadata-v3:2892', 'webpro-conference-metadata-v3:148:2892'):
        assert 'shared_provider:v1:' + hashlib.sha256(raw.encode()).hexdigest() in source[1]


def test_selected_first_original_acquisition_bounds_partial_cache(source, monkeypatch):
    import official_financials_webpro_conference as webpro
    result, first_meta = webpro._fetch_category('2892', 170)
    source[5][0] = first_meta['fetched_at_epoch'] + 86390
    source[0][148] = {}
    context = webpro.fetch_webpro_conference_context('2892.TW')
    cached = source[1]['webpro-conference-context:v2:2892']
    assert context['fetched_at_epoch'] == first_meta['fetched_at_epoch']
    assert 0 < cached['fresh_until_epoch'] - source[5][0] < 11
    assert cached['fresh_until_epoch'] == first_meta['fetched_at_epoch'] + 86400


def test_mixed_age_categories_cannot_renew_older_comparison_evidence(source):
    import official_financials_webpro_conference as webpro
    _, first_meta = webpro._fetch_category('2892', 170)
    source[5][0] += 86300
    _, second_meta = webpro._fetch_category('2892', 148)
    context = webpro.fetch_webpro_conference_context('2892.TW')
    stored = deepcopy(source[1]['webpro-conference-context:v2:2892'])
    assert context['date'] == '2026-08-27'
    assert context['fetched_at_epoch'] == second_meta['fetched_at_epoch']
    assert stored['fresh_until_epoch'] == first_meta['fetched_at_epoch'] + 86400
    assert 0 < stored['fresh_until_epoch'] - source[5][0] < 100
    source[5][0] += 20
    assert webpro.fetch_webpro_conference_context('2892.TW') == context
    assert source[1]['webpro-conference-context:v2:2892'] == stored
    assert source[2] == [170, 148] and len(source[3]) == 2


def test_clean_first_positive_and_second_empty_stays_metadata_result(source):
    import official_financials_webpro_conference as webpro
    source[0][170]['result']['materials']['material'] = source[0][170]['result']['materials']['material'][:1]
    source[0][148] = deepcopy(EMPTY)
    audit = {}
    context = webpro.fetch_webpro_conference_context('2892.TW', diagnostics=audit)
    assert context['category_id'] == 170
    assert audit['outcome'] == 'results'
    assert audit['coverage_status'] == context['coverage_status'] == 'metadata_only'
    assert audit['recency_comparison_complete'] is True
    assert 'selection_status' not in context
    assert [row['outcome'] for row in audit['category_observations']] == ['results', 'valid_empty']
    assert [row['status'] for row in source[3]] == ['success', 'degraded_enrichment']


def test_second_failure_partial_survives_provider_snapshot_and_prompt(source, monkeypatch):
    import official_financials
    import provider_resilience
    from search_provider_runtime import SourceResponseError
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from prompt_evidence import prompt_evidence_copy
    provider_resilience.clear_provider_circuits()
    provider_resilience.clear_provider_throttles()
    def denied(*args, **kwargs):
        raise SourceResponseError('access_denied', status_code=200)
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', denied)
    source[0][148] = {}
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2892.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.audit['outcome'] == 'partial'
    assert result.audit['quality_status'] == 'incomplete_category'
    assert result.audit['component_statuses']['MOPS']['error_kind'] == 'access_denied'
    assert result.audit['category_observations'][1]['error_kind'] == 'parse_error'
    data = {'ticker': '2892.TW', 'source_audit': [result.audit]}
    merged = _merge_optional_http_bundle(data, {'earnings_call': result.value}, refreshed_sources=['earnings_call'])
    assert merged['earnings_call']['date'] == '2023-11-30'
    assert merged['earnings_call']['recency_comparison_complete'] is False
    assert merged['earnings_call']['category_observations'][1]['error_kind'] == 'parse_error'
    assert merged['source_audit'][-1]['status'] == 'degraded_enrichment'
    prompt = prompt_evidence_copy(merged)
    assert 'source_record_archive' not in json.dumps(prompt)
    assert 'http://www.zucast.com' not in json.dumps(prompt)
    assert prompt['earnings_call']['selection_status'] == 'partial'
