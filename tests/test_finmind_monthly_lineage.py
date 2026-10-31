import json
from copy import deepcopy
from pathlib import Path
import pandas as pd
import requests,pytest
from provider_correlation import correlation_scope

ROWS=[{'date':'2026-10-10','stock_id':'2330','country':'Taiwan','revenue':123456789,'revenue_month':9,'revenue_year':2026}]

@pytest.fixture
def native(monkeypatch,tmp_path):
 import cache_store,provider_sla
 from cache_backends import InMemoryCache
 from settings import storage
 from finmind_transport_receipts import observed_loader_class
 import time
 from datetime import datetime
 from zoneinfo import ZoneInfo
 from data_fetch.market_sources import finmind_monthly_revenue as monthly
 class FixedDatetime(datetime):
  @classmethod
  def now(cls,tz=None):
   value=cls(2026,10,31,14,0,0)
   return value if tz is None else value.replace(tzinfo=ZoneInfo('Asia/Taipei')).astimezone(tz)
 monkeypatch.setattr(time,'time',lambda:1793426400.)
 monkeypatch.setattr(monthly,'datetime',FixedDatetime)
 events=[];original_recorder=provider_sla.record_source_audit_entries;state={'original_recorder':original_recorder,'rows':deepcopy(ROWS),'status':200,'from_cache':False,'calls':0,'fail_archive':False}
 monkeypatch.setattr(storage,'CACHE_DIR',str(tmp_path/'archive'))
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda e:events.extend(deepcopy(e)))
 cache_store.set_cache_backend(InMemoryCache())
 def send(self,request,*a,**kw):
  state['calls']+=1;r=requests.Response();r.request=request;r.url=request.url;r.status_code=state['status'];r._content_consumed=True;r.from_cache=state['from_cache'];r._content=state.get('body_override') or json.dumps({'msg':'success','status':200,'data':state['rows']}).encode();return r
 monkeypatch.setattr(requests.Session,'send',send)
 class Loader:
  def __init__(self):self._FinMindApi__session=requests.Session()
  def taiwan_stock_month_revenue(self,stock_id,start_date):
   r=self._FinMindApi__session.get('https://api.finmindtrade.com/api/v4/data',params={'dataset':'TaiwanStockMonthRevenue','data_id':stock_id,'start_date':start_date,'token':state.get('token','secret-query')})
   r.raise_for_status();rows=r.json()['data'];frame=pd.DataFrame(rows)
   if state.get('cast_float'):frame['revenue']=frame['revenue'].astype(float)
   if state.get('tamper_frame'):frame.loc[0,'revenue']+=1
   state['frame']=frame;return frame
 yield observed_loader_class(Loader),events,state
 cache_store.reset_cache_store_for_tests()

def acquire(loader):
 from data_fetch.market_sources.finmind_monthly_revenue import fetch_monthly_records
 from source_audit import audited_fetch
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='unit-fetch'):
  return fetch_monthly_records('2330.TW',loader,audit_fetch=audited_fetch,force_refresh=False)

def test_same_native_body_is_bound_to_sdk_rows_and_formatted_output(native):
 loader,events,state=native;result=acquire(loader);lineage=result['audit'].get('sdk_payload_lineage')
 assert lineage is not None, 'Current nonempty monthly result has no verifiable raw-body to SDK to formatter lineage'
 assert lineage['schema']=='finmind-monthly-body-to-result:v1'
 assert lineage['sdk_row_count']==lineage['formatted_row_count']==1
 assert lineage['independent_primary_source_verified'] is False
 assert lineage['request_url_credentials_redacted'] is True
 assert result['value']==['2026年9月: NT$1.23億'] and state['calls']==1
 assert 'secret' not in str(events) and 'secret' not in str(lineage)
 before=deepcopy(state['frame']);pd.testing.assert_frame_equal(before,state['frame'])
 warm=acquire(loader);assert warm['value']==result['value'] and warm['audit']['cache_hit'] is True
 assert 'sdk_payload_lineage' not in warm['audit'] and state['calls']==1

@pytest.mark.parametrize('mode',['sdk_tamper','foreign_issuer','future_date','extra_secret_field','echoed_query_secret','cached_response','archive_failure'])
def test_ambiguous_or_cached_response_never_upgrades_lineage(native,monkeypatch,mode):
 loader,events,state=native
 if mode=='sdk_tamper':state['tamper_frame']=True
 elif mode=='foreign_issuer':state['rows'][0]['stock_id']='9999'
 elif mode=='future_date':state['rows'][0]['date']='2099-10-10'
 elif mode=='extra_secret_field':state['rows'][0]['token']='secret-query'
 elif mode=='echoed_query_secret':state['rows'][0]['country']='secret-query'
 elif mode=='cached_response':state['from_cache']=True
 else:
  import official_response_evidence
  monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:(_ for _ in ()).throw(OSError('unit archive failure')))
 result=acquire(loader)
 assert result['value'] and 'sdk_payload_lineage' not in result['audit']
 assert state['calls']==1 and 'secret-query' not in str(events)


