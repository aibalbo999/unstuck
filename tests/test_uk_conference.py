"""Real complete source bytes, typed replay, and no-HTTP cache boundaries."""
from copy import deepcopy
from contextlib import contextmanager
import asyncio
import gzip
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from data_fetch.market_sources import uk_conference as uk
from official_response_evidence import archive_response
from search_provider_runtime import SourceResponseError


FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'
NOW = 1791758000.


def raw(name):
    return gzip.decompress((FIXTURES / name).read_bytes())


@pytest.fixture
def harness(monkeypatch):
    index = raw('uk1325_conference_index_20261010.html.gz')
    pdf = raw('uk1325_presentation_20251219.pdf.gz')
    master = raw('uk1325_complete_roster_20261010.json.gz')
    monkeypatch.setattr(uk.time, 'time', lambda: NOW)
    monkeypatch.setattr(uk, 'read_cached_listed_roster_bytes', lambda: (master, {'fetched_at_epoch': NOW-100}))
    calls, observations = [], []
    def download(url, **kwargs):
        calls.append(url)
        kwargs['diagnostics'].update(http_request_sent=True, http_status=200, response_complete=True)
        return index if url == uk.INDEX_URL else pdf
    monkeypatch.setattr(uk, 'download', download)
    monkeypatch.setattr(uk, 'cooldown_state', lambda key: None)
    monkeypatch.setattr(uk, 'record_observation', lambda *args, **kwargs: observations.append(kwargs))
    @contextmanager
    def lease(*args, **kwargs):
        yield lambda: True
    monkeypatch.setattr(uk, 'endpoint_admission', lease)
    return calls, observations


def test_saved_native_index_selects_presentation_not_unread_video():
    selected = uk.select_index(raw('uk1325_conference_index_20261010.html.gz'))
    assert selected['event_date'] == '2025-12-19'
    assert selected['url'].endswith('re_id=2174&fid=42331')


def test_full_originals_and_native_text_preserve_partial_content_and_no_transcript(harness):
    calls, observations = harness
    result = uk._fetch()
    value = result['context']
    assert len(calls) == 2
    assert [r['outcome'] for r in observations] == ['results', 'results']
    assert value['transcript_available'] is False
    assert value['transcript_excerpt'] == value['summary'] == ''
    assert value['coverage_status'] == 'partial'
    doc = value['documents'][0]
    assert doc['page_count'] == 31 and len(doc['pages']) == 31
    assert doc['native_text_coverage'] == 'complete'
    assert doc['full_content_coverage_verified'] is False
    assert sum(p['occurrences'] for p in doc['symbol_mapping_evidence']) == 46
    assert value['uk_conference_receipt']['identity']['http_status'] is None
    assert value['uk_conference_receipt']['identity']['retrieved_at'] == NOW-100
    assert uk.verify_context(value, '1325.TW')


@pytest.mark.parametrize('field', ['text', 'date', 'issuer', 'receipt'])
def test_changed_context_cannot_pass_original_replay(harness, field):
    value = uk._fetch()['context']
    if field == 'text':
        value['documents'][0]['pages'][1]['text'] += ' asserted invented content'
    elif field == 'date':
        value['date'] = '2026-10-12'
    elif field == 'issuer':
        value['ticker'] = '9103.TW'
    else:
        value.pop('uk_conference_receipt')
    assert not uk.verify_context(value, '1325.TW')


def test_cached_native_context_retains_original_acquisition_not_cache_generation(harness, monkeypatch):
    result = uk._fetch()
    calls, _ = harness
    calls.clear()
    monkeypatch.setattr(uk, 'shared_fetch', lambda *args, **kwargs: (result,
                        {'cache_hit': True, 'fetched_at_epoch': NOW+60}))
    diagnostic = {}
    value = uk.fetch_uk_context('1325.TW', diagnostics=diagnostic)
    assert not calls
    assert diagnostic['http_request_sent'] is False and diagnostic['http_request_count'] == 0
    assert diagnostic['fetched_at_epoch'] == value['fetched_at_epoch'] == NOW


def test_bad_cached_pdf_is_typed_invalid_original_not_uncaught_parser_failure(harness):
    value = uk._fetch()['context']
    value['uk_conference_receipt']['pdf'] = archive_response(b'%PDF-invalid',
        source_url=value['documents'][0]['url'], retrieved_at=NOW)
    assert uk.verify_context(value, '1325.TW') is False


