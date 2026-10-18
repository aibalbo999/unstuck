"""Offline public-behavior replay of the saved issuer chain, never a live success."""
from copy import deepcopy
from pathlib import Path
import base64
import gzip
from hashlib import sha256
import json
import time
import os
import pytest

E=Path(__file__).resolve().parent
R=E.parent
F=E/'fixtures/source_acquisition'
NOW=1792134300.
MASTER='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX='https://www.guc-asic.com/en/investor/financial'
PDF='https://www.guc-asic.com/upload/2026_07_30/8_20260730150613pzdzkmEKs3.pdf'

@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch import earnings_call_fetcher
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time,'time',lambda:NOW)
    monkeypatch.setattr(earnings_call_fetcher,'_fetch_official_index_context',lambda *a,**k:{})
    bodies={MASTER:gzip.decompress((F/'guc3443_master_20261014.gz').read_bytes()),
            INDEX:gzip.decompress((F/'guc3443_index_20261016.gz').read_bytes()),PDF:gzip.decompress((F/'guc3443_pdf_20261016.gz').read_bytes())}
    calls=[]
    if (R/'backend/data_fetch/market_sources/guc_conference_transport.py').exists():
        from data_fetch.market_sources.guc_conference_transport import GucConferenceHttp
        from data_fetch.market_sources import issuer_news_transport as native, gce_conference_transport as master_native
        monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
        for k in native.PROXY_ENV:monkeypatch.delenv(k,raising=False)
        def process(args,deadline,**options):
            assert args[-1]==MASTER
            raw=bodies[MASTER];calls.append(MASTER)
            return {'body':raw,'headers':b'HTTP/2 200\r\nContent-Type: text/csv\r\n\r\n',
              'metadata':json.dumps({'http_code':200,'url_effective':MASTER,'num_redirects':0,'size_download':len(raw),'content_type':'text/csv','method':'GET','proxy_used':0}).encode(),'process_started':True},0,None
        for module in (native,master_native):
            monkeypatch.setattr(module,'collect_capped_process',process)
            monkeypatch.setattr(module,'proxy_url_for_request',lambda *a:None)
            monkeypatch.setattr(module,'observe_http_response',lambda *a:None)
        def download(self,url,diagnostic):
            calls.append(url);self.http_request_count+=1;raw=bodies[url]
            diagnostic.update(http_request_sent=True,http_status=200)
            return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
              'http_status':200,'response_complete':True,'request_method':'GET','http_status_observed':True,'fetched_at_epoch':time.time()}
        monkeypatch.setattr(GucConferenceHttp,'_download',download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()

def test_public_source_acquires_original_body_instead_of_metadata(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    details={};value=fetch_free_earnings_call_context('3443.TW',diagnostics=details)
    assert value.get('documents'),'Normal GUC acquisition must obtain the official presentation body'
    doc=value['documents'][0]
    assert doc['page_count']==20 and len(doc['pages'])==20 and doc['url']==PDF
    assert doc['garbled_pages']==[3,4] and doc['coverage_status']=='partial'
    assert not doc['full_content_coverage_verified'] and not value['transcript_available']
    assert value['date']=='2026-07-31' and doc['document_date']=='2026-07-30'
    assert details['guc_originals_verified'] is True

@pytest.mark.parametrize('data',[
 {'ticker':'3443.TW','quote_type':'EQUITY','company_name':'雙鴻'},
 {'ticker':'3443.TW','quote_type':'EQUITY','company_name':'創意','company_identity':{'official_ubn':'00000000'}},
 {'ticker':'3443.TW','quote_type':'ETF','company_name':'創意'},
 {'ticker':'3443.TW','quote_type':'EQUITY','company_name':'創意','company_identity':{'stock_id':'3714'}},
])
def test_conflicting_company_blocks_before_any_http(harness,data):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('3443.TW'),{'data':data})
    assert result.status=='unavailable' and result.audit['event_kind']=='local_block'
    assert not harness[1]

def test_qualified_english_alias_matches_exact_official_master(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('3443.TW'),{'data':{
      'ticker':'3443.TW','quote_type':'EQUITY','company_name':'創意 / Global Unichip Corp.',
      'company_identity':{'stock_id':'3443','official_name':'創意','official_ubn':'16299879'}}})
    assert result.status=='success' and result.audit['record_count']==1
    assert result.value['documents'][0]['page_count']==20

@pytest.mark.parametrize('change',['text','date','url','transcript','omissions','receipt','age','identity','projection'])
def test_original_replay_rejects_tampering(harness,change):
    from data_fetch.market_sources import guc_conference as source
    value=source.fetch_guc_context('3443.TW')
    if change=='text':value['documents'][0]['pages'][5]['text']+=' fabricated'
    elif change=='date':value['date']='2026-07-30'
    elif change=='url':value['documents'][0]['url']+='?x=1'
    elif change=='transcript':value['transcript_available']=True
    elif change=='omissions':value['documents'][0]['projection_excluded_pages']=[]
    elif change=='receipt':value.pop('guc_conference_receipt')
    elif change=='age':value['guc_conference_receipt']['pdf']['retrieved_at']=NOW-1801
    elif change=='projection':value['documents'][0]['selected_quarter']['quarter']=1
    else:value['ticker']='3714.TW'
    assert source.is_marked(value) and not source.verify_context(value,'3443.TW',max_age=1800)

def test_warm_pdf_keeps_epoch_and_only_reacquires_index(harness,monkeypatch):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    p=EarningsCallProvider();request=FetchRequest.from_ticker('3443.TW')
    cold=p.fetch(request);assert cold.status=='success' and len(harness[1])==3
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    warm=p.fetch(request)
    assert warm.audit['status']=='skipped_fresh_cache'
    assert harness[1]==[MASTER,INDEX,PDF,INDEX]
    assert warm.value['fetched_at_epoch']==cold.value['fetched_at_epoch']==NOW
    monkeypatch.setattr(time,'time',lambda:NOW+1801)
    refreshed=p.fetch(request)
    assert refreshed.status=='success' and refreshed.value['fetched_at_epoch']==NOW+1801
    assert harness[1][-1]==PDF and harness[1].count(PDF)==2

@pytest.mark.parametrize('tampered',[False,True])
def test_actual_agent_roles_keep_whole_table_without_receipts_or_false_transcript(harness,tampered):
    from data_fetch.market_sources import guc_conference as source
    from agent_runtime.prompting import data_for_agent_prompt
    value=source.fetch_guc_context('3443.TW')
    original_pages=deepcopy(value['documents'][0]['pages'])
    if tampered:
        value['source']='issuer_official';value['documents'][0]['source']='issuer_official'
        value['documents'][0]['pages'][5]['text']+=' fabricated profit'
    data={'ticker':'3443.TW','company_name':'創意','earnings_call':value};before=deepcopy(data)
    for role in (3,5,12):
        result=data_for_agent_prompt(role,data)
        assert bool(result.get('conference_presentation')) is (not tampered)
        assert 'guc_conference_receipt' not in json.dumps(result,ensure_ascii=False)
        if not tampered:
            d=result['conference_presentation']['documents'][0]
            assert [p['page_number'] for p in d['pages']]==[6]
            assert d['pages'][0]['text']==original_pages[5]['text']
            assert not d['pages'][0]['content_truncated']
            assert d['document_date']=='2026-07-30' and d['event_date']=='2026-07-31'
            assert d['native_period_alignment_unverified_pages']==[7]
            assert '非逐字稿' in d['financial_scope_caution'] and 'NT$M' in d['financial_scope_caution']
    assert data==before

@pytest.mark.parametrize('change',['missing_row','wrong_unit','wrong_period'])
def test_unqualified_table_never_becomes_role_evidence(harness,change):
    from data_fetch.market_sources import guc_conference as source
    doc=source.fetch_guc_context('3443.TW')['documents'][0]
    changes={'missing_row':('Revenues','missing'),'wrong_unit':('NT$M','USD'),'wrong_period':('2Q26 QoQ','1Q26 QoQ')}
    old,new=changes[change];doc['pages'][5]['text']=doc['pages'][5]['text'].replace(old,new)
    assert source.role_pages(doc)==[]

@pytest.mark.parametrize('change',['missing_attachment','duplicate_quarter','foreign_host','missing_event','future_latest','quarter_mismatch'])
def test_bad_or_new_unavailable_latest_index_never_falls_back(harness,change):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources.guc_conference import select_presentation
    soup=BeautifulSoup(harness[0][INDEX],'html.parser')
    group=soup.select('.quarterly-list[data-year="2026"]')[0]
    item=group.select('.quarterly-item')[1]
    if change=='missing_attachment':
        for row in item.select('.tr'):
            if 'Quarterly Result Presentation Material' in row.get_text():row.decompose()
    elif change=='duplicate_quarter':group.append(deepcopy(item))
    elif change=='foreign_host':item.select('a[href]')[1]['href']='https://evil.example/a.pdf'
    elif change=='missing_event':
        for row in soup.select('.tr'):
            if 'Investor Conference - Q2 2026' in row.get_text():row.decompose()
    elif change=='future_latest':
        for row in soup.select('.tr'):
            if 'Business Report - Q3 2026' in row.get_text():
                row.select('p')[0].string='2026/10/15(Thu) 17:30'
    else:item.select('.quarterly-title .unit-blocktitle-s')[-1].string='Q3'
    with pytest.raises(ValueError):select_presentation(str(soup).encode(),NOW)

def test_dynamic_later_quarter_uses_new_published_link_not_fixed_hash(harness,monkeypatch):
    from bs4 import BeautifulSoup
    from datetime import datetime,timezone
    from data_fetch.market_sources.guc_conference import select_presentation
    epoch=datetime(2026,11,1,tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(time,'time',lambda:epoch)
    soup=BeautifulSoup(harness[0][INDEX],'html.parser')
    group=soup.select('.quarterly-list[data-year="2026"]')[0]
    item=deepcopy(group.select('.quarterly-item')[1])
    item.select('.quarterly-title .unit-blocktitle-s')[-1].string='Q3'
    expected='https://www.guc-asic.com/upload/2026_10_29/8_20261029150613NewPublicQ3.pdf'
    item.select('a[href]')[1]['href']=expected
    group.append(item)
    for row in soup.select('.tr'):
        if 'Investor Conference - Q2 2026' in row.get_text():
            new=deepcopy(row);new.select('p')[0].string='2026/10/30(Fri) 14:00'
            new.select('p')[1].string='Quarterly Results & Investor Conference - Q3 2026'
            row.parent.append(new);break
    selected=select_presentation(str(soup).encode(),epoch)
    assert selected['pdf_url']==expected and selected['event_date']=='2026-10-30'
    assert selected['period_label']=='2026Q3' and selected['document_date']=='2026-10-29'

@pytest.mark.parametrize('tampered',[False,True])
def test_source_refresh_checks_originals_and_preserves_analysis(harness,tmp_path,monkeypatch,tampered):
    import asyncio
    from fastapi import HTTPException
    from data_fetch import StockDataService,ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.market_sources import guc_conference as source
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db
    init_db();storage=InMemoryStorage();filename,keys,old=saved_report(storage)
    old=json.loads(json.dumps(old,ensure_ascii=False).replace('6214.TW','3443.TW').replace('精誠','創意'))
    old['data']['quote_type']='EQUITY';original=json.dumps(old).encode()
    storage.save_report(keys.data_key,original,content_type='application/json')
    if tampered:
        fetch=source.fetch_guc_context
        def altered(*a,**kw):
            v=fetch(*a,**kw);v['documents'][0]['pages'][5]['text']+=' fabricated';return v
        monkeypatch.setattr(source,'fetch_guc_context',altered)
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    def refresh():return asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
        refresh_service=service,source='earnings_call',return_refreshed_data=True))
    if tampered:
        with pytest.raises(HTTPException) as exc:refresh()
        assert exc.value.status_code==502 and storage.get_report(keys.data_key).content==original
    else:
        assert refresh()['analysis_text_stale'] is True
        new=json.loads(storage.get_report(keys.data_key).content)
        assert new['data']['earnings_call']['documents'][0]['page_count']==20
        for key in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
            assert new[key]==old[key]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'

