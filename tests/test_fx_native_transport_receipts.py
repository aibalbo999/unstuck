"""Native FX HTTP is distinct from parsed quotes, shared cache and source truth."""
import httpx
import pytest
import provider_sla
from provider_correlation import correlation_scope,source_operation

URL='https://rate.bot.com.tw/xrt/flcsv/0/day'
OWNER=('taiwan_open_data','Taiwan Open Data (Exchange Rates)')

def setup(monkeypatch):
    events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows));return events

def receive(*,url=URL,status=200,method='GET',cached=False,native=True,request_url=URL,stream=False):
    from fx_transport_receipts import observe_response
    response=httpx.Response(status,request=httpx.Request(method,url),stream=httpx.ByteStream(b'private-fx-body')) if stream else httpx.Response(status,content=b'private-fx-body',request=httpx.Request(method,url))
    response.from_cache=cached
    observe_response(response,request_url=request_url,native_call=native)
    return response

def test_native_response_keeps_root_operation_and_never_implies_parsed_success(monkeypatch):
    events=setup(monkeypatch)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='fetch-1'):
        with source_operation(*OWNER):response=receive()
    assert len(events)==1 and response.content==b'private-fx-body'
    row=events[0];assert row['source']=='taiwan_open_data' and row['fetch_id']=='fetch-1'
    assert row['operation_id'] and row['record_count']==0 and row['http_request_sent'] is True
    assert 'private-fx-body' not in str(events)

@pytest.mark.parametrize('options',[{'cached':True},{'native':False},{'method':'POST'},{'stream':True},
    {'url':'https://evil.example/xrt/flcsv/0/day'},{'url':URL+'?token=private-key'},
    {'request_url':'https://other.example/not-bound'}])
def test_unknown_response_cache_or_non_native_is_not_outward_sample(monkeypatch,options):
    events=setup(monkeypatch)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='f'):
        with source_operation(*OWNER):receive(**options)
    assert not events

@pytest.mark.parametrize('owner',[('macro_indicators','FRED'),('taiwan_open_data','wrong')])
def test_wrong_owner_cannot_relabel_response(monkeypatch,owner):
    events=setup(monkeypatch)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='f'):
        with source_operation(*owner):receive()
    assert not events

@pytest.mark.parametrize('status',[429,503])
def test_native_error_stays_error_with_zero_parsed_records(monkeypatch,status):
    events=setup(monkeypatch)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='f'):
        with source_operation(*OWNER):receive(status=status)
    assert len(events)==1 and events[0]['status']=='error' and events[0]['record_count']==0

def test_no_active_ticker_operation_refuses_receipt(monkeypatch):
    events=setup(monkeypatch);receive();assert not events


def test_http_status_exception_is_recorded_and_reraised_unchanged(monkeypatch):
    from fx_transport_receipts import native_get
    events=setup(monkeypatch)
    response=httpx.Response(429,content=b'private-error',request=httpx.Request('GET',URL))
    error=httpx.HTTPStatusError('quota',request=response.request,response=response)
    def fail(*a,**kw):raise error
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='f'):
        with source_operation(*OWNER):
            with pytest.raises(httpx.HTTPStatusError)as caught:native_get(fail,URL)
    assert caught.value is error and len(events)==1 and events[0]['http_status']==429
    assert events[0]['status']=='error' and 'private-error' not in str(events)


def test_native_get_returns_same_response_and_no_duplicate_receipt(monkeypatch):
    from fx_transport_receipts import native_get
    events=setup(monkeypatch);response=httpx.Response(200,content=b'body',request=httpx.Request('GET',URL))
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='f'):
        with source_operation(*OWNER):assert native_get(lambda *a,**kw:response,URL)is response
    assert len(events)==1


@pytest.mark.parametrize('cached',[False,True])
def test_provider_native_fetch_and_shared_cache_keep_distinct_samples(monkeypatch,cached):
    import shared_provider_cache
    import data_fetch.taiwan_open_data_provider as provider
    from data_fetch.types import FetchRequest
    from fx_transport_receipts import native_get
    from datetime import datetime,timezone
    events=setup(monkeypatch);calls=[];options={}
    def fetch():
        calls.append('native')
        response=httpx.Response(200,content=b'original',request=httpx.Request('GET',URL))
        native_get(lambda *a,**k:response,URL)
        return value()
    def value():return {'actual_provider':'Bank of Taiwan','status':'success','rates':{
        currency:{'buy':'1','sell':'2','as_of':datetime.now(timezone.utc).isoformat()} for currency in ['USD','EUR','JPY']}}
    def cache(key,fetcher,**kwargs):
        options.update(kwargs)
        return (value() if cached else fetcher()),{'cache_hit':cached,'stale':False}
    monkeypatch.setattr(provider,'_fetch_exchange_rates',fetch)
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',cache)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='root-fetch'):
        result=provider.TaiwanOpenDataProvider().fetch(FetchRequest('2356.TW'))
    assert options['use_cache']is True and options['freshness_seconds']==3600
    assert result.audit['cache_hit']is cached and result.audit['fetch_id']=='root-fetch'
    assert len(events)==(0 if cached else 1) and len(calls)==(0 if cached else 1)
    if events:assert events[0]['operation_id']==result.audit['operation_id']

@pytest.mark.parametrize('url',[
    'https://www.megabank.com.tw/api/client/ExchangeRate/GetRateData?sc_lang=zh-TW&sc_site=bank-zh-tw&dic_lang=zh-TW',
    'https://www.megabank.com.tw/api/client/ExchangeRate/GetCurrenciesData?sc_lang=zh-TW&sc_site=bank-zh-tw&dic_lang=zh-TW',
    'https://open.er-api.com/v6/latest/USD',
    'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXTAUS',
])
def test_existing_fallback_endpoints_have_exact_bound_receipts(monkeypatch,url):
    events=setup(monkeypatch)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='f'):
        with source_operation(*OWNER):receive(url=url,request_url=url)
    assert len(events)==1 and events[0]['source']=='taiwan_open_data'

@pytest.mark.parametrize('url',[
    URL+'?token=', 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10',
    'https://open.er-api.com/v6/latest/EUR',
    'https://www.megabank.com.tw/api/client/ExchangeRate/GetRateData?sc_lang=en-US',
])
def test_other_dataset_or_query_not_the_selected_fx_endpoint(monkeypatch,url):
    events=setup(monkeypatch)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='f'):
        with source_operation(*OWNER):receive(url=url,request_url=url)
    assert not events


def test_receipt_store_failure_does_not_change_native_response(monkeypatch):
    from fx_transport_receipts import native_get
    def broken(*a,**k):raise RuntimeError('audit unavailable')
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',broken)
    response=httpx.Response(200,content=b'original',request=httpx.Request('GET',URL))
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='f'):
        with source_operation(*OWNER):assert native_get(lambda *a,**k:response,URL)is response
