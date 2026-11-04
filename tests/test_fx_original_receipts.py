"""Existing anonymous bank downloads get originals, never extra data successes."""
from hashlib import sha256
from datetime import datetime,timezone
import httpx
import pytest
import provider_sla
from provider_correlation import correlation_scope,source_operation
import fx_transport_receipts as module
from data_fetch import taiwan_open_data_provider as fx
from data_fetch.types import FetchRequest
URL=fx.BOT_EXCHANGE_RATE_URL


def receive(monkeypatch,response,url=URL):
    events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    with correlation_scope(replace=True,ticker='1623.TW',fetch_id='fx-test'):
        with source_operation(*module.OWNER):
            same=module.native_get(lambda *a,**kw:response,url)
    assert same is response
    return events


@pytest.mark.parametrize('url',[
    URL,fx.ER_API_USD_URL,fx.FRED_TWD_USD_URL,
    'https://www.megabank.com.tw/api/client/ExchangeRate/GetRateData?sc_lang=zh-TW&sc_site=bank-zh-tw&dic_lang=zh-TW',
    'https://www.megabank.com.tw/api/client/ExchangeRate/GetCurrenciesData?sc_lang=zh-TW&sc_site=bank-zh-tw&dic_lang=zh-TW'])
def test_complete_download_replays_but_does_not_assert_parsed_quotes(monkeypatch,url):
    from official_response_evidence import read_response
    from provider_observation_details import observation_details
    body=b'body without any qualified quote';response=httpx.Response(200,content=body,request=httpx.Request('GET',url))
    events=receive(monkeypatch,response,url);assert len(events)==1
    event=events[0];proof=event['raw_http_receipt'];assert read_response(proof)==body
    assert proof['evidence_kind']=='decoded_complete_http_response_body'
    assert proof['http_status_observed'] is True and proof['response_complete'] is True
    assert proof['cache_hit'] is False and proof['request_method']=='GET'
    assert event['record_count']==0
    summary=observation_details(event)['original_http_receipts'][0]
    assert summary['response_sha256']==sha256(body).hexdigest() and summary['response_complete'] is True
    assert 'raw_response_path' not in str(summary) and body.decode() not in str(events)


@pytest.mark.parametrize('change',['cached_extension','cache_hit','authorization','proxy-authorization','cookie','partial','length','empty','redirect'])
def test_unqualified_http_response_never_gets_complete_original(monkeypatch,change):
    headers={};request_headers={};status=200;extensions={};body=b'[]'
    if change in {'authorization','proxy-authorization','cookie'}:request_headers[change]='secret'
    if change in {'cached_extension','cache_hit'}:extensions['from_cache' if change=='cached_extension' else 'cache_hit']=True
    if change=='partial':headers['content-range']='bytes 0-1/100';status=206
    if change=='length':headers['content-length']='100'
    if change=='empty':body=b''
    response=httpx.Response(status,content=body,headers=headers,request=httpx.Request('GET',URL,headers=request_headers),extensions=extensions,history=[httpx.Response(302)]if change=='redirect'else[])
    events=receive(monkeypatch,response)
    assert all('raw_http_receipt' not in row for row in events)
    if change!='empty':
        assert all(row.get('response_complete') is not True for row in events)
    else:
        assert all(row['record_count']==0 and row['response_bytes']==0 for row in events)


@pytest.mark.parametrize('failure',['exception','unavailable'])
def test_archive_failure_cannot_change_response_or_retry(monkeypatch,failure):
    import official_response_evidence
    def archive(*a,**kw):
        if failure=='exception':raise OSError('storage failure')
        return {'status':'unavailable'}
    monkeypatch.setattr(official_response_evidence,'archive_response',archive)
    response=httpx.Response(200,content=b'[]',request=httpx.Request('GET',URL))
    events=receive(monkeypatch,response)
    assert len(events)==1 and events[0]['http_status']==200 and 'raw_http_receipt' not in events[0]


def test_research_option_keeps_same_provider_result_without_audit_or_archive(monkeypatch):
    import official_response_evidence,shared_provider_cache
    events=[];archives=[];calls=[]
    monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:archives.append(1))
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    def fetch():
        response=httpx.Response(200,content=b'original',request=httpx.Request('GET',URL));calls.append(1)
        module.native_get(lambda *a,**kw:response,URL)
        return {'actual_provider':'Bank of Taiwan','status':'success','rates':{
            currency:{'buy':'1','sell':'2','as_of':datetime.now(timezone.utc).isoformat()}for currency in ('USD','EUR','JPY')}}
    monkeypatch.setattr(fx,'_fetch_exchange_rates',fetch)
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda key,fetcher,**kw:(fetcher(),{'cache_hit':False,'stale':False}))
    with correlation_scope(replace=True,ticker='1623.TW',fetch_id='research'):
        result=fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('1623.TW',record_provider_sla=False))
    assert result.status=='success' and len(calls)==1 and events==[] and archives==[]


