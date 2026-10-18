"""Recover an issuer's published QA summary without inventing a transcript."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import gzip
import time

import pytest

NOW = datetime(2026, 10, 13, 13, tzinfo=timezone.utc).timestamp()
F = Path(__file__).parent / 'fixtures/source_acquisition'
MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX = 'https://www.tcfhc.com.tw/investors-relations/event/2026year'
EVENT = INDEX + '/2026q2'
QA = 'https://www.tcfhc.com.tw/-/media/files/tcfhc/investors-relations/event/2026year/2026q2question.pdf?sc_lang=zh-tw&hash=59FFDEA57931BF37983CFC2556648D41'


@pytest.fixture
def harness(monkeypatch):
    from data_fetch import earnings_call_fetcher
    from cache_backends import InMemoryCache
    import cache_store
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.setattr(earnings_call_fetcher, '_fetch_official_index_context', lambda *a, **k: {})
    bodies = {url: gzip.decompress((F / ('tcfhc5880_' + kind + '_20261013.gz')).read_bytes())
              for url, kind in [(MASTER, 'master'), (INDEX, 'index'), (EVENT, 'event'), (QA, 'qa')]}
    calls = []
    if (Path(__file__).parents[1] / 'backend/data_fetch/market_sources/tcfhc_conference_transport.py').exists():
        from data_fetch.market_sources.tcfhc_conference_transport import ConferenceHttp
        from data_fetch.market_sources import issuer_news_transport as native
        from data_fetch.market_sources import gce_conference_transport as master_native
        # Exercise the shared master native boundary with the same mutable CSV
        # original. Issuer-body fixtures remain at their previous boundary.
        import json
        monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
        for key in native.PROXY_ENV:
            monkeypatch.delenv(key, raising=False)
        def master_process(args, deadline, **options):
            assert args[-1] == MASTER
            calls.append(MASTER)
            raw = bodies[MASTER]
            return {'body': raw, 'headers': b'HTTP/2 200\r\nContent-Type: text/csv\r\n\r\n',
                    'metadata': json.dumps({'http_code': 200, 'url_effective': MASTER, 'num_redirects': 0,
                        'size_download': len(raw), 'content_type': 'text/csv', 'method': 'GET', 'proxy_used': 0}).encode(),
                    'process_started': True}, 0, None
        for module in (native, master_native):
            monkeypatch.setattr(module, 'collect_capped_process', master_process)
            monkeypatch.setattr(module, 'proxy_url_for_request', lambda *a: None)
            monkeypatch.setattr(module, 'observe_http_response', lambda *a: None)
        def download(self, url, diagnostic):
            from hashlib import sha256
            import base64
            calls.append(url)
            self.http_request_count += 1
            diagnostic.update(http_request_sent=True, http_status=200)
            raw = bodies[url]
            return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                    'http_status': 200, 'response_complete': True, 'request_method': 'GET',
                    'http_status_observed': True, 'fetched_at_epoch': time.time()}
        monkeypatch.setattr(ConferenceHttp, '_download', download)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_public_free_call_recovers_issuer_qa_original_instead_of_empty_index(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    diagnostic = {}
    value = fetch_free_earnings_call_context('5880.TW', diagnostics=diagnostic)
    assert value.get('documents'), 'the original complete issuer QA must replace metadata-only fallback'
    doc = value['documents'][0]
    assert doc['document_kind'] == 'issuer_qa_summary'
    assert doc['page_count'] == 10 and len(doc['pages']) == 10
    assert value['date'] == '2026-08-31'
    assert value['transcript_available'] is False and not value['transcript_excerpt']
    assert diagnostic['tcfhc_originals_verified'] is True


def test_public_provider_rejects_context_override_before_network(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('5880.TW'), {'data': {
        'ticker': '5880.TW', 'quote_type': 'ETF', 'company_identity': {'ticker': '5880.TW', 'official_name': '合庫金'}}})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert not harness[1]


@pytest.mark.parametrize('change', ['text', 'date', 'period', 'transcript', 'url', 'hash', 'missing_receipt',
                                  'fake_cache_status', 'future_epoch', 'expired', 'extra'])
def test_tampered_saved_packet_is_rejected(harness, change):
    from data_fetch.market_sources import tcfhc_conference as source
    value = source.fetch_tcfhc_context('5880.TW')
    if change == 'text': value['documents'][0]['pages'][0]['text'] += 'invented'
    elif change == 'date': value['date'] = '2026-09-01'
    elif change == 'period': value['documents'][0]['content_period'] = '2026Q3'
    elif change == 'transcript': value['transcript_available'] = True
    elif change == 'url': value['documents'][0]['url'] = 'https://other.example/a.pdf'
    elif change == 'hash': value['tcfhc_qa_receipt']['qa']['raw_response_sha256'] = '0' * 64
    elif change == 'missing_receipt': value.pop('tcfhc_qa_receipt')
    elif change == 'fake_cache_status': value['tcfhc_qa_receipt']['qa']['http_status'] = None
    elif change == 'future_epoch': value['tcfhc_qa_receipt']['qa']['retrieved_at'] = NOW + 1
    elif change == 'expired': value['tcfhc_qa_receipt']['identity']['retrieved_at'] = NOW - 86401
    else: value['hidden_transcript'] = 'invented'
    assert source.is_marked(value)
    assert not source.verify_context(value, '5880.TW')


def test_cold_then_warm_counts_one_source_acquisition_not_four_downloads(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from provider_acquisition import project_acquisition_events
    import json
    provider = EarningsCallProvider()
    request = FetchRequest.from_ticker('5880.TW')
    cold = provider.fetch(request)
    assert cold.status == 'success' and cold.audit['http_request_count'] == 4
    assert harness[1] == [MASTER, INDEX, EVENT, QA]
    harness[1].clear()
    warm = provider.fetch(request)
    assert warm.audit['status'] == 'skipped_fresh_cache' and not harness[1]
    assert warm.value['fetched_at_epoch'] == cold.value['fetched_at_epoch'] == NOW
    events = []
    for result in [cold, warm]:
        a = result.audit
        events.append({'source': 'earnings_call', 'provider': a['provider'], 'status': a['status'],
                       'record_count': a['record_count'], 'message': a['message'], 'created_at': NOW,
                       'details_json': json.dumps(a)})
    row = project_acquisition_events(events, window='last_24h', now=NOW)['sources'][0]
    assert row['fetched_count'] == row['fetch_attempts'] == row['fresh_cache_count'] == 1


def test_raw_cache_expiry_is_not_renewed_by_repeated_reads(harness, monkeypatch):
    from data_fetch.market_sources import tcfhc_conference as source
    cold = source.fetch_tcfhc_context('5880.TW')
    monkeypatch.setattr(time, 'time', lambda: NOW + 1790)
    harness[1].clear()
    assert source.fetch_tcfhc_context('5880.TW')['fetched_at_epoch'] == cold['fetched_at_epoch']
    assert not harness[1]
    monkeypatch.setattr(time, 'time', lambda: NOW + 1801)
    assert source.fetch_tcfhc_context('5880.TW')['fetched_at_epoch'] == NOW + 1801
    # The shared CSV lifetime remains 1800s; JSON has its own original policy.
    assert harness[1] == [MASTER, INDEX, EVENT, QA]


def test_qa_prompt_has_bounded_excerpts_and_explicit_scope_without_receipts(harness):
    from data_fetch.market_sources import tcfhc_conference as source
    from conference_presentation_prompt import presentation_prompt_context, without_presentation_documents
    from prompt_evidence import prompt_evidence_copy
    value = source.fetch_tcfhc_context('5880.TW'); original = deepcopy(value)
    for agent in [3, 5, 12]:
        projected = presentation_prompt_context(value, agent)
        doc = projected['documents'][0]
        assert doc['document_kind'] == 'issuer_qa_summary' and doc['material_file_date'] == '2026-08-31'
        assert sum(len(p['text']) for p in doc['pages']) <= 6000
        assert '子公司' in projected['evidence_policy'] and projected['transcript_available'] is False
    assert 'documents' not in without_presentation_documents(value)
    assert 'tcfhc_qa_receipt' not in prompt_evidence_copy(value)
    assert value == original


@pytest.mark.parametrize('kind', ['timeout', 'single_flight_busy', 'guard_storage_unavailable'])
def test_terminal_provider_error_does_not_trigger_more_index_requests(harness, monkeypatch, kind):
    from data_fetch.market_sources import tcfhc_conference as source
    from data_fetch import earnings_call_fetcher
    from search_provider_runtime import SourceResponseError
    def fail(*a, **k): raise SourceResponseError(kind)
    monkeypatch.setattr(source, 'fetch_tcfhc_context', fail)
    monkeypatch.setattr(earnings_call_fetcher, '_fetch_official_index_context', lambda *a, **k: pytest.fail('fallback after terminal error'))
    with pytest.raises(SourceResponseError) as exc:
        earnings_call_fetcher.fetch_free_earnings_call_context('5880.TW')
    assert exc.value.error_kind == kind


@pytest.mark.parametrize('change', ['master_ubn', 'wrong_attachment_period', 'future_event', 'ambiguous_qa'])
def test_original_public_evidence_must_match_issuer_and_event(harness, change):
    from data_fetch.market_sources import tcfhc_conference as source
    from search_provider_runtime import SourceResponseError
    bodies, calls = harness
    if change == 'master_ubn': bodies[MASTER] = bodies[MASTER].replace(b'53021433', b'12345678')
    elif change == 'wrong_attachment_period': bodies[EVENT] = bodies[EVENT].replace(b'2026q2question.pdf', b'2026q1question.pdf')
    elif change == 'future_event': bodies[EVENT] = bodies[EVENT].replace(b'2026-08-31', b'2026-12-31')
    else: bodies[EVENT] = bodies[EVENT].replace('投資人提問重點摘要'.encode(), '其他文件'.encode())
    with pytest.raises(SourceResponseError): source.fetch_tcfhc_context('5880.TW')
    assert QA not in calls


def test_source_only_recovery_rejects_tampered_pdf_text_and_keeps_original(harness):
    import asyncio
    from fastapi import HTTPException
    from types import SimpleNamespace
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from report_source_refresh import fetch_report_source_data
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('5880.TW'))
    data = {'ticker': '5880.TW', 'quote_type': 'EQUITY', 'company_name': '合庫金', 'last_price': 99}
    old = {'ticker': '5880.TW', 'data': data, 'source_audit': [{'source': 'market_data', 'status': 'success', 'fetched_at_epoch': NOW - 100}]}
    before = deepcopy(old)
    class Service:
        _fetcher = None
        async def fetch_source_async(self, *a, **kw):
            assert kw['context']['data'] == data
            return SimpleNamespace(data={'ticker': '5880.TW', 'earnings_call': result.value}, source_audit=[result.audit])
    result.value['documents'][0]['pages'][0]['text'] += 'unverified'
    with pytest.raises(HTTPException) as exc: asyncio.run(fetch_report_source_data(old, 'earnings_call', Service()))
    assert exc.value.status_code == 502 and old == before


@pytest.mark.parametrize('identity', [[], False, 0, ''])
def test_malformed_identity_is_rejected_before_acquisition(harness, identity):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('5880.TW'), {'data': {
        'ticker': '5880.TW', 'quote_type': 'EQUITY', 'company_identity': identity}})
    assert result.status == 'unavailable' and not harness[1]


def test_source_only_qa_refresh_preserves_report_and_core_observations(harness, tmp_path):
    import asyncio
    import json
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db, events
    init_db()
    storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    def replace(value):
        if isinstance(value, str): return value.replace('6214.TW', '5880.TW').replace('精誠', '合庫金')
        if isinstance(value, dict): return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list): return [replace(v) for v in value]
        return value
    old = replace(old)
    old['data']['quote_type'] = 'EQUITY'
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    service = StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    response = asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                            refresh_service=service, source='earnings_call', return_refreshed_data=True))
    new = json.loads(storage.get_report(keys.data_key).content)
    assert new['data']['earnings_call']['documents'][0]['document_kind'] == 'issuer_qa_summary'
    for key in ['current_price', 'revenue_history', 'years', 'peer_discovery_results']:
        assert new['data'][key] == old['data'][key]
    assert next(a for a in new['source_audit'] if a['source'] == 'market_data') == old['source_audit'][0]
    for key in ['analysis_evidence', 'report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        assert new[key] == old[key]
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'
    assert response['analysis_text_stale'] is True
    observed = events()
    assert len(observed) == 1 and observed[0]['source'] == 'earnings_call' and observed[0]['status'] == 'success'
