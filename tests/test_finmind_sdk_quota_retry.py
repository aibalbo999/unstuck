"""Real installed SDK decoding under an isolated HTTP seam; no live requests."""
import asyncio
import json

import pytest
import requests
from FinMind.data.finmind_api import FinMindApi

import provider_resilience as resilience
import provider_throttle as throttle
from source_audit import audited_fetch,audited_fetch_async

MSG='Requests reach the upper limit. https://finmindtrade.com/'
ERROR='FinMind API unexpected response: '+MSG
PROVIDER='FinMind TaiwanStockMonthRevenue'


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    resilience.clear_provider_circuits();throttle.clear_provider_throttles()
    monkeypatch.setenv('PROVIDER_RETRY_ATTEMPTS','3')
    monkeypatch.setenv('PROVIDER_RETRY_BACKOFF_SECONDS','0')
    monkeypatch.setenv('PROVIDER_RETRY_JITTER_SECONDS','0')
    monkeypatch.setenv('PROVIDER_CIRCUIT_BREAKER_THRESHOLD','10')
    monkeypatch.setenv('PROVIDER_RATE_LIMIT_MIN_INTERVAL_SECONDS','0')
    monkeypatch.setenv('PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS','30')
    yield
    resilience.clear_provider_circuits();throttle.clear_provider_throttles()
    cache_store.reset_cache_store_for_tests()


def response(payload,status=200):
    value=requests.Response();value.status_code=status;value._content=json.dumps(payload).encode();return value


def sdk_seam(monkeypatch,payload):
    import FinMind.data.finmind_api as sdk
    calls=[];body=[payload];api=FinMindApi()
    def get(*a,**k):calls.append(1);return response(body[0])
    monkeypatch.setattr(sdk,'request_get',get)
    def callback():return api.get_data(dataset='TaiwanStockMonthRevenue',data_id='2330',start_date='2026-01-01').to_dict('records')
    return calls,body,callback


@pytest.mark.parametrize('async_mode',[False,True])
def test_real_sdk_quota_is_one_failure_then_local_cooldown_and_normal_recovery(monkeypatch,async_mode):
    calls,body,callback=sdk_seam(monkeypatch,{'status':402,'msg':MSG});clock=[1000.]
    monkeypatch.setattr(throttle.time,'time',lambda:clock[0])
    async def async_callback():return callback()
    def run():return asyncio.run(audited_fetch_async('monthly_revenue',PROVIDER,async_callback,default=[]))if async_mode else audited_fetch('monthly_revenue',PROVIDER,callback,default=[])
    failed=run();assert failed['value']==[] and failed['audit']['status']=='error'
    assert failed['audit']['error_kind']=='Exception'and failed['audit']['message']==ERROR
    assert len(calls)==len(failed['audit']['provider_attempts'])==1
    assert 'http_status'not in failed['audit'] and 'http_request_sent'not in failed['audit']
    assert throttle.provider_throttle_state(PROVIDER)['cooldown_until']==1030.
    blocked=run();assert len(calls)==1 and blocked['audit']['status']=='unavailable'
    assert blocked['audit']['error_kind']=='ProviderRateLimitOpenError'and blocked['audit']['http_request_sent']is False
    other=audited_fetch('monthly_revenue','different-provider',lambda:['available'],default=[])
    assert other['audit']['status']=='success'
    clock[0]+=31.;body[0]={'data':[{'revenue':123}]}
    recovered=run();assert recovered['value']==[{'revenue':123}] and recovered['audit']['status']=='success'and len(calls)==2


@pytest.mark.parametrize('payload',[{'msg':MSG},{'detail':MSG,'status':402}])
def test_supported_decoder_message_shapes_are_not_immediately_retried(monkeypatch,payload):
    calls,_,callback=sdk_seam(monkeypatch,payload)
    result=audited_fetch('monthly_revenue',PROVIDER,callback,default=[])
    assert len(calls)==1 and result['audit']['status']=='error'and throttle.provider_throttle_state(PROVIDER)['open']


