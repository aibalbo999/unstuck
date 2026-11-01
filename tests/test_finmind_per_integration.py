import sys,json
from copy import deepcopy
from types import SimpleNamespace
import pandas as pd,pytest,requests
from provider_correlation import correlation_scope

@pytest.fixture
def native(monkeypatch,tmp_path):
 from settings import storage
 import provider_sla
 from finmind_transport_receipts import observed_loader_class
 from data_fetch.market_sources import valuation
 monkeypatch.setattr(storage,'CACHE_DIR',str(tmp_path/'archive'))
 rows=[{'date':f'2026-10-{i:02d}','stock_id':'6409','dividend_yield':1.2,'PER':float(10+i),'PBR':3.4}for i in range(1,29)]
 events=[];state={'rows':rows,'calls':0,'tamper':False,'status':200,'cache':False,'archive_fail':False}
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda e:events.extend(deepcopy(e)))
 def send(self,request,*a,**kw):
  state['calls']+=1;r=requests.Response();r.request=request;r.url=request.url;r.status_code=state['status'];r._content_consumed=True;r.from_cache=state['cache'];r._content=json.dumps({'msg':'success','status':200,'data':state['rows']}).encode();return r
 monkeypatch.setattr(requests.Session,'send',send)
 class Loader:
  def __init__(self):self._FinMindApi__session=requests.Session()
  def taiwan_stock_per_pbr(self,stock_id,start_date,timeout=None):
   r=self._FinMindApi__session.get('https://api.finmindtrade.com/api/v4/data',params={'dataset':'TaiwanStockPER','data_id':stock_id,'stock_id':'','end_date':'','start_date':start_date,'token':'private-credential'},timeout=timeout)
   r.raise_for_status();f=pd.DataFrame(r.json()['data'])
   if state['tamper']:f.loc[0,'PER']+=1
   state['frame']=f;return f
 monkeypatch.setattr(valuation,'DataLoader',observed_loader_class(Loader))
 return events,state

def fetch():
 from source_audit import audited_fetch
 from data_fetch.market_sources.valuation import build_pe_river_chart_data
 with correlation_scope(replace=True,ticker='6409.TW',fetch_id='native-fixture'):
  return audited_fetch('pe_river_chart','FinMind/default multiples',build_pe_river_chart_data,('6409.TW',['2025'],[1],1e9))

def test_real_builder_and_sync_audit_emit_exact_proof(native):
 from provider_observation_details import observation_details
 events,state=native;r=fetch();p=r['audit'].get('sdk_per_quantile_lineage')
 assert p is not None,'Native PER body -> SDK -> result proof missing in actual sync audit'
 assert state['calls']==1 and r['value']['historical_sample_count']==28 and r['value']['eps_twd']==[1.0]
 assert p['coverage']=='historical_per_quantiles_only' and p['eps_and_bands_verified']is False
 assert observation_details(r['audit'])['sdk_per_quantile_lineage']==p
 assert events[0]['raw_http_receipt']['raw_response_sha256']==p['native_response_sha256']
 assert 'private-credential'not in str(p)+str(events)
 assert 'sdk_per_quantile_lineage'not in json.loads(json.dumps(r['value']))

@pytest.mark.parametrize('mode',['sdk_tamper','foreign_issuer','cached','wrong_schema','archive_failure'])
def test_optional_proof_failure_preserves_normal_result(native,monkeypatch,mode):
 events,state=native
 if mode=='sdk_tamper':state['tamper']=True
 elif mode=='foreign_issuer':state['rows'][0]['stock_id']='3653'
 elif mode=='cached':state['cache']=True
 elif mode=='wrong_schema':state['rows'][0]['unexpected']='field'
 else:
  import official_response_evidence
  monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:(_ for _ in ()).throw(OSError('isolated failure')))
 r=fetch();assert r['audit']['status']=='success' and r['value']['historical_quantiles_available']is True
 assert 'sdk_per_quantile_lineage'not in r['audit'] and state['calls']==1


def test_provider_path_exposes_same_bounded_proof(native):
 from data_fetch.enrichment_providers import PeRiverChartProvider
 from data_fetch.types import FetchRequest
 with correlation_scope(replace=True,ticker='6409.TW',fetch_id='provider-fixture'):
  r=PeRiverChartProvider().fetch(FetchRequest.from_ticker('6409.TW'),{'data':{'ticker':'6409.TW','years':['2025'],'net_income_history':[1],'shares_raw':1e9}})
 assert r.audit.get('sdk_per_quantile_lineage') is not None

