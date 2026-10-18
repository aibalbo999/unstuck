from copy import deepcopy
import asyncio,json,time,sys
from pathlib import Path
import pytest
from fastapi import HTTPException
from conftest import isolate_provider_sla_db
from test_tdr_mops_component_refresh import saved_tdr
from test_tdr_mops_history import _source,NOW
from test_report_refresh_acquisition_audit import init_db,events
from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.provider_base import CallableProvider
from data_fetch.types import ProviderResult
from report_refresh_service import refresh_report_data_snapshot
from storage.report_storage import InMemoryStorage

@pytest.mark.parametrize('cold_status',['success','degraded_enrichment'])
def test_actual_history_provider_warm_rows_remain_refreshable_with_no_new_http(monkeypatch,tmp_path,cold_status):
    init_db();get,post,_=_source(monkeypatch)
    rows,diag=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)
    epoch=time.time()-120
    diag.update(status=cold_status,http_request_sent=True,http_request_count=5)
    import shared_provider_cache
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:((deepcopy(rows),deepcopy(diag)),{'cache_hit':True,'stale':False,'fetched_at_epoch':epoch}))
    storage=InMemoryStorage();name,keys,old,_=saved_tdr(storage,rows)
    service=StockDataService(registry=ProviderRegistry([TwseCompanyHistoryProvider()]))
    response=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='tdr_announcements'))
    assert response['success'] is True
    after=json.loads(storage.get_report(keys.data_key).content)
    audit=next(x for x in after['source_audit'] if x['provider']=='TWSE company announcement history')
    assert audit['http_request_sent'] is False and audit['http_request_count']==0,audit
    assert audit['fetched_at_epoch']==epoch
    assert after['analysis_evidence']==old['analysis_evidence']

@pytest.mark.parametrize('mode',['empty','error','wrong_ticker','missing_receipt','count_mismatch'])
def test_tdr_invalid_component_cannot_overwrite_saved_snapshot(monkeypatch,tmp_path,mode):
    init_db();get,post,_=_source(monkeypatch)
    rows,_=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)
    storage=InMemoryStorage();name,keys,old,_=saved_tdr(storage,rows);before=storage.get_report(keys.data_key).content
    count=len(rows);status='success';value=deepcopy(rows)
    if mode=='empty':value=[];count=0
    elif mode=='error':value=[];count=0;status='error'
    elif mode=='wrong_ticker':value[0]['ticker']='2236.TW'
    elif mode=='missing_receipt':value[0].pop('tdr_mops_receipt')
    elif mode=='count_mismatch':count=1
    def acquire(request,context):
        audit={'source':'recent_catalysts','provider':'TWSE company announcement history','status':status,'record_count':count,'event_kind':'http_request','http_request_sent':True,'http_request_count':5,'fetched_at_epoch':time.time()}
        return ProviderResult('recent_catalysts',audit['provider'],status,value=value,audit=audit)
    service=StockDataService(registry=ProviderRegistry([CallableProvider('recent_catalysts','TWSE company announcement history',acquire)]))
    with pytest.raises(HTTPException):
        asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='tdr_announcements'))
    assert storage.get_report(keys.data_key).content==before
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert len(events())==1
