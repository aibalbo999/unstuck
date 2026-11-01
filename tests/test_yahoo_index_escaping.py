import json,time
from urllib.parse import quote
import pytest
from curl_cffi.requests import Response,Headers
from curl_cffi.requests.models import Request
from provider_correlation import correlation_scope,source_operation

@pytest.mark.parametrize('symbol',['^VIX','^TNX','^TWII'])
@pytest.mark.parametrize('reverse',[False,True])
def test_native_caret_escape_has_same_owned_symbol_original(monkeypatch,symbol,reverse):
 import provider_sla,yfinance_transport_receipts as observer
 events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:events.extend(entries));monkeypatch.setattr(observer,'observe_yfinance',lambda:True)
 raw='https://query1.finance.yahoo.com/v8/finance/chart/'+symbol
 encoded='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')
 sent,actual=(encoded,raw)if reverse else(raw,encoded)
 r=Response(request=Request(sent,Headers(),'GET'));r.url=actual;r.content=json.dumps({'chart':{'result':[{'meta':{'symbol':symbol},'timestamp':[1],'indicators':{'quote':[{'close':[10.0]}]}}],'error':None}}).encode()
 with correlation_scope(replace=True,ticker='2367.TW',fetch_id='f'):
  with source_operation('global_market_context','yfinance global context'):
   with observer.observe_global_proxy(symbol):observer._record('GET',sent,None,r,time.monotonic(),False)
 assert len(events)==1
 assert events[0]['source']=='global_market_context'and events[0]['record_count']==0
 proof=events[0]['raw_http_receipt'];assert proof['status']=='archived'
 from official_response_evidence import read_response
 assert read_response(proof)==r.content

@pytest.mark.parametrize('left,right',[
 ('/v8/finance/chart/^VIX','/v8/finance/chart/%5ETNX'),
 ('/v8/finance/chart/^VIX','/v8/finance/chart/%255EVIX'),
 ('/v8/finance/chart/^VIX','/v8/finance/chart/%5EVIX%2Fother'),
 ('/v8/finance/chart/^VIX','/v8/finance/chart/%5EVIX/'),
 ('/v8/finance/chart/^VIX','/v8/finance/chart/%5Evix'),
 ('/v8/finance/chart/^VIX','/v8/finance/quoteSummary/%5EVIX'),
 ('/v10/finance/quoteSummary/^VIX','/v10/finance/quoteSummary/%5EVIX'),
 ('/v8/finance/chart/2330.TW','/v8/finance/chart/%32%33%33%30.TW'),
 (None,None),
])
def test_equivalence_is_not_general_url_decoding(left,right):
 from yahoo_public_original import same_public_path
 assert same_public_path(left,right)is False

@pytest.mark.parametrize('kind',['redirect','wrong_host','wrong_symbol'])
def test_caret_encoding_keeps_original_source_and_redirect_gates(kind):
 from yahoo_public_original import capture_public_response
 raw='https://query1.finance.yahoo.com/v8/finance/chart/^VIX';actual=raw.replace('^','%5E')
 r=Response(request=Request(raw,Headers(),'GET'));r.url=actual
 r.content=json.dumps({'chart':{'result':[{'meta':{'symbol':'^VIX'},'indicators':{'quote':[{'close':[10.0]}]}}],'error':None}}).encode()
 if kind=='redirect':r.redirect_count=1
 if kind=='wrong_host':r.url=r.url.replace('query1.finance.yahoo.com','other.example')
 if kind=='wrong_symbol':r.content=r.content.replace(b'^VIX',b'^TNX')
 with correlation_scope(replace=True,ticker='2367.TW',fetch_id='f'):
  with source_operation('global_market_context','yfinance global context'):
   assert capture_public_response(r,source='global_market_context',symbol='^VIX')is None
