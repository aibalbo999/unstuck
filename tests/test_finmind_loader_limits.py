"""Actual installed SDK at its owned Session.send seam; no live HTTP."""
import json
from copy import deepcopy
import pytest
import requests

@pytest.fixture
def native(monkeypatch):
    import FinMind.utility.request as transport
    import provider_sla,provider_throttle,provider_resilience,cache_store
    from cache_backends import InMemoryCache
    from FinMind.data import DataLoader
    from finmind_transport_receipts import observed_loader_class
    import external_data_twse as twse
    state={'calls':[],'responses':[],'code':200,'events':[]}
    monkeypatch.setattr(transport.time,'sleep',lambda *a:None)
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:state['events'].extend(deepcopy(entries)))
    monkeypatch.setenv('PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS','30')
    monkeypatch.setenv('PROVIDER_RATE_LIMIT_MIN_INTERVAL_SECONDS','0')
    monkeypatch.setenv('PROVIDER_RETRY_BACKOFF_SECONDS','0')
    monkeypatch.setenv('PROVIDER_RETRY_JITTER_SECONDS','0')
    cache_store.set_cache_backend(InMemoryCache());provider_resilience.clear_provider_circuits();provider_throttle.clear_provider_throttles()
    def send(self,request,**kwargs):
        state['calls'].append({'url':request.url,'kwargs':kwargs,'headers':dict(request.headers)})
        if state.get('error'):raise state['error']
        r=requests.Response();r.request=request;r.url=request.url
        r.status_code=200 if request.url=='https://api.web.finmindtrade.com/v2/user_info'else state['code'];r._content_consumed=True
        rows=[{'date':'2026-09-30','stock_id':'2330','type':'Revenue','value':100}]
        if state.get('complete_income'):
            rows=[{'date':d,'stock_id':'2330','type':'Revenue','value':100}for d in ('2025-12-31','2026-03-31','2026-06-30','2026-09-30')]
        r._content=json.dumps(state.get('body')or{'status':r.status_code,'msg':'success'if r.status_code==200 else 'unit gateway failure','data':rows}).encode()
        r.headers['Retry-After']='17';state['responses'].append(r);return r
    monkeypatch.setattr(requests.Session,'send',send)
    loader=observed_loader_class(DataLoader)
    monkeypatch.setattr(twse,'DataLoader',loader);monkeypatch.setattr(twse,'FINMIND_API_TOKEN','')
    yield loader,state,twse
    provider_resilience.clear_provider_circuits();provider_throttle.clear_provider_throttles();cache_store.reset_cache_store_for_tests()

def test_sdk_504_is_one_wire_attempt_not_two_nested_retry_loops(native):
    _,s,twse=native;s['code']=504
    assert twse._fetch_finmind_with_retry('2330')is None
    assert len([c for c in s['calls']if '/api/v4/data?'in c['url']])==1, 'Actual installed SDK and outer wrapper repeated the same failed data request'
    assert len(s['calls'])==2  # One unchanged constructor login and one data GET.

def test_successful_sdk_frame_and_request_identity_are_unchanged(native):
    import FinMind.data.finmind_api as sdk
    loader,s,_=native;original=sdk.request_get;session_request=requests.Session.request
    value=loader().taiwan_stock_financial_statement(stock_id='2330',start_date='2026-01-01')
    assert value.to_dict('records')==[{'date':'2026-09-30','stock_id':'2330','type':'Revenue','value':100}]
    assert len(s['calls'])==2 and all(c['kwargs']['timeout']==(3.,5.)for c in s['calls'])
    assert all(c['kwargs']['allow_redirects']is False for c in s['calls'])
    assert sdk.request_get is original and requests.Session.request is session_request

def test_existing_token_login_is_kept_but_has_a_finite_timeout(native):
    loader,s,twse=native;twse.FINMIND_API_TOKEN='unit-private-token';s['complete_income']=True
    value=twse._fetch_finmind_payload('2330')
    assert value and len(s['calls'])==4
    assert s['calls'][0]['url']=='https://api.web.finmindtrade.com/v2/user_info'
    assert all(c['kwargs']['timeout']==(3.,5.)for c in s['calls'])
    assert all(c['headers'].get('Authorization')=='Bearer unit-private-token'for c in s['calls'])

@pytest.mark.parametrize('code',[402,403,429,503,504,206,302])
def test_native_status_response_and_retry_after_are_preserved(native,code):
    from finmind_loader_limits import NativeSdkHTTPError
    loader,s,_=native;api=loader();s['code']=code
    with pytest.raises(NativeSdkHTTPError)as caught:
        api.taiwan_stock_financial_statement(stock_id='2330',start_date='2026-01-01')
    assert caught.value.response is s['responses'][-1]
    assert caught.value.response.status_code==code and caught.value.response.headers['Retry-After']=='17'
    assert 'unit gateway'not in str(caught.value)and 'password'not in str(caught.value)
    assert len(s['calls'])==2

