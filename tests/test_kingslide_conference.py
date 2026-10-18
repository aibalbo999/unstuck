"""Future normal acquisition must find issuer bodies, with original evidence."""
from copy import deepcopy
from pathlib import Path
import gzip
import json
import time
import pytest

NOW = 1792113000.
MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX = 'https://www.kingslide.com/investor_stockholderservice_reports/'
PDF = 'https://www.kingslide.com/media/wysiwyg/company/investor/document/205920260807M001.pdf'
F = Path(__file__).parent / 'fixtures/source_acquisition'


@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch import earnings_call_fetcher
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.setattr(earnings_call_fetcher, '_fetch_official_index_context', lambda *a, **k: {})
    bodies = {MASTER: gzip.decompress((F/'tcfhc5880_master_20261013.gz').read_bytes()),
              INDEX: gzip.decompress((F/'kingslide2059_index_20261016.gz').read_bytes()),
              PDF: gzip.decompress((F/'kingslide2059_pdf_20261016.gz').read_bytes())}
    calls = []
    if (Path(__file__).parents[1]/'backend/data_fetch/market_sources/kingslide_conference_transport.py').exists():
        from data_fetch.market_sources.kingslide_conference_transport import KingSlideConferenceHttp
        from data_fetch.market_sources import issuer_news_transport as native, gce_conference_transport as master_native
        monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
        for k in native.PROXY_ENV: monkeypatch.delenv(k, raising=False)
        def process(args, deadline, **options):
            assert args[-1] == MASTER
            raw = bodies[MASTER]; calls.append(MASTER)
            return {'body': raw, 'headers': b'HTTP/2 200\r\nContent-Type: text/csv\r\n\r\n',
                    'metadata': json.dumps({'http_code':200,'url_effective':MASTER,'num_redirects':0,
                        'size_download':len(raw),'content_type':'text/csv','method':'GET','proxy_used':0}).encode(),
                    'process_started':True}, 0, None
        for module in (native, master_native):
            monkeypatch.setattr(module, 'collect_capped_process', process)
            monkeypatch.setattr(module, 'proxy_url_for_request', lambda *a: None)
            monkeypatch.setattr(module, 'observe_http_response', lambda *a: None)
        def download(self, url, diagnostic):
            import base64
            from hashlib import sha256
            calls.append(url); self.http_request_count += 1
            raw = bodies[url]
            diagnostic.update(http_request_sent=True, http_status=200)
            return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
                    'http_status':200,'response_complete':True,'request_method':'GET',
                    'http_status_observed':True,'fetched_at_epoch':time.time()}
        monkeypatch.setattr(KingSlideConferenceHttp, '_download', download)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_public_source_acquires_body_not_date_only_old_link(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    details = {}; value = fetch_free_earnings_call_context('2059.TW', diagnostics=details)
    assert value.get('documents'), 'Normal acquisition must replace metadata with the published body'
    doc = value['documents'][0]
    assert doc['url'] == PDF and doc['page_count'] == 32 and len(doc['pages']) == 32
    assert value['date'] == '2026-08-07' and value['transcript_available'] is False
    assert doc['coverage_status'] == 'partial' and not doc['full_content_coverage_verified']
    assert details['kingslide_originals_verified'] is True


def test_conflicting_company_blocks_before_network(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2059.TW'), {'data':{
        'ticker':'2059.TW','company_name':'雙鴻','quote_type':'EQUITY'}})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert not harness[1]


def test_observed_cache_english_name_is_same_issuer(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2059.TW'), {'data':{
        'ticker':'2059.TW', 'quote_type':'EQUITY', 'company_name':'川湖 / King Slide Works Co., Ltd.',
        'company_identity':{'stock_id':'2059', 'official_name':'川湖', 'official_ubn':'22274989'}}})
    assert result.status == 'success' and result.value['documents'][0]['page_count'] == 32



@pytest.mark.parametrize('change', ['text','date','url','transcript','omissions','receipt','age','identity'])
def test_original_replay_rejects_tampering(harness, change):
    from data_fetch.market_sources import kingslide_conference as source
    v = source.fetch_kingslide_context('2059.TW')
    if change == 'text': v['documents'][0]['pages'][0]['text'] += 'fabricated'
    elif change == 'date': v['date'] = '2026-10-16'
    elif change == 'url': v['documents'][0]['url'] += '?new=1'
    elif change == 'transcript': v['transcript_available'] = True
    elif change == 'omissions': v['documents'][0]['known_native_text_omission_pages'] = []
    elif change == 'receipt': v.pop('kingslide_conference_receipt')
    elif change == 'age': v['kingslide_conference_receipt']['pdf']['retrieved_at'] = NOW - 86401
    else: v['ticker'] = '6577.TWO'
    assert source.is_marked(v) and not source.verify_context(v, '2059.TW')


