from copy import deepcopy
import json,time
import pytest
from data_fetch.market_sources.official_xbrl_financial import FilingError,FilingTransportError,PROVIDER
from provider_correlation import correlation_scope


@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def run(fetch):
    from data_fetch.official_financial_gap_cache import fetch_official_financial_result
    return fetch_official_financial_result('3023.TW',fetcher=fetch)


def confirmed_error():
    """Use the real collector's validated exception, never an error string."""
    import httpx
    from test_official_xbrl_financial import filing
    from data_fetch.market_sources.official_xbrl_financial import fetch_official_annual_histories
    index=''.join(f'/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=3023&season=4&report_id=C&year={year}'+'" ' for year in range(2021,2026)).encode()
    def respond(request):
        if request.method=='POST':return httpx.Response(200,content=index)
        year=int(request.url.params['year'])
        missing=('PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities',) if year==2021 else ()
        return httpx.Response(200,content=filing(year,issuer='3023',missing=missing))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        try:fetch_official_annual_histories('3023.TW',client=client)
        except FilingError as exc:
            assert exc.validation_gap['year']==2021
            return exc
    raise AssertionError('Expected an original missing-fact error')


def test_confirmed_issuer_gap_is_reused_without_calling_provider_or_marking_success():
    calls=[]
    def fetch(ticker):
        calls.append(ticker);raise confirmed_error()
    with correlation_scope(replace=True,fetch_id='first',ticker='3023.TW'):first=run(fetch)
    with correlation_scope(replace=True,fetch_id='second',ticker='3023.TW'):second=run(fetch)
    assert calls==['3023.TW']
    assert first['value'] is second['value'] is None
    assert first['audit']['status']==second['audit']['status']=='error'
    assert second['audit']['record_count']==0 and second['audit']['error_kind']=='FilingError'
    assert second['audit']['cache_hit'] is True and second['audit']['stale'] is False
    assert second['audit']['event_kind']=='cache_hit' and second['audit']['http_request_sent'] is False
    assert second['audit']['fetched_at']==first['audit']['fetched_at']
    assert second['audit']['fetch_id']=='second' and second['audit']['provider_attempts']==[]


@pytest.mark.parametrize('exc',[FilingTransportError('timeout'),FilingError('XBRL is not well-formed XML'),FilingError('comparison HTTP 429'),FilingError('fewer than five consolidated annual filings'),FilingError('annual XBRL facts are incomplete for 2021'),FilingError('conflicting incomplete comparative statement for 2022')])
def test_transport_and_other_unverified_errors_are_not_a_cached_issuer_gap(exc):
    calls=[]
    def fetch(ticker):calls.append(ticker);raise exc
    run(fetch);run(fetch)
    assert len(calls)==2


def test_gap_expiry_rechecks_provider_and_can_recover(monkeypatch):
    import data_fetch.official_financial_gap_cache as source
    calls=[]
    def fetch(ticker):
        calls.append(ticker)
        if len(calls)==1:raise confirmed_error()
        return {'years':['2021','2022','2023','2024','2025'],'marker':'recovered'}
    first=run(fetch);original=source.get_cache_json
    def expired(key):
        value=original(key)
        if value:value['audit']['fetched_at_epoch']=time.time()-301
        return value
    monkeypatch.setattr(source,'get_cache_json',expired)
    after=run(fetch)
    assert len(calls)==2 and after['audit']['status']=='success' and after['value']['marker']=='recovered'
    monkeypatch.setattr(source,'get_cache_json',original)
    assert run(fetch)['audit']['status']=='success' and len(calls)==3


