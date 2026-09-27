"""Bounded category fallback replays the public 2367 MOPS index response."""
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/webpro148_2367_20260927.json'
EMPTY = {'status': {'code': '1'}, 'result': {}, 'pagingObject': {'totalCount': 0}}


@pytest.fixture
def index(monkeypatch):
    import cache_store
    import official_financials_webpro_conference as webpro
    import search_provider_runtime as runtime
    state, calls, observations = {}, [], []
    for module in (cache_store, runtime):
        monkeypatch.setattr(module, 'get_cache_json', lambda key: state.get(key))
        monkeypatch.setattr(module, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(entries))
    responses = {170: EMPTY, 148: json.loads(FIXTURE.read_text())}
    def post(url, **kwargs):
        calls.append(kwargs['data'])
        category = int(kwargs['data']['categoryId'])
        return httpx.Response(200, json=responses[category], request=httpx.Request('POST', url))
    monkeypatch.setattr(webpro, 'sync_post', post)
    return responses, calls, state, observations


def test_captured_mops_category_recovers_metadata_and_keeps_each_category_evidence(index):
    import official_financials_webpro_conference as webpro
    audit = {}
    result = webpro.fetch_webpro_conference_context('2367.TW', diagnostics=audit)
    assert result['date'] == '2026-06-26'
    assert result['category_id'] == 148
    assert result['source_url'].endswith('categoryId=148')
    assert result['event_url'] == 'https://irconference.twse.com.tw/2367_12_20260626_ch.mp4'
    assert result['coverage_status'] == 'metadata_only'
    assert result['transcript_available'] is False
    assert result['transcript_excerpt'] == result['summary'] == ''
    assert result['materials'] == []
    assert [row['outcome'] for row in audit['category_observations']] == ['valid_empty', 'results']
    assert [row['category_id'] for row in audit['category_observations']] == [170, 148]
    assert [int(call['categoryId']) for call in index[1]] == [170, 148]
    assert all(call['pageNumber'] == '1' and call['pagingSize'] == '3' for call in index[1])
    second_audit = {}
    assert webpro.fetch_webpro_conference_context('2367.TW', diagnostics=second_audit) == result
    assert len(index[1]) == 2
    assert second_audit['cache_hit'] is True
    assert all(row['event_kind'] == 'cache_hit' for row in second_audit['category_observations'])


def test_both_valid_empty_categories_are_cached_separately_for_five_minutes(index):
    import official_financials_webpro_conference as webpro
    index[0][148] = EMPTY
    for _ in range(2):
        audit = {}
        assert webpro.fetch_webpro_conference_context('2367.TW', diagnostics=audit) == {}
        assert [row['outcome'] for row in audit['category_observations']] == ['valid_empty', 'valid_empty']
    assert len(index[1]) == 2
    entries = [v for k, v in index[2].items() if k.startswith('shared_provider:')]
    assert len(entries) == 2
    assert all(299 <= row['fresh_until_epoch'] - row['fetched_at_epoch'] < 301 for row in entries)


def test_usable_first_category_stops_after_one_page(index):
    import official_financials_webpro_conference as webpro
    first = deepcopy(index[0][148])
    for row in first['result']['materials']['material']: row['categoryId'] = 170
    index[0][170] = first
    assert webpro.fetch_webpro_conference_context('2367.TW')['category_id'] == 170
    assert [int(call['categoryId']) for call in index[1]] == [170]


@pytest.mark.parametrize('change', [{'agentUserName': '2330'}, {'eventDate': '2099-12-01 00:00:00.0'}, {'isValid': False}])
def test_new_category_keeps_same_identity_validity_and_date_rules(index, change):
    import official_financials_webpro_conference as webpro
    for row in index[0][148]['result']['materials']['material']: row.update(change)
    assert webpro.fetch_webpro_conference_context('2367.TW') == {}
    assert len(index[1]) == 2


def test_second_category_failure_preserves_first_valid_empty_and_stops_host(index):
    import official_financials_webpro_conference as webpro
    from search_provider_runtime import SourceResponseError
    index[0][148] = {}
    with pytest.raises(SourceResponseError) as error:
        webpro.fetch_webpro_conference_context('2367.TW')
    assert error.value.error_kind == 'parse_error'
    categories = error.value.diagnostic['category_observations']
    assert categories[0]['category_id'] == 170 and categories[0]['outcome'] == 'valid_empty'
    assert categories[1]['category_id'] == 148 and categories[1]['error_kind'] == 'parse_error'
    with pytest.raises(SourceResponseError):
        webpro.fetch_webpro_conference_context('2330.TW')
    assert len(index[1]) == 2


def test_positive_fallback_context_reused_after_primary_empty_cache_expires(monkeypatch, index):
    import official_financials_webpro_conference as webpro
    now = [webpro.time.time()]
    monkeypatch.setattr(webpro.time, 'time', lambda: now[0])
    first_audit = {}
    first = webpro.fetch_webpro_conference_context('2367.TW', diagnostics=first_audit)
    assert len(index[1]) == 2
    now[0] += 301
    second_audit = {}
    second = webpro.fetch_webpro_conference_context('2367.TW', diagnostics=second_audit)
    assert second == first
    assert len(index[1]) == 2
    assert second_audit['fetched_at_epoch'] == first_audit['fetched_at_epoch']
    assert second_audit['cache_hit'] is True
    assert second_audit['http_request_sent'] is False
    assert [row['fetched_at_epoch'] for row in second_audit['category_observations']] == [row['fetched_at_epoch'] for row in first_audit['category_observations']]
