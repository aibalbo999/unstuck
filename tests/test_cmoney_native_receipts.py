"""Native forum transport is separate from admitted post records and cache hits."""
import hashlib
import json
import pytest
import provider_sla
from provider_correlation import correlation_scope
from data_fetch.market_sources import cmoney_stock_posts as module

URL=module.FINANCE_URL.format(ticker='2356')
MARKER=b'\nSTOCK_AGENT_CURL_META:'


def transport(monkeypatch, *, code=200, rc=0, error=None, body=b'<html>client shell</html>', metadata=None, started=True):
 events=[];calls=[]
 meta={'http_code':code,'url_effective':URL,'num_redirects':0,'size_download':len(body)}
 meta.update(metadata or {})
 def collect(argv,deadline,**kwargs):
  calls.append((argv,kwargs))
  return {'body':body,'headers':f'HTTP/2 {code}\r\nContent-Type: text/html\r\n\r\n'.encode(),
          'metadata':MARKER+json.dumps(meta).encode()+b'\n','process_started':started},rc,error
 monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
 monkeypatch.setattr(module,'collect_capped_process',collect)
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 return events,calls,body


def test_native_shell_get_is_observed_but_never_a_parsed_acquisition(monkeypatch):
 events,calls,body=transport(monkeypatch)
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='forum-fetch'):
  assert module._download(URL) is body
 assert len(calls)==1 and len(events)==1
 e=events[0]
 assert e['source']=='social_sentiment' and e['record_count']==0
 assert e['http_status']==200 and e['http_request_sent'] is True
 assert e['event_kind']=='http_transport_receipt'
 assert e['selection_policy']=='transport-receipt-only:v1'
 assert e['response_sha256']==hashlib.sha256(body).hexdigest()
 assert calls[0][1]['headers'] is True
 assert '--max-redirs' in calls[0][0] and '--retry' in calls[0][0]
 # An observed HTTP 200 shell still cannot produce a single post.
 assert module.parse_finance_listing(body,'2356')==('',[])


@pytest.mark.parametrize('code',[403,429,503,504])
def test_received_refusal_is_recorded_and_existing_failure_preserved(monkeypatch,code):
 events,calls,_=transport(monkeypatch,code=code,rc=22,body=b'access denied')
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='forum-fetch'):
  with pytest.raises(RuntimeError,match='forum HTTP response unavailable'):
   module._download(URL)
 assert len(calls)==len(events)==1
 assert events[0]['status']=='error' and events[0]['http_status']==code
 assert events[0]['record_count']==0


@pytest.mark.parametrize('change',[
 {'metadata':{'http_code':0}},
 {'metadata':{'url_effective':'https://other.example/'}},
 {'metadata':{'num_redirects':1}},
 {'metadata':{'size_download':1}},
 {'metadata':{'http_code':True}},
 {'started':False},
 {'error':'timeout','rc':28},
 {'error':'response_too_large','rc':63},
])
def test_unknown_partial_redirect_or_mismatched_transport_is_not_native_proof(monkeypatch,change):
 events,_,_=transport(monkeypatch,**change)
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='forum-fetch'):
  try:module._download(URL)
  except RuntimeError:pass
 assert not events


@pytest.mark.parametrize('context',[{}, {'ticker':'2356.TW'},
 {'ticker':'1101.TW','fetch_id':'forum-fetch'}, {'ticker':'AAPL','fetch_id':'forum-fetch'}])
def test_missing_or_wrong_instrument_correlation_is_not_native_proof(monkeypatch,context):
 events,_,body=transport(monkeypatch)
 with correlation_scope(replace=True,**context):assert module._download(URL) is body
 assert not events


def test_observer_write_failure_does_not_replace_original_result(monkeypatch):
 _,calls,body=transport(monkeypatch)
 def fail(*a):raise OSError('audit store unavailable')
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',fail)
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='forum-fetch'):
  assert module._download(URL) is body
 assert len(calls)==1


def test_cache_without_downloader_has_no_native_receipt(monkeypatch):
 from data_fetch.agent_context_providers import SocialSentimentProvider
 from data_fetch.types import FetchRequest,ProviderResult
 import shared_provider_cache
 events=[]
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:(
  {'source':'social_sentiment','provider':SocialSentimentProvider.name,'status':'success',
   'value':{'sample_count':1},'audit':{'cache_hit':False}},
  {'cache_hit':True,'stale':False,'fetched_at_epoch':1}))
 monkeypatch.setattr(module,'_download',lambda *a,**k:pytest.fail('cache must not download'))
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='cached-forum'):
  result=SocialSentimentProvider().fetch(FetchRequest.from_ticker('2356.TW',force_refresh=False))
 assert result.audit['cache_hit'] is True and not events


def test_persisted_receipt_keeps_transport_proof_without_acquisition_inflation(monkeypatch,tmp_path):
 import sqlite3,time
 from provider_acquisition import project_acquisition_events
 writer=provider_sla.record_source_audit_entries
 _,_,_=transport(monkeypatch)
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',writer)
 monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'receipts.sqlite3'))
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='forum-native'):
  module._download(URL)
 c=sqlite3.connect(tmp_path/'receipts.sqlite3');c.row_factory=sqlite3.Row
 rows=[dict(r)for r in c.execute('select * from provider_sla_events')]
 assert len(rows)==1
 d=json.loads(rows[0]['details_json'])
 assert d['component_statuses']['finance_listing']['http_status']==200
 assert 'client shell' not in rows[0]['details_json']
 assert c.execute('select count(*) from provider_sla_stats').fetchone()[0]==0
 source,=project_acquisition_events(rows,window='last_24h',now=time.time())['sources']
 assert source['http_attempt_count']==1
 assert source['fetch_attempts']==0 and source['fetched_count']==0


@pytest.mark.parametrize('headers,metadata',[
 (b'HTTP/1.1 200 Connection established\r\n\r\n',b'\nSTOCK_AGENT_CURL_META:{"http_code":0}\n'),
 (b'HTTP/2 200\r\n\r\n',b'no curl metadata'),
 (b'HTTP/2 200\r\n\r\n',b'\nSTOCK_AGENT_CURL_META:[]\n'),
])
def test_connect_header_or_malformed_metadata_cannot_create_receipt(monkeypatch,headers,metadata):
 events=[]
 monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 monkeypatch.setattr(module,'collect_capped_process',lambda *a,**k:(
  {'body':b'x','headers':headers,'metadata':metadata,'process_started':True},0,None))
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='bad-meta'):
  assert module._download(URL)==b'x'
 assert not events
