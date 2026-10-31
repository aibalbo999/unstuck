from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import time
import pytest

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261016/remaining-source-expansion/pcsc-integration-candidate'
R=D.parent/'conference-next-entry'
NOW=1792144662.
MASTER='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX='https://ir.7-11.com.tw/tw/event.php'
PROFILE='https://ir.7-11.com.tw/tw/companyprofile.php'
PDF='https://ir.7-11.com.tw/taiwan/2912/events/262/CH/20260916174252-1.pdf'

@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch import earnings_call_fetcher
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time,'time',lambda:NOW)
    monkeypatch.setattr(earnings_call_fetcher,'_fetch_official_index_context',lambda *a,**k:{'ticker':'2912','date':'2026-09-17','documents':[]})
    bodies={MASTER:(ROOT/'docs/evidence/source-acquisition/20261015/moenv-environmental-penalties/twse_issuer_master.csv').read_bytes(),
            INDEX:(R/'pcsc-index.body').read_bytes(),PROFILE:(R/'pcsc-profile.body').read_bytes(),PDF:(R/'pcsc-presentation.body').read_bytes()}
    calls=[]
    path=ROOT/'backend/data_fetch/market_sources/pcsc_conference_transport.py'
    if path.exists():
        from data_fetch.market_sources import pcsc_conference_transport as native, gce_conference_transport as shared_native
        monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
        for key in native.PROXY_ENV:monkeypatch.delenv(key,raising=False)
        def process(args,deadline,**options):
            url=args[-1];calls.append(url);raw=bodies[url]
            ctype='text/csv' if url==MASTER else 'application/pdf' if url.endswith('.pdf') else 'text/html'
            return {'body':raw,'headers':f'HTTP/2 200\r\nContent-Type: {ctype}\r\nContent-Length: {len(raw)}\r\n\r\n'.encode(),
                'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0,'size_download':len(raw),'content_type':ctype,'method':'GET','proxy_used':0}).encode(),
                'process_started':True},0,None
        for m in (native,shared_native):
            monkeypatch.setattr(m,'collect_capped_process',process)
            monkeypatch.setattr(m,'proxy_url_for_request',lambda *a:None)
            monkeypatch.setattr(m,'observe_http_response',lambda *a:None)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()


