from types import SimpleNamespace
import pytest
from curl_cffi.requests import Session
from provider_correlation import correlation_scope
import provider_sla
from yfinance_transport_receipts import observe_session

@pytest.mark.parametrize('path',['/v8/finance/chart/2330.TW','/v10/finance/quoteSummary/2330.TW','/v7/finance/quote?symbols=2330.TW'])
def test_native_response_unchanged_and_secret_safe_receipt(monkeypatch,path):
 events=[];responses=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 def send(self,method,url,**kwargs):
  response=SimpleNamespace(url=url,status_code=200,content=b'secret-body');responses.append(response);return response
 monkeypatch.setattr(Session,'_request_once',send);session=Session();assert observe_session(session);observe_session(session)
 with correlation_scope(replace=True,ticker='2330.TW'):result=session._request_once('GET','https://query1.finance.yahoo.com'+path,headers={'Authorization':'secret-header'})
 assert result is responses[-1]and len(events)==1 and events[0]['record_count']==0 and 'secret'not in str(events)
 assert Session._request_once is send

@pytest.mark.parametrize('path',['/v1/test/getcrumb','/v8/finance/chart/9999.TW','/unknown'])
def test_non_data_and_other_symbols_are_not_samples(monkeypatch,path):
 events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 monkeypatch.setattr(Session,'_request_once',lambda self,method,url,**kw:SimpleNamespace(url=url,status_code=200,content=b'unchanged'))
 session=Session();observe_session(session)
 with correlation_scope(replace=True,ticker='2330.TW'):result=session._request_once('GET','https://query1.finance.yahoo.com'+path)
 assert result.content==b'unchanged'and not events


def test_network_exception_is_unchanged(monkeypatch):
 error=RuntimeError('unit-only')
 def fail(*a,**k):raise error
 monkeypatch.setattr(Session,'_request_once',fail);session=Session();observe_session(session)
 with pytest.raises(RuntimeError)as caught:session._request_once('GET','https://example.com')
 assert caught.value is error


@pytest.mark.parametrize('options',[{'stream':True},{'from_cache':True},{'wrong_host':True}])
def test_ambiguous_or_cached_responses_not_outward_samples(monkeypatch,options):
 events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 def send(self,method,url,params=None,stream=False):
  return SimpleNamespace(url='https://other.example/v8/finance/chart/2330.TW'if options.get('wrong_host')else url,status_code=200,content=b'body',from_cache=options.get('from_cache',False))
 monkeypatch.setattr(Session,'_request_once',send);session=Session();assert observe_session(session)
 with correlation_scope(replace=True,ticker='2330.TW'):
  response=session._request_once('GET','https://query1.finance.yahoo.com/v8/finance/chart/2330.TW',None,options.get('stream',False))
 assert response.content==b'body'and not events


def test_receipt_failure_does_not_change_response(monkeypatch):
 def failure(rows):raise RuntimeError('audit store unavailable')
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',failure)
 response=SimpleNamespace(url='https://query1.finance.yahoo.com/v8/finance/chart/2330.TW',status_code=200,content=b'body')
 monkeypatch.setattr(Session,'_request_once',lambda self,method,url,**kw:response)
 session=Session();assert observe_session(session)
 with correlation_scope(replace=True,ticker='2330.TW'):assert session._request_once('GET',response.url)is response


def test_market_provider_installs_observer_before_sdk_info(monkeypatch):
 import yfinance_transport_receipts as observer
 import data_fetch.market_sources.ticker_resolver as resolver
 calls=[]
 monkeypatch.setattr(observer,'observe_yfinance',lambda:calls.append('observer'))
 class Stock:
  @property
  def info(self):
   calls.append('info');return {'currentPrice':3}
 monkeypatch.setattr(resolver.yf,'Ticker',lambda ticker:Stock())
 stock,info,valid=resolver.MarketDataProvider().get_valid_info('2330.TW')
 assert calls==['observer','info']and valid and info['currentPrice']==3
