"""NCC source-only admission must preserve the existing thermal boundary."""
import asyncio
from copy import deepcopy
import pytest
from fastapi import HTTPException
from test_shared_provider_cache import memory_cache
from test_ncc_mobile_peer_cohort import metrics_harness
from data_fetch.types import FetchRequest
from data_fetch.service import StockDataService
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.provider_base import CallableProvider
from data_fetch.enrichment_providers import DynamicPeerMetricsProvider


def context():return {'ticker':'2412.TW','company_name':'中華電','quote_type':'EQUITY','instrument_type':'EQUITY',
 'industry':'Telecom Services','sector':'Communication Services','current_price':100,'revenue_history':[1,2,3],
 'dynamic_peer_metrics':[],'peer_discovery_results':[{'original':'retained'}],
 'company_identity':{'ticker':'2412.TW','stock_id':'2412','official_name':'中華電','instrument_type':'EQUITY'}}


def service():
 def forbidden(*a,**kw):pytest.fail('Source-only must not call core or unrelated sources')
 return StockDataService(registry=ProviderRegistry([DynamicPeerMetricsProvider(),CallableProvider('market_data','forbidden',forbidden)]))


def test_canonical_source_only_recovers_verified_ncc_metrics_without_other_sources(monkeypatch):
 _,calls,_=metrics_harness(monkeypatch);data=context();before=deepcopy(data)
 result=asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2412.TW'),'dynamic_peer_metrics',context={'data':data}))
 assert len(result.data['dynamic_peer_metrics'])==2
 assert len(result.data['source_audit'])==1 and result.data['source_audit'][0]['source']=='dynamic_peer_metrics'
 assert data==before and len(calls)==1

@pytest.mark.parametrize('change',[
 lambda d:d.update(ticker='2330.TW'),lambda d:d.update(company_name='其他公司'),
 lambda d:d.update(quote_type='ETF'),lambda d:d.update(industry='Specialty Retail'),
 lambda d:d['company_identity'].update(official_name='中華電信子公司'),
 lambda d:d['company_identity'].update(stock_id='2330'),
 lambda d:d.pop('dynamic_peer_metrics')])
def test_conflicting_original_context_rejects_before_any_source_fetch(monkeypatch,change):
 _,calls,_=metrics_harness(monkeypatch);data=context();change(data);before=deepcopy(data)
 with pytest.raises(HTTPException)as error:asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2412.TW'),'dynamic_peer_metrics',context={'data':data}))
 assert error.value.status_code==400 and not calls and data==before


def acquired(monkeypatch):
 metrics_harness(monkeypatch);data=context();result=asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2412.TW'),'dynamic_peer_metrics',context={'data':data}))
 return data,result.data['dynamic_peer_metrics'],result.data['source_audit']


def test_merge_replaces_only_peer_source_and_preserves_original_core_age(monkeypatch):
 from peer_source_refresh import merge_peer_source
 from test_ncc_mobile_peer_cohort import NOW
 data,value,audits=acquired(monkeypatch)
 old_audits=[{'source':'market_data','provider':'original market','status':'success','record_count':1,'fetch_id':'old','fetched_at_epoch':NOW-3*86400,'cache_hit':False,'stale':True},
             {'source':'dynamic_peer_metrics','provider':'FinMind/yfinance','status':'unavailable','record_count':0,'fetch_id':'old','fetched_at_epoch':NOW-3*86400}]
 data['source_audit']=deepcopy(old_audits);before=deepcopy(data)
 merged=merge_peer_source(data,old_audits,value,audits,'2412.TW')
 assert data==before and len(merged['dynamic_peer_metrics'])==2
 for k in('current_price','revenue_history','peer_discovery_results','company_identity','company_name','industry'):assert merged[k]==before[k]
 assert next(a for a in merged['source_audit']if a['source']=='market_data')==old_audits[0]
 assert next(a for a in merged['source_audit']if a['source']=='dynamic_peer_metrics')['fetch_id']!=old_audits[1]['fetch_id']

@pytest.mark.parametrize('change',[
 lambda v,a:v[0].pop('ncc_mobile_membership_originals'),lambda v,a:v[0].update(ticker='2330.TW'),
 lambda v,a:v[0].update(numeric_comparability_verified=True),lambda v,a:v[0].update(business_comparability_verified_current=True),
 lambda v,a:v.append(deepcopy(v[0])),lambda v,a:v[0].update(gross_margin_pct=float('nan')),
 lambda v,a:v[0].update(gross_margin_pct=True),lambda v,a:v[0].update(reported_industry='Specialty Retail'),
 lambda v,a:v[0].update(comparison_status='industry_candidate_only'),
 lambda v,a:v[0]['metric_sources'].pop('gross_margin_pct'),lambda v,a:v[0]['metric_sources']['gross_margin_pct'].update(observed_at='2099-12-31'),
 lambda v,a:a[0].update(record_count=9),lambda v,a:a[0].update(record_count=True),lambda v,a:a[0].update(usable_count=0),
 lambda v,a:a[0].update(provider='other'),lambda v,a:a[0].update(ticker='4904.TW'),
 lambda v,a:a[0].update(operation_id=None),lambda v,a:a[0].update(fetch_id=''),
 lambda v,a:a[0].update(status='skipped_fresh_cache',cache_hit=True),lambda v,a:a[0].update(stale=True),
 lambda v,a:a[0].update(fetched_at='2000-01-01T00:00:00+00:00'),lambda v,a:a[0].update(quality_status='metrics_missing'),
 lambda v,a:a[0].update(coverage_status='success')])