def test_public_normal_route_acquires_current_same_row_body(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    details={};value=fetch_free_earnings_call_context('2912.TW',diagnostics=details)
    assert value.get('documents'), '2912 normal source must acquire current original body instead of metadata only'
    d=value['documents'][0]
    assert d['page_count']==22 and len(d['pages'])==22 and d['url']==PDF
    assert value['date']=='2026-09-17' and value['transcript_available'] is False
    assert d['coverage_status']=='partial' and d['native_text_coverage']=='partial'
    assert d['projection_excluded_pages']==[3,4,5,8,11,12,13,14,15,16,17,19,20]
    assert details['pcsc_originals_verified'] is True and details['http_request_count']==4


def test_warm_identity_still_requires_three_new_issuer_originals(harness):
    from data_fetch.market_sources.pcsc_conference import fetch_pcsc_context
    first={};second={}
    fetch_pcsc_context('2912.TW',diagnostics=first)
    fetch_pcsc_context('2912.TW',diagnostics=second,force_refresh=True,use_cache=False)
    assert harness[1]==[MASTER,INDEX,PROFILE,PDF,INDEX,PROFILE,PDF]
    assert first['http_request_count']==4 and second['http_request_count']==3
    assert second['cache_hit'] is False and second['component_statuses'][0]['cache_hit'] is True


def test_provider_uses_actual_snapshot_alias_and_keeps_success_partial(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    p=EarningsCallProvider().fetch(FetchRequest.from_ticker('2912.TW'),{'data':{
        'ticker':'2912.TW','company_name':'統一超 / President Chain Store Corporation','quote_type':'EQUITY',
        'company_identity':{'stock_id':'2912','official_name':'統一超','english_names':['PRESIDENT CHAIN STORE CORP']}}})
    assert p.status=='success' and p.audit['record_count']==1
    assert p.value['coverage_status']=='partial' and p.audit['coverage_status']=='qualified_partial_presentation'


@pytest.mark.parametrize('edit',['ticker','legal','ubn','name','etf','forbidden'])
def test_wrong_context_blocks_before_any_http(harness,edit):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    d={'ticker':'2912.TW','company_name':'統一超','quote_type':'EQUITY','company_identity':{}}
    if edit=='ticker':d['ticker']='1216.TW'
    elif edit=='legal':d['company_identity']['legal_name']='統一企業股份有限公司'
    elif edit=='ubn':d['company_identity']['official_ubn']='12345678'
    elif edit=='name':d['company_name']='統一'
    elif edit=='etf':d['quoteType']='ETF'
    else:d['company_identity']['forbidden_aliases']=['<b>統一超</b>']
    value=EarningsCallProvider().fetch(FetchRequest.from_ticker('2912.TW'),{'data':d})
    assert value.status=='unavailable' and not harness[1]


@pytest.mark.parametrize('edit',['text','event','url','policy','allowlist','xref_bool','coverage','transcript','expiry','epoch','cache_bool','manifest','identity'])
def test_immutable_context_replay_rejects_tamper(harness,edit):
    from data_fetch.market_sources import pcsc_conference as s
    v=s.fetch_pcsc_context('2912.TW');p=v['pcsc_conference_receipt'];d=v['documents'][0]
    if edit=='text':d['pages'][6]['text']+=' made-up profit'
    elif edit=='event':p['selected']['event_date']='2026-09-18'
    elif edit=='url':d['url']=PDF.replace('/262/','/260/')
    elif edit=='policy':d['projection_policy']='generic'
    elif edit=='allowlist':d['role_page_allowlist'].append(19)
    elif edit=='xref_bool':d['xref_validation_evidence']['raw_bytes_rewritten']=0
    elif edit=='coverage':d['full_visual_content_verified']=True
    elif edit=='transcript':v['transcript_available']=True
    elif edit=='expiry':p['pdf']['fresh_until_epoch']+=1000
    elif edit=='epoch':p['pdf']['retrieved_at']+=1
    elif edit=='cache_bool':p['pdf']['cache_hit']=0
    elif edit=='manifest':p['pdf'].pop('acquisition_manifest')
    else:p['identity'].pop('retrieval_policy')
    assert s.is_marked(v) and not s.verify_context(v,'2912.TW')


def test_role_pages_v2_exact_raw_order_and_semantic_limits(harness):
    from data_fetch.market_sources import pcsc_conference as s
    from conference_presentation_prompt import presentation_prompt_context
    from prompt_evidence import prompt_evidence_copy
    from data_fetch.cache_helpers import _contains_allis_no_store
    v=s.fetch_pcsc_context('2912.TW');before=deepcopy(v)
    for role in (3,5,12):
        result=presentation_prompt_context(v,role)
        d=result['documents'][0]
        assert [p['page_number'] for p in d['pages']]==list(s.ROLE_PAGES)
        assert not any(p['content_truncated'] for p in d['pages'])
        assert d['full_visual_content_verified'] is False and d['q_and_a_transcript_available'] is False
        assert '第19頁' in d['financial_scope_caution'] and '導入ING' in d['financial_scope_caution']
        assert d['financial_statement_complete'] is False
        assert 'pcsc_conference_receipt' not in json.dumps(prompt_evidence_copy(result))
    assert _contains_allis_no_store(v) and before==v
    v['documents'][0]['source']='issuer_official';v['source']='issuer_official';v.pop('pcsc_conference_receipt')
    assert s.is_marked(v) and presentation_prompt_context(v,3)=={}


@pytest.mark.parametrize('edit',['no_pdf','wrong_host','wrong_issuer','duplicate_pdf','duplicate_event','wrong_year','not_active_latest','truncated'])
def test_latest_index_has_no_silent_fallback(harness,edit):
    from data_fetch.market_sources.pcsc_conference import select_presentation
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(harness[0][INDEX],'html.parser')
    a=soup.find('a',href='../taiwan/2912/events/262/CH/20260916174252-1.pdf')
    row=a.find_parent('tr')
    if edit=='no_pdf':a.decompose()
    elif edit=='wrong_host':a['href']='https://unrelated.example/a.pdf'
    elif edit=='wrong_issuer':a['href']=a['href'].replace('/2912/','/1216/')
    elif edit=='duplicate_pdf':a.insert_after(deepcopy(a))
    elif edit=='duplicate_event':row.insert_after(deepcopy(row))
    elif edit=='wrong_year':row.find('td').string='2025-09-17'
    elif edit=='not_active_latest':soup.select_one('li[aria-selected="true"]')['aria-selected']='false'
    raw=str(soup).encode()
    if edit=='truncated':raw=raw.replace(b'</html>',b'')
    with pytest.raises(ValueError):select_presentation(raw,NOW)


def test_new_year_same_row_href_is_discovered_but_old_body_not_promoted(harness,monkeypatch):
    from data_fetch.market_sources import pcsc_conference as s
    from datetime import datetime
    from zoneinfo import ZoneInfo
    later=datetime(2027,10,16,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    monkeypatch.setattr(time,'time',lambda:later)
    raw=harness[0][INDEX].replace(b'2026',b'2027').replace(b'/262/',b'/280/')
    selected=s.select_presentation(raw,later)
    assert selected['event_date']=='2027-09-17' and '/280/CH/202709' in selected['pdf_url']
    with pytest.raises(ValueError,match='period incompatible'):
        s.native_presentation(harness[0][PDF],selected,time.monotonic()+10)


def test_same_qualified_material_new_published_event_path_not_fixed_url(harness):
    from data_fetch.market_sources import pcsc_conference as s
    newpdf=PDF.replace('/262/','/263/')
    harness[0][INDEX]=harness[0][INDEX].replace(b'/262/',b'/263/').replace(b'2026-09-17',b'2026-10-15')
    harness[0][newpdf]=harness[0][PDF]
    v=s.fetch_pcsc_context('2912.TW')
    assert v['date']=='2026-10-15' and v['documents'][0]['url']==newpdf
    assert v['documents'][0]['content_periods'][0]=='2026H1'


def test_unknown_clean_pdf_is_acquired_but_not_qualified_or_projected(harness):
    from test_source_pdf_reader import make_pdf
    from data_fetch.market_sources import pcsc_conference as s
    from source_pdf_reader import extract_pdf_pages
    from search_provider_runtime import SourceResponseError
    raw=make_pdf([b'PCSC 2912 clean new issuer presentation text, not yet visually qualified'])
    assert extract_pdf_pages(raw)['coverage_status']=='complete'
    harness[0][PDF]=raw;diag={}
    with pytest.raises(SourceResponseError) as err:s.fetch_pcsc_context('2912.TW',diagnostics=diag)
    assert err.value.error_kind=='unqualified_revision' and diag['pcsc_originals_verified'] is False
    assert diag['http_request_count']==4 and 'coverage_status' not in diag
    assert diag['component_statuses'][-1]['original_receipt']['raw_response_sha256']==sha256(raw).hexdigest()


def test_unknown_warning_is_fatal_not_exact_repair(harness):
    from data_fetch.market_sources import pcsc_conference as s
    from source_pdf_reader import SourcePdfError
    selected=s.select_presentation(harness[0][INDEX],NOW)
    raw=harness[0][PDF].replace(b'%PDF-1.7',b'%PDF-1.6',1)
    assert raw!=harness[0][PDF]
    with pytest.raises(SourcePdfError,match='parser_warning'):s.native_presentation(raw,selected,time.monotonic()+10)


def test_short_ttl_expires_at_final_handoff_not_extended(harness,monkeypatch):
    from data_fetch.market_sources import pcsc_conference as s
    from search_provider_runtime import SourceResponseError
    original=s.deepcopy;clock={'late':False}
    monkeypatch.setattr(time,'time',lambda:NOW+(1800 if clock['late'] else 0))
    def late(v,*a,**k):
        result=original(v,*a,**k)
        if isinstance(v,list) and v and isinstance(v[0],dict) and 'url' in v[0]:clock['late']=True
        return result
    monkeypatch.setattr(s,'deepcopy',late);diag={}
    with pytest.raises(SourceResponseError) as error:s.fetch_pcsc_context('2912.TW',diagnostics=diag)
    assert error.value.error_kind=='original_expired'
    assert clock['late'] and diag['pcsc_originals_verified'] is False and diag['http_request_count']==4


@pytest.mark.parametrize('tampered',[False,True])
def test_saved_source_only_preserves_analysis_and_requires_exact_packet(harness,tmp_path,monkeypatch,tampered):
    import asyncio
    from fastapi import HTTPException
    from data_fetch import StockDataService,ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.market_sources import pcsc_conference as source
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db
    init_db();storage=InMemoryStorage();filename,keys,old=saved_report(storage)
    old=json.loads(json.dumps(old,ensure_ascii=False).replace('6214.TW','2912.TW').replace('精誠','統一超'))
    old['data']['quote_type']='EQUITY';original=json.dumps(old).encode()
    storage.save_report(keys.data_key,original,content_type='application/json')
    if tampered:
        acquire=source.fetch_pcsc_context
        def altered(*a,**kw):
            v=acquire(*a,**kw);v['documents'][0]['role_page_allowlist'].append(19);return v
        monkeypatch.setattr(source,'fetch_pcsc_context',altered)
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    def refresh():return asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
        refresh_service=service,source='earnings_call',return_refreshed_data=True))
    if tampered:
        with pytest.raises(HTTPException) as exc:refresh()
        assert exc.value.status_code==502 and storage.get_report(keys.data_key).content==original
    else:
        assert refresh()['analysis_text_stale'] is True
        new=json.loads(storage.get_report(keys.data_key).content)
        assert new['data']['earnings_call']['documents'][0]['page_count']==22
        for k in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
            assert new[k]==old[k]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'


def test_page_number_tamper_cannot_project_excluded_site_claims(harness):
    from data_fetch.market_sources import pcsc_conference as s
    value=s.fetch_pcsc_context('2912.TW');doc=value['documents'][0]
    doc['pages'][18]['page_number']=1
    assert s.role_pages(doc)==[]


def test_false_identity_is_not_absent_identity(harness):
    from data_fetch.market_sources.pcsc_conference import validate_context
    assert not validate_context({'ticker':'2912.TW','quote_type':'EQUITY','company_identity':False},'2912.TW')


@pytest.mark.parametrize('part,count',[(MASTER,1),(PROFILE,3)])
def test_conflicting_native_identity_stops_before_material(harness,part,count):
    from data_fetch.market_sources import pcsc_conference as s
    from search_provider_runtime import SourceResponseError
    harness[0][part]=harness[0][part].replace('統一超商股份有限公司'.encode(),'別的公司股份有限公司'.encode())
    diag={}
    with pytest.raises(SourceResponseError):s.fetch_pcsc_context('2912.TW',diagnostics=diag)
    assert len(harness[1])==count and PDF not in harness[1] and diag['pcsc_originals_verified'] is False


def test_source_only_context_is_retained_before_http(harness):
    import asyncio
    from data_fetch import StockDataService,ProviderRegistry,FetchRequest
    from data_fetch.enrichment_providers import EarningsCallProvider
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    value=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('2912.TW'),'earnings_call',context={'data':{
        'ticker':'2912.TW','company_name':'統一企業','quote_type':'EQUITY'}}))
    assert not value.data.get('earnings_call') and not harness[1]


