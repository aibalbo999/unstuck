"""Captured original replay and fail-closed CHT source contracts; no live networking."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64
import time
import pytest
from data_fetch.market_sources.cht_conference_transport import MASTER_URL, INDEX_URL, PDF_URL, PUBLISHED_PDF_URL

ROOT = Path(__file__).parents[1]
D = ROOT/'docs/evidence/source-acquisition/20261014/remaining-gaps-after-csc/cht-yageo-research'
MASTER_FILE = ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW = 1791939500.0


@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    bodies = {MASTER_URL: MASTER_FILE.read_bytes(), INDEX_URL: (D/'cht-calendar.body').read_bytes(),
              PDF_URL: (D/'cht-latest-ibf-presentation.body').read_bytes()}
    calls = []
    def download(self, url, diagnostic):
        raw = bodies[url]; calls.append(url); self.http_request_count += 1
        diagnostic.update(http_request_sent=True, http_status=200, status='complete',
                          response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                'http_status': 200, 'response_complete': True, 'request_method': 'GET',
                'http_status_observed': True, 'fetched_at_epoch': time.time()}
    monkeypatch.setattr(ConferenceHttp, 'download_original', download)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def valid_data():
    return {'ticker': '2412.TW', 'instrument_type': 'EQUITY', 'company_name': '中華電 / Chunghwa Telecom Co., Ltd.',
            'raw_company_name': 'Chunghwa Telecom Co., Ltd.', 'company_identity': {'ticker': '2412.TW', 'stock_id': '2412',
            'official_name': '中華電', 'legal_name': None, 'display_name': '中華電 / Chunghwa Telecom Co., Ltd.',
            'allowed_aliases': ['中華電', '2412', '2412.TW', '中華電 / Chunghwa Telecom Co., Ltd.', 'CHT'],
            'english_names': ['Chunghwa Telecom Co., Ltd.', 'CHT'], 'forbidden_aliases': []}}


def test_public_metadata_gap_requires_official_original_body(harness):
    from data_fetch.market_sources import cht_conference as source
    d = {}; value = source.fetch_cht_context('2412.TW', diagnostics=d)
    assert value.get('documents'), 'CHT metadata gap must acquire the qualified official presentation body'
    doc = value['documents'][0]
    assert value['date'] == doc['event_date'] == '2026-10-13'
    assert value['period'] == doc['content_period'] == ''
    assert doc['content_periods'][:2] == ['2026Q2','2026H1']
    assert doc['page_count'] == len(doc['pages']) == 17
    assert doc['document_kind'] == 'presentation' and doc['projection_policy'] == 'cht-presentation-role-v1'
    assert doc['event_time_Taipei'] is None and doc['event_timezone'] is None
    assert value['upcoming_event']['date'] == '2026-11-04'
    assert value['upcoming_event']['status'] == 'future_event_not_current_evidence'
    assert value['transcript_available'] is doc['q_and_a_transcript_available'] is False
    assert value['summary'] == value['transcript_excerpt'] == ''
    assert value['coverage_status'] == doc['coverage_status'] == 'partial'
    assert doc['full_content_coverage_verified'] is False and doc['native_text_coverage'] == 'complete'
    assert doc['financial_scope_caution'] and doc['non_gaap_caution'] and doc['contract_value_caution']
    assert doc['native_editorial_caution'] and doc['commercial_reuse_permission_verified'] is False
    assert doc['published_at'] is doc['material_file_date'] is None
    assert 'XXX' in doc['pages'][3]['text'] and '惠請協助' in doc['pages'][13]['text']
    assert {v['page_number'] for v in doc['known_native_text_omissions'] if 'editorial' in v['issue']} == {4,14}
    assert doc['copyright_notice'] == '© Chunghwa Telecom'
    assert doc['pages'][16]['text'].strip().endswith('Q & A')
    assert 'ICT Contract Value Growth' in doc['pages'][8]['text']
    assert harness[1] == [MASTER_URL, INDEX_URL, PDF_URL]
    assert d['http_request_count'] == 3 and d['cht_originals_verified'] is True
    assert d['cache_hit'] is False and source.verify_context(value, '2412.TW', max_age=1800)


@pytest.mark.parametrize('change', ['ticker', 'instrument', 'legal', 'ubn', 'alias', 'forbidden', 'name', 'bool'])
def test_identity_context_contradictions_rejected(change):
    from data_fetch.market_sources.cht_conference import validate_context
    data = valid_data(); assert validate_context(data, '2412.TW')
    if change == 'ticker': data['company_identity']['stock_id'] = '2412A'
    elif change == 'instrument': data['quoteType'] = 'ETF'
    elif change == 'legal': data['company_identity']['legal_name'] = '中華電信子公司'
    elif change == 'ubn': data['company_identity']['official_ubn'] = '00000000'
    elif change == 'alias': data['company_identity']['allowed_aliases'].append('中華電構')
    elif change == 'forbidden': data['company_identity']['forbidden_aliases'].append('CHT')
    elif change == 'name': data['raw_company_name'] = 'Other Telecom Co., Ltd.'
    else: data['company_identity']['stock_id'] = True
    assert not validate_context(data, '2412.TW')


def test_unsupported_is_explicit_and_does_not_acquire(harness):
    from data_fetch.market_sources import cht_conference as source
    for ticker in ['2412A.TW', '2412.TWO', '2013.TW', None, True]:
        assert not source.supports_cht(ticker)
        assert source.fetch_cht_context(ticker) == {}
    assert not harness[1]


@pytest.mark.parametrize('change', ['wrong_master','wrong_domain','changed_href','duplicate_latest','future_latest','date_conflict','older_year','newer_missing_body','wrong_latest_title','only_older_event','upcoming_now_due','missing_upcoming','missing_query','duplicate_calendar','changed_future_title'])
def test_master_complete_calendar_and_latest_event_fail_closed_before_pdf(harness, change):
    from bs4 import BeautifulSoup
    from copy import deepcopy
    from data_fetch.market_sources import cht_conference as source
    from search_provider_runtime import SourceResponseError
    if change in {'wrong_master','wrong_domain'}:
        before,after = (b'96979933',b'96979934') if change=='wrong_master' else (b'https://www.cht.com.tw',b'https://www.evil.example')
        harness[0][MASTER_URL] = harness[0][MASTER_URL].replace(before,after)
    else:
        soup = BeautifulSoup(harness[0][INDEX_URL].decode(), 'html.parser')
        card = soup.select_one('.calendar .list-item')
        when = card.select_one('p.h5'); label = card.select_one('.col-12 > p.h3')
        if change=='changed_href': card.select_one('a[href]')['href']='https://evil.example/body.pdf'
        elif change=='duplicate_latest': card.insert_after(deepcopy(card))
        elif change=='future_latest': when.string='2026/10/30 Place : Taipei'; label.string='10/30'
        elif change=='date_conflict': label.string='10/12'
        elif change=='older_year': soup.select_one('.dropdown-text').string='2025'
        elif change=='newer_missing_body':
            new=deepcopy(card);new.select_one('p.h5').string='2026/10/14 Place : Taipei';new.select_one('.col-12 > p.h3').string='10/14'
            new.select_one('.col-auto > p.h3').string='New conference';new.select_one('a[href]').decompose();card.insert_before(new)
        elif change=='wrong_latest_title': card.select_one('.col-auto > p.h3').string='Earnings Announcement for Q3 2026'
        elif change=='only_older_event': card.decompose()
        elif change=='upcoming_now_due':
            note=soup.select_one('.calendar .note');note.select_one('p.h2').string='2026/10/14';note.select_one('p.h5').string='2026/10/14 Place : Taipei'
        elif change=='changed_future_title': soup.select_one('.calendar .note > p.h3').string='Earnings Announcement for Q4 2026'
        elif change=='missing_upcoming': soup.select_one('.calendar .note').decompose()
        elif change=='missing_query': card.select_one('a[href]')['href']=card.select_one('a[href]')['href'].split('?')[0]
        elif change=='duplicate_calendar': soup.select_one('section.calendar').insert_after(deepcopy(soup.select_one('section.calendar')))
        harness[0][INDEX_URL]=str(soup).encode()
    d={}
    with pytest.raises(SourceResponseError):source.fetch_cht_context('2412.TW',diagnostics=d)
    assert PDF_URL not in harness[1] and not d['cht_originals_verified']


@pytest.mark.parametrize('mutation', ['raw','old_august_body','coverage','page_number','period','preliminary','disclaimer','editorial','Q_and_A','copyright'])
def test_unqualified_original_or_native_projection_never_becomes_success(harness, monkeypatch, mutation):
    from data_fetch.market_sources import cht_conference as source
    from search_provider_runtime import SourceResponseError
    if mutation=='raw':harness[0][PDF_URL]+=b'changed-revision'
    elif mutation=='old_august_body':harness[0][PDF_URL]=(D/'cht-presentation.body').read_bytes()
    else:
        original=source.extract_pdf_pages
        def bad(*args,**kwargs):
            value=original(*args,**kwargs)
            if mutation=='coverage':value['coverage_status']='partial'
            elif mutation=='page_number':value['pages'][2]['page_number']=4
            elif mutation=='period':value['pages'][12]['text']=value['pages'][12]['text'].replace('Q2 2026','Q3 2026')
            elif mutation=='preliminary':value['pages'][1]['text']=value['pages'][1]['text'].replace('T-IFRSs in this presentation is preliminary','audited results')
            elif mutation=='disclaimer':value['pages'][1]['text']='No disclaimer'
            elif mutation=='editorial':value['pages'][13]['text']=value['pages'][13]['text'].replace('惠請協助','approved fact')
            elif mutation=='Q_and_A':value['pages'][16]['text']+=' invented answers'
            elif mutation=='copyright':value['pages'][3]['text']=value['pages'][3]['text'].replace('©','')
            return value
        monkeypatch.setattr(source,'extract_pdf_pages',bad)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_cht_context('2412.TW',diagnostics=d)
    assert not d['cht_originals_verified'] and 'coverage_status' not in d


@pytest.mark.parametrize('path,value',[('period','2026Q3'),('binary_complete',1),('transcript_available',True),('published_at','2026-10-13'),('native_editorial_caution',''),('non_gaap_caution',''),('known_native_text_omissions',[]),('projection_policy','generic-presentation'),('event_date','2026-08-05')])
def test_public_replay_rejects_semantic_projection_tampering(harness,path,value):
    from data_fetch.market_sources import cht_conference as source
    result=source.fetch_cht_context('2412.TW')
    if path in {'period','transcript_available'}:result[path]=value
    else:result['documents'][0][path]=value
    assert source.verify_context(result,'2412.TW') is False


def test_cold_then_warm_preserves_original_epoch_and_has_zero_HTTP(harness, monkeypatch):
    from data_fetch.market_sources import cht_conference as source
    first = source.fetch_cht_context('2412.TW'); harness[1].clear()
    monkeypatch.setattr(time, 'time', lambda: NOW+1790)
    diagnostic = {}; again = source.fetch_cht_context('2412.TW', diagnostics=diagnostic)
    assert not harness[1] and diagnostic['http_request_count'] == 0 and diagnostic['cache_hit'] is True
    assert again['fetched_at_epoch'] == first['fetched_at_epoch'] == NOW


@pytest.mark.parametrize('opts', [{'force_refresh': True}, {'use_cache': False}])
def test_force_or_uncached_refresh_uses_exact_origins(harness, opts):
    from data_fetch.market_sources import cht_conference as source
    source.fetch_cht_context('2412.TW'); harness[1].clear()
    source.fetch_cht_context('2412.TW', **opts)
    assert harness[1] == [MASTER_URL, INDEX_URL, PDF_URL]


@pytest.mark.parametrize('kind', ['timeout', 'access_denied', 'rate_limited'])
def test_failure_admission_cannot_be_bypassed_by_force_or_uncached(harness, monkeypatch, kind):
    from data_fetch.market_sources import cht_conference as source
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    calls = []
    def bad(self, url, diagnostic):
        self.http_request_count += 1; calls.append(url); diagnostic.update(http_request_sent=True)
        raise SourceResponseError(kind)
    monkeypatch.setattr(ConferenceHttp, 'download_original', bad)
    for opts in ({}, {'force_refresh': True}, {'use_cache': False}):
        diagnostic = {}
        with pytest.raises(SourceResponseError): source.fetch_cht_context('2412.TW', diagnostics=diagnostic, **opts)
        assert not diagnostic['cht_originals_verified'] and diagnostic['status'] == 'error'
    assert calls == [MASTER_URL]


def test_storage_failure_sends_zero_HTTP(harness, monkeypatch):
    import cache_store
    from data_fetch.market_sources import cht_conference as source
    from search_provider_runtime import SourceResponseError
    def bad(*args, **kwargs): raise OSError('read-only cache')
    monkeypatch.setattr(cache_store, 'set_cache_json', bad)
    diagnostic = {}
    with pytest.raises(SourceResponseError): source.fetch_cht_context('2412.TW', diagnostics=diagnostic)
    assert not harness[1] and diagnostic['http_request_count'] == 0 and not diagnostic['cht_originals_verified']


@pytest.mark.parametrize('url', [PDF_URL.replace('?sc_lang=en',''), PDF_URL.replace('sc_lang=en','sc_lang=zh-tw'), PDF_URL+'&x=1', PDF_URL+'#x', PDF_URL.replace('https:', 'http:'), PDF_URL.replace('www.cht.com.tw', 'www.cht.com.tw.evil.example'), INDEX_URL+'?year=2025', MASTER_URL+'?x=1'])
def test_only_exact_qualified_URLs_are_admitted(harness, url):
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError): ConferenceHttp(time.monotonic()+25).get_receipt(url)
    assert not harness[1]


@pytest.mark.parametrize('warm',[False,True])
def test_reader_timeout_preserves_real_HTTP_and_no_success(harness,monkeypatch,warm):
    from data_fetch.market_sources import cht_conference as source
    from source_pdf_reader import SourcePdfError
    from search_provider_runtime import SourceResponseError
    if warm:source.fetch_cht_context('2412.TW');harness[1].clear()
    def timeout(*a,**kw):raise SourcePdfError('timeout')
    monkeypatch.setattr(source,'extract_pdf_pages',timeout);d={}
    with pytest.raises(SourceResponseError) as err:source.fetch_cht_context('2412.TW',diagnostics=d)
    assert err.value.error_kind=='timeout' and d['status']=='error' and d['cht_originals_verified'] is False
    assert d['http_request_count']==(0 if warm else 3) and 'coverage_status' not in d


@pytest.mark.parametrize('stage',['reader','equality','handoff','components'])
def test_total_deadline_includes_all_parsing_projection_and_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import cht_conference as source
    from search_provider_runtime import SourceResponseError
    from types import SimpleNamespace
    clock=[time.monotonic()];expired=clock[0]+26
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    if stage=='reader':
        original=source.extract_pdf_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=expired;return v
        monkeypatch.setattr(source,'extract_pdf_pages',delayed)
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
    with pytest.raises(SourceResponseError) as err:source.fetch_cht_context('2412.TW')
    assert err.value.error_kind=='timeout'


@pytest.mark.parametrize('stage',['reader','equality','handoff','components'])
def test_original_TTL_is_checked_after_final_work(harness,monkeypatch,stage):
    from data_fetch.market_sources import cht_conference as source
    from search_provider_runtime import SourceResponseError
    source.fetch_cht_context('2412.TW');harness[1].clear();clock=[NOW+1799]
    monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_pdf_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=NOW+1800;return v
        monkeypatch.setattr(source,'extract_pdf_pages',delayed)
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
    with pytest.raises(SourceResponseError):source.fetch_cht_context('2412.TW',diagnostics=d)
    assert not harness[1] and d['status']=='error' and not d['cht_originals_verified']


def test_simultaneous_master_requests_share_one_native_acquisition(harness):
    from concurrent.futures import ThreadPoolExecutor
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    from threading import Barrier
    gate=Barrier(2)
    def request():
        gate.wait();return ConferenceHttp(time.monotonic()+25).get_receipt(MASTER_URL)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:request(),range(2)))
    assert harness[1]==[MASTER_URL] and results[0][0]==results[1][0]
    assert sorted(v[1]['cache_hit'] for v in results)==[False,True]


@pytest.mark.parametrize('budget',[3,25])
@pytest.mark.parametrize('pdf_url',[PDF_URL,PUBLISHED_PDF_URL])
def test_native_request_budget_no_retry_redirect_proxy_or_cookie(monkeypatch,budget,pdf_url):
    from cache_backends import InMemoryCache
    import cache_store,json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache());calls=[]
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    for key in base.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(base,'proxy_url_for_request',lambda *a:None)
    def native(argv,deadline,*,body_limit,headers):
        calls.append((argv,deadline,body_limit,headers));url=argv[-1]
        return {'process_started':True,'body':b'%PDF-guard-test','headers':b'HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\n\r\n',
                'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0}).encode()},0,None
    monkeypatch.setattr(base,'collect_capped_process',native)
    http=ConferenceHttp(time.monotonic()+budget);raw,receipt=http.get_receipt(pdf_url)
    argv,deadline,limit,headers=calls[0]
    assert len(calls)==1 and 0<float(argv[argv.index('--max-time')+1])<=min(5,budget)
    assert float(argv[argv.index('--connect-timeout')+1])<=2 and limit==8*1024*1024
    assert argv[argv.index('--retry')+1]=='0' and argv[argv.index('--max-redirs')+1]=='0'
    assert '--location' not in argv and '--cookie' not in argv and '--proxy' not in argv
    assert receipt['http_status']==200 and receipt['response_complete'] is True and receipt['cache_hit'] is False
    cache_store.reset_cache_store_for_tests()


@pytest.mark.parametrize('url',[MASTER_URL,INDEX_URL,PDF_URL])
@pytest.mark.parametrize('stage',['reader','handoff'])
def test_shorter_shared_expiry_cannot_cross_projection_or_delivery(harness,monkeypatch,url,stage):
    import cache_store
    from data_fetch.market_sources import cht_conference as source
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    source.fetch_cht_context('2412.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+2;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    clock=[NOW+1];monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_pdf_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=NOW+3;return v
        monkeypatch.setattr(source,'extract_pdf_pages',delayed)
    else:
        original=source.deepcopy
        def delayed(value):
            v=original(value)
            if isinstance(value,dict) and 'documents' in value:clock[0]=NOW+3
            return v
        monkeypatch.setattr(source,'deepcopy',delayed)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_cht_context('2412.TW',diagnostics=d)
    assert not harness[1] and not d['cht_originals_verified']


def test_shorter_cache_expiry_is_preserved_without_epoch_renewal(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import cht_conference as source
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    source.fetch_cht_context('2412.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+10;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+5);d={};value=source.fetch_cht_context('2412.TW',diagnostics=d)
    proof=value['cht_conference_receipt']['pdf']
    assert proof['retrieved_at']==value['fetched_at_epoch']==NOW and proof['fresh_until_epoch']==NOW+10
    assert not harness[1] and d['cache_hit'] is True and d['http_request_count']==0
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    assert source.verify_context(value,'2412.TW') is False


def test_complete_archive_is_revalidated_after_final_copy(harness,monkeypatch):
    from data_fetch.market_sources import cht_conference as source
    from search_provider_runtime import SourceResponseError
    original=source.deepcopy;saved={}
    def corrupt_at_handoff(value):
        copied=original(value)
        if isinstance(value,dict) and 'cht_conference_receipt' in value:
            path=Path(value['cht_conference_receipt']['pdf']['raw_response_path'])
            saved[path]=path.read_bytes();path.write_bytes(b'corrupt gzip')
        return copied
    monkeypatch.setattr(source,'deepcopy',corrupt_at_handoff);d={}
    try:
        with pytest.raises(SourceResponseError):source.fetch_cht_context('2412.TW',diagnostics=d)
        assert not d['cht_originals_verified']
    finally:
        for path,raw in saved.items():path.write_bytes(raw)


def test_receipt_alone_cannot_extend_saved_shorter_deadline(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import cht_conference as source
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    source.fetch_cht_context('2412.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+10;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+5);value=source.fetch_cht_context('2412.TW')
    assert value['cht_conference_receipt']['pdf']['fresh_until_epoch']==NOW+10
    value['cht_conference_receipt']['pdf']['fresh_until_epoch']=NOW+20
    monkeypatch.setattr(time,'time',lambda:NOW+15)
    assert source.verify_context(value,'2412.TW',max_age=1800) is False
    assert not harness[1]


def test_newer_same_bytes_cache_row_cannot_renew_older_receipt(harness,monkeypatch):
    from data_fetch.market_sources import cht_conference as source
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    old=source.fetch_cht_context('2412.TW');harness[1].clear()
    monkeypatch.setattr(time,'time',lambda:NOW+5)
    raw,new=ConferenceHttp(time.monotonic()+25,force_refresh=True).get_receipt(PDF_URL)
    assert new['retrieved_at']==NOW+5 and old['cht_conference_receipt']['pdf']['retrieved_at']==NOW
    old['cht_conference_receipt']['pdf']['fresh_until_epoch']=NOW+1800
    assert source.verify_context(old,'2412.TW',max_age=1800) is False
    assert harness[1]==[PDF_URL]


@pytest.mark.parametrize('state',['missing','storage_unavailable'])
def test_saved_receipt_requires_independent_cache_observation(harness,monkeypatch,state):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import cht_conference as source
    value=source.fetch_cht_context('2412.TW');harness[1].clear()
    if state=='missing':cache_store.set_cache_backend(InMemoryCache())
    else:
        def unavailable(*args):raise RuntimeError('storage unavailable')
        monkeypatch.setattr(cache_store,'get_cache_json',unavailable)
    assert source.verify_context(value,'2412.TW',max_age=1800) is False
    assert not harness[1]


@pytest.mark.parametrize('expiry',['deadline','original_ttl','shorter_ttl'])
def test_final_diagnostic_handoff_cannot_advertise_expired_success(harness,monkeypatch,expiry):
    from types import SimpleNamespace
    from data_fetch.market_sources import cht_conference as source
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    import cache_store
    source.fetch_cht_context('2412.TW');harness[1].clear()
    clock=[NOW+1];mono=[time.monotonic()]
    monkeypatch.setattr(time,'time',lambda:clock[0])
    monkeypatch.setattr(source,'time',SimpleNamespace(time=lambda:clock[0],monotonic=lambda:mono[0]))
    if expiry=='shorter_ttl':
        key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
        row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+2;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    class DelayedDiagnostics(dict):
        def update(self,*args,**kwargs):
            super().update(*args,**kwargs)
            if self.get('cht_originals_verified') is True:
                if expiry=='deadline':mono[0]+=26
                else:clock[0]=NOW+(1800 if expiry=='original_ttl' else 3)
    d=DelayedDiagnostics()
    with pytest.raises(SourceResponseError) as err:source.fetch_cht_context('2412.TW',diagnostics=d)
    assert err.value.error_kind==('timeout' if expiry=='deadline' else 'original_expired')
    assert not harness[1] and d['status']=='error' and d['cht_originals_verified'] is False
    assert not any(k in d or k in err.value.diagnostic for k in ('coverage_status','cache_hit','stale','fetched_at_epoch'))


PUBLISHED_LINK_REPAIR = ROOT/'docs/evidence/source-acquisition/20261014/remaining-gaps-after-csc/cht-integration/published-link-repair/author'
FORMAL_INDEX = ROOT/'docs/evidence/source-acquisition/20261014/remaining-gaps-after-csc/cht-integration/integration/first-formal-diagnosis/index.body'
LIVE_PDF_URL = 'https://www.cht.com.tw/home/eshop/-/media/web/pdf/investors/shareholder-services/en/ir-calendar-en/20261013/2q26-en.pdf'


def test_saved_formal_index_uses_actual_published_URL_through_whole_collector(harness):
    from data_fetch.market_sources import cht_conference as source
    harness[0][INDEX_URL] = FORMAL_INDEX.read_bytes()
    harness[0][LIVE_PDF_URL] = (PUBLISHED_LINK_REPAIR/'new-published-presentation.body').read_bytes()
    d={};value=source.fetch_cht_context('2412.TW',diagnostics=d)
    assert value.get('documents'), 'saved actual live index must acquire its published qualified presentation'
    proof=value['cht_conference_receipt'];doc=value['documents'][0]
    assert harness[1]==[MASTER_URL,INDEX_URL,LIVE_PDF_URL]
    assert d['http_request_count']==3 and d['cht_originals_verified']
    assert proof['selected']['pdf_url']==proof['pdf']['source_url']==doc['url']==value['materials'][0]['url']==LIVE_PDF_URL
    assert doc['page_count']==17 and doc['content_sha256']=='c4b36eac7005add9f41d65f563e867dffb0c2cca3c5acc476c6a7bcc1ae1f62f'
    assert source.verify_context(value,'2412.TW',max_age=1800)
    assert source.is_marked({'documents':[{'url':LIVE_PDF_URL}]})
    assert source.is_marked({'materials':[{'url':LIVE_PDF_URL}]})
    harness[1].clear();warm={};again=source.fetch_cht_context('2412.TW',diagnostics=warm)
    assert not harness[1] and warm['http_request_count']==0 and warm['cache_hit'] is True
    assert again['fetched_at_epoch']==value['fetched_at_epoch']==NOW


@pytest.mark.parametrize('part',['selected','receipt','document','material'])
def test_saved_live_variant_cannot_relabel_provenance_to_research_variant(harness,part):
    from data_fetch.market_sources import cht_conference as source
    harness[0][INDEX_URL]=FORMAL_INDEX.read_bytes()
    harness[0][LIVE_PDF_URL]=(PUBLISHED_LINK_REPAIR/'new-published-presentation.body').read_bytes()
    value=source.fetch_cht_context('2412.TW')
    if part=='selected':value['cht_conference_receipt']['selected']['pdf_url']=PDF_URL
    elif part=='receipt':value['cht_conference_receipt']['pdf']['source_url']=PDF_URL
    elif part=='document':value['documents'][0]['url']=PDF_URL
    else:value['materials'][0]['url']=PDF_URL
    assert source.verify_context(value,'2412.TW',max_age=1800) is False


def test_same_PDF_bytes_do_not_allow_receipt_from_other_URL(harness):
    from data_fetch.market_sources import cht_conference as source
    old=source.fetch_cht_context('2412.TW')
    harness[0][INDEX_URL]=FORMAL_INDEX.read_bytes()
    harness[0][LIVE_PDF_URL]=(PUBLISHED_LINK_REPAIR/'new-published-presentation.body').read_bytes()
    value=source.fetch_cht_context('2412.TW',force_refresh=True)
    assert value['documents'][0]['content_sha256']==old['documents'][0]['content_sha256']
    value['cht_conference_receipt']['pdf']=old['cht_conference_receipt']['pdf']
    assert source.verify_context(value,'2412.TW',max_age=1800) is False


@pytest.mark.parametrize('href',[PDF_URL.removeprefix('https://www.cht.com.tw').split('?')[0],LIVE_PDF_URL.removeprefix('https://www.cht.com.tw')+'?sc_lang=en',LIVE_PDF_URL.removeprefix('https://www.cht.com.tw').replace('/eshop/','/web/'),LIVE_PDF_URL.removeprefix('https://www.cht.com.tw')+'#presentation'])
def test_only_two_observed_published_paths_are_accepted_without_normalization(harness,href):
    from data_fetch.market_sources import cht_conference as source
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(FORMAL_INDEX.read_bytes().decode(),'html.parser')
    soup.select_one('section.calendar .list-item a[href]')['href']=href
    harness[0][INDEX_URL]=str(soup).encode()
    with pytest.raises(SourceResponseError):source.fetch_cht_context('2412.TW')
    assert harness[1]==[MASTER_URL,INDEX_URL]
    with pytest.raises(SourceResponseError):ConferenceHttp(time.monotonic()+25).get_receipt('https://www.cht.com.tw'+href)
    assert harness[1]==[MASTER_URL,INDEX_URL]


def test_new_URL_cannot_import_a_different_original_revision(harness):
    from data_fetch.market_sources import cht_conference as source
    from search_provider_runtime import SourceResponseError
    harness[0][INDEX_URL]=FORMAL_INDEX.read_bytes()
    harness[0][LIVE_PDF_URL]=(PUBLISHED_LINK_REPAIR/'new-published-presentation.body').read_bytes()+b'changed'
    d={}
    with pytest.raises(SourceResponseError):source.fetch_cht_context('2412.TW',diagnostics=d)
    assert not d['cht_originals_verified'] and d['http_request_count']==3
    assert harness[1]==[MASTER_URL,INDEX_URL,LIVE_PDF_URL]
