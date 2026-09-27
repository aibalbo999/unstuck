"""Official presentation content must retain source and coverage limitations."""
from datetime import date
import hashlib
import json
from pathlib import Path
import time

import httpx
import pytest


INDEX = '''<html><title>世紀民生科技股份有限公司</title><a href="https://www.myson.com.tw/public/uploads/pdf/new.pdf">1150415世紀民生法說會簡報</a><a href="https://www.myson.com.tw/public/uploads/pdf/old.pdf">1140918世紀民生法說會簡報</a></html>'''.encode()


def test_index_uses_event_anchor_date_not_upload_filename():
    from company_conference_content import select_presentation
    selected = select_presentation(INDEX, today=date(2026, 9, 27))
    assert selected['event_date'] == '2026-04-15'
    assert selected['url'].endswith('/new.pdf')


@pytest.mark.parametrize('label,url', [
    ('1150415另一公司法說會簡報', 'https://www.myson.com.tw/public/uploads/pdf/new.pdf'),
    ('1150415世紀民生法說會簡報(英)', 'https://www.myson.com.tw/public/uploads/pdf/new.pdf'),
    ('1150415世紀民生法說會簡報', 'https://example.com/fake.pdf'),
    ('1150415世紀民生法說會簡報', 'https://www.myson.com.tw@127.0.0.1/fake.pdf'),
    ('1150415世紀民生法說會簡報', 'https://www.myson.com.tw/public/uploads/pdf/new.pdf?redirect=x'),
    ('1150230世紀民生法說會簡報', 'https://www.myson.com.tw/public/uploads/pdf/new.pdf'),
    ('1160415世紀民生法說會簡報', 'https://www.myson.com.tw/public/uploads/pdf/new.pdf'),
])
def test_invalid_candidate_is_never_promoted(label, url):
    from company_conference_content import select_presentation
    assert select_presentation(f'<title>世紀民生科技股份有限公司</title><a href="{url}">{label}</a>'.encode(), today=date(2026, 9, 27)) is None


@pytest.fixture
def source(monkeypatch):
    import company_conference_content as module
    import cache_store
    import search_provider_runtime as runtime
    store, observations, calls = {}, [], []
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: store.get(key))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds: store.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: store.get(key))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: store.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda rows: observations.extend(rows))
    def get(url, **kwargs):
        calls.append(url)
        raw = INDEX if url == module.INDEX_URL else b'%PDF-FAKE-OFFLINE'
        kwargs['diagnostics'].update(http_request_sent=True, http_status=200,
            response_complete=True, response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw))
        return raw
    monkeypatch.setattr(module, 'download', get)
    def extract(raw, **kwargs):
        return {'page_count': 2, 'pages': [{'page_number': 1, 'text': '世紀民生（股票代號：5314）原文'}, {'page_number': 2, 'text': ''}],
                'empty_pages': [2], 'coverage_status': 'partial', 'parser_version': 'pypdf-test', 'content_sha256': hashlib.sha256(raw).hexdigest()}
    monkeypatch.setattr(module, 'extract_pdf_pages', extract)
    return module, store, observations, calls


def test_real_content_is_partial_and_never_a_transcript(source):
    module, _, observations, calls = source
    details = {}
    value = module.fetch_company_conference('5314.TWO', diagnostics=details)
    assert len(calls) == 2
    assert value['transcript_available'] is False and value['transcript_excerpt'] == ''
    assert not value.get('content') and not value.get('transcript')
    assert value['date'] == '2026-04-15'
    document = value['documents'][0]
    assert document['document_kind'] == 'presentation'
    assert document['missing_text_pages'] == [2] and document['page_count'] == 2
    assert document['pages'][0]['text'].endswith('原文')
    assert details['coverage_status'] == 'partial'
    assert len(observations) == 2
    assert all(row['status'] == 'degraded_enrichment' for row in observations)
    assert all(row['http_request_sent'] is True for row in observations)


def test_shared_content_cache_preserves_original_acquisition_time(source):
    module, _, observations, calls = source
    first_details, second_details = {}, {}
    first = module.fetch_company_conference('5314.TWO', diagnostics=first_details)
    second = module.fetch_company_conference('5314.TWO', diagnostics=second_details)
    assert second == first and len(calls) == 2 and len(observations) == 2
    assert second_details['cache_hit'] is True
    assert second_details['http_request_sent'] is False
    assert second_details['fetched_at_epoch'] == first_details['fetched_at_epoch']


def test_pdf_refusal_keeps_index_partial_and_failure_then_cools_down(source, monkeypatch):
    module, _, observations, calls = source
    original = module.download
    def get(url, **kwargs):
        if url == module.INDEX_URL:
            return original(url, **kwargs)
        calls.append(url)
        kwargs['diagnostics'].update(http_request_sent=True, http_status=403)
        response = httpx.Response(403, request=httpx.Request('GET', url))
        response.raise_for_status()
    monkeypatch.setattr(module, 'download', get)
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):
        module.fetch_company_conference('5314.TWO')
    with pytest.raises(SourceResponseError):
        module.fetch_company_conference('5314.TWO')
    assert len(calls) == 2
    assert [row['status'] for row in observations] == ['degraded_enrichment', 'error']
    assert observations[1]['http_status'] == 403


def test_wrong_issuer_cover_is_not_content_success(source, monkeypatch):
    module, _, observations, _ = source
    monkeypatch.setattr(module, 'extract_pdf_pages', lambda *a, **k: {'page_count': 1, 'pages': [{'page_number': 1, 'text': '其他公司2330'}], 'coverage_status': 'complete', 'empty_pages': []})
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):
        module.fetch_company_conference('5314.TWO')
    assert observations[-1]['status'] == 'error'


