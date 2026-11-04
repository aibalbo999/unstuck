"""The new source-only path cannot refresh old conclusions or weaken audits."""
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
import json,time

import pytest

from test_security_related_peer_cohort import pipeline

DATA={'ticker':'9917.TW','company_name':'中保科','sector':'Industrials','industry':'Security & Protection Services',
      'instrument_type':'EQUITY','dynamic_peer_metrics':[],
      'company_identity':{'ticker':'9917.TW','stock_id':'9917','official_name':'中保科','instrument_type':'EQUITY'}}


def observed(monkeypatch):
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.types import FetchRequest
    pipeline(monkeypatch)
    return DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('9917.TW'),{'data':deepcopy(DATA)})


@pytest.mark.parametrize('damage',['count_bool','wrong_count','missing_operation','wrong_ticker','wrong_provider','stale_audit','wrong_status','wrong_quality','missing_body','changed_peer','rank_upgrade','bool_metric','unknown_asset_period'])
def test_source_guard_rejects_bad_observations_without_mutating_original(damage,monkeypatch):
    from security_peer_source_refresh import guard_result
    from dataclasses import replace
    result=observed(monkeypatch);value=deepcopy(result.value);audit=deepcopy(result.audit)
    assert result.status=='success'and len(value)==1
    if damage=='count_bool':audit['record_count']=True
    elif damage=='wrong_count':audit['record_count']=2
    elif damage=='missing_operation':audit.pop('operation_id',None)
    elif damage=='wrong_ticker':audit['ticker']='2330.TW'
    elif damage=='wrong_provider':audit['provider']='other'
    elif damage=='stale_audit':audit['fetched_at_epoch']=time.time()-1801;audit['fetched_at']=datetime.fromtimestamp(audit['fetched_at_epoch'],timezone.utc).isoformat()
    elif damage=='wrong_status':audit['status']='degraded_enrichment'
    elif damage=='wrong_quality':audit['quality_status']='partial_metrics'
    elif damage=='missing_body':value[0]['security_related_originals']['publication_receipt']['raw_response_sha256']='0'*64
    elif damage=='changed_peer':value[0]['ticker']='2891.TW'
    elif damage=='rank_upgrade':value[0]['business_comparability_verified_current']=True
    elif damage=='bool_metric':value[0]['roe_pct']=True
    else:value[0]['metric_sources']['asset_turnover']['observed_at']=None
    data=deepcopy(DATA);bad=replace(result,value=value,audit=audit)
    guarded=guard_result(bad,data,'9917.TW')
    assert guarded.status=='error'and guarded.value==[]and data==DATA
    assert result.value[0]['ticker']=='9925.TW'


@pytest.mark.parametrize('damage',['name','industry','ticker','stock_id','float_id','not_equity','missing_list'])
def test_context_refusal_happens_before_source_calls(damage):
    from peer_source_refresh import validate_peer_refresh_context
    from fastapi import HTTPException
    data=deepcopy(DATA)
    if damage=='name':data['company_name']='另一公司'
    elif damage=='industry':data['industry']='Banks - Regional'
    elif damage=='ticker':data['ticker']='2330.TW'
    elif damage=='stock_id':data['company_identity']['stock_id']='2330'
    elif damage=='float_id':data['company_identity']['stock_id']=9917.0
    elif damage=='not_equity':data['quoteType']='ETF'
    else:data.pop('dynamic_peer_metrics')
    with pytest.raises(HTTPException)as caught:validate_peer_refresh_context(data,'9917.TW')
    assert caught.value.status_code==400


def test_source_only_refresh_preserves_report_analysis_quotes_and_quality_gates(monkeypatch,tmp_path):
    from storage.report_storage import InMemoryStorage
    from report_analysis_evidence import capture_analysis_evidence
    from report_persistence import report_bundle_keys_for_filename
    from report_refresh_service import refresh_report_data_snapshot
    from data_fetch.service import StockDataService
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from test_report_refresh_acquisition_audit import init_db,events
    init_db();pipeline(monkeypatch)
    name='9917_TW_v4_report_20261104_210000.html';keys=report_bundle_keys_for_filename(name);storage=InMemoryStorage()
    stamp=time.time()-86400;data={**deepcopy(DATA),'current_price':100,'years':['2025'],'revenue_history':[1],
        'source_audit':[{'source':'market_data','provider':'original','status':'success','record_count':1,'fetched_at_epoch':stamp,
            'fetched_at':datetime.fromtimestamp(stamp,timezone.utc).isoformat()}]}
    old={'ticker':'9917.TW','pipeline':'v4','generated_at':datetime.fromtimestamp(stamp,timezone.utc).isoformat(),'data':data,'source_audit':deepcopy(data['source_audit'])}
    for k in('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):old[k]={'original':k}
    old['analysis_evidence']=capture_analysis_evidence({'data':data},generated_at=old['generated_at'])
    for key,body,ctype in[(keys.html_key,b'<html>original conclusions</html>','text/html'),(keys.md_key,b'original conclusions','text/markdown'),(keys.data_key,json.dumps(old).encode(),'application/json')]:storage.save_report(key,body,content_type=ctype)
    def forbidden(*a,**kw):pytest.fail('no unrelated core/model request')
    service=StockDataService(registry=ProviderRegistry([DynamicPeerMetricsProvider(),CallableProvider('market_data','forbidden',forbidden)]))
    original=service.fetch_source_async;calls=[]
    async def checked(request,*a,**kw):
        calls.append(request.options.force_refresh);return await original(request,*a,**kw)
    monkeypatch.setattr(service,'fetch_source_async',checked)
    result=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='dynamic_peer_metrics',return_refreshed_data=True))
    updated=json.loads(storage.get_report(keys.data_key).content)
    assert calls==[False]and [r['ticker']for r in updated['data']['dynamic_peer_metrics']]==['9925.TW']
    for k in('current_price','years','revenue_history'):assert updated['data'][k]==data[k]
    assert updated['analysis_evidence']==old['analysis_evidence']
    for k in('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert updated[k]==old[k]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'and storage.get_report(keys.md_key).content==b'original conclusions'
    assert result['analysis_text_stale']is True
    assert len([r for r in events()if r['source']=='dynamic_peer_metrics'])==1
