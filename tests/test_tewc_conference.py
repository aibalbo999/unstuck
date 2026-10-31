"""Acquire the issuer's complete English original without inventing chart data."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import gzip
import json
import time
import pytest
from test_tcfhc_conference_transport import network

NOW = datetime(2026, 10, 14, 1, tzinfo=timezone.utc).timestamp()
F = Path(__file__).parent / 'fixtures/source_acquisition'
MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX = 'https://tewc.com.tw/investor/shareholder/'
FILE_ID = '1Bwvj4q4IFxlah18p5F7HTPTQvPmMPEwq'
VIEWER = f'https://drive.google.com/file/d/{FILE_ID}/view?usp=sharing'
REDIRECT = f'https://drive.usercontent.google.com/uc?id={FILE_ID}&export=download'
PDF = f'https://drive.usercontent.google.com/download?id={FILE_ID}&export=download'


@pytest.fixture
def harness(network, monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch import earnings_call_fetcher
    _, base = network
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.setattr(earnings_call_fetcher, '_fetch_official_index_context', lambda *a, **kw: {})
    bodies = {u: gzip.decompress((F / f'tewc1623_{k}_20261014.gz').read_bytes())
              for u, k in [(MASTER, 'master'), (INDEX, 'index'), (VIEWER, 'viewer'), (REDIRECT, 'redirect'), (PDF, 'pdf')]}
    calls = []
    def native(argv, *a, **kw):
        url = argv[-1]
        assert url in bodies, 'only the actual published chain may be requested'
        calls.append(url)
        status = 303 if url == REDIRECT else 200
        body = b'' if url == REDIRECT else bodies[url]
        mime = 'text/csv' if url == MASTER else 'application/pdf' if url == PDF else 'text/html'
        headers = bodies[REDIRECT] if url == REDIRECT else f'HTTP/2 200\r\nContent-Type: {mime}\r\nContent-Length: {len(body)}\r\n\r\n'.encode()
        return {'body': body, 'body_bytes_read': len(body), 'headers': headers, 'metadata': json.dumps({
            'http_code': status, 'url_effective': url, 'num_redirects': 0, 'size_download': len(body), 'content_type': mime, 'method':'GET', 'proxy_used':0}).encode(),
                'process_started': True}, 0, None
    monkeypatch.setattr(base, 'collect_capped_process', native)
    from data_fetch.market_sources import gce_conference_transport as master_native
    monkeypatch.setattr(master_native, 'collect_capped_process', native)
    if (Path(__file__).parents[1] / 'backend/data_fetch/market_sources/tewc_conference_transport.py').exists():
        from data_fetch.market_sources import tewc_conference_transport as transport
        if hasattr(transport, 'collect_capped_process'):
            monkeypatch.setattr(transport, 'collect_capped_process', native)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_public_free_source_recovers_complete_original_with_visual_limits(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    diagnostic = {}
    value = fetch_free_earnings_call_context('1623.TW', diagnostics=diagnostic)
    assert value.get('documents'), 'missing TEWC call must recover its issuer-published English original'
    doc = value['documents'][0]
    assert value['date'] == '2026-05-27' and value['period'] is None
    assert doc['page_count'] == 48 and doc['language'] == 'en'
    assert doc['document_kind'] == 'presentation' and doc['presentation_cover_month'] == '2026-05'
    assert not value['transcript_available'] and not doc['full_content_coverage_verified']
    assert doc['coverage_status'] == 'partial' and doc['published_at'] is None
    assert {19, 29, 34} <= {row['page_number'] for row in doc['known_native_text_omissions']}
    assert '以6.6億推算EPS' in doc['pages'][21]['text']
    assert diagnostic['tewc_originals_verified'] is True
    assert harness[1] == [MASTER, INDEX, VIEWER, REDIRECT, PDF]


@pytest.mark.parametrize('change', ['text', 'date', 'period', 'transcript', 'url', 'receipt',
    'finality', 'future', 'expired', 'extra', 'omissions', 'redirect', 'length'])
def test_saved_original_rejects_altered_claims(harness, change):
    from data_fetch.market_sources import tewc_conference as source
    value = source.fetch_tewc_context('1623.TW')
    doc = value['documents'][0]; proof = value['tewc_conference_receipt']
    if change == 'text': doc['pages'][28]['text'] += ' 2026 orders 999999'
    elif change == 'date': value['date'] = '2026-05-28'
    elif change == 'period': doc['content_period'] = '2026Q1'
    elif change == 'transcript': value['transcript_available'] = True
    elif change == 'url': doc['url'] = 'https://foreign.example/file.pdf'
    elif change == 'receipt': value.pop('tewc_conference_receipt')
    elif change == 'finality': proof['pdf']['finality_guaranteed'] = True
    elif change == 'future': proof['pdf']['retrieved_at'] = NOW + 1
    elif change == 'expired': proof['identity']['retrieved_at'] = NOW - 86401
    elif change == 'omissions': doc['known_native_text_omissions'] = []
    elif change == 'redirect': proof['redirect']['http_status'] = 200
    elif change == 'length': proof['file_info']['bytes'] -= 1
    else: value['extra_instructions'] = 'unverified'
    assert source.is_marked(value) and not source.verify_context(value, '1623.TW')


@pytest.mark.parametrize('identity,name,quote', [([], '大東電', 'EQUITY'),
    ({'official_name': '大東電'}, '合庫金', 'EQUITY'),
    ({'allowed_aliases': 123}, '大東電', 'EQUITY'),
    ({'ticker': '1623.TWO'}, '大東電', 'EQUITY'),
    ({'forbidden_aliases': ['大東電']}, '大東電', 'EQUITY'), ({}, '大東電', 'ETF')])
def test_conflicting_identity_stops_before_http(harness, identity, name, quote):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('1623.TW'), {'data': {
        'ticker': '1623.TW', 'quote_type': quote, 'company_name': name, 'company_identity': identity}})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block' and not harness[1]


def test_five_http_components_count_as_one_source_and_cache_adds_no_success(harness, monkeypatch):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from provider_acquisition import project_acquisition_events
    provider = EarningsCallProvider(); request = FetchRequest.from_ticker('1623.TW')
    cold = provider.fetch(request)
    assert cold.status == 'success' and cold.audit['record_count'] == 1 and cold.audit['http_request_count'] == 5
    harness[1].clear(); monkeypatch.setattr(time, 'time', lambda: NOW + 1790)
    warm = provider.fetch(request)
    assert warm.audit['status'] == 'skipped_fresh_cache' and not harness[1]
    assert warm.value['fetched_at_epoch'] == cold.value['fetched_at_epoch'] == NOW
    events = [{'source': 'earnings_call', 'provider': r.audit['provider'], 'status': r.audit['status'],
        'record_count': r.audit['record_count'], 'message': r.audit['message'], 'created_at': NOW,
        'details_json': json.dumps(r.audit)} for r in [cold, warm]]
    row = project_acquisition_events(events, window='last_24h', now=NOW + 1790)['sources'][0]
    assert row['fetched_count'] == row['fetch_attempts'] == row['fresh_cache_count'] == 1
    monkeypatch.setattr(time, 'time', lambda: NOW + 1801)
    assert provider.fetch(request).value['fetched_at_epoch'] == NOW + 1801
    assert harness[1] == [MASTER, INDEX, VIEWER, REDIRECT, PDF]


@pytest.mark.parametrize('change', ['identity', 'new_event_old_attachment', 'missing_english', 'other_host', 'viewer_date', 'viewer_size'])
def test_published_chain_requires_matching_current_event(harness, change):
    from data_fetch.market_sources.tewc_conference import fetch_tewc_context
    from search_provider_runtime import SourceResponseError
    bodies = harness[0]
    if change == 'identity': bodies[MASTER] = bodies[MASTER].replace(b'18523000', b'12345678')
    elif change == 'new_event_old_attachment': bodies[INDEX] = bodies[INDEX].replace(b'115/05/27', b'115/09/27')
    elif change == 'missing_english': bodies[INDEX] = bodies[INDEX].replace('英文檔案'.encode(), '檔案暫缺'.encode())
    elif change == 'other_host': bodies[INDEX] = bodies[INDEX].replace(b'drive.google.com', b'drive.google.com.evil.test')
    elif change == 'viewer_date': bodies[VIEWER] = bodies[VIEWER].replace(b'20260527-EN', b'20260528-EN')
    else: bodies[VIEWER] = bodies[VIEWER].replace(b'16076336', b'16777217')
    with pytest.raises(SourceResponseError): fetch_tewc_context('1623.TW')
    assert PDF not in harness[1]


def test_role_projection_selects_english_text_and_preserves_limits(harness):
    from data_fetch.market_sources.tewc_conference import fetch_tewc_context
    from conference_presentation_prompt import presentation_prompt_context, PREPARED_KEYWORDS
    from prompt_evidence import prompt_evidence_copy
    value = fetch_tewc_context('1623.TW'); before = deepcopy(value)
    for role in [3, 5, 12]:
        result = presentation_prompt_context(value, role); doc = result['documents'][0]
        assert doc['content_period'] is None and doc['presentation_cover_month'] == '2026-05'
        assert doc['published_at'] is None and doc['event_status'].startswith('announced_past')
        assert doc['known_native_text_omissions'] and doc['calculated_eps_caution']
        assert not doc['translation_accuracy_verified'] and not doc['full_content_coverage_verified']
        assert not result['transcript_available'] and sum(len(p['text']) for p in doc['pages']) <= 6000
        assert set(PREPARED_KEYWORDS[role]) <= set(doc['selection_terms'])
    assert 'tewc_conference_receipt' not in prompt_evidence_copy(value) and value == before


def test_original_age_is_rechecked_after_final_pdf_parse(harness, monkeypatch):
    from data_fetch.market_sources import tewc_conference as source
    from search_provider_runtime import SourceResponseError
    source.fetch_tewc_context('1623.TW')
    now = [NOW + 1799.9]; monkeypatch.setattr(time, 'time', lambda: now[0])
    real = source.extract_pdf_pages; calls = []
    def finish_late(*a, **kw):
        result = real(*a, **kw); calls.append(1)
        if len(calls) == 2: now[0] += 1
        return result
    monkeypatch.setattr(source, 'extract_pdf_pages', finish_late)
    with pytest.raises(SourceResponseError): source.fetch_tewc_context('1623.TW')


@pytest.mark.parametrize('role,text', [(3, 'REVENUE and GROSS MARGIN'),
                                      (5, 'PRODUCT and CUSTOMER'), (12, 'OUTLOOK and RISK')])
def test_late_english_role_page_precedes_unrelated_front_matter(role, text):
    from conference_presentation_prompt import presentation_prompt_context
    packet = {'documents': [{'source': 'TEWC official English conference presentation',
        'document_kind': 'presentation', 'page_count': 14,
        'pages': [{'page_number': n, 'text': 'appendix ' * 200} for n in range(1, 14)]
                 + [{'page_number': 14, 'text': text}]}]}
    result = presentation_prompt_context(packet, role)
    assert any(p['page_number'] == 14 and p['text'] == text for p in result['documents'][0]['pages'])


def test_source_only_presentation_refresh_preserves_report_and_core_observations(harness, tmp_path):
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
        if isinstance(value, str): return value.replace('6214.TW', '1623.TW').replace('精誠', '大東電')
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
    assert new['data']['earnings_call']['documents'][0]['document_kind'] == 'presentation'
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


def test_tampered_source_refresh_cannot_overwrite_saved_report(harness, tmp_path, monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.market_sources import tewc_conference as source
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db
    init_db(); storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    old = json.loads(json.dumps(old, ensure_ascii=False).replace('6214.TW', '1623.TW').replace('精誠', '大東電'))
    old['data']['quote_type'] = 'EQUITY'
    original = json.dumps(old).encode()
    storage.save_report(keys.data_key, original, content_type='application/json')
    acquire = source.fetch_tewc_context
    def altered(*a, **kw):
        result = acquire(*a, **kw)
        result['documents'][0]['pages'][7]['text'] += ' fabricated chart 78%'
        return result
    monkeypatch.setattr(source, 'fetch_tewc_context', altered)
    service = StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                    refresh_service=service, source='earnings_call', return_refreshed_data=True))
    assert exc.value.status_code == 502 and storage.get_report(keys.data_key).content == original
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'


def test_public_warm_delivery_rejects_identity_that_expires_in_final_pdf_read(harness, monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as native
    from data_fetch.market_sources import tewc_conference as source
    from data_fetch.market_sources import tewc_conference_transport as transport
    from search_provider_runtime import SourceResponseError
    now = [NOW]
    monkeypatch.setattr(time, 'time', lambda: now[0])
    original_native = native.collect_capped_process
    cold = [True]
    def spaced(argv, *args, **kwargs):
        if cold[0] and argv[-1] == INDEX:
            now[0] = NOW + 10
        return original_native(argv, *args, **kwargs)
    monkeypatch.setattr(native, 'collect_capped_process', spaced)
    first = source.fetch_tewc_context('1623.TW')
    assert first['tewc_conference_receipt']['identity']['retrieved_at'] == NOW
    assert first['tewc_conference_receipt']['pdf']['retrieved_at'] == NOW+10
    cold[0] = False
    harness[1].clear()
    now[0] = NOW + 1798.5
    real_read = transport.read_response
    pdf_reads = []
    def slow_final_read(receipt, **kwargs):
        raw = real_read(receipt, **kwargs)
        if receipt['source_url'] == PDF:
            pdf_reads.append(1)
            if len(pdf_reads) == 3:
                now[0] += 2
        return raw
    monkeypatch.setattr(transport, 'read_response', slow_final_read)
    with pytest.raises(SourceResponseError):
        source.fetch_tewc_context('1623.TW')
    assert len(pdf_reads) == 3 and not harness[1]