def test_new_index_cannot_repackage_an_older_pdf_as_new_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import pcsc_conference as s
    first=s.fetch_pcsc_context('2912.TW')
    monkeypatch.setattr(time,'time',lambda:NOW+60)
    new=s.fetch_pcsc_context('2912.TW')
    new['pcsc_conference_receipt']['pdf']=first['pcsc_conference_receipt']['pdf']
    new['documents'][0]['retrieved_at_epoch']=first['documents'][0]['retrieved_at_epoch']
    new['fetched_at_epoch']=first['fetched_at_epoch']
    assert not s.verify_context(new,'2912.TW')


@pytest.mark.parametrize('payload',[
    {'ticker':'2912.TW','company_name':'統一超','quote_type':'EQUITY','stock_id':'1216'},
    {'ticker':'2912.TW','company_name':'統一超','quote_type':'EQUITY','company_identity':{'quote_type':'ETF'}},
    {'ticker':'2912.TW','company_name':'統一超','quote_type':'EQUITY','company_identity':{'quoteType':'ETF'}},
    False,
])
def test_explicit_nested_or_top_identity_conflict_blocks_native(harness,payload):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2912.TW'),{'data':payload})
    assert result.status=='unavailable' and not result.value and result.audit['event_kind']=='local_block'
    assert not harness[1]
