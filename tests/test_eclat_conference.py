"""A future ordinary source request must discover and verify issuer material."""
import gzip
import json
from pathlib import Path
import time
from copy import deepcopy

import pytest

NOW = 1792241204.
MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX = 'https://www.eclat.com.tw/investors/events-presentations/'
PDF = 'https://eclatglobal.s3.amazonaws.com/uploads/2026/08/2026_eclat_Investor-Conference-Slides_Q2_en.pdf'
F = Path(__file__).parent / 'fixtures/source_acquisition'


@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch import earnings_call_fetcher
    from data_fetch.market_sources import issuer_news_transport as native, gce_conference_transport as master_native
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.setattr(earnings_call_fetcher, '_fetch_official_index_context', lambda *a, **k: {})
    bodies = {MASTER: gzip.decompress((F/'tcfhc5880_master_20261013.gz').read_bytes()),
              INDEX: gzip.decompress((F/'eclat1476_index_20261017.gz').read_bytes()),
              PDF: gzip.decompress((F/'eclat1476_pdf_20261017.gz').read_bytes())}
    calls = []
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in native.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)

    def process(args, deadline, **options):
        url = args[-1]
        assert url in bodies, 'unexpected external URL: '+url
        raw = bodies[url]; calls.append(url)
        content_type = 'text/csv' if url == MASTER else 'text/html' if url == INDEX else 'application/pdf'
        return {'body': raw, 'headers': ('HTTP/2 200\r\nContent-Type: '+content_type+'\r\n\r\n').encode(),
                'metadata': json.dumps({'http_code':200,'url_effective':url,'num_redirects':0,
                    'size_download':len(raw),'content_type':content_type,'method':'GET','proxy_used':0}).encode(),
                'process_started':True}, 0, None
    for module in (native, master_native):
        monkeypatch.setattr(module, 'collect_capped_process', process)
        monkeypatch.setattr(module, 'proxy_url_for_request', lambda *a: None)
        monkeypatch.setattr(module, 'observe_http_response', lambda *a: None)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_normal_request_discovers_latest_official_document(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    details = {}; value = fetch_free_earnings_call_context('1476.TW', diagnostics=details)
    assert value.get('documents'), 'normal acquisition must retrieve the official presentation body'
    document = value['documents'][0]
    assert value['date'] == '2026-08-18' and document['url'] == PDF
    assert document['page_count'] == len(document['pages']) == 19
    assert value['transcript_available'] is False
    assert document['coverage_status'] == 'partial' and document['financial_statement_complete'] is False
    assert details['eclat_originals_verified'] is True
    assert harness[1] == [MASTER, INDEX, PDF]


def test_source_only_preserves_identity_gate(harness):
    import asyncio
    from data_fetch import StockDataService
    from data_fetch.types import FetchRequest
    value = asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker('1476.TW'), 'earnings_call',
        context={'data': {'ticker':'1476.TW', 'quote_type':'EQUITY', 'company_name':'先益'}}))
    assert value.source_audit[0]['error_kind'] == 'context_unverified'
    assert not harness[1]


def test_private_receipts_never_enter_general_prompts(harness):
    from prompt_evidence import prompt_evidence_copy
    value = prompt_evidence_copy({'earnings_call': {'eclat_conference_receipt': {'raw_response_path':'private/path'}}})
    assert value == {'earnings_call': {}}


@pytest.mark.parametrize('change', ['text','date','url','transcript','receipt','age','identity'])
def test_replay_rejects_altered_evidence(harness, change):
    from data_fetch.market_sources import eclat_conference as source
    value = source.fetch_eclat_context('1476.TW')
    if change == 'text': value['documents'][0]['pages'][12]['text'] += ' fabricated'
    elif change == 'date': value['date'] = '2026-10-17'
    elif change == 'url': value['documents'][0]['url'] += '?new=1'
    elif change == 'transcript': value['transcript_available'] = True
    elif change == 'receipt': value.pop('eclat_conference_receipt')
    elif change == 'age': value['eclat_conference_receipt']['pdf']['retrieved_at'] = NOW-1801
    else: value['ticker'] = '1104.TW'
    assert source.is_marked(value) and not source.verify_context(value, '1476.TW')


