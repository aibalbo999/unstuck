"""Captured original replay and fail-closed CSC source contracts; no live networking."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64
import time
import pytest
from data_fetch.market_sources.csc_conference_transport import MASTER_URL, INDEX_URL, PDF_URL

CHINESE_INDEX_URL = 'https://www.csc.com.tw/csc/ss/pst/pst_index2.html'
CHINESE_PDF_URL = 'https://www.csc.com.tw/csc/ss/pst/pdf/2026Sep23.pdf'
CHINESE_EVIDENCE = Path(__file__).resolve().parents[1] / 'docs/evidence/source-acquisition/20261017/csc-chinese-presentation-fallback'

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'tests/run_prompt_boundary_tests.py').exists())
D = ROOT/'docs/evidence/source-acquisition/20261014/free-gap-followup/industrial-research'
MASTER_FILE = ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW = 1791938000.0


def raw_key(url):
    from data_fetch.market_sources import official_issuer_master
    if url==MASTER_URL:return official_issuer_master.CACHE_KEY
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    return 'shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest()


@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    bodies = {MASTER_URL: MASTER_FILE.read_bytes(), INDEX_URL: (D/'csc-conference-index.body').read_bytes(),
              PDF_URL: (D/'csc-presentation.body').read_bytes(),
              CHINESE_INDEX_URL: (CHINESE_EVIDENCE/'index.html').read_bytes(),
              CHINESE_PDF_URL: (CHINESE_EVIDENCE/'presentation.pdf').read_bytes()}
    calls = []
    def download(self, url, diagnostic):
        raw = bodies[url]; calls.append(url); self.http_request_count += 1
        diagnostic.update(http_request_sent=True, http_status=200, status='complete',
                          response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                'http_status': 200, 'response_complete': True, 'request_method': 'GET',
                'http_status_observed': True, 'fetched_at_epoch': time.time()}
    monkeypatch.setattr(ConferenceHttp, 'download_original', download)
    # New shared-master route is exercised at its real native subprocess seam;
    # saved issuer index/PDF keep their original body seam above.
    import json
    from data_fetch.market_sources import gce_conference_transport as shared_native
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for key in shared_native.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    def process(args,deadline,**options):
        url=args[-1];assert url==MASTER_URL
        calls.append(url);raw=bodies[url]
        return {'body':raw,'headers':f'HTTP/2 200\r\nContent-Type: text/csv\r\nContent-Length: {len(raw)}\r\n\r\n'.encode(),
            'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0,'size_download':len(raw),'content_type':'text/csv','method':'GET','proxy_used':0}).encode(),'process_started':True},0,None
    monkeypatch.setattr(shared_native,'collect_capped_process',process)
    monkeypatch.setattr(shared_native,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(shared_native,'observe_http_response',lambda *a:None)

    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def valid_data():
    return {'ticker': '2002.TW', 'instrument_type': 'EQUITY', 'company_name': '中鋼 / China Steel Corporation',
            'raw_company_name': 'China Steel Corporation', 'company_identity': {'ticker': '2002.TW', 'stock_id': '2002',
            'official_name': '中鋼', 'legal_name': None, 'display_name': '中鋼 / China Steel Corporation',
            'allowed_aliases': ['中鋼', '2002', '2002.TW', '中鋼 / China Steel Corporation', 'CSC'],
            'english_names': ['China Steel Corporation', 'CSC'], 'forbidden_aliases': []}}


def test_public_metadata_gap_requires_official_original_body(harness):
    from data_fetch.market_sources import csc_conference as source
    diagnostic = {}; value = source.fetch_csc_context('2002.TW', diagnostics=diagnostic)
    assert value.get('documents'), 'metadata-only CSC context must acquire the qualified official presentation body'
    doc = value['documents'][0]
    assert value['date'] == doc['event_date'] == '2026-09-23'
    assert value['period'] == doc['content_period'] == ''
    assert doc['content_periods'] == ['2026H1', '2026 Jan-Jul preliminary', 'historical and forward-looking periods']
    assert doc['page_count'] == len(doc['pages']) == 35 and doc['language'] == 'en'
    assert doc['document_kind'] == 'presentation' and doc['csc_glyph_evidence']
    assert value['transcript_available'] is doc['q_and_a_transcript_available'] is False
    assert value['coverage_status'] == doc['coverage_status'] == 'partial'
    assert doc['full_content_coverage_verified'] is False and doc['native_text_coverage'] == 'complete'
    assert doc['financial_scope_caution'] and doc['subsidiary_scope_caution'] and doc['known_native_text_omissions']
    assert doc['published_at'] is doc['material_file_date'] is None
    assert 'Safe Harbor Statement' in doc['pages'][2]['text'] and '*preliminary results' in doc['pages'][10]['text']
    assert harness[1] == [MASTER_URL, INDEX_URL, PDF_URL]
    assert diagnostic['http_request_count'] == 3 and diagnostic['csc_originals_verified'] is True
    assert diagnostic['cache_hit'] is False and source.verify_context(value, '2002.TW', max_age=1800)


def test_official_mops_month_index_recovers_csc_presentation_when_issuer_host_times_out(harness, monkeypatch):
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError

    fixture = ROOT/'tests/fixtures/source_acquisition/csc_mops_month_202609'
    iih_url = 'https://wwwc.twse.com.tw/rwd/en/IIH/company/events?code=2002'
    month_url = ('https://emops.twse.com.tw/server-java/t100sb07_1_e?TYPEK=all&step=show&code=2002'
                 '&LPSHOW_DATE_YY=2026&LPSHOW_DATE_MM=09')
    pdf_url = 'https://emops.twse.com.tw/nas/STR/200220260922E001.pdf'
    harness[0].update({iih_url: (fixture/'iih.json').read_bytes(),
                       month_url: (fixture/'month.html').read_bytes(),
                       pdf_url: harness[0][PDF_URL]})
    normal_download = ConferenceHttp.download_original

    def download_with_issuer_timeout(self, url, diagnostic):
        if url == INDEX_URL:
            harness[1].append(url)
            self.http_request_count += 1
            diagnostic.update(status='error', error_kind='timeout', http_request_sent=True)
            raise SourceResponseError('timeout')
        return normal_download(self, url, diagnostic)

    monkeypatch.setattr(ConferenceHttp, 'download_original', download_with_issuer_timeout)
    diagnostic = {}
    try:
        value = source.fetch_csc_context('2002.TW', diagnostics=diagnostic)
    except SourceResponseError as exc:
        pytest.fail(f'verified MOPS mirror should recover the qualified presentation after CSC timeout: {exc.error_kind}')

    doc = value['documents'][0]
    assert doc['content_sha256'] == source.KNOWN_SHA
    assert doc['native_text_coverage'] == 'complete' and doc['coverage_status'] == 'partial'
    assert value['materials'][0]['url'] == pdf_url
    assert value['source_url'] == month_url
    assert value['date'] == doc['event_date'] == '2026-09-23'
    assert diagnostic['actual_provider'] == 'MOPS published presentation'
    assert diagnostic['csc_mops_fallback'] is True
    assert source.verify_context(value, '2002.TW', max_age=1800)
    assert harness[1] == [MASTER_URL, INDEX_URL, iih_url, month_url, pdf_url]


def test_chinese_issuer_archive_recovers_when_mops_index_period_mismatches(harness, monkeypatch):
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp, MOPS_IIH_URL
    from search_provider_runtime import SourceResponseError

    fixture = ROOT/'tests/fixtures/source_acquisition/csc_mops_month_202609'
    month_url = ('https://emops.twse.com.tw/server-java/t100sb07_1_e?TYPEK=all&step=show&code=2002'
                 '&LPSHOW_DATE_YY=2026&LPSHOW_DATE_MM=09')
    month = (fixture/'month.html').read_bytes().replace(b'China Steel Corporation', b'China Steel Structure Corporation')
    harness[0].update({MOPS_IIH_URL: (fixture/'iih.json').read_bytes(), month_url: month})
    normal_download = ConferenceHttp.download_original

    def timeout_issuer_index(self, url, diagnostic):
        if url == INDEX_URL:
            harness[1].append(url)
            self.http_request_count += 1
            diagnostic.update(status='error', error_kind='timeout', http_request_sent=True)
            raise SourceResponseError('timeout')
        return normal_download(self, url, diagnostic)

    monkeypatch.setattr(ConferenceHttp, 'download_original', timeout_issuer_index)
    diagnostic = {}
    value = source.fetch_csc_context('2002.TW', diagnostics=diagnostic)

    doc = value['documents'][0]
    assert doc['content_sha256'] == 'f801da2a4a8fa92512c1d4265c2a6a35c70164bcae909fea45837665a94883e4'
    assert doc['language'] == 'zh' and doc['page_count'] == 35
    assert doc['native_text_coverage'] == 'complete' and doc['coverage_status'] == 'partial'
    assert doc['q_and_a_transcript_available'] is False
    assert value['materials'][0]['language'] == 'zh'
    assert value['source_url'] == CHINESE_INDEX_URL
    assert value['materials'][0]['url'] == CHINESE_PDF_URL
    assert diagnostic['actual_provider'] == 'CSC Chinese official conference presentation'
    assert diagnostic['csc_chinese_fallback'] is True
    assert source.verify_context(value, '2002.TW', max_age=1800)
    assert harness[1] == [MASTER_URL, INDEX_URL, MOPS_IIH_URL, month_url, CHINESE_INDEX_URL, CHINESE_PDF_URL]


@pytest.mark.parametrize('old,new', [
    ('近期法說簡報'.encode(), '年度簡報    '.encode()),
    (b'115', b'114'),
    ('09月23日'.encode(), '09月24日'.encode()),
    (b'pdf/2026Sep23.pdf', b'pdf/2026Jun24.pdf'),
])
def test_chinese_archive_rejects_changed_role_year_date_or_pdf(old, new):
    from data_fetch.market_sources.csc_conference import select_chinese_presentation
    raw = (CHINESE_EVIDENCE/'index.html').read_bytes()
    assert old in raw
    with pytest.raises(ValueError):
        select_chinese_presentation(raw.replace(old,new,1), NOW)


@pytest.mark.parametrize('change', ['ticker', 'instrument', 'legal', 'ubn', 'alias', 'forbidden', 'name', 'bool'])
def test_identity_context_contradictions_rejected(change):
    from data_fetch.market_sources.csc_conference import validate_context
    data = valid_data(); assert validate_context(data, '2002.TW')
    if change == 'ticker': data['company_identity']['stock_id'] = '2002A'
    elif change == 'instrument': data['quoteType'] = 'ETF'
    elif change == 'legal': data['company_identity']['legal_name'] = '中國鋼鐵結構股份有限公司'
    elif change == 'ubn': data['company_identity']['official_ubn'] = '00000000'
    elif change == 'alias': data['company_identity']['allowed_aliases'].append('中鋼構')
    elif change == 'forbidden': data['company_identity']['forbidden_aliases'].append('CSC')
    elif change == 'name': data['raw_company_name'] = 'China Steel Structure Co., Ltd.'
    else: data['company_identity']['stock_id'] = True
    assert not validate_context(data, '2002.TW')


def test_unsupported_is_explicit_and_does_not_acquire(harness):
    from data_fetch.market_sources import csc_conference as source
    for ticker in ['2002A.TW', '2002.TWO', '2013.TW', None, True]:
        assert not source.supports_csc(ticker)
        assert source.fetch_csc_context(ticker) == {}
    assert not harness[1]


@pytest.mark.parametrize('change', ['wrong_master', 'changed_href', 'duplicate_latest', 'future_latest', 'disagree_date', 'download_permission'])
def test_master_and_latest_index_fail_closed_before_pdf(harness, change):
    from data_fetch.market_sources import csc_conference as source
    from search_provider_runtime import SourceResponseError
    if change == 'wrong_master':
        harness[0][MASTER_URL] = harness[0][MASTER_URL].replace(b'30414175', b'30414176')
    else:
        raw = harness[0][INDEX_URL]
        if change == 'changed_href': raw = raw.replace(b'pdf/2026Sep23.pdf', b'https://evil.example/2026Sep23.pdf')
        elif change == 'duplicate_latest': raw = raw.replace(b'<li class="pst_top_wDay">', b'<li class="pst_top_wDay">September 23, 2026.</li><li class="pst_top_wDay">')
        elif change == 'future_latest': raw = raw.replace(b'September 23, 2026.', b'October 30, 2026.')
        elif change == 'disagree_date': raw = raw.replace(b'on September 23, 2026.', b'on September 22, 2026.')
        else: raw = raw.replace(b'Welcome downloading.', b'Prior written permission is required.')
        harness[0][INDEX_URL] = raw
    diagnostic = {}
    with pytest.raises(SourceResponseError): source.fetch_csc_context('2002.TW', diagnostics=diagnostic)
    assert PDF_URL not in harness[1] and not diagnostic['csc_originals_verified']


@pytest.mark.parametrize('mutation', ['raw', 'coverage', 'glyph', 'page_number', 'period', 'preliminary', 'disclaimer'])
def test_unqualified_original_or_reader_projection_never_becomes_success(harness, monkeypatch, mutation):
    from data_fetch.market_sources import csc_conference as source
    from search_provider_runtime import SourceResponseError
    if mutation == 'raw': harness[0][PDF_URL] += b'\nchanged-revision'
    else:
        original = source.extract_csc_presentation_pages
        def bad(*args, **kwargs):
            value = original(*args, **kwargs)
            if mutation == 'coverage': value['coverage_status'] = 'partial'
            elif mutation == 'glyph': value.pop('csc_glyph_evidence')
            elif mutation == 'page_number': value['pages'][2]['page_number'] = 4
            elif mutation == 'period': value['pages'][33]['text'] = value['pages'][33]['text'].replace('2026. H1', '2026. Q3')
            elif mutation == 'preliminary': value['pages'][10]['text'] = value['pages'][10]['text'].replace('*preliminary results', 'audited results')
            else: value['pages'][2]['text'] = 'No disclaimer'
            return value
        monkeypatch.setattr(source, 'extract_csc_presentation_pages', bad)
    diagnostic = {}
    with pytest.raises(SourceResponseError): source.fetch_csc_context('2002.TW', diagnostics=diagnostic)
    assert diagnostic['csc_originals_verified'] is False and 'coverage_status' not in diagnostic


@pytest.mark.parametrize('path,value', [('period', '2026Q3'), ('binary_complete', 1), ('transcript_available', True), ('published_at', '2026-09-23'), ('csc_glyph_evidence', {'forged': True})])
def test_public_replay_rejects_tampered_semantics_and_glyph_evidence(harness, path, value):
    from data_fetch.market_sources import csc_conference as source
    result = source.fetch_csc_context('2002.TW')
    if path in {'period', 'transcript_available'}: result[path] = value
    else: result['documents'][0][path] = value
    assert source.verify_context(result, '2002.TW') is False


def test_cold_then_warm_preserves_original_epoch_and_has_zero_HTTP(harness, monkeypatch):
    from data_fetch.market_sources import csc_conference as source
    first = source.fetch_csc_context('2002.TW'); harness[1].clear()
    monkeypatch.setattr(time, 'time', lambda: NOW+1790)
    diagnostic = {}; again = source.fetch_csc_context('2002.TW', diagnostics=diagnostic)
    assert not harness[1] and diagnostic['http_request_count'] == 0 and diagnostic['cache_hit'] is True
    assert again['fetched_at_epoch'] == first['fetched_at_epoch'] == NOW


@pytest.mark.parametrize('opts', [{'force_refresh': True}, {'use_cache': False}])
def test_force_or_uncached_refresh_uses_exact_origins(harness, opts):
    from data_fetch.market_sources import csc_conference as source
    source.fetch_csc_context('2002.TW'); harness[1].clear()
    source.fetch_csc_context('2002.TW', **opts)
    assert harness[1] == [INDEX_URL, PDF_URL]


@pytest.mark.parametrize('kind', ['timeout', 'access_denied', 'rate_limited'])
def test_body_failure_admission_cannot_be_bypassed_by_force_or_uncached(harness, monkeypatch, kind):
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp, CHINESE_INDEX_URL
    from search_provider_runtime import SourceResponseError
    calls = []
    def bad(self, url, diagnostic):
        self.http_request_count += 1; calls.append(url); diagnostic.update(http_request_sent=True)
        raise SourceResponseError(kind)
    monkeypatch.setattr(ConferenceHttp, 'download_original', bad)
    for opts in ({}, {'force_refresh': True}, {'use_cache': False}):
        diagnostic = {}
        with pytest.raises(SourceResponseError): source.fetch_csc_context('2002.TW', diagnostics=diagnostic, **opts)
        assert not diagnostic['csc_originals_verified'] and diagnostic['status'] == 'error'
    from data_fetch.market_sources.csc_conference_transport import MOPS_IIH_URL
    assert calls == ([INDEX_URL,MOPS_IIH_URL,CHINESE_INDEX_URL] if kind == 'timeout' else [INDEX_URL])


def test_storage_failure_sends_zero_HTTP(harness, monkeypatch):
    import cache_store
    from data_fetch.market_sources import csc_conference as source
    from search_provider_runtime import SourceResponseError
    def bad(*args, **kwargs): raise OSError('read-only cache')
    monkeypatch.setattr(cache_store, 'set_cache_json', bad)
    from data_fetch.market_sources import official_issuer_master
    monkeypatch.setattr(official_issuer_master,'set_cache_json',bad)
    diagnostic = {}
    with pytest.raises(SourceResponseError): source.fetch_csc_context('2002.TW', diagnostics=diagnostic)
    assert not harness[1] and diagnostic['http_request_count'] == 0 and not diagnostic['csc_originals_verified']


@pytest.mark.parametrize('url', [PDF_URL+'?x=1', PDF_URL+'#x', PDF_URL.replace('https:', 'http:'), PDF_URL.replace('www.csc.com.tw', 'www.csc.com.tw.evil.example'), INDEX_URL+'?year=2026', MASTER_URL+'?x=1',
                                'https://wwwc.twse.com.tw/rwd/en/IIH/company/events?code=2003',
                                'http://wwwc.twse.com.tw/rwd/en/IIH/company/events?code=2002',
                                'https://emops.twse.com.tw/server-java/t100sb07_1_e?TYPEK=all&step=show&code=2003&LPSHOW_DATE_YY=2026&LPSHOW_DATE_MM=09',
                                'https://emops.twse.com.tw/nas/STR/200320260922E001.pdf'])
def test_only_exact_qualified_URLs_are_admitted(harness, url):
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError): ConferenceHttp(time.monotonic()+25).get_receipt(url)
    assert not harness[1]


def test_mops_fallback_replay_rejects_tampered_route_and_selection(harness, monkeypatch):
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    fixture = ROOT/'tests/fixtures/source_acquisition/csc_mops_month_202609'
    iih_url = 'https://wwwc.twse.com.tw/rwd/en/IIH/company/events?code=2002'
    month_url = ('https://emops.twse.com.tw/server-java/t100sb07_1_e?TYPEK=all&step=show&code=2002'
                 '&LPSHOW_DATE_YY=2026&LPSHOW_DATE_MM=09')
    pdf_url = 'https://emops.twse.com.tw/nas/STR/200220260922E001.pdf'
    harness[0].update({iih_url:(fixture/'iih.json').read_bytes(),month_url:(fixture/'month.html').read_bytes(),
                       pdf_url:harness[0][PDF_URL]})
    normal_download = ConferenceHttp.download_original
    def timeout_index(self,url,diagnostic):
        if url == INDEX_URL:
            self.http_request_count += 1
            diagnostic.update(status='error',error_kind='timeout',http_request_sent=True)
            raise SourceResponseError('timeout')
        return normal_download(self,url,diagnostic)
    monkeypatch.setattr(ConferenceHttp,'download_original',timeout_index)
    value = source.fetch_csc_context('2002.TW')
    from copy import deepcopy
    altered = deepcopy(value); altered['source_url'] = INDEX_URL
    assert source.verify_context(altered,'2002.TW') is False
    altered = deepcopy(value); altered['materials'][0]['url'] = PDF_URL
    assert source.verify_context(altered,'2002.TW') is False
    altered = deepcopy(value); altered['csc_conference_receipt']['selected']['pdf_url'] = PDF_URL
    assert source.verify_context(altered,'2002.TW') is False


@pytest.mark.parametrize('warm',[False,True])
def test_reader_timeout_preserves_real_HTTP_and_no_success(harness,monkeypatch,warm):
    from data_fetch.market_sources import csc_conference as source
    from source_pdf_reader import SourcePdfError
    from search_provider_runtime import SourceResponseError
    if warm:source.fetch_csc_context('2002.TW');harness[1].clear()
    def timeout(*a,**kw):raise SourcePdfError('timeout')
    monkeypatch.setattr(source,'extract_csc_presentation_pages',timeout);d={}
    with pytest.raises(SourceResponseError) as err:source.fetch_csc_context('2002.TW',diagnostics=d)
    assert err.value.error_kind=='timeout' and d['status']=='error' and d['csc_originals_verified'] is False
    assert d['http_request_count']==(0 if warm else 3) and 'coverage_status' not in d


@pytest.mark.parametrize('stage',['reader','equality','handoff','components'])
def test_total_deadline_includes_all_parsing_projection_and_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import csc_conference as source
    from search_provider_runtime import SourceResponseError
    from types import SimpleNamespace
    clock=[time.monotonic()];expired=clock[0]+26
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    if stage=='reader':
        original=source.extract_csc_presentation_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=expired;return v
        monkeypatch.setattr(source,'extract_csc_presentation_pages',delayed)
    elif stage=='equality':
        original=source._context
        class Delayed(dict):
            def __eq__(self,other):v=super().__eq__(other);clock[0]=expired;return v
        monkeypatch.setattr(source,'_context',lambda *a,**kw:Delayed(original(*a,**kw)))
    else:
        original=source.deepcopy
        def delayed(v):
            result=original(v)
            if stage=='handoff' and isinstance(v,dict) and 'documents' in v or stage=='components' and isinstance(v,list):clock[0]=expired
            return result
        monkeypatch.setattr(source,'deepcopy',delayed)
    with pytest.raises(SourceResponseError) as err:source.fetch_csc_context('2002.TW')
    assert err.value.error_kind=='timeout'


@pytest.mark.parametrize('stage',['reader','equality','handoff','components'])
def test_original_TTL_is_checked_after_final_work(harness,monkeypatch,stage):
    from data_fetch.market_sources import csc_conference as source
    from search_provider_runtime import SourceResponseError
    source.fetch_csc_context('2002.TW');harness[1].clear();clock=[NOW+1799]
    monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_csc_presentation_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=NOW+1800;return v
        monkeypatch.setattr(source,'extract_csc_presentation_pages',delayed)
    elif stage=='equality':
        original=source._context
        class Delayed(dict):
            def __eq__(self,other):v=super().__eq__(other);clock[0]=NOW+1800;return v
        monkeypatch.setattr(source,'_context',lambda *a,**kw:Delayed(original(*a,**kw)))
    else:
        original=source.deepcopy
        def delayed(v):
            result=original(v)
            if stage=='handoff' and isinstance(v,dict) and 'documents' in v or stage=='components' and isinstance(v,list):clock[0]=NOW+1800
            return result
        monkeypatch.setattr(source,'deepcopy',delayed)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_csc_context('2002.TW',diagnostics=d)
    assert not harness[1] and d['status']=='error' and not d['csc_originals_verified']


def test_simultaneous_master_requests_share_one_native_acquisition(harness):
    from concurrent.futures import ThreadPoolExecutor
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    from threading import Barrier
    gate=Barrier(2)
    def request():
        gate.wait();return ConferenceHttp(time.monotonic()+25).get_receipt(MASTER_URL)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:request(),range(2)))
    assert harness[1]==[MASTER_URL] and results[0][0]==results[1][0]
    assert sorted(v[1]['cache_hit'] for v in results)==[False,True]


@pytest.mark.parametrize('budget',[3,25])
def test_native_request_budget_no_retry_redirect_proxy_or_cookie(monkeypatch,budget):
    from cache_backends import InMemoryCache
    import cache_store,json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache());calls=[]
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    for key in base.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(base,'proxy_url_for_request',lambda *a:None)
    def native(argv,deadline,*,body_limit,headers):
        calls.append((argv,deadline,body_limit,headers));url=argv[-1]
        return {'process_started':True,'body':b'%PDF-guard-test','headers':b'HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\n\r\n',
                'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0}).encode()},0,None
    monkeypatch.setattr(base,'collect_capped_process',native)
    http=ConferenceHttp(time.monotonic()+budget);raw,receipt=http.get_receipt(PDF_URL)
    argv,deadline,limit,headers=calls[0]
    assert len(calls)==1 and 0<float(argv[argv.index('--max-time')+1])<=min(5,budget)
    assert float(argv[argv.index('--connect-timeout')+1])<=2 and limit==8*1024*1024
    assert argv[argv.index('--retry')+1]=='0' and argv[argv.index('--max-redirs')+1]=='0'
    assert '--location' not in argv and '--cookie' not in argv and '--proxy' not in argv
    assert receipt['http_status']==200 and receipt['response_complete'] is True and receipt['cache_hit'] is False
    cache_store.reset_cache_store_for_tests()


def test_native_csc_index_request_gets_targeted_timeout(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store, json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for key in base.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(base,'proxy_url_for_request',lambda *a:None)
    calls=[]
    body=b'<html></html>'
    def native(argv,deadline,*,body_limit,headers):
        calls.append((argv,deadline,body_limit,headers));url=argv[-1]
        return {'process_started':True,'body':body,
                'headers':f'HTTP/2 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(body)}\r\n\r\n'.encode(),
                'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0,
                                       'size_download':len(body),'content_type':'text/html',
                                       'method':'GET','proxy_used':0}).encode()},0,None
    monkeypatch.setattr(base,'collect_capped_process',native)
    try:
        http=ConferenceHttp(time.monotonic()+25,force_refresh=True)
        value=http._download(INDEX_URL,{'url':INDEX_URL})
        argv,deadline,limit,_=calls[0]
        assert value['url']==INDEX_URL and len(calls)==1
        assert float(argv[argv.index('--max-time')+1])==8
        assert float(argv[argv.index('--connect-timeout')+1])==6
        assert argv[argv.index('--retry')+1]=='0' and argv[argv.index('--max-redirs')+1]=='0'
    finally:
        cache_store.reset_cache_store_for_tests()


@pytest.mark.parametrize('url',[MASTER_URL,INDEX_URL,PDF_URL])
@pytest.mark.parametrize('stage',['reader','handoff'])
def test_shorter_shared_expiry_cannot_cross_projection_or_delivery(harness,monkeypatch,url,stage):
    import cache_store
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    source.fetch_csc_context('2002.TW');harness[1].clear()
    key=raw_key(url)
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+2;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    clock=[NOW+1];monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_csc_presentation_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=NOW+3;return v
        monkeypatch.setattr(source,'extract_csc_presentation_pages',delayed)
    else:
        original=source.deepcopy
        def delayed(value):
            v=original(value)
            if isinstance(value,dict) and 'documents' in value:clock[0]=NOW+3
            return v
        monkeypatch.setattr(source,'deepcopy',delayed)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_csc_context('2002.TW',diagnostics=d)
    assert not harness[1] and not d['csc_originals_verified']


def test_shorter_cache_expiry_is_preserved_without_epoch_renewal(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    source.fetch_csc_context('2002.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+10;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+5);d={};value=source.fetch_csc_context('2002.TW',diagnostics=d)
    proof=value['csc_conference_receipt']['pdf']
    assert proof['retrieved_at']==value['fetched_at_epoch']==NOW and proof['fresh_until_epoch']==NOW+10
    assert not harness[1] and d['cache_hit'] is True and d['http_request_count']==0
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    assert source.verify_context(value,'2002.TW') is False


def test_complete_archive_is_revalidated_after_final_copy(harness,monkeypatch):
    from data_fetch.market_sources import csc_conference as source
    from search_provider_runtime import SourceResponseError
    original=source.deepcopy;saved={}
    def corrupt_at_handoff(value):
        copied=original(value)
        if isinstance(value,dict) and 'csc_conference_receipt' in value:
            path=Path(value['csc_conference_receipt']['pdf']['raw_response_path'])
            saved[path]=path.read_bytes();path.write_bytes(b'corrupt gzip')
        return copied
    monkeypatch.setattr(source,'deepcopy',corrupt_at_handoff);d={}
    try:
        with pytest.raises(SourceResponseError):source.fetch_csc_context('2002.TW',diagnostics=d)
        assert not d['csc_originals_verified']
    finally:
        for path,raw in saved.items():path.write_bytes(raw)


def test_receipt_alone_cannot_extend_saved_shorter_deadline(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    source.fetch_csc_context('2002.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+10;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+5);value=source.fetch_csc_context('2002.TW')
    assert value['csc_conference_receipt']['pdf']['fresh_until_epoch']==NOW+10
    value['csc_conference_receipt']['pdf']['fresh_until_epoch']=NOW+20
    monkeypatch.setattr(time,'time',lambda:NOW+15)
    assert source.verify_context(value,'2002.TW',max_age=1800) is False
    assert not harness[1]


def test_newer_same_bytes_cache_row_cannot_renew_older_receipt(harness,monkeypatch):
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    old=source.fetch_csc_context('2002.TW');harness[1].clear()
    monkeypatch.setattr(time,'time',lambda:NOW+5)
    raw,new=ConferenceHttp(time.monotonic()+25,force_refresh=True).get_receipt(PDF_URL)
    assert new['retrieved_at']==NOW+5 and old['csc_conference_receipt']['pdf']['retrieved_at']==NOW
    old['csc_conference_receipt']['pdf']['fresh_until_epoch']=NOW+1800
    assert source.verify_context(old,'2002.TW',max_age=1800) is False
    assert harness[1]==[PDF_URL]


@pytest.mark.parametrize('state',['missing','storage_unavailable'])
def test_saved_receipt_requires_independent_cache_observation(harness,monkeypatch,state):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import csc_conference as source
    value=source.fetch_csc_context('2002.TW');harness[1].clear()
    if state=='missing':cache_store.set_cache_backend(InMemoryCache())
    else:
        def unavailable(*args):raise RuntimeError('storage unavailable')
        monkeypatch.setattr(cache_store,'get_cache_json',unavailable)
    assert source.verify_context(value,'2002.TW',max_age=1800) is False
    assert not harness[1]