def test_unconfigured_company_has_no_request(source):
    module, _, observations, calls = source
    assert module.fetch_company_conference('2330.TW') == {}
    assert not observations and not calls


def test_native_text_complete_does_not_certify_all_presentation_content(source, monkeypatch):
    module, _, observations, _ = source
    monkeypatch.setattr(module, 'extract_pdf_pages', lambda *a, **k: {
        'page_count': 1, 'pages': [{'page_number': 1, 'text': '世紀民生5314 visible native text'}],
        'empty_pages': [], 'coverage_status': 'complete', 'parser_version': 'pypdf-test'})
    value = module.fetch_company_conference('5314.TWO')
    assert value['coverage_status'] == 'partial'
    document = value['documents'][0]
    assert document['native_text_coverage'] == 'complete'
    assert document['full_content_coverage_verified'] is False
    assert all(row['status'] == 'degraded_enrichment' for row in observations)


@pytest.mark.parametrize('guard', [{}, {'retry_at': True}, {'retry_at': float('nan')}, {'retry_at': '0'}])
def test_malformed_host_guard_stops_requests(source, guard):
    module, store, observations, calls = source
    store[module.GUARD_KEY] = guard
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):
        module.fetch_company_conference('5314.TWO')
    assert not calls
    assert observations[0]['http_request_sent'] is False
    assert observations[0]['error_kind'] == 'guard_storage_unavailable'


def test_http_provider_service_projection_has_no_double_count(source, monkeypatch):
    module, _, observations, _ = source
    import official_financials
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', lambda *a, **k: pytest.fail('configured issuer content precedes MOPS'))
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.service import StockDataService
    import data_fetch.service as service
    monkeypatch.setattr(service, 'record_source_audit_entries', lambda rows: observations.extend(rows))
    request = FetchRequest.from_ticker('5314.TWO')
    provider = EarningsCallProvider().fetch(request)
    assert provider.status == 'degraded_enrichment'
    StockDataService()._build_result(request, {'ticker': '5314.TWO', 'earnings_call': provider.value, 'source_audit': [provider.audit]}, 1)
    from provider_acquisition import project_acquisition_events
    now = time.time()
    rows = [{**row, 'created_at': now, 'details_json': json.dumps(row)} for row in observations]
    summary = project_acquisition_events(rows, window='last_24h', now=now)['sources'][0]
    assert summary['http_attempt_count'] == 2
    assert summary['fetch_attempts'] == 2 and summary['degraded_count'] == 2
    assert summary['fetched_count'] == 0 and summary['aggregate_count'] == 1


def test_partial_pages_reach_fundamental_roles_but_not_management_tone(source):
    module, _, _, _ = source
    value = module.fetch_company_conference('5314.TWO')
    from agent_runtime.prompting import data_for_agent_prompt
    from prompt_builder_helpers import _agent_context
    from agent_runtime.deterministic_skips import _earnings_call_transcript
    data = {'ticker': '5314.TWO', 'earnings_call': value}
    for agent in (3, 5, 12):
        routed = data_for_agent_prompt(agent, data)
        assert 'earnings_call' not in routed
        projected = _agent_context(routed)['conference_presentation']
        assert projected['transcript_available'] is False
        doc = projected['documents'][0]
        assert doc['pages'][0]['page_number'] == 1 and doc['pages'][0]['text'].endswith('原文')
        assert doc['missing_text_pages'] == [2]
    for agent in (1, 4, 17, 20, 24):
        assert 'conference_presentation' not in data_for_agent_prompt(agent, data)
    assert _earnings_call_transcript(data, {}) == ''
    assert 'documents' not in data_for_agent_prompt(20, data)['earnings_call']
    assert value['documents']  # projection never mutates source


def test_presentation_cannot_bypass_roles_through_rag():
    from rag_runtime.documents import collect_rag_documents
    call = {'transcript_excerpt': 'Real transcript evidence remains visible.',
            'documents': [{'document_kind': 'presentation', 'title': 'Hidden presentation title',
                           'pages': [{'page_number': 1, 'text': 'HIDDEN_PRESENTATION_PAYLOAD'}]},
                          {'document_kind': 'transcript', 'text': 'Other transcript document remains visible.'}]}
    value = {'earnings_call': call, 'business_description': 'Ordinary business description remains visible.'}
    records = json.dumps(collect_rag_documents(value))
    assert 'HIDDEN_PRESENTATION_PAYLOAD' not in records and 'Hidden presentation title' not in records
    assert 'Real transcript evidence remains visible.' in records
    assert 'Other transcript document remains visible.' in records
    assert 'Ordinary business description remains visible.' in records
    assert call['documents'][0]['pages'][0]['text'] == 'HIDDEN_PRESENTATION_PAYLOAD'


@pytest.mark.parametrize('role', [20, 21])
def test_presentation_cannot_bypass_roles_through_state(role):
    from state_memory import state_view_for, initialize_agent_state
    from agent_runtime.prompting import build_state_view_section
    call = {'transcript_excerpt': 'Real transcript evidence remains visible.',
            'documents': [{'document_kind': 'presentation', 'pages': [{'page_number': 1, 'text': 'HIDDEN_STATE_PRESENTATION'}]}]}
    state = initialize_agent_state({'ticker': '5314.TWO', 'earnings_call': call})
    view = state_view_for(role, state)
    rendered = build_state_view_section(role, {'agent_state': state})
    assert 'HIDDEN_STATE_PRESENTATION' not in json.dumps(view)
    assert 'HIDDEN_STATE_PRESENTATION' not in rendered
    assert view['earnings_call_context']['transcript_excerpt'] == call['transcript_excerpt']
    assert 'Real transcript evidence remains visible.' in rendered
    assert state.normalized_financials['earnings_call']['documents']