def test_unverified_metrics_or_audits_never_mutate_original_snapshot(monkeypatch,change):
 from peer_source_refresh import merge_peer_source
 data,value,audits=acquired(monkeypatch);before=deepcopy(data);change(value,audits)
 with pytest.raises(HTTPException)as error:merge_peer_source(data,[],value,audits,'2412.TW')
 assert error.value.status_code==502 and data==before


def test_ncc_source_only_refuses_force_and_retail_without_fetching(monkeypatch):
 _,calls,_=metrics_harness(monkeypatch)
 with pytest.raises(HTTPException)as error:asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2412.TW',force_refresh=True),'dynamic_peer_metrics',context={'data':context()}))
 assert error.value.status_code==400 and not calls


def test_invalid_source_result_is_recorded_as_failure_without_losing_native_evidence(monkeypatch):
 from ncc_peer_source_refresh import guard_ncc_result
 from data_fetch.types import ProviderResult
 data,value,audits=acquired(monkeypatch);audit=audits[0];audit.update(http_request_sent=True,http_request_count=1)
 value[0]['numeric_comparability_verified']=True
 result=ProviderResult('dynamic_peer_metrics','FinMind/yfinance','success',value=value,audit=audit)
 guarded=guard_ncc_result(result,data,'2412.TW')
 assert guarded.status=='error'and guarded.value==[]and guarded.audit['record_count']==0
 assert guarded.audit['http_request_sent']is True and guarded.audit['http_request_count']==1
 assert audit['record_count']==2 and value[0]['numeric_comparability_verified']is True


def saved_report(storage):
 from datetime import datetime,timezone
 import json,time
 from report_analysis_evidence import capture_analysis_evidence
 from report_persistence import report_bundle_keys_for_filename
 filename='2412_TW_v1_report_20261027_152000.html';keys=report_bundle_keys_for_filename(filename);epoch=time.time()-3*86400
 old_audits=[{'source':'market_data','provider':'original market','status':'success','record_count':1,
   'fetch_id':'original','fetched_at_epoch':epoch,'fetched_at':datetime.fromtimestamp(epoch,timezone.utc).isoformat(),'cache_hit':False,'stale':True},
  {'source':'dynamic_peer_metrics','provider':'FinMind/yfinance','status':'unavailable','record_count':0,'fetch_id':'original','fetched_at_epoch':epoch}]
 data=context();data['source_audit']=deepcopy(old_audits)
 snapshot={'ticker':'2412.TW','company_name':data['company_name'],'pipeline':'v1','generated_at':datetime.fromtimestamp(epoch,timezone.utc).isoformat(),'data':data,'source_audit':old_audits}
 for key in('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance','analysis_completeness'):snapshot[key]={'original':key}
 snapshot['analysis_evidence']=capture_analysis_evidence({'data':data},generated_at=snapshot['generated_at'])
 storage.save_report(keys.html_key,b'<html>original conclusions preserved</html>',content_type='text/html')
 storage.save_report(keys.md_key,b'original conclusions preserved',content_type='text/markdown')
 storage.save_report(keys.data_key,json.dumps(snapshot).encode(),content_type='application/json')
 return filename,keys,snapshot


def test_public_source_refresh_preserves_original_claims_gates_and_core_with_normal_cache(monkeypatch,tmp_path):
 import json
 from storage.report_storage import InMemoryStorage
 from report_refresh_service import refresh_report_data_snapshot
 metrics_harness(monkeypatch);store=InMemoryStorage();filename,keys,old=saved_report(store);svc=service();requests=[];original=svc.fetch_source_async
 async def capture(request,*a,**kw):requests.append(request);return await original(request,*a,**kw)
 monkeypatch.setattr(svc,'fetch_source_async',capture)
 response=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=store,refresh_service=svc,source='dynamic_peer_metrics',return_refreshed_data=True))
 updated=json.loads(store.get_report(keys.data_key).content)
 assert len(updated['data']['dynamic_peer_metrics'])==2 and len(requests)==1 and requests[0].options.force_refresh is False
 for k in('current_price','revenue_history','peer_discovery_results','company_identity','company_name','industry'):assert updated['data'][k]==old['data'][k]
 for k in('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance','analysis_completeness'):assert updated[k]==old[k]
 assert next(a for a in updated['source_audit']if a['source']=='market_data')==old['source_audit'][0]
 assert store.get_report(keys.html_key).content==b'<html>original conclusions preserved</html>'
 assert store.get_report(keys.md_key).content==b'original conclusions preserved'
 assert response['analysis_text_stale']is True and response['refresh_sources']==['dynamic_peer_metrics']


def test_failed_original_binding_keeps_saved_report_bytes_and_failed_audit(monkeypatch,tmp_path):
 from storage.report_storage import InMemoryStorage
 from report_refresh_service import refresh_report_data_snapshot
 from ncc_peer_source_refresh import guard_ncc_result
 import ncc_peer_source_refresh as consumer
 from test_report_refresh_acquisition_audit import init_db,events
 init_db();metrics_harness(monkeypatch);store=InMemoryStorage();filename,keys,_=saved_report(store);before={k:store.get_report(k).content for k in(keys.html_key,keys.md_key,keys.data_key)}
 monkeypatch.setattr(consumer,'verified_candidates',lambda *a,**kw:False)
 with pytest.raises(HTTPException)as error:asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=store,refresh_service=service(),source='dynamic_peer_metrics'))
 assert error.value.status_code==502 and all(store.get_report(k).content==v for k,v in before.items())
 assert any(r['source']=='dynamic_peer_metrics'and r['record_count']==0 and r['status']=='error'for r in events())
