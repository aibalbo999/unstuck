import json,pytest
from curl_cffi.requests import Response,Headers
from curl_cffi.requests.models import Request
from provider_correlation import correlation_scope,source_operation
from yahoo_public_original import capture_public_response

def response():
 url='https://query1.finance.yahoo.com/v8/finance/chart/3653.TW?range=2y&interval=1d&crumb=private'
 r=Response(request=Request(url,Headers({'Cookie':'private'}),'GET'));r.url=url
 r.content=json.dumps({'chart':{'result':[{'meta':{'symbol':'3653.TW'},'timestamp':[1],'indicators':{'quote':[{'close':[10.0],'volume':[100]}]}}],'error':None}}).encode();return r

def test_normal_market_radar_native_chart_retains_exact_original():
 from official_response_evidence import read_response
 r=response()
 with correlation_scope(replace=True,ticker='3653.TW',fetch_id='f'):
  with source_operation('market_data','yfinance radar'):
   proof=capture_public_response(r,source='market_data',symbol='3653.TW')
 assert proof and read_response(proof)==r.content
 assert '?' not in proof['source_url'] and 'private'not in json.dumps(proof)

@pytest.mark.parametrize('change',['owner','issuer','status','redirect','cache','summary','private_body','wrong_source'])
def test_radar_owner_only_allows_exact_native_issuer_public_chart(monkeypatch,change):
 import official_response_evidence
 monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**k:pytest.fail('must not archive'))
 r=response()
 if change=='issuer':r.content=r.content.replace(b'3653.TW',b'2330.TW')
 if change=='status':r.status_code=429
 if change=='redirect':r.redirect_count=1
 if change=='cache':r.from_cache=True
 if change=='summary':
  r.url=r.url.replace('/v8/finance/chart/','/v10/finance/quoteSummary/');r.request=Request(r.url,Headers(),'GET');r.content=json.dumps({'quoteSummary':{'result':[{'quoteType':{'symbol':'3653.TW'}}],'error':None}}).encode()
 if change=='private_body':r.content=r.content.replace(b'"meta": {',b'"credentials": "private", "meta": {')
 with correlation_scope(replace=True,ticker='3653.TW',fetch_id='f'):
  with source_operation('market_data','other'if change=='owner'else'yfinance radar'):
   assert capture_public_response(r,source='global_market_context'if change=='wrong_source'else'market_data',symbol='3653.TW')is None

def test_native_radar_transport_preserves_sdk_response_and_one_request(monkeypatch):
 from curl_cffi.requests import Session
 import provider_sla,yfinance_transport_receipts as observer
 events=[];calls=[];r=response()
 def native(self,method,url,**kwargs):calls.append(url);return r
 monkeypatch.setattr(Session,'_request_once',native)
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:events.extend(entries))
 session=Session();assert observer.observe_session(session)
 with correlation_scope(replace=True,ticker='3653.TW',fetch_id='f'):
  with source_operation('market_data','yfinance radar'):
   assert session._request_once('GET',r.url)is r
 assert calls==[r.url] and len(events)==1 and events[0]['record_count']==0
 assert events[0]['raw_http_receipt']['raw_response_sha256']==__import__('hashlib').sha256(r.content).hexdigest()
 assert 'private'not in json.dumps(events)