def test_async_audit_preserves_same_source_context(native):
 import asyncio
 from source_audit import audited_fetch_async
 from data_fetch.market_sources.valuation import build_pe_river_chart_data
 async def acquire():return build_pe_river_chart_data('6409.TW',['2025'],[1],1e9)
 with correlation_scope(replace=True,ticker='6409.TW',fetch_id='async-fixture'):
  r=asyncio.run(audited_fetch_async('pe_river_chart','FinMind/default multiples',acquire))
 assert r['audit'].get('sdk_per_quantile_lineage')is not None

@pytest.mark.parametrize('mode',['cache','stale','owner','operation','attempt','hash','nan_time','wrong_scope','band_promotion','quantile_promotion','schema','count'])
def test_public_proof_projection_fails_closed_on_tampered_audit(native,mode):
 from provider_observation_details import observation_details
 r=fetch();a=deepcopy(r['audit']);p=a['sdk_per_quantile_lineage']
 if mode=='cache':a['cache_hit']=True
 elif mode=='stale':a['stale']=True
 elif mode=='owner':a['provider']='other'
 elif mode=='operation':a['operation_id']='other'
 elif mode=='attempt':a['provider_attempts']=[]
 elif mode=='hash':p['native_response_sha256']='bad'
 elif mode=='nan_time':p['native_received_at_epoch']=float('nan')
 elif mode=='wrong_scope':p['coverage']='all_financials'
 elif mode=='band_promotion':p['eps_and_bands_verified']=True
 elif mode=='quantile_promotion':p['multiples']=[1000.0]
 elif mode=='schema':p['schema']='other'
 else:p['sdk_row_count']=1
 assert 'sdk_per_quantile_lineage'not in observation_details(a)

def test_public_projection_drops_unknown_metadata(native):
 from provider_observation_details import observation_details
 r=fetch();r['audit']['sdk_per_quantile_lineage']['unexpected']='private-credential'
 projected=observation_details(r['audit']);assert 'sdk_per_quantile_lineage'in projected
 assert 'private-credential'not in str(projected)

@pytest.mark.parametrize('mode',['504','connection','read_timeout'])
def test_sdk_internal_retry_loop_cannot_resend_per_request(native,monkeypatch,mode):
 from FinMind.data import finmind_api as sdk
 from data_fetch.market_sources import valuation
 state=native[1];base=valuation.DataLoader
 monkeypatch.setitem(sdk.request_get.__globals__,'time',SimpleNamespace(sleep=lambda *_:None))
 class ActualSdkRequestLoop(base):
  def taiwan_stock_per_pbr(self,stock_id,start_date,timeout=None):
   self._FinMindApi__session.sdk_validation_timeout=timeout
   response=sdk.request_get(self._FinMindApi__session,'https://api.finmindtrade.com/api/v4/data',params={'dataset':'TaiwanStockPER','data_id':stock_id,'stock_id':'','start_date':start_date,'end_date':''},timeout=timeout)
   return pd.DataFrame(response.json()['data'])
 monkeypatch.setattr(valuation,'DataLoader',ActualSdkRequestLoop)
 if mode=='504':state['status']=504
 else:
  def fail(self,request,*a,**kw):
   state['calls']+=1;state['timeout']=kw.get('timeout')
   raise requests.ConnectionError('isolated')if mode=='connection'else requests.ReadTimeout('isolated')
  monkeypatch.setattr(requests.Session,'send',fail)
 result=fetch()
 assert state['calls']==1,'Installed SDK resent this PER source request'
 assert result['value']['valuation_basis']=='scenario_assumption'
 assert 'sdk_per_quantile_lineage'not in result['audit']
 if mode!='504':assert state['timeout']==12

@pytest.mark.parametrize('fail',[False,True])
def test_single_send_budget_restores_only_owned_session(native,monkeypatch,fail):
 from finmind_per_lineage import bounded_per_frame,PerTransportError
 from data_fetch.market_sources import valuation
 from provider_correlation import source_operation
 loader=valuation.DataLoader();session=loader._FinMindApi__session;original=session.send;global_send=requests.Session.send
 if fail:
  def loop(self,stock_id,start_date,timeout=None):
   req=requests.Request('GET','https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPER&data_id=6409&start_date=2021-10-01').prepare()
   self._FinMindApi__session.send(req,timeout=timeout)
   self._FinMindApi__session.send(req,timeout=timeout)
  monkeypatch.setattr(type(loader),'taiwan_stock_per_pbr',loop)
 with source_operation('pe_river_chart','FinMind/default multiples'):
  if fail:
   with pytest.raises(PerTransportError):bounded_per_frame(loader,stock_id='6409',start_date='2021-10-01')
  else:assert len(bounded_per_frame(loader,stock_id='6409',start_date='2021-10-01'))==28
 assert session.send is original and requests.Session.send is global_send
 assert native[1]['calls']==1
