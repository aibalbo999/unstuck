import sys,importlib.util,json
from pathlib import Path
import httpx,pytest
sys.path.insert(0,'/Volumes/X10 Pro Mac/stock-agent/backend')
from provider_correlation import correlation_scope,source_operation
D=Path(__file__).parent
import twse_credit_source as module

def response(**changes):
 return httpx.Response(changes.get('status',200),content=b'{"stat":"OK"}',request=httpx.Request(changes.get('method','GET'),changes.get('url',module.URL),headers=changes.get('headers',{})))

def test_native_margin_original_is_owned_and_complete(monkeypatch):
 import official_response_evidence
 seen=[]
 monkeypatch.setattr(official_response_evidence,'archive_response',lambda body,**kwargs:seen.append((body,kwargs))or{'status':'archived'})
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('chip_data','TDCC/TWSE/TPEx chip data'):
   out=module.capture_margin_original(response())
 assert out['http_status_observed'] and out['response_complete'] and out['cache_hit']is False
 assert len(seen)==1 and seen[0][0]==b'{"stat":"OK"}' and seen[0][1]['source_url']==module.URL

@pytest.mark.parametrize('change',[{'status':429},{'method':'POST'},{'url':'https://example.com/'},{'url':module.URL+'&token=secret'},{'headers':{'Authorization':'Bearer secret'}},{'headers':{'Cookie':'session=secret'}}])
def test_ineligible_original_is_not_archived(monkeypatch,change):
 import official_response_evidence
 def fail(*a,**kw):raise AssertionError('must not archive')
 monkeypatch.setattr(official_response_evidence,'archive_response',fail)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('chip_data','TDCC/TWSE/TPEx chip data'):
   assert module.capture_margin_original(response(**change))is None

def test_unowned_or_cached_response_is_not_new_http(monkeypatch):
 import official_response_evidence
 monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:pytest.fail('must not archive'))
 assert module.capture_margin_original(response())is None
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('chip_data','TDCC/TWSE/TPEx chip data'):
   r=response();r.extensions['from_cache']=True
   assert module.capture_margin_original(r)is None

def test_archive_error_does_not_change_source_result(monkeypatch):
 import official_response_evidence
 def fail(*a,**kw):raise OSError('archive unavailable')
 monkeypatch.setattr(official_response_evidence,'archive_response',fail)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('chip_data','TDCC/TWSE/TPEx chip data'):
   assert module.capture_margin_original(response())is None

def test_existing_parse_stays_before_original_capture(monkeypatch):
 import search_provider_runtime as runtime
 calls=[]
 monkeypatch.setattr(runtime,'cooldown_state',lambda key:None)
 monkeypatch.setattr(runtime,'remember_failure',lambda *a:{})
 monkeypatch.setattr(runtime,'record_observation',lambda *a,**kw:None)
 monkeypatch.setattr(module,'capture_margin_original',lambda r:pytest.fail('invalid parsed report must not archive'))
 with pytest.raises(ValueError):module._fetch_report(lambda *a,**kw:calls.append(1)or response(),15)
 assert calls==[1]

def test_shared_cache_keeps_original_receipt_and_acquisition_time(monkeypatch):
 import shared_provider_cache
 from test_twse_credit_source import dated_payload
 report=module._report(dated_payload());proof={'status':'archived','retrieved_at':123456.0,'raw_response_sha256':'a'*64};report['original_receipt']=proof
 monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**kw:(report,{'cache_hit':True,'fetched_at_epoch':123456.0}))
 def forbidden(*a,**kw):pytest.fail('cached result must not issue HTTP or create receipt')
 monkeypatch.setattr(module,'capture_margin_original',forbidden)
 out=module.fetch_twse_dated_margin('2330',http_get=forbidden)
 assert out['status']=='success' and out['margin_balance']==29707
 assert out['margin_cache_hit']is True and out['margin_fetched_at_epoch']==123456.0
 assert out['margin_original_receipt']==proof

def test_existing_parse_archives_exact_body_and_exposes_safe_observation(monkeypatch):
 import search_provider_runtime as runtime
 from official_response_evidence import read_response
 from provider_observation_details import _original_http_receipts
 from test_twse_credit_source import dated_payload
 entries=[];calls=[]
 monkeypatch.setattr(runtime,'cooldown_state',lambda key:None)
 monkeypatch.setattr(runtime,'record_source_audit_entries',lambda values:entries.extend(values))
 body=json.dumps(dated_payload(),ensure_ascii=False).encode('utf-8')
 r=httpx.Response(200,content=body,request=httpx.Request('GET',module.URL))
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='actual-f'):
  with source_operation('chip_data','TDCC/TWSE/TPEx chip data'):
   report=module._fetch_report(lambda *a,**kw:calls.append(1)or r,15)
 assert calls==[1] and report['as_of_date']=='2026-09-24'
 assert read_response(report['original_receipt'])==body
 assert len(entries)==1 and entries[0]['fetch_id']=='actual-f'
 safe=_original_http_receipts(entries[0]);assert len(safe)==1
 assert safe[0]['response_complete'] and safe[0]['http_status_observed']
 assert safe[0]['http_request_sent']is True and safe[0]['original_cache_hit']is False
 assert 'raw_response_path'not in safe[0] and 'body'not in safe[0]