def test_public_details_keep_binding_but_transport_is_still_not_acquisition(native):
 from provider_observation_details import observation_details
 from provider_acquisition import observation_kind
 loader,events,state=native;result=acquire(loader)
 details=observation_details(result['audit'])
 assert details['sdk_payload_lineage']==result['audit']['sdk_payload_lineage']
 receipt=events[0]['raw_http_receipt']
 assert 'token' not in receipt['source_url'] and 'secret-query' not in str(details)
 from official_response_evidence import read_response
 assert json.loads(read_response(receipt))['data']==ROWS
 raw={**events[0],'details':observation_details(events[0])}
 assert observation_kind(raw)=='aggregate_count' and raw['record_count']==0
 assert raw['details']['original_http_receipts'][0]['request_method']=='GET'
 assert 'http_request_sent' not in result['audit']  # no duplicate HTTP counter

@pytest.mark.parametrize('damage',['attempt','operation','cache','future','status_type','counter_type','date_order'])
def test_unbound_metadata_is_not_persisted_as_qualified_lineage(native,damage):
 from provider_observation_details import observation_details
 loader,events,state=native;result=acquire(loader);entry=deepcopy(result['audit']);meta=entry['sdk_payload_lineage']
 if damage=='attempt':entry['provider_attempts']=[]
 elif damage=='operation':meta['operation_id']='different-operation'
 elif damage=='cache':entry['cache_hit']=True
 elif damage=='future':meta['native_received_at_epoch']=999999999999
 elif damage=='status_type':meta['native_http_status']=200.0
 elif damage=='counter_type':entry['record_count']=True
 else:meta['query_end_date']='2020-01-01'
 assert 'sdk_payload_lineage' not in observation_details(entry)

@pytest.mark.parametrize('payload',[{'revenue':'1e1000000000'},{'revenue':True},{'country':'secret-query'},{'country':'秘密'}])
def test_unsafe_or_unbounded_payload_keeps_original_result_path(native,payload):
 loader,events,state=native
 if payload.get('revenue')=='1e1000000000':
  # Direct passive helper refuses the exponent before any fixed-point render.
  from finmind_monthly_lineage import _number
  with pytest.raises(ValueError):_number(payload['revenue'])
  return
 state['rows'][0].update(payload)
 if payload.get('country')=='秘密':state['token']='秘密'
 result=acquire(loader)
 assert 'sdk_payload_lineage' not in result['audit']


def test_observer_does_not_keep_an_sdk_loader_alive(native):
 import weakref,gc
 loader,events,state=native;instance=loader();session=instance._FinMindApi__session;reference=weakref.ref(instance)
 del instance;gc.collect()
 assert reference() is None and callable(session.send)

def test_public_detail_filter_discards_unrecognized_private_fields(native):
 from provider_observation_details import observation_details
 loader,events,state=native;result=acquire(loader);entry=deepcopy(result['audit'])
 entry['sdk_payload_lineage']['raw_response_path']='secret-query'
 entry['sdk_payload_lineage']['token']='secret-query'
 details=observation_details(entry)
 assert 'sdk_payload_lineage' in details and 'secret' not in str(details)


@pytest.mark.parametrize('mode',['large_integer_difference','sdk_float_loss','json_decimal_loss'])
def test_decimal_context_and_sdk_float_rounding_cannot_hide_changed_values(native,mode):
 loader,events,state=native
 if mode=='large_integer_difference':
  state['rows'][0]['revenue']=10**29+123456789;state['tamper_frame']=True
 elif mode=='sdk_float_loss':
  state['rows'][0]['revenue']=2**53+1;state['cast_float']=True
 else:
  state['body_override']=json.dumps({'msg':'success','status':200,'data':ROWS}).replace('123456789','9007199254740993.0').encode()
 result=acquire(loader)
 assert result['value'] and 'sdk_payload_lineage' not in result['audit']


def test_real_sqlite_roundtrip_keeps_same_attempt_lineage_without_double_counts(native,monkeypatch,tmp_path):
 import sqlite3,time
 import provider_sla
 from provider_acquisition import project_acquisition_events
 loader,events,state=native;database=tmp_path/'lineage.sqlite3'
 monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(database))
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',state['original_recorder'])
 result=acquire(loader);provider_sla.record_source_audit_entries([result['audit']])
 with sqlite3.connect(database) as db:
  db.row_factory=sqlite3.Row;rows=[dict(r) for r in db.execute('select * from provider_sla_events order by id')]
  stats=[tuple(r) for r in db.execute('select provider,attempts from provider_sla_stats')]
 assert len(rows)==2 and stats==[('FinMind TaiwanStockMonthRevenue',1)]
 transport=json.loads(rows[0]['details_json']);parsed=json.loads(rows[1]['details_json']);lineage=parsed['sdk_payload_lineage']
 assert transport['attempt_id']==lineage['transport_attempt_id']
 assert transport['operation_id']==parsed['operation_id']==lineage['operation_id']
 assert transport['response_sha256']==lineage['native_response_sha256']
 assert transport['original_http_receipts'][0]['response_sha256']==lineage['native_response_sha256']
 summary=project_acquisition_events(rows,window='last_24h',now=time.time())['sources'][0]
 assert summary['fetch_attempts']==summary['fetched_count']==summary['http_attempt_count']==1
 assert summary['aggregate_count']==1