def test_deadline_during_final_handoff_removes_success_markers(harness,monkeypatch):
    from data_fetch.market_sources import guc_conference as source
    from search_provider_runtime import SourceResponseError
    clock=time.monotonic;deep=source.deepcopy;late={'v':False}
    monkeypatch.setattr(time,'monotonic',lambda:clock()+(21 if late['v'] else 0))
    def slow(value,*a,**kw):
        out=deep(value,*a,**kw)
        if isinstance(value,list) and value and all(isinstance(x,dict) and 'url' in x for x in value):late['v']=True
        return out
    monkeypatch.setattr(source,'deepcopy',slow)
    details={}
    with pytest.raises(SourceResponseError) as exc:source.fetch_guc_context('3443.TW',diagnostics=details)
    assert exc.value.error_kind=='timeout' and details['guc_originals_verified'] is False
    assert details['http_request_count']==3 and 'coverage_status' not in details and 'cache_hit' not in details

def test_complete_native_pages_are_preserved_byte_for_byte_in_context(harness):
    from data_fetch.market_sources.guc_conference import fetch_guc_context
    doc=fetch_guc_context('3443.TW')['documents'][0]
    saved=json.loads((F/'guc3443_reader.json').read_text())
    assert doc['pages']==saved['pages'] and doc['content_sha256']==saved['content_sha256']
    assert doc['projection_excluded_pages']==[p for p in range(1,21) if p!=6]
    assert doc['native_period_alignment_unverified_pages']==[7]
    assert set([3,4,9,10,11,12,13,14,15,16,17,18]) <= set(doc['known_native_text_omission_pages'])

