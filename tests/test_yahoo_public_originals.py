import json,pytest
from curl_cffi.requests import Response,Headers
from curl_cffi.requests.models import Request
from provider_correlation import correlation_scope,source_operation
from yahoo_public_original import capture_public_response

def response(symbol='2330.TW'):
 url='https://query1.finance.yahoo.com/v8/finance/chart/'+symbol+'?crumb=private-cookie-token'
 r=Response(request=Request(url,Headers({'Cookie':'private-cookie-token'}),'GET'));r.url=url
 r.content=json.dumps({'chart':{'result':[{'meta':{'symbol':symbol},'timestamp':[1],'indicators':{'quote':[{'close':[10.0]}]}}],'error':None}}).encode()
 return r

def test_owned_public_body_preserves_bytes_without_cookie_or_query():
 from official_response_evidence import read_response
 r=response()
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('market_data','yfinance'):
   proof=capture_public_response(r,source='market_data',symbol='2330.TW')
 assert proof['source_url']=='https://query1.finance.yahoo.com/v8/finance/chart/2330.TW'
 assert 'private-cookie-token'not in json.dumps(proof) and read_response(proof)==r.content
 assert proof['http_status_observed']and proof['response_complete']and proof['cache_hit']is False

@pytest.mark.parametrize('change',['owner','issuer','status','redirect','cached','stream','authorization','private_json','invalid_json'])
def test_ineligible_response_does_not_archive(monkeypatch,change):
 import official_response_evidence
 monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:pytest.fail('must not archive'))
 r=response('9999.TW'if change=='issuer'else'2330.TW')
 if change=='status':r.status_code=429
 if change=='redirect':r.redirect_count=1
 if change=='cached':r.from_cache=True
 if change=='stream':r.queue=object()
 if change=='authorization':r.request.headers['Authorization']='secret'
 if change=='private_json':
  payload=json.loads(r.content);payload['chart']['result'][0]['credentials']={'token':'secret'};r.content=json.dumps(payload).encode()
 if change=='invalid_json':r.content=b'invalid'
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('market_data','wrong'if change=='owner'else'yfinance'):
   assert capture_public_response(r,source='market_data',symbol='2330.TW')is None

def test_observed_native_session_still_calls_once_and_returns_same_response(monkeypatch):
 from curl_cffi.requests import Session
 import provider_sla
 import yfinance_transport_receipts as observer
 from provider_observation_details import _original_http_receipts
 calls=[];events=[];r=response()
 def send(self,method,url,**kwargs):calls.append(url);return r
 monkeypatch.setattr(Session,'_request_once',send);monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:events.extend(entries))
 session=Session();assert observer.observe_session(session)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('market_data','yfinance'):
   returned=session._request_once('GET',r.url)
 assert returned is r and calls==[r.url] and len(events)==1 and events[0]['record_count']==0
 safe=_original_http_receipts(events[0]);assert len(safe)==1 and safe[0]['response_complete']
 assert 'private-cookie-token'not in json.dumps(events)

@pytest.mark.parametrize('kind',['global','peer'])
def test_non_root_symbol_requires_existing_native_source_binding(monkeypatch,kind):
 import provider_sla
 import yfinance_transport_receipts as observer
 import time
 events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:events.extend(entries));monkeypatch.setattr(observer,'observe_yfinance',lambda:True)
 if kind=='global':
  from data_fetch.market_sources.global_context import TECH_PROXY_SYMBOLS
  symbol=TECH_PROXY_SYMBOLS[0][0];r=response(symbol);owner=('global_market_context','yfinance global context');scope=observer.observe_global_proxy
 else:
  symbol='6230.TW';r=response(symbol);r.url='https://query1.finance.yahoo.com/v10/finance/quoteSummary/'+symbol;r.request=Request(r.url,Headers(),'GET');r.content=json.dumps({'quoteSummary':{'result':[{'quoteType':{'symbol':symbol},'defaultKeyStatistics':{'trailingPE':None}}],'error':None}}).encode();owner=('dynamic_peer_metrics','FinMind/yfinance');scope=observer.observe_peer_metrics
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation(*owner):
   with scope(symbol):observer._record('GET',r.url,None,r,time.monotonic(),False)
 assert len(events)==1 and events[0]['source']==owner[0]
 assert events[0]['raw_http_receipt']['status']=='archived'and events[0]['record_count']==0

def test_archive_failure_keeps_original_sdk_result(monkeypatch):
 from curl_cffi.requests import Session
 import provider_sla,official_response_evidence
 import yfinance_transport_receipts as observer
 r=response();calls=[];events=[]
 def send(self,method,url,**kwargs):calls.append(1);return r
 def unavailable(*args,**kwargs):raise OSError('archive unavailable')
 monkeypatch.setattr(Session,'_request_once',send);monkeypatch.setattr(official_response_evidence,'archive_response',unavailable);monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:events.extend(entries))
 session=Session();observer.observe_session(session)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('market_data','yfinance'):
   assert session._request_once('GET',r.url)is r
 assert calls==[1] and len(events)==1 and 'raw_http_receipt'not in events[0]

@pytest.mark.parametrize('kind',['oversize','nonfinite','foreign_host','missing_owner_operation'])
def test_bounded_and_owned_originals_only(monkeypatch,kind):
 import official_response_evidence
 monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:pytest.fail('must not archive'))
 r=response()
 if kind=='oversize':r.content=b' '*(2_000_001)
 if kind=='nonfinite':r.content=r.content.replace(b'10.0',b'NaN')
 if kind=='foreign_host':r.url=r.url.replace('query1.finance.yahoo.com','other.example')
 if kind=='missing_owner_operation':
  with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
   assert capture_public_response(r,source='market_data',symbol='2330.TW')is None
 else:
  with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
   with source_operation('market_data','yfinance'):
    assert capture_public_response(r,source='market_data',symbol='2330.TW')is None

@pytest.mark.parametrize('symbol',['SPY','^VIX','^TNX','^TWII','CL=F','TWD=X','DX-Y.NYB'])
def test_existing_global_index_future_fx_identifiers_are_supported(symbol):
 from urllib.parse import quote
 r=response(symbol)
 r.url='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')
 r.request=Request(r.url,Headers(),'GET')
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('global_market_context','yfinance global context'):
   proof=capture_public_response(r,source='global_market_context',symbol=symbol)
 assert proof and proof['status']=='archived'