def test_scope_restores_after_failure(monkeypatch):
    with pytest.raises(RuntimeError):
        with module.receipt_observation_scope(False):raise RuntimeError('provider failure')
    response=httpx.Response(200,content=b'[]',request=httpx.Request('GET',URL))
    assert len(receive(monkeypatch,response))==1


def test_compressed_response_archives_decoded_body_not_wire_length(monkeypatch):
    import gzip
    from official_response_evidence import read_response
    body=b'original JSON data '*40;compressed=gzip.compress(body)
    response=httpx.Response(200,content=compressed,headers={'content-encoding':'gzip','content-length':str(len(compressed))},request=httpx.Request('GET',URL))
    assert response.content==body
    events=receive(monkeypatch,response);proof=events[0]['raw_http_receipt']
    assert read_response(proof)==body and proof['raw_response_bytes']==len(body)
    assert proof['evidence_kind']=='decoded_complete_http_response_body'


@pytest.mark.parametrize('enabled',[True,False])
def test_existing_radar_plan_fetches_only_fx_and_honors_audit_option(monkeypatch,enabled):
    import asyncio,shared_provider_cache
    from types import SimpleNamespace
    import data_fetch.service as service
    events=[];requested=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    monkeypatch.setattr(service,'record_source_audit_entries',lambda rows:events.extend(rows))
    def fetch():
        response=httpx.Response(200,content=b'original',request=httpx.Request('GET',URL))
        module.native_get(lambda *a,**kw:response,URL)
        return {'actual_provider':'Bank of Taiwan','status':'success','rates':{
            currency:{'buy':'1','sell':'2','as_of':datetime.now(timezone.utc).isoformat()}for currency in ('USD','EUR','JPY')}}
    monkeypatch.setattr(fx,'_fetch_exchange_rates',fetch)
    def cache(key,fetcher,**kw):
        assert kw['use_cache'] is True
        return fetcher(),{'cache_hit':False,'stale':False}
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',cache)
    def provider(request,source):
        requested.append(source);assert source=='taiwan_open_data'
        return fx.TaiwanOpenDataProvider()
    app=service.StockDataService(registry=SimpleNamespace(first_provider=provider))
    result=asyncio.run(app.fetch_radar_async(FetchRequest.from_ticker('1623.TW',record_provider_sla=enabled),('taiwan_open_data',)))
    assert requested==['taiwan_open_data'] and len(result.source_audit)==1
    assert result.data['taiwan_open_data']['status']=='success'
    assert set(result.data['taiwan_open_data']['rates'])=={'USD','EUR','JPY'}
    assert len(events)==(2 if enabled else 0)
    if enabled:
        assert len({row['operation_id'] for row in events})==1
        assert [row['record_count']for row in events]==[0,3]


@pytest.mark.parametrize('status',[429,503,504])
def test_complete_error_response_is_not_misstated_as_truncated_or_parsed_success(monkeypatch,status):
    response=httpx.Response(status,content=b'complete error response',request=httpx.Request('GET',URL))
    events=receive(monkeypatch,response);assert len(events)==1
    event=events[0]
    assert event['response_complete'] is True and event['http_status']==status
    assert event['status']=='error' and event['record_count']==0 and 'raw_http_receipt' not in event


@pytest.mark.parametrize('status',[429,503,504])
def test_annual_complete_error_response_retains_same_transport_semantics(monkeypatch,status):
    from annual_disclosure_transport import observe_response
    from data_fetch.annual_workforce_provider import URLS,MAX_BYTES
    events=[];url=URLS['.TW']
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    response=httpx.Response(status,content=b'complete error response',request=httpx.Request('GET',url))
    with correlation_scope(replace=True,ticker='1623.TW',fetch_id='annual-error'):
        observe_response(url,response,max_bytes=MAX_BYTES)
    assert len(events)==1 and events[0]['response_complete'] is True
    assert events[0]['status']=='error' and events[0]['record_count']==0 and 'raw_http_receipt' not in events[0]