def test_wrong_full_master_identity_stops_before_issuer_index(harness):
    from data_fetch.market_sources.guc_conference import fetch_guc_context
    from search_provider_runtime import SourceResponseError
    harness[0][MASTER]=harness[0][MASTER].replace('創意電子股份有限公司'.encode(),'別家公司股份有限公司'.encode())
    with pytest.raises(SourceResponseError) as exc:fetch_guc_context('3443.TW')
    assert exc.value.error_kind=='parse_error' and harness[1]==[MASTER]

def test_source_only_fetch_keeps_company_context_and_blocks_before_http(harness):
    import asyncio
    from data_fetch import StockDataService,ProviderRegistry,FetchRequest
    from data_fetch.enrichment_providers import EarningsCallProvider
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    result=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('3443.TW'),'earnings_call',context={'data':{
        'ticker':'3443.TW','company_name':'雙鴻','quote_type':'EQUITY'}}))
    assert not result.data.get('earnings_call') and not harness[1]

def test_shorter_identity_store_deadline_is_not_extended(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import guc_conference as source, official_issuer_master as master
    source.fetch_guc_context('3443.TW')
    value=source.fetch_guc_context('3443.TW')
    backend=cache_store.get_cache_backend();row,_=backend._entries[master.CACHE_KEY]
    backend._entries[master.CACHE_KEY]=(row,NOW+1)
    monkeypatch.setattr(time,'time',lambda:NOW+2)
    assert not source.verify_context(value,'3443.TW',max_age=1800)
    # Archive replay is a separately bounded historical check, never a new
    # acquisition or renewed original timestamp (existing shared contract).
    assert source.verify_context(value,'3443.TW',max_age=86400)
    assert value['guc_conference_receipt']['identity']['retrieved_at']==NOW


@pytest.mark.parametrize('conflict', ['root_stock_id', 'nested_quoteType', 'nested_quote_type'])
def test_explicit_identity_alias_conflicts_block_provider_and_service_before_http(harness, conflict):
    import asyncio
    from data_fetch import FetchRequest, ProviderRegistry, StockDataService
    from data_fetch.enrichment_providers import EarningsCallProvider
    data = {'ticker': '3443.TW', 'company_name': '創意', 'quote_type': 'EQUITY',
            'company_identity': {'ticker': '3443.TW', 'stock_id': '3443',
                                 'official_name': '創意', 'instrument_type': 'EQUITY'}}
    if conflict == 'root_stock_id':
        data['stock_id'] = '3714'
    else:
        data['company_identity'][conflict.removeprefix('nested_')] = 'ETF'
    before = deepcopy(data)
    request = FetchRequest.from_ticker('3443.TW')
    provider = EarningsCallProvider()
    direct = provider.fetch(request, {'data': data})
    assert direct.status == 'unavailable' and not direct.value
    assert direct.audit['event_kind'] == 'local_block'
    assert direct.audit['http_request_count'] == 0 and not direct.audit['http_request_sent']
    assert not harness[1]
    service = StockDataService(registry=ProviderRegistry([provider]))
    result = asyncio.run(service.fetch_source_async(request, 'earnings_call', context={'data': data}))
    assert not result.data.get('earnings_call') and not harness[1]
    assert data == before


def test_matching_explicit_identity_aliases_still_acquire_original(harness):
    from data_fetch import FetchRequest
    from data_fetch.enrichment_providers import EarningsCallProvider
    data = {'ticker': '3443.TW', 'stock_id': '3443', 'company_name': '創意', 'quote_type': 'EQUITY',
            'company_identity': {'ticker': '3443.TW', 'stock_id': '3443', 'official_name': '創意',
                                 'instrument_type': 'EQUITY', 'quote_type': 'EQUITY', 'quoteType': 'EQUITY'}}
    before = deepcopy(data)
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('3443.TW'), {'data': data})
    assert result.status == 'success' and result.value['documents'][0]['page_count'] == 20
    assert harness[1] == [MASTER, INDEX, PDF] and data == before


