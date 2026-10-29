from types import SimpleNamespace
import pytest
import httpx
import macro_fetcher as module
import provider_sla
from provider_correlation import correlation_scope

PARAMS={'series_id':'DGS10','api_key':'PRIVATE_API_KEY','file_type':'json','limit':'10','sort_order':'desc'}

@pytest.mark.parametrize('session_mode',[True,False])
def test_existing_fred_get_has_secret_safe_native_receipt(monkeypatch,session_mode):
 from urllib.parse import urlencode
 events=[];calls=[];url=module.FRED_OBSERVATIONS_URL+'?'+urlencode(PARAMS)
 response=httpx.Response(200,content=b'{"observations":[]}',request=httpx.Request('GET',url))
 def get(*a,**kw):calls.append(1);return response
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows));monkeypatch.setattr(module,'sync_get',get)
 session=httpx.Client() if session_mode else None
 if session is not None:monkeypatch.setattr(session,'get',get)
 with correlation_scope(replace=True,ticker='1101.TW',fetch_id='macro-fetch'):
  assert module._fred_get(session,params=dict(PARAMS),timeout=15) is response
 assert len(calls)==1 and len(events)==1
 assert events[0]['source']=='macro_indicators' and events[0]['record_count']==0
 assert events[0]['http_status']==200 and events[0]['event_kind']=='http_transport_receipt'
 assert 'PRIVATE_API_KEY' not in str(events) and 'api_key' not in str(events)


@pytest.mark.parametrize('change',[
 {'url':'https://other.example/?series_id=DGS10'},
 {'url':module.FRED_OBSERVATIONS_URL+'?series_id=VIXCLS'},
 {'from_cache':True},{'status_code':None},
])
def test_ambiguous_cached_or_other_series_is_not_native_proof(monkeypatch,change):
 events=[];code=change.get('status_code',200);url=change.get('url',module.FRED_OBSERVATIONS_URL+'?series_id=DGS10')
 response=(httpx.Response(code,content=b'{}',request=httpx.Request('GET',url))
           if type(code) is int else SimpleNamespace(url=url,status_code=code,content=b'{}'))
 response.from_cache=change.get('from_cache',False)
 monkeypatch.setattr(module,'sync_get',lambda *a,**kw:response);monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 with correlation_scope(replace=True,ticker='1101.TW',fetch_id='macro-fetch'):assert module._fred_get(None,params=dict(PARAMS),timeout=15) is response
 assert not events


def test_real_fred_error_is_recorded_without_replacing_exception(monkeypatch):
 import httpx
 events=[];response=httpx.Response(429,request=httpx.Request('GET',module.FRED_OBSERVATIONS_URL+'?series_id=DGS10'))
 err=httpx.HTTPStatusError('original',request=response.request,response=response)
 def fail(*a,**kw):raise err
 monkeypatch.setattr(module,'sync_get',fail);monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 with correlation_scope(replace=True,ticker='1101.TW',fetch_id='macro-fetch'):
  with pytest.raises(httpx.HTTPStatusError) as caught:module._fred_get(None,params=dict(PARAMS),timeout=15)
 assert caught.value is err and len(events)==1 and events[0]['http_status']==429
 assert events[0]['status']=='error'


def test_persisted_receipt_keeps_series_identity_without_query_or_key(monkeypatch,tmp_path):
 import sqlite3,json
 monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'audit.sqlite3'))
 response=httpx.Response(200,content=b'{}',request=httpx.Request('GET',module.FRED_OBSERVATIONS_URL+'?series_id=DGS10&api_key=PRIVATE_API_KEY'))
 monkeypatch.setattr(module,'sync_get',lambda *a,**kw:response)
 with correlation_scope(replace=True,ticker='1101.TW',fetch_id='macro-fetch'):module._fred_get(None,params=dict(PARAMS),timeout=15)
 c=sqlite3.connect(tmp_path/'audit.sqlite3');rows=c.execute('select details_json from provider_sla_events').fetchall();assert len(rows)==1
 raw=rows[0][0];assert 'PRIVATE_API_KEY' not in raw and 'api_key' not in raw
 saved=json.loads(raw);assert saved['component_statuses']['DGS10']['series_id']=='DGS10'
 assert saved['component_statuses']['DGS10']['http_status']==200


def test_custom_session_cannot_certify_native_transport(monkeypatch):
 import httpx
 events=[];response=httpx.Response(200,content=b'{}',request=httpx.Request('GET',module.FRED_OBSERVATIONS_URL+'?series_id=DGS10'))
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 custom=SimpleNamespace(get=lambda *a,**kw:response)
 with correlation_scope(replace=True,ticker='1101.TW',fetch_id='macro-fetch'):assert module._fred_get(custom,params=dict(PARAMS),timeout=15) is response
 assert not events