def test_dynamic_future_event_comes_from_new_index(harness):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources.eclat_conference import select_presentation
    soup = BeautifulSoup(harness[0][INDEX], 'html.parser'); card = soup.select_one('div.pt-event')
    card.select_one('.pt-event__date__day').string = '12'
    card.select_one('.pt-event__date__month').clear()
    card.select_one('.pt-event__date__month').append('Oct ')
    year = soup.new_tag('span'); year.string = '2026'; card.select_one('.pt-event__date__month').append(year)
    a = next(a for a in card.find_all('a',href=True) if a.get_text(' ',strip=True)=='Presentation Slides (PDF)')
    new_url = PDF.replace('/08/', '/10/').replace('_Q2_', '_Q3_'); a['href'] = new_url
    selected = select_presentation(str(soup).encode(), NOW)
    assert selected['event_date'] == '2026-10-12' and selected['pdf_url'] == new_url


@pytest.mark.parametrize('edit', ['missing','duplicate_pdf','duplicate_event','bad_host','truncated'])
def test_bad_latest_event_cannot_fall_back_to_stale_file(harness, edit):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources.eclat_conference import select_presentation
    soup = BeautifulSoup(harness[0][INDEX], 'html.parser'); card = soup.select_one('div.pt-event')
    a = next(a for a in card.find_all('a',href=True) if a.get_text(' ',strip=True)=='Presentation Slides (PDF)')
    if edit == 'missing': a.decompose()
    elif edit == 'duplicate_pdf': a.insert_after(deepcopy(a))
    elif edit == 'duplicate_event': card.insert_after(deepcopy(card))
    elif edit == 'bad_host': a['href'] = PDF.replace('s3.amazonaws.com', 'evil.example')
    raw = str(soup).encode()
    if edit == 'truncated': raw = raw.replace(b'</html>',b'')
    with pytest.raises(ValueError): select_presentation(raw, NOW)


def test_warm_pdf_not_counted_as_new_data_and_new_index_is_checked(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    provider = EarningsCallProvider(); request = FetchRequest.from_ticker('1476.TW')
    first = provider.fetch(request); second = provider.fetch(request)
    assert first.status == 'success' and first.audit['record_count'] == 1
    assert second.status == 'skipped_fresh_cache'
    assert harness[1] == [MASTER, INDEX, PDF, INDEX]


def test_roles_keep_complete_period_tables_and_exclude_ambiguous_graphs(harness):
    from data_fetch.market_sources import eclat_conference as source
    from conference_presentation_prompt import presentation_prompt_context
    context = source.fetch_eclat_context('1476.TW')
    for agent in (3, 5, 12):
        projected = presentation_prompt_context(context, agent)
        assert projected['transcript_available'] is False and projected['evidence_policy']
        pages = projected['documents'][0]['pages']; numbers = {page['page_number'] for page in pages}
        assert not numbers.intersection({4,6,7,8,10,11,12,15,16,17,18,19})
        assert all(not page['content_truncated'] for page in pages)
        if agent in (3,12):
            for n,period in ((13,'2026 Q2'),(14,'2026 H1')):
                page = next(p for p in pages if p['page_number']==n)
                assert period in page['text'] and 'Expressed in Thousands of NTD' in page['text']
                assert 'Earnings per share (in dollars)' in page['text']
    context['documents'][0]['pages'][12]['text'] += ' invented'
    assert presentation_prompt_context(context, 3) == {}


@pytest.mark.parametrize('tamper', [False, True])
def test_saved_report_preserves_analysis_and_requires_originals(harness, tmp_path, monkeypatch, tamper):
    import asyncio
    from fastapi import HTTPException
    from data_fetch import StockDataService, ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.market_sources import eclat_conference as source
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db
    init_db(); storage = InMemoryStorage(); filename, keys, old = saved_report(storage)
    old = json.loads(json.dumps(old, ensure_ascii=False).replace('6214.TW','1476.TW').replace('精誠','儒鴻'))
    old['data']['quote_type'] = 'EQUITY'; original = json.dumps(old).encode()
    storage.save_report(keys.data_key, original, content_type='application/json')
    acquire = source.fetch_eclat_context
    def tampered(*a, **kw):
        value = acquire(*a, **kw); value['documents'][0]['pages'][0]['text'] += ' altered'; return value
    if tamper:
        monkeypatch.setattr(source, 'fetch_eclat_context', tampered)
    service = StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    def refresh():
        return asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
            refresh_service=service, source='earnings_call'))
    if tamper:
        with pytest.raises(HTTPException) as error: refresh()
        assert error.value.status_code == 502
        assert storage.get_report(keys.data_key).content == original
    else:
        assert refresh()['analysis_text_stale'] is True
        saved = json.loads(storage.get_report(keys.data_key).content)
        assert saved['data']['earnings_call']['documents'][0]['page_count'] == 19
        for key in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
            assert saved[key] == old[key]
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'