@pytest.mark.parametrize('include_annual_table', [False, True])
def test_new_pdf_layout_must_qualify_entire_projected_page(harness, include_annual_table):
    """Native PDF control and mixed-table counterexample; no parser mock."""
    from test_source_pdf_reader import make_pdf
    from data_fetch.market_sources import guc_conference as source
    from agent_runtime.prompting import data_for_agent_prompt
    from search_provider_runtime import SourceResponseError
    pages = json.loads((F/'guc3443_reader.json').read_text())['pages']
    table = pages[5]['text'] + ('\n'+pages[6]['text'] if include_annual_table else '')
    texts = [pages[1]['text'], table, 'GUC Proprietary & Security B\nEnd']
    def escaped(text):
        return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').encode('latin-1')
    raw = make_pdf([escaped(text) for text in texts])
    # The helper uses Helvetica StandardEncoding: latin-1 0xA9 becomes an
    # apostrophe there. Declare WinAnsi for this real native-reader control,
    # preserving the saved copyright footer and rebuilding offsets correctly.
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject
    reader = PdfReader(BytesIO(raw)); writer = PdfWriter()
    for page in reader.pages:
        page['/Resources']['/Font']['/F1'].get_object()[NameObject('/Encoding')] = NameObject('/WinAnsiEncoding')
        writer.add_page(page)
    output = BytesIO(); writer.write(output); raw = output.getvalue()
    harness[0][PDF] = raw
    diagnostics = {}
    if include_annual_table:
        with pytest.raises(SourceResponseError) as exc:
            source.fetch_guc_context('3443.TW', diagnostics=diagnostics)
        assert exc.value.error_kind == 'parse_error'
        assert diagnostics['guc_originals_verified'] is False
        assert harness[1] == [MASTER, INDEX, PDF]
        pdf_component = next(c for c in diagnostics['component_statuses'] if c['url'] == PDF)
        assert source.original_bytes(pdf_component['original_receipt'], PDF, max_age=1800) == raw
    else:
        value = source.fetch_guc_context('3443.TW', diagnostics=diagnostics)
        assert value['documents'][0]['page_count'] == 3
        assert source.verify_context(value, '3443.TW', max_age=1800)
        for role in (3,5,12):
            prompt = data_for_agent_prompt(role, {'ticker':'3443.TW','company_name':'創意','earnings_call':value})
            assert prompt.get('conference_presentation')
            assert 'Amount % Amount %' not in json.dumps(prompt['conference_presentation'])