def test_dynamic_index_new_event_range_without_filename_as_event_date(harness):
    from data_fetch.market_sources.kingslide_conference import select_presentation
    raw = harness[0][INDEX]
    new = raw.replace(b'2026:{', b'2026:{ "J":{"year":"2026","date":"2026 / 10 / 01 ~ 02","local":"Taipei","video":"","pdf":"205920260930M001.pdf"},',1)
    result = select_presentation(new,NOW)
    assert result['event_date'] == '2026-10-01' and result['event_end_date'] == '2026-10-02'
    assert result['material_file_date'] == '2026-09-30' and result['pdf_url'].endswith('205920260930M001.pdf')
    # A not-yet-past new event never claims to have occurred.
    future = new.replace(b'2026 / 10 / 01 ~ 02',b'2026 / 12 / 01 ~ 02')
    assert select_presentation(future,NOW)['event_date'] == '2026-08-07'


@pytest.mark.parametrize('change', ['duplicate','missing_pdf','bad_path','javascript','truncated','invalid_range'])
def test_newest_index_cannot_silently_fall_back_or_execute_code(harness, change):
    from data_fetch.market_sources.kingslide_conference import select_presentation
    raw=harness[0][INDEX]
    if change=='duplicate': raw=raw.replace(b'2026:{',b'2026:{"I":{},',1)
    elif change=='missing_pdf': raw=raw.replace(b'205920260807M001.pdf',b'',1)
    elif change=='bad_path': raw=raw.replace(b'205920260807M001.pdf',b'../../other.pdf',1)
    elif change=='javascript':raw=raw.replace(b'let dataList={',b'let dataList={"execute":alert("test"),',1)
    elif change=='truncated':raw=raw.replace(b'</html>',b'')
    else:raw=raw.replace(b'2026 \\/ 08 \\/ 07',b'2026 / 08 / 07 ~ 01',1)
    with pytest.raises(ValueError):select_presentation(raw,NOW)


@pytest.mark.parametrize('change', ['other_master','html_pdf','content_date','conflicting_alias'])
def test_invalid_original_or_context_fails_closed(harness, change):
    from data_fetch.market_sources import kingslide_conference as source
    from search_provider_runtime import SourceResponseError
    if change=='conflicting_alias':
        assert not source.validate_context({'ticker':'2059.TW','quote_type':'EQUITY','company_name':'雙鴻'},'2059.TW')
        return
    if change=='other_master':harness[0][MASTER]=harness[0][MASTER].replace('川湖科技股份有限公司'.encode(),'別家科技股份有限公司'.encode())
    elif change=='html_pdf':harness[0][PDF]=b'<html>error page</html>'
    else:
        # A recycled document cannot masquerade as a newly named older file.
        harness[0][INDEX]=harness[0][INDEX].replace(b'205920260807M001.pdf',b'205920260701M001.pdf')
        harness[0][PDF.replace('0807','0701')]=harness[0][PDF]
    details={}
    with pytest.raises(SourceResponseError):source.fetch_kingslide_context('2059.TW',diagnostics=details)
    assert not details.get('kingslide_originals_verified')