@pytest.mark.parametrize('url', [PDF+'?a=1', PDF+'#x', PDF.replace('https:', 'http:'),
    PDF.replace('s3.amazonaws.com','s3.amazonaws.com.evil.example'), PDF.replace('/08/','/99/'), PDF.replace('/2026/','/2025/')])
def test_unpublished_routes_never_reach_transport(harness, url):
    from data_fetch.market_sources.eclat_conference_transport import EclatConferenceHttp
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError): EclatConferenceHttp(time.monotonic()+20).get_receipt(url)
    assert not harness[1]


def test_standalone_valid_pdf_route_also_requires_current_index(harness):
    from data_fetch.market_sources.eclat_conference_transport import EclatConferenceHttp
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError): EclatConferenceHttp(time.monotonic()+20).get_receipt(PDF)
    assert not harness[1]


def test_issuer_failure_retains_failed_observation_and_uses_official_fallback(harness, monkeypatch):
    from data_fetch.market_sources import eclat_conference as source
    from data_fetch import earnings_call_fetcher as fetcher
    from search_provider_runtime import SourceResponseError
    import search_provider_runtime
    observations = []
    def failed(*a, **kw):
        error = SourceResponseError('parse_error')
        error.diagnostic.update(actual_provider=source.PROVIDER, http_request_sent=True, http_request_count=1)
        raise error
    monkeypatch.setattr(source, 'fetch_eclat_context', failed)
    monkeypatch.setattr(search_provider_runtime, 'record_observation', lambda *a, **kw: observations.append((a,kw)))
    fallback = {'source':'MOPS investor conference','date':'2026-08-18','materials':[]}
    def official(*a, **kw):
        kw['diagnostics'].update(actual_provider='MOPS investor conference',http_request_sent=True,http_request_count=1)
        return deepcopy(fallback)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', official)
    diagnostic = {}; value = fetcher.fetch_free_earnings_call_context('1476.TW', diagnostics=diagnostic)
    assert value == fallback and diagnostic['actual_provider'] == 'MOPS investor conference'
    assert diagnostic['http_request_count'] == 2 and diagnostic['component_statuses']['issuer_content']['error_kind'] == 'parse_error'
    assert len(observations) == 1 and observations[0][1]['outcome'] == 'failure'


@pytest.mark.parametrize('kind', ['timeout','single_flight_busy','lease_lost','guard_storage_unavailable','context_unverified'])
def test_failed_operation_ownership_never_starts_fallback(harness, monkeypatch, kind):
    from data_fetch.market_sources import eclat_conference as source
    from data_fetch import earnings_call_fetcher as fetcher
    from search_provider_runtime import SourceResponseError
    def failed(*a, **kw): raise SourceResponseError(kind)
    monkeypatch.setattr(source, 'fetch_eclat_context', failed)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', lambda *a, **kw: pytest.fail('unexpected fallback'))
    with pytest.raises(SourceResponseError) as error: fetcher.fetch_free_earnings_call_context('1476.TW')
    assert error.value.error_kind == kind


def test_source_only_observation_counts_one_acquisition_not_three_http_requests(harness):
    import asyncio
    from data_fetch import StockDataService
    from data_fetch.types import FetchRequest
    from test_report_refresh_acquisition_audit import init_db, events
    init_db()
    value = asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker('1476.TW'), 'earnings_call',
        context={'data': {'ticker':'1476.TW','quote_type':'EQUITY','company_name':'儒鴻 / Eclat Textile Co., Ltd.'}}))
    audit = value.source_audit[0]
    rows = [r for r in events() if json.loads(r['details_json']).get('fetch_id') == audit['fetch_id']]
    assert len(rows) == 1 and rows[0]['status'] == 'success' and rows[0]['record_count'] == 1
    assert audit['http_request_count'] == 3 and value.data['earnings_call']['documents'][0]['page_count'] == 19


def test_invalid_source_context_is_not_missing_context(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('1476.TW'), {'data':False})
    assert result.status == 'unavailable' and result.audit['error_kind'] == 'context_unverified'
    assert not harness[1]


def test_role_verification_timeout_omits_unverified_evidence(harness, monkeypatch):
    from data_fetch.market_sources import eclat_conference as source
    from conference_presentation_prompt import presentation_prompt_context
    from search_provider_runtime import SourceResponseError
    value = source.fetch_eclat_context('1476.TW')
    def timeout(*a, **kw): raise SourceResponseError('timeout')
    monkeypatch.setattr(source, 'verify_context', timeout)
    assert presentation_prompt_context(value, 3) == {}