@pytest.mark.parametrize('payload',[{'status':500,'msg':MSG},{'status':True,'msg':MSG},
                                  {'status':'402','msg':MSG},{'status':402,'msg':'Temporary upstream failure'},
                                  {'status':402,'msg':MSG+' extra text'}])
def test_ambiguous_or_other_sdk_errors_keep_existing_retry_policy(monkeypatch,payload):
    calls,_,callback=sdk_seam(monkeypatch,payload)
    result=audited_fetch('monthly_revenue',PROVIDER,callback,default=[])
    assert len(calls)==3 and result['audit']['status']=='error'
    assert not throttle.provider_throttle_state(PROVIDER)['open']


def test_identical_text_outside_sdk_is_not_a_confirmed_quota(monkeypatch):
    calls=[]
    def callback():calls.append(1);raise Exception(ERROR)
    result=audited_fetch('monthly_revenue',PROVIDER,callback,default=[])
    assert len(calls)==3 and result['audit']['status']=='error'and not throttle.provider_throttle_state(PROVIDER)['open']


def test_zero_configured_cooldown_disables_wait_without_restoring_quota_retries(monkeypatch):
    monkeypatch.setenv('PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS','0')
    calls,_,callback=sdk_seam(monkeypatch,{'status':402,'msg':MSG})
    assert audited_fetch('monthly_revenue',PROVIDER,callback,default=[])['audit']['status']=='error'
    assert len(calls)==1 and not throttle.provider_throttle_state(PROVIDER)['open']


def test_monthly_real_sdk_quota_reaches_existing_official_fallback_once(monkeypatch):
    from test_official_monthly_revenue import native_csv
    from FinMind.data import DataLoader
    from data_fetch.types import FetchRequest
    from data_fetch.taiwan_providers import MonthlyRevenueProvider
    native=native_csv(monkeypatch);sdk_calls=[]
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader',DataLoader)
    def get(self,url,**kwargs):
        if url=='https://api.web.finmindtrade.com/v2/user_info':sdk_calls.append('user_info');return response({})
        assert url=='https://api.finmindtrade.com/api/v4/data';sdk_calls.append('data');return response({'status':402,'msg':MSG},402)
    monkeypatch.setattr(requests.Session,'get',get)
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status=='success'and len(native)==1 and sdk_calls==['user_info','data']
    assert result.audit['coverage_status']=='partial_two_adjacent_months'and result.audit['window_complete']is False
    primary=result.audit['related_entries'][0];assert primary['status']=='error'and primary['error_kind']=='Exception'
    assert len(primary['provider_attempts'])==1 and 'http_status'not in primary


@pytest.mark.parametrize('async_mode',[False,True])
@pytest.mark.parametrize('code',[402,403,429])
def test_confirmed_native_restricted_status_stops_before_immediate_retry(monkeypatch,async_mode,code):
    calls=[];original=requests.HTTPError('confirmed restricted response',response=response({},code))
    def callback():calls.append(1);raise original
    async def async_callback():return callback()
    with pytest.raises(requests.HTTPError)as caught:
        if async_mode:asyncio.run(resilience.call_provider_with_resilience_async(PROVIDER,async_callback))
        else:resilience.call_provider_with_resilience(PROVIDER,callback)
    assert caught.value is original and len(calls)==1
    assert throttle.provider_throttle_state(PROVIDER)['open']


@pytest.mark.parametrize('code',[500,403])
def test_unrestricted_native_status_retains_retry_and_configured_policy(monkeypatch,code):
    monkeypatch.setenv('PROVIDER_RATE_LIMIT_STATUS_CODES','429');calls=[]
    def callback():calls.append(1);raise requests.HTTPError('other response',response=response({},code))
    with pytest.raises(requests.HTTPError):resilience.call_provider_with_resilience(PROVIDER,callback)
    assert len(calls)==3 and not throttle.provider_throttle_state(PROVIDER)['open']
