import requests,pytest
from types import SimpleNamespace
from provider_correlation import correlation_scope
from finmind_transport_receipts import observe_loader
import provider_sla

@pytest.fixture
def harness(monkeypatch):
 events=[];responses=[]
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 def send(self,request,*a,**k):
  response=requests.Response();response.status_code=200;response.request=request;response._content=b'secret-body';response._content_consumed=True;responses.append(response);return response
 monkeypatch.setattr(requests.Session,'send',send)
 session=requests.Session();loader=SimpleNamespace(_FinMindApi__session=session)
 observe_loader(loader)
 def run(url,method='GET'):
  request=requests.Request(method,url).prepare()
  with correlation_scope(replace=True,job_id='unit',ticker='2330.TW'):result=session.send(request)
  assert result is responses[-1]
  return result
 return loader,session,events,responses,run

@pytest.mark.parametrize('dataset,source',[('TaiwanStockMonthRevenue','monthly_revenue'),('TaiwanStockInstitutionalInvestorsBuySell','institutional_trading'),('TaiwanStockNews','recent_catalysts'),('TaiwanStockPER','pe_river_chart')])
def test_native_dataset_receipt_is_secret_safe_and_not_an_acquisition(harness,dataset,source):
 loader,session,events,responses,run=harness
 run('https://api.finmindtrade.com/api/v4/data?dataset='+dataset+'&data_id=2330&token=secret-query')
 assert len(events)==1 and events[0]['source']==source and events[0]['http_request_sent']is True
 assert events[0]['record_count']==0 and 'secret'not in str(events)
 observe_loader(loader);run('https://api.finmindtrade.com/api/v4/data?dataset='+dataset+'&data_id=2330')
 assert len(events)==2

@pytest.mark.parametrize('url,method',[('https://api.finmindtrade.com/api/v4/login','POST'),('https://example.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id=2330','GET'),('https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id=9999','GET'),('https://api.finmindtrade.com/api/v4/data?dataset=Unknown&data_id=2330','GET')])
def test_unknown_or_auth_paths_preserve_response_without_inventing_samples(harness,url,method):
 *_,events,responses,run=harness
 run(url,method);assert events==[]


def test_original_network_error_is_never_suppressed(monkeypatch):
 error=requests.Timeout('unit-only')
 def fail(self,*a,**k):raise error
 monkeypatch.setattr(requests.Session,'send',fail);session=requests.Session();observe_loader(SimpleNamespace(_FinMindApi__session=session))
 with pytest.raises(requests.Timeout)as caught:session.send(requests.Request('GET','https://example.com').prepare())
 assert caught.value is error


def test_custom_session_is_not_claimed_as_native():
 class Custom:
  def send(self,*a,**k):return 'unchanged'
 session=Custom();loader=SimpleNamespace(_FinMindApi__session=session)
 assert observe_loader(loader)is loader and session.send()=='unchanged'

@pytest.mark.parametrize('mode',['cache','stream','retry','redirect','no_context'])
def test_non_native_or_ambiguous_observation_does_not_claim_http(monkeypatch,mode):
 from urllib3.util.retry import Retry
 events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 def send(self,request,*a,**k):
  response=requests.Response();response.status_code=200;response.request=request.copy()if mode=='redirect'else request;response._content=b'bytes';response._content_consumed=mode!='stream';response.from_cache=mode=='cache';return response
 monkeypatch.setattr(requests.Session,'send',send);session=requests.Session()
 if mode=='retry':session.get_adapter('https://api.finmindtrade.com').max_retries=Retry(total=1)
 observe_loader(SimpleNamespace(_FinMindApi__session=session))
 request=requests.Request('GET','https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id=2330').prepare()
 with correlation_scope(replace=True,**({}if mode=='no_context'else{'ticker':'2330.TW'})):
  result=session.send(request)
 assert result._content==b'bytes'and not events


def test_telemetry_failure_does_not_change_native_result(monkeypatch):
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:(_ for _ in ()).throw(RuntimeError('unit-only')))
 def send(self,request,*a,**k):
  r=requests.Response();r.status_code=200;r.request=request;r._content=b'original';r._content_consumed=True;return r
 monkeypatch.setattr(requests.Session,'send',send);session=requests.Session();observe_loader(SimpleNamespace(_FinMindApi__session=session))
 with correlation_scope(replace=True,ticker='2330.TW'):
  result=session.send(requests.Request('GET','https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id=2330').prepare())
 assert result.content==b'original'and requests.Session.send is send


def test_loader_wrapper_preserves_constructor_and_does_not_patch_class(monkeypatch):
 from finmind_transport_receipts import observed_loader_class
 original=requests.Session.send
 class Loader:
  def __init__(self,arg,*,flag):self.arg=arg;self.flag=flag;self._FinMindApi__session=requests.Session()
 wrapped=observed_loader_class(Loader);value=wrapped('input',flag=True)
 assert isinstance(value,Loader)and value.arg=='input'and value.flag is True
 assert requests.Session.send is original
