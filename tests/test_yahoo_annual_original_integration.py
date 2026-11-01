import time,json
import pytest
from test_yahoo_annual_originals import response,B
from provider_correlation import correlation_scope

def test_same_native_request_and_response_with_passive_original(monkeypatch):
 from curl_cffi.requests import Session
 import provider_sla
 import yfinance_transport_receipts as observer
 from official_response_evidence import read_response
 from provider_observation_details import _original_http_receipts
 r=response();before=r.content;events=[];calls=[]
 def send(self,method,url,**kwargs):calls.append((method,url));return r
 monkeypatch.setattr(Session,'_request_once',send)
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 session=Session();assert observer.observe_session(session)
 with correlation_scope(replace=True,ticker=B['ticker'],fetch_id=B['fetch_id']):
  with observer.observe_annual_statements(B['ticker'],B):returned=session._request_once('GET',r.url)
 assert returned is r and r.content==before and calls==[('GET',r.url)]
 assert len(events)==1 and events[0]['record_count']==0
 assert events[0]['selection_policy']=='transport-receipt-only:v1'
 proof=events[0]['raw_http_receipt'];assert read_response(proof)==before
 assert proof['financial_semantics_verified']is False
 assert 'private-test-value'not in json.dumps(events)
 assert len(_original_http_receipts(events[0]))==1

@pytest.mark.parametrize('failure',[429,504])
def test_error_stays_transport_error_without_archival(monkeypatch,failure):
 import provider_sla,official_response_evidence
 import yfinance_transport_receipts as observer
 r=response();r.status_code=failure;events=[]
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:pytest.fail('Error body must not be archived as original'))
 with correlation_scope(replace=True,ticker=B['ticker'],fetch_id=B['fetch_id']):
  with observer.observe_annual_statements(B['ticker'],B):observer._record('GET',r.url,None,r,time.monotonic(),False)
 assert len(events)==1 and events[0]['status']=='error'and events[0]['record_count']==0
 assert 'raw_http_receipt'not in events[0]


def test_persisted_telemetry_keeps_original_summary_not_private_raw_field():
 import sqlite3
 import provider_sla
 import yfinance_transport_receipts as observer
 r=response()
 with correlation_scope(replace=True,ticker=B['ticker'],fetch_id=B['fetch_id']):
  with observer.observe_annual_statements(B['ticker'],B):observer._record('GET',r.url,None,r,time.monotonic(),False)
 with sqlite3.connect(provider_sla.TASK_DB_PATH)as c:
  count,value=c.execute("select record_count,details_json from provider_sla_events where provider=? order by id desc limit 1",('yfinance annual statements native HTTP',)).fetchone()
 details=json.loads(value)
 assert len(details['original_http_receipts'])==1
 assert details['original_http_receipts'][0]['response_complete']is True
 assert count==0
 assert 'raw_http_receipt'not in details and 'private-test-value'not in value