def test_warm_replay_is_not_new_acquisition(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    p=EarningsCallProvider();request=FetchRequest.from_ticker('2059.TW')
    cold=p.fetch(request);calls=len(harness[1]);warm=p.fetch(request)
    assert cold.status=='success' and cold.audit['record_count']==1
    assert warm.audit['status']=='skipped_fresh_cache' and calls==3 and len(harness[1])==4 and harness[1][-1]==INDEX
    assert warm.value['fetched_at_epoch']==cold.value['fetched_at_epoch']==NOW


def test_role_projection_retains_issuer_scope_and_real_omissions(harness):
    from data_fetch.market_sources.kingslide_conference import fetch_kingslide_context
    from conference_presentation_prompt import presentation_prompt_context
    from prompt_evidence import prompt_evidence_copy
    value=fetch_kingslide_context('2059.TW');before=deepcopy(value)
    assert value['documents'][0]['known_native_text_omission_pages']==[21,22,25,28,31]
    for role in (3,5,12):
        result=presentation_prompt_context(value,role);d=result['documents'][0]
        assert [p['page_number'] for p in d['pages']]==[1,3,4,11,12,13,14]
        assert all(not p['content_truncated'] for p in d['pages'])
        assert d['known_native_text_omission_pages']==[21,22,25,28,31]
        assert d['full_content_coverage_verified'] is False and '子公司' in d['financial_scope_caution']
    assert value==before and 'kingslide_conference_receipt' not in prompt_evidence_copy(value)


@pytest.mark.parametrize('tampered',[False,True])
def test_report_refresh_preserves_analysis_and_verifies_original(harness,tmp_path,monkeypatch,tampered):
    import asyncio
    from fastapi import HTTPException
    from data_fetch import StockDataService,ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.market_sources import kingslide_conference as source
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db
    init_db();storage=InMemoryStorage();filename,keys,old=saved_report(storage)
    old=json.loads(json.dumps(old,ensure_ascii=False).replace('6214.TW','2059.TW').replace('精誠','川湖'))
    old['data']['quote_type']='EQUITY';original=json.dumps(old).encode()
    storage.save_report(keys.data_key,original,content_type='application/json')
    if tampered:
        acquire=source.fetch_kingslide_context
        def altered(*a,**kw):
            v=acquire(*a,**kw);v['documents'][0]['pages'][7]['text']+=' fabricated revenue';return v
        monkeypatch.setattr(source,'fetch_kingslide_context',altered)
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    def refresh():return asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
        refresh_service=service,source='earnings_call',return_refreshed_data=True))
    if tampered:
        with pytest.raises(HTTPException) as exc:refresh()
        assert exc.value.status_code==502 and storage.get_report(keys.data_key).content==original
    else:
        assert refresh()['analysis_text_stale'] is True
        new=json.loads(storage.get_report(keys.data_key).content)
        assert new['data']['earnings_call']['documents'][0]['page_count']==32
        for k in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
            assert new[k]==old[k]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'


def test_source_only_request_keeps_company_context_before_any_http(harness):
    import asyncio
    from data_fetch import StockDataService,ProviderRegistry,FetchRequest
    from data_fetch.enrichment_providers import EarningsCallProvider
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    result=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('2059.TW'),'earnings_call',context={'data':{
        'ticker':'2059.TW','company_name':'雙鴻','quote_type':'EQUITY'}}))
    assert not result.data.get('earnings_call') and not harness[1]

@pytest.mark.parametrize('tampered',[False,True])
def test_actual_agent_prompt_keeps_verified_body_and_never_internal_receipts(harness,tampered):
    from data_fetch.market_sources.kingslide_conference import fetch_kingslide_context
    from agent_runtime.prompting import data_for_agent_prompt
    value=fetch_kingslide_context('2059.TW')
    if tampered:value['documents'][0]['pages'][3]['text'] += ' fabricated profit'
    data={'ticker':'2059.TW','company_name':'川湖','earnings_call':value}
    before=deepcopy(data)
    for role in (3,5,12):
        result=data_for_agent_prompt(role,data)
        assert bool(result.get('conference_presentation')) is (not tampered)
        assert 'kingslide_conference_receipt' not in json.dumps(result,ensure_ascii=False)
    assert data==before


def test_failed_warm_handoff_is_failure_not_empty_cache(harness,monkeypatch):
 from data_fetch.market_sources import kingslide_conference as source
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 from provider_acquisition import observation_kind
 p=EarningsCallProvider();req=FetchRequest.from_ticker('2059.TW')
 cold=p.fetch(req,{'data':{'ticker':'2059.TW','quote_type':'EQUITY','company_name':'川湖'}});assert cold.status=='success'
 old_count=len(harness[1]);original_deepcopy=source.deepcopy;original_monotonic=time.monotonic
 state={'late':False}
 monkeypatch.setattr(time,'monotonic',lambda:original_monotonic()+(21 if state['late'] else 0))
 def slow_components(value,*a,**kw):
  out=original_deepcopy(value,*a,**kw)
  if isinstance(value,list) and value and all(isinstance(x,dict) and 'url' in x for x in value):state['late']=True
  return out
 monkeypatch.setattr(source,'deepcopy',slow_components)
 failed=p.fetch(req,{'data':{'ticker':'2059.TW','quote_type':'EQUITY','company_name':'川湖'}})
 assert state['late'] and failed.status=='error' and not failed.value
 assert len(harness[1])==old_count+1 and failed.audit['http_request_count']==1
 assert failed.audit['record_count']==0 and not failed.audit['kingslide_originals_verified']
 row={**failed.audit,'details':dict(failed.audit)}
 assert observation_kind(row)=='failed_count',failed.audit
 assert 'coverage_status' not in failed.audit