@pytest.mark.parametrize('change',['wrong_ticker','wrong_version','future','bool_epoch','nan_epoch','false_status','positive_count','mismatched_timestamp','no_proof','wrong_issuer','wrong_document_hash','empty_verified_facts'])
def test_unverified_gap_cache_never_prevents_a_real_source_attempt(monkeypatch,change):
    import data_fetch.official_financial_gap_cache as source
    def fail(ticker):raise confirmed_error()
    run(fail);original=source.get_cache_json
    def altered(key):
        value=deepcopy(original(key))
        if change=='wrong_ticker':value['ticker']='2330.TW'
        elif change=='wrong_version':value['parser_fingerprint']='0'*64
        elif change=='future':value['audit']['fetched_at_epoch']=time.time()+60
        elif change=='bool_epoch':value['audit']['fetched_at_epoch']=True
        elif change=='nan_epoch':value['audit']['fetched_at_epoch']=float('nan')
        elif change=='false_status':value['audit']['status']='success'
        elif change=='mismatched_timestamp':value['audit']['fetched_at']='2026-01-01T00:00:00+00:00'
        elif change=='no_proof':value.pop('validation_gap')
        elif change=='wrong_issuer':value['validation_gap']['issuer']='2330'
        elif change=='wrong_document_hash':value['validation_gap']['documents'][0]['sha256']=''
        elif change=='empty_verified_facts':value['validation_gap']['raw_twd_by_year']['2021']={}
        else:value['audit']['record_count']=1
        return value
    monkeypatch.setattr(source,'get_cache_json',altered)
    calls=[]
    def success(ticker):calls.append(ticker);return {'years':['2021','2022','2023','2024','2025']}
    recovered=run(success)
    assert calls==['3023.TW'] and recovered['audit']['status']=='success'


def test_stored_failure_is_not_reclassified_as_a_new_failed_or_successful_acquisition():
    from provider_observation_details import observation_details
    from provider_acquisition import observation_kind
    def fail(ticker):raise confirmed_error()
    first=run(fail);second=run(fail)
    def kind(result):
        a=result['audit'];return observation_kind({**a,'details':observation_details(a)})
    assert kind(first)=='failed_count' and kind(second)=='empty_cache_count'


def test_optional_cache_read_and_write_failures_leave_provider_fallback_available(monkeypatch):
    import data_fetch.official_financial_gap_cache as source
    calls=[]
    def unavailable(*a):raise Exception('synthetic cache backend unavailable')
    monkeypatch.setattr(source,'get_cache_json',unavailable)
    def fail(ticker):calls.append(ticker);raise confirmed_error()
    assert run(fail)['audit']['status']=='error' and calls==['3023.TW']
    monkeypatch.setattr(source,'get_cache_json',lambda key:None)
    monkeypatch.setattr(source,'set_cache_json',unavailable)
    assert run(fail)['audit']['status']=='error' and calls==['3023.TW','3023.TW']


@pytest.mark.parametrize('bad_source',['security_index','wrong_issuer'])
def test_unverified_source_can_recover_on_the_next_real_attempt(bad_source):
    import httpx
    from test_official_xbrl_financial import filing
    from data_fetch.market_sources.official_xbrl_financial import fetch_official_annual_histories
    index=''.join(f'/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=3023&season=4&report_id=C&year={year}'+'" ' for year in range(2021,2026)).encode()
    attempt=[0]
    def respond(request):
        if request.method=='POST':
            attempt[0]+=1
            content=b'<html>Security check</html>' if attempt[0]==1 and bad_source=='security_index' else index
        else:
            year=int(request.url.params['year'])
            content=filing(year,issuer='2330' if attempt[0]==1 and bad_source=='wrong_issuer' else '3023')
        return httpx.Response(200,content=content)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        def fetch(ticker):return fetch_official_annual_histories(ticker,client=client)
        first=run(fetch);second=run(fetch)
    assert first['audit']['status']=='error'
    assert second['audit']['status']=='success' and attempt[0]==2
    assert second['value']['years']==['2021','2022','2023','2024','2025']


def test_warm_gap_cannot_inherit_the_previous_data_fingerprint():
    def fail(ticker):raise confirmed_error()
    with correlation_scope(replace=True,fetch_id='first',data_fingerprint='a'*64):first=run(fail)
    with correlation_scope(replace=True,fetch_id='second'):second=run(fail)
    assert first['audit']['data_fingerprint']=='a'*64
    assert 'data_fingerprint' not in second['audit']