def test_broken_cached_shape_does_not_fetch_again(harness, monkeypatch):
    calls, _ = harness
    monkeypatch.setattr(uk, 'shared_fetch', lambda *args, **kwargs: (None, {'cache_hit': True}))
    with pytest.raises(SourceResponseError) as raised:
        uk.fetch_uk_context('1325.TW')
    assert raised.value.error_kind == 'cached_original_unverified'
    assert not calls


def test_unknown_ticker_has_no_source_work(harness):
    calls, _ = harness
    assert uk.fetch_uk_context('9103.TW') == {}
    assert not calls


@pytest.fixture
def isolated_shared_cache(monkeypatch):
    import cache_store
    saved = {}
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: deepcopy(saved.get(key)))
    monkeypatch.setattr(cache_store, 'set_cache_json',
                        lambda key, value, **kwargs: saved.update({key: deepcopy(value)}))
    return saved


@pytest.mark.parametrize('kind', ['lease_lost', 'timeout', 'guard_storage_unavailable'])
def test_shared_fetch_preserves_abort_kind_without_starting_fallback(monkeypatch, isolated_shared_cache, kind):
    from data_fetch import earnings_call_fetcher as earnings
    def fail(**kwargs):
        raise SourceResponseError(kind)
    monkeypatch.setattr(uk, '_fetch', fail)
    fallback = []
    monkeypatch.setattr(earnings, '_fetch_official_index_context',
                        lambda *args, **kwargs: fallback.append(args) or {'ticker': '1325.TW'})
    with pytest.raises(SourceResponseError) as raised:
        earnings.fetch_free_earnings_call_context('1325.TW')
    assert raised.value.error_kind == kind and not fallback


def test_actual_lost_endpoint_lease_cannot_fetch_or_start_fallback(harness, monkeypatch, isolated_shared_cache):
    from data_fetch import earnings_call_fetcher as earnings
    @contextmanager
    def lost(*args, **kwargs):
        yield lambda: False
    monkeypatch.setattr(uk, 'endpoint_admission', lost)
    fallback = []
    monkeypatch.setattr(earnings, '_fetch_official_index_context',
                        lambda *args, **kwargs: fallback.append(args) or {'ticker': '1325.TW'})
    with pytest.raises(SourceResponseError) as raised:
        earnings.fetch_free_earnings_call_context('1325.TW')
    assert raised.value.error_kind == 'lease_lost'
    assert not harness[0] and not fallback


@pytest.mark.parametrize('identity_hint', ['source', 'url', 'document', 'document_url'])
def test_report_source_refresh_cannot_accept_damaged_original_after_marker_removal(harness, identity_hint):
    from report_source_refresh import fetch_report_source_data
    value = uk._fetch()['context']
    value.pop('uk_conference_receipt')
    if identity_hint != 'source':
        value['source'] = 'MOPS index'
    if identity_hint in {'document', 'document_url'}:
        value['source_url'] = 'https://mopsov.twse.com.tw/'
    if identity_hint == 'document_url':
        value['documents'][0]['source'] = 'MOPS index'
        value['documents'][0]['pages'][0]['text'] += ' invented asserted content'
    old = {'ticker': '1325.TW', 'data': {'ticker': '1325.TW', 'current_price': 100},
           'source_audit': [{'source': 'market_data', 'status': 'success',
                             'fetched_at_epoch': NOW-100, 'ticker': '1325.TW'}]}
    before = deepcopy(old)
    class Service:
        _fetcher = None
        async def fetch_source_async(self, *args, **kwargs):
            return SimpleNamespace(data={'ticker': '1325.TW', 'earnings_call': value},
                source_audit=[{'source': 'earnings_call', 'provider': uk.PROVIDER,
                               'status': 'success', 'fetch_id': 'fixture', 'record_count': 1,
                               'fetched_at_epoch': NOW}])
    with pytest.raises(HTTPException) as raised:
        asyncio.run(fetch_report_source_data(old, 'earnings_call', Service()))
    assert raised.value.status_code == 502 and old == before


def test_internal_original_receipts_stay_out_of_prompt_while_native_pages_remain(harness):
    from prompt_evidence import prompt_evidence_copy
    value = uk._fetch()['context']
    projected = prompt_evidence_copy(value)
    assert 'uk_conference_receipt' not in projected
    assert projected['documents'][0]['pages'] == value['documents'][0]['pages']
    assert projected['transcript_available'] is False