@pytest.mark.parametrize('kind',[requests.ReadTimeout,requests.ConnectionError])
def test_actual_transport_failure_is_not_replaced_by_sdk_none_json_error(native,kind):
    from finmind_loader_limits import NativeSdkTransportError
    loader,s,_=native;api=loader();original=kind('private-url-and-token');s['error']=original
    with pytest.raises(NativeSdkTransportError)as caught:
        api.taiwan_stock_financial_statement(stock_id='2330',start_date='2026-01-01')
    assert caught.value.__cause__ is original and caught.value.response is None
    assert caught.value.http_status_observed is False
    assert 'private'not in str(caught.value)and len(s['calls'])==2

def test_configured_token_does_not_require_an_extra_anonymous_login(native):
    _,s,twse=native;twse.FINMIND_API_TOKEN='existing-unit-token';s['complete_income']=True
    assert twse._fetch_finmind_with_retry('2330')
    assert len(s['calls'])==4 and len([c for c in s['calls']if '/user_info'in c['url']])==1
    assert all(c['headers']['Authorization']=='Bearer existing-unit-token'for c in s['calls'])

def test_component_cooldown_does_not_disable_independent_existing_fallback(native,monkeypatch):
    import provider_throttle as throttle
    _,s,twse=native;s['code']=429;s['complete_income']=True;clock=[1000.]
    monkeypatch.setattr(throttle.time,'time',lambda:clock[0]);fallback=[];value={'source':'TWSE_OpenAPI','revenue_ttm_raw':100}
    monkeypatch.setattr(twse,'_fetch_twse_openapi_fallback',lambda symbol:fallback.append(symbol)or value)
    assert twse.fetch_twse_official_data('2330.TW')is value
    assert len(s['calls'])==2 and throttle.provider_throttle_state('FinMind SDK TWSE financials')['open']
    assert twse.fetch_twse_official_data('2330.TW')is value
    assert len(s['calls'])==2 and fallback==['2330','2330']
    clock[0]+=31.;s['code']=200
    assert twse.fetch_twse_official_data('2330.TW')['source']=='FinMind_TWSE'
    assert len(s['calls'])==6 and fallback==['2330','2330']

def test_shorter_existing_timeout_is_not_increased(native):
    loader,s,_=native;api=loader()
    api.get_data(dataset='TaiwanStockFinancialStatements',data_id='2330',start_date='2026-01-01',timeout=.5)
    assert s['calls'][-1]['kwargs']['timeout']==(.5,.5)

def test_existing_per_explicit_budget_is_preserved_without_leaking(native):
    from finmind_loader_limits import existing_per_socket_budget
    loader,s,_=native;api=loader()
    with existing_per_socket_budget():
        api.get_data(dataset='TaiwanStockFinancialStatements',data_id='2330',timeout=12)
        assert s['calls'][-1]['kwargs']['timeout']==12
    api.get_data(dataset='TaiwanStockFinancialStatements',data_id='2330',timeout=12)
    assert s['calls'][-1]['kwargs']['timeout']==(3.,5.)

@pytest.mark.parametrize('mode',['504','timeout'])
def test_existing_per_source_does_not_gain_outer_retries_with_real_limited_sdk(native,mode):
    from finmind_per_lineage import bounded_per_frame
    from provider_resilience import call_provider_with_resilience
    loader,s,_=native;api=loader()
    if mode=='504':s['code']=504
    else:s['error']=requests.ReadTimeout('unit')
    with pytest.raises(requests.RequestException)as caught:
        call_provider_with_resilience('unit-PER',lambda:bounded_per_frame(api,stock_id='2330',start_date='2026-01-01'))
    assert caught.value.retryable is False and len(s['calls'])==2

@pytest.mark.parametrize('timeout',[0,-1,True,float('nan'),float('inf')])
def test_invalid_timeout_is_rejected_before_data_http(native,timeout):
    loader,s,_=native;api=loader()
    with pytest.raises(ValueError):api.get_data(dataset='TaiwanStockFinancialStatements',data_id='2330',timeout=timeout)
    assert len(s['calls'])==1

def test_sdk_async_transport_is_not_silently_claimed_as_single_sync_attempt(native):
    from finmind_loader_limits import UnsupportedFinMindSdkError
    loader,s,_=native;api=loader()
    with pytest.raises(UnsupportedFinMindSdkError):api.get_data(dataset='TaiwanStockFinancialStatements',use_async=True)
    assert len(s['calls'])==1

def test_an_unwrapped_sdk_instance_and_global_functions_remain_unchanged(native):
    from FinMind.data import DataLoader
    import FinMind.data.finmind_api as sdk
    loader,s,_=native;original=sdk.request_get;original_request=requests.Session.request
    loader().taiwan_stock_financial_statement(stock_id='2330',start_date='2026-01-01')
    unwrapped=DataLoader();unwrapped.taiwan_stock_financial_statement(stock_id='2330',start_date='2026-01-01')
    assert s['calls'][-1]['kwargs']['timeout']is None and s['calls'][-1]['kwargs']['allow_redirects']is True
    assert sdk.request_get is original and requests.Session.request is original_request

