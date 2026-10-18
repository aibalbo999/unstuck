import asyncio,json
from copy import deepcopy
import pytest
from fastapi import HTTPException
from test_honhai_conference import harness,NOW
from test_report_source_refresh import saved_report
from storage.report_storage import InMemoryStorage
from report_persistence import report_bundle_keys_for_filename
from report_analysis_evidence import capture_analysis_evidence
from report_refresh_service import refresh_report_data_snapshot
from data_fetch.service import StockDataService
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.provider_base import CallableProvider
from data_fetch.enrichment_providers import EarningsCallProvider
from data_fetch.types import ProviderResult,FetchRequest
from data_fetch.market_sources import honhai_conference as hh
from source_pdf_reader import SourcePdfError

def original(storage):
    _,oldkeys,old=saved_report(storage)
    filename='2317_TW_v4_report_20261010_100000.html';keys=report_bundle_keys_for_filename(filename)
    old['ticker']='2317.TW';old['company_name']='鴻海';old['data'].update(ticker='2317.TW',company_name='鴻海',instrument_type='EQUITY',quote_type='EQUITY',quoteType='EQUITY')
    old['data']['earnings_call']={'ticker':'2317.TW','date':hh.EVENT_DATE,'source':'TWSE WebPro conference metadata','documents':[]}
    old['analysis_evidence']=capture_analysis_evidence({'data':old['data']},generated_at=old['generated_at'])
    for k,a,mime in [(keys.html_key,oldkeys.html_key,'text/html'),(keys.md_key,oldkeys.md_key,'text/markdown')]:storage.save_report(k,storage.get_report(a).content,content_type=mime)
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    return filename,keys,old

def test_actual_service_provider_source_only_save_retains_core_age_analysis_and_all_gates(harness,tmp_path,monkeypatch):
    from data_fetch import earnings_call_fetcher as earnings
    monkeypatch.setattr(earnings,'_fetch_official_index_context',lambda *a,**k:pytest.fail('matching source-only call does not repeat metadata'))
    storage=InMemoryStorage();filename,keys,old=original(storage)
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    response=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='earnings_call',return_refreshed_data=True))
    after=json.loads(storage.get_report(keys.data_key).content);v=after['data']['earnings_call'];assert hh.verify_context(v,'2317.TW') and v['documents'][0]['page_count']==23
    assert harness[1]==[hh.PAGE_URL,hh.TRANSCRIPT_URL]
    for k in ('current_price','revenue_history','years','peer_discovery_results','instrument_type','quote_type','quoteType'):assert after['data'][k]==old['data'][k]
    assert after['analysis_evidence']==old['analysis_evidence']
    for k in ('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert after[k]==old[k]
    assert [a for a in after['source_audit']if a['source']!='earnings_call']==[a for a in old['source_audit']if a['source']!='earnings_call']
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>' and storage.get_report(keys.md_key).content==b'original conclusions'
    assert response['analysis_text_stale']is True
    audit=next(a for a in after['source_audit']if a['source']=='earnings_call');assert audit['provider']==hh.PROVIDER and audit['event_kind']=='aggregate'and audit['http_request_sent']is False and audit['http_request_count']==2

@pytest.mark.parametrize('reason',['timeout','invalid_worker_result'])
def test_native_verification_failure_keeps_entire_saved_bundle(harness,tmp_path,monkeypatch,reason):
    value=hh._fetch()['context'];storage=InMemoryStorage();filename,keys,_=original(storage);before={k:storage.get_report(k).content for k in (keys.html_key,keys.md_key,keys.data_key)}
    def acquire(request,context):
        return ProviderResult('earnings_call',hh.PROVIDER,'success',value=value,audit={'source':'earnings_call','provider':hh.PROVIDER,'status':'success','record_count':1,'event_kind':'aggregate','http_request_sent':False,'fetched_at_epoch':NOW})
    service=StockDataService(registry=ProviderRegistry([CallableProvider('earnings_call',hh.PROVIDER,acquire)]))
    def fail(*a,**k):raise SourcePdfError(reason)
    monkeypatch.setattr(hh,'extract_pdf_pages',fail)
    with pytest.raises(HTTPException)as exc:asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='earnings_call'))
    assert exc.value.status_code==502 and all(storage.get_report(k).content==raw for k,raw in before.items())

def test_non_recovery_service_context_keeps_original_ticker_contract(harness):
    called=[]
    def acquire(request,context):
        called.append(context)
        return ProviderResult('earnings_call','legacy','success',value={'ticker':'2317.TW','date':'2026-05-14'},audit={})
    service=StockDataService(registry=ProviderRegistry([CallableProvider('earnings_call','legacy',acquire)]))
    asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('2317.TW'),'earnings_call'))
    assert called==[{'original_ticker':'2317.TW'}]