def test_sdk_json_quota_keeps_actual_http200_and_decoder_signal(native):
    from finmind_loader_limits import NativeSdkHTTPError
    from provider_quota_signals import is_finmind_sdk_request_quota
    loader,s,_=native;api=loader();s['body']={'status':402,'msg':'Requests reach the upper limit. https://finmindtrade.com/'}
    with pytest.raises(Exception)as caught:
        api.taiwan_stock_financial_statement(stock_id='2330',start_date='2026-01-01')
    assert not isinstance(caught.value,NativeSdkHTTPError)and is_finmind_sdk_request_quota(caught.value)
    assert s['responses'][-1].status_code==200 and len(s['calls'])==2

def test_constructor_login_http_is_observed_without_private_account_content(native):
    from provider_correlation import correlation_scope,source_operation,provider_attempt
    from provider_acquisition import observation_kind
    from provider_observation_details import observation_details
    loader,s,_=native
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='unit-login'),source_operation('twse_official','FinMind TWSE official'),provider_attempt('FinMind TWSE official',1):
        loader(token='unit-private-token')
    assert len(s['events'])==1
    event=s['events'][0]
    assert event['provider']=='FinMind account native HTTP'and event['record_count']==0
    assert event['http_request_sent']is True and event['http_status']==200
    assert 'raw_http_receipt'not in event and 'response_sha256'not in event and 'unit-private-token'not in str(event)
    assert observation_kind({**event,'details':observation_details(event)})=='aggregate_count'

@pytest.mark.parametrize('kind',['seconds','date','malformed','unknown_status'])
def test_native_retry_after_is_a_minimum_without_inventing_status(native,monkeypatch,kind):
    from email.utils import formatdate
    import provider_throttle as throttle
    from finmind_loader_limits import NativeSdkHTTPError
    _,s,_=native;clock=[1000.];monkeypatch.setattr(throttle.time,'time',lambda:clock[0])
    r=requests.Response();r.status_code=429
    r.headers['Retry-After']='120'if kind in ('seconds','unknown_status')else formatdate(1120.,usegmt=True)if kind=='date'else'not-a-date'
    error=NativeSdkHTTPError('unit',response=r)
    if kind=='unknown_status':error.http_status_observed=False
    throttle.mark_rate_limit_cooldown('unit-retry-after',error)
    expected=0. if kind=='unknown_status'else 1030. if kind=='malformed'else 1120.
    assert throttle.provider_throttle_state('unit-retry-after')['cooldown_until']==expected
    assert r.status_code==429

def test_sdk_component_circuit_uses_existing_guard_and_keeps_fallback(native,monkeypatch):
    import provider_resilience as resilience
    _,s,twse=native;s['code']=503
    monkeypatch.setenv('PROVIDER_CIRCUIT_BREAKER_THRESHOLD','1')
    calls=[];value={'source':'TWSE_OpenAPI','revenue_ttm_raw':100}
    monkeypatch.setattr(twse,'_fetch_twse_openapi_fallback',lambda symbol:calls.append(symbol)or value)
    assert twse.fetch_twse_official_data('2330.TW')is value
    assert resilience.provider_circuit_state('FinMind SDK TWSE financials')['open']
    count=len(s['calls']);assert twse.fetch_twse_official_data('2330.TW')is value
    assert len(s['calls'])==count and len(calls)==2

def test_component_once_keeps_existing_attempt_identity_and_original_error(native):
    from provider_resilience import call_provider_component_once
    from provider_correlation import correlation_scope,source_operation,provider_attempt,current_correlation,current_audit_correlation
    original=RuntimeError('unit');before=[]
    def fail():before.append(current_correlation());raise original
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='unit'),source_operation('twse_official','FinMind TWSE official'),provider_attempt('FinMind TWSE official',1):
        identity=current_correlation()
        with pytest.raises(RuntimeError)as caught:call_provider_component_once('unit-component',fail)
        assert caught.value is original and before==[identity]
        assert current_correlation()==identity and current_audit_correlation()['provider_attempts']==[]

@pytest.mark.parametrize('code',[403,429])
@pytest.mark.parametrize('flag_location',['attribute','details'])
def test_explicit_unknown_status_does_not_reuse_an_earlier_response_for_cooldown(native,code,flag_location):
    import provider_throttle as throttle
    r=requests.Response();r.status_code=code;r.headers['Retry-After']='120'
    e=requests.HTTPError('unrelated earlier response',response=r)
    if flag_location=='attribute':e.http_status_observed=False
    else:e.details={'http_status_observed':False}
    assert not throttle.is_provider_rate_limit_error(e)
    throttle.mark_rate_limit_cooldown('unit-unknown',e)
    assert not throttle.provider_throttle_state('unit-unknown')['open']
