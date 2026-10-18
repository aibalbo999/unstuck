"""Actual KGI public bodies must yield exact, recent parent-company evidence."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
from test_shared_provider_cache import memory_cache

NOW = 1791881818.4368
FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition/kgi_2883_jobs_20261013'


def fixtures():
    from data_fetch.market_sources.kgi_careers import API_URL, detail_url, REQUEST
    listing_raw = (FIXTURES / 'native-filtered-list.json').read_bytes()
    listing = {'url': API_URL, 'method': 'POST', 'request_json': REQUEST,
               'body_b64': base64.b64encode(listing_raw).decode(), 'sha256': sha256(listing_raw).hexdigest(),
               'fetched_at_epoch': NOW}
    details = []
    for row in json.loads(listing_raw)['jobPostings'][:2]:
        raw = (FIXTURES / ('native-detail-' + row['bulletFields'][0] + '.json')).read_bytes()
        details.append({'url': detail_url(row['externalPath']), 'method': 'GET', 'request_json': None,
                        'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                        'fetched_at_epoch': NOW})
    return listing, details


def test_original_list11_contains_only_two_recent_exact_issuer_details():
    from data_fetch.market_sources.kgi_careers import parse_jobs, verified_job_count, TICKER, LEGAL, UBN
    listing, details = fixtures()
    value = parse_jobs(listing, details, now=NOW)
    assert value['listing_total'] == 11 and value['current_open_job_count'] == 2
    assert value['job_count'] is None and value['recent_company_job_count'] is None
    assert [r['job_no'] for r in value['job_postings']] == ['JR106341', 'JR106307']
    assert all(r['description'] and r['published_date'] is None for r in value['job_postings'])
    assert verified_job_count(value, TICKER, LEGAL, UBN, now=NOW) == 2


@pytest.mark.parametrize('mutation', [
    lambda x: x.update(current_open_job_count=11),
    lambda x: x['job_postings'][0].update(employer='凱基商業銀行股份有限公司'),
    lambda x: x['job_postings'][0].update(published_date='2026-09-21'),
    lambda x: x['job_postings'][0].update(description='fabricated content'),
    lambda x: x['source_record_archive']['detail_receipts'][0].update(sha256='0'*64),
    lambda x: x['source_record_archive']['listing_receipt'].update(request_json={}),
    lambda x: x['source_record_archive']['detail_receipts'].append(x['source_record_archive']['detail_receipts'][0]),
])
def test_counter_rechecks_raw_receipts_and_prompt_fields(mutation):
    from data_fetch.market_sources.kgi_careers import parse_jobs, verified_job_count, TICKER, LEGAL, UBN
    value = parse_jobs(*fixtures(), now=NOW)
    mutation(value)
    assert verified_job_count(value, TICKER, LEGAL, UBN, now=NOW) == 0


@pytest.mark.parametrize('changes', [
    {'startDate':'2026-10-14'}, {'startDate':'2026-08-01'}, {'canApply':False},
    {'posted':False}, {'title':'different'}, {'jobReqId':'JR106999'},
    {'jobDescription':'applications closed'},
])
def test_changed_native_detail_fails_closed(changes):
    from data_fetch.market_sources.kgi_careers import parse_jobs
    listing, details = fixtures()
    data = json.loads(base64.b64decode(details[0]['body_b64']))
    data['jobPostingInfo'].update(changes)
    raw = json.dumps(data).encode();details[0].update(body_b64=base64.b64encode(raw).decode(),sha256=sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        parse_jobs(listing, details, now=NOW)


def test_late_read_never_makes_future_at_acquisition_date_valid():
    from data_fetch.market_sources.kgi_careers import parse_jobs
    listing, details = fixtures()
    data = json.loads(base64.b64decode(details[0]['body_b64']))
    data['jobPostingInfo']['startDate']='2026-10-14'
    raw=json.dumps(data).encode();details[0].update(body_b64=base64.b64encode(raw).decode(),sha256=sha256(raw).hexdigest())
    with pytest.raises(ValueError):parse_jobs(listing, details, now=NOW+86400)


def issuer_data():
    from data_fetch.market_sources.kgi_careers import LEGAL, SHORT, UBN, TICKER
    return {'ticker':TICKER,'company_name':SHORT,'quote_type':'EQUITY','instrument_type':'EQUITY',
            'company_identity':{'ticker':TICKER,'official_name':SHORT,'stock_id':'2883','instrument_type':'EQUITY','legal_name':None},
            'anchor':{'ticker':TICKER,'official_short_name':SHORT,'legal_name':LEGAL,'official_ubn':UBN,
                      'source_url':'https://openapi.twse.com.tw/v1/opendata/t187ap03_L',
                      'response_sha256':'a'*64,'as_of':'2026-10-13','fetched_at_epoch':NOW}}


@pytest.fixture
def provider_setup(monkeypatch):
    import time
    from data_fetch.market_sources import kgi_careers as kgi, kgi_careers_transport as transport
    from data_fetch.market_sources import official_company_legal_name as master, taiwanjobs_company_jobs as tj
    import alternative_data_fetcher as search
    monkeypatch.setattr(time,'time',lambda:NOW)
    data=issuer_data();calls=[];keywords=[]
    data['_test_original_get_receipt']=transport.KgiCareersHttp.get_receipt
    monkeypatch.setattr(master,'get_official_legal_name',lambda *a:data['anchor'])
    for name in ['fetch_104_company_jobs','fetch_104_company_jobs_by_ubn']:
        monkeypatch.setattr(search,name,lambda *a,**k:{'status':'unavailable'})
    for name in ['fetch_taiwanjobs_company_jobs','fetch_taiwanjobs_regional_jobs']:
        monkeypatch.setattr(tj,name,lambda *a,**k:{'status':'unavailable'})
    monkeypatch.setattr(search,'fetch_104_job_openings_count',lambda *a,**k:keywords.append('104') or {'status':'unavailable'})
    monkeypatch.setattr(search,'fetch_1111_job_openings_count',lambda *a,**k:keywords.append('1111') or {'status':'unavailable'})
    listing, details=fixtures()
    def read(self,path=None):
        calls.append(path)
        return listing if path is None else next(r for r in details if r['url']==kgi.detail_url(path))
    monkeypatch.setattr(transport.KgiCareersHttp,'get_receipt',read)
    return data,calls,keywords


def test_public_provider_recovers_real_two_jobs_and_skips_failed_keyword_search(provider_setup):
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count
    data,calls,keywords=provider_setup
    result=AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2883.TW'),{'data':data})
    assert result.status=='success' and result.audit['record_count']==2
    assert source_record_count('alternative_data',{**data,'alternative_data':result.value})==2
    assert len(calls)==3 and keywords==[]
    assert result.value['job_openings_official']['listing_total']==11


@pytest.mark.parametrize('change', [
    lambda d:d['company_identity'].update(ticker='2882.TW'),
    lambda d:d.update(ticker='2882.TW'),
    lambda d:d.update(quote_type='ETF'),
    lambda d:d.update(instrument_type='ETF'),
    lambda d:d['company_identity'].update(stock_id='2882'),
    lambda d:d.update(stock_id='2882'),
    lambda d:d['company_identity'].update(official_ubn='12345678'),
    lambda d:d['anchor'].update(fetched_at_epoch=NOW-86401),
    lambda d:d['anchor'].update(official_ubn='12345678'),
])
def test_invalid_current_parent_identity_cannot_trigger_workday(provider_setup,change):
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    data,calls,_=provider_setup;change(data)
    result=AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2883.TW'),{'data':data})
    assert calls==[] and result.audit['record_count']==0


def test_forced_public_context_read_keeps_original_receipt_age(provider_setup,monkeypatch):
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    import time
    data,_,_=provider_setup
    monkeypatch.setattr(time,'time',lambda:NOW+20)
    result=AlternativeJobOpeningsProvider().fetch(FetchRequest.from_ticker('2883.TW',force_refresh=True),{'data':data})
    assert result.status=='success' and result.audit['fetched_at_epoch']==NOW
    assert result.value['fetched_at_epoch']==NOW


def test_context_cache_does_not_cross_issuer_identity(provider_setup):
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    data,calls,_=provider_setup;request=FetchRequest.from_ticker('2883.TW')
    first=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
    assert first.status=='success' and len(calls)==3
    data['company_identity']['ticker']='2882.TW'
    second=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
    assert second.status!='success' and second.audit['record_count']==0 and len(calls)==3


def test_cold_warm_and_forced_raw_cache_do_not_create_extra_acquisition_success(provider_setup,monkeypatch):
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import kgi_careers_transport as t
    from provider_acquisition import get_provider_acquisition_summary
    from provider_correlation import correlation_scope
    from test_kgi_careers_transport import response
    data,_,_=provider_setup
    monkeypatch.setattr(t.KgiCareersHttp,'get_receipt',data.pop('_test_original_get_receipt'))
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for key in t.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(t,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(t,'cooldown_state',lambda *a:None)
    monkeypatch.setattr(t,'observe_http_response',lambda *a:None)
    listing,details=fixtures();by_url={r['url']:base64.b64decode(r['body_b64']) for r in [listing,*details]};calls=[]
    def run(argv,*a,**k):calls.append(argv[-1]);return response(argv,body=by_url[argv[-1]])
    monkeypatch.setattr(t,'collect_capped_process',run)
    results=[]
    for number,force in enumerate([False,False,True]):
        request=FetchRequest.from_ticker('2883.TW',force_refresh=force)
        with correlation_scope(replace=True,ticker=request.ticker,fetch_id='kgi-isolated-'+str(number)):
            result=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
            assert result.status=='success' and result.audit['record_count']==2
            StockDataService()._build_result(request,{**data,'alternative_data':result.value,'source_audit':[result.audit]},0)
            results.append(result)
    assert len(calls)==3
    assert results[0].audit['http_request_count']==3 and results[0].audit['cache_hit'] is False
    assert all(r.audit['http_request_count']==0 and r.audit['cache_hit'] is True for r in results[1:])
    counts=next(x for x in get_provider_acquisition_summary('last_24h')['sources'] if x['source']=='alternative_data')
    assert counts['fetched_count']==1 and counts['fetch_attempts']==1 and counts['fresh_cache_count']==2


def test_snapshot_contains_raw_evidence_but_prompt_does_not(monkeypatch):
    from data_fetch.market_sources.kgi_careers import parse_jobs
    from prompt_builder import format_data_for_prompt
    from data_trust import source_record_count
    import time
    monkeypatch.setattr(time,'time',lambda:NOW)
    data=issuer_data();value=parse_jobs(*fixtures(),now=NOW)
    snapshot={**data,'alternative_data':{'company_legal_name_evidence':data['anchor'],'job_openings_official':value}}
    serialized=json.loads(json.dumps(snapshot))
    assert source_record_count('alternative_data',serialized)==2
    text=format_data_for_prompt(serialized)
    assert 'body_b64' not in text and 'detail_receipts' not in text
    assert '數據分析師' in text and 'source_start_date' in text and 'published_date' in text


def test_late_context_fill_cannot_extend_original_1800_second_lifetime(provider_setup,monkeypatch):
    import time
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    data,calls,_=provider_setup
    now=[NOW+1790]
    monkeypatch.setattr(time,'time',lambda:now[0])
    request=FetchRequest.from_ticker('2883.TW')
    first=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
    assert first.status=='success' and first.audit['fetched_at_epoch']==NOW
    now[0]=NOW+1801
    late=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
    assert late.status!='success' or late.audit.get('stale') is True


@pytest.mark.parametrize('first_age, late_age', [(1790, 1801), (1799.5, 1800.1)])
def test_near_expiry_context_fill_refreshes_native_originals_at_expiry(provider_setup,monkeypatch,first_age,late_age):
    import time
    from test_kgi_careers_transport import response
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    from data_fetch.market_sources import kgi_careers_transport as transport, kgi_careers as kgi
    data,_,_=provider_setup
    monkeypatch.setattr(transport.KgiCareersHttp,'get_receipt',data.pop('_test_original_get_receipt'))
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for key in transport.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(transport,'cooldown_state',lambda *a:None)
    monkeypatch.setattr(transport,'observe_http_response',lambda *a:None)
    listing,details=fixtures();bodies={r['url']:base64.b64decode(r['body_b64']) for r in [listing,*details]}
    calls=[];now=[NOW]
    monkeypatch.setattr(time,'time',lambda:now[0])
    def run(argv,*a,**kwargs):calls.append(argv[-1]);return response(argv,body=bodies[argv[-1]])
    monkeypatch.setattr(transport,'collect_capped_process',run)
    # A preceding collector uses the shared raw originals without filling this context.
    raw=kgi.fetch_official_jobs(kgi.TICKER,kgi.LEGAL,kgi.UBN)
    assert raw['status']=='success' and len(calls)==3
    now[0]=NOW+first_age
    request=FetchRequest.from_ticker(kgi.TICKER)
    first=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
    assert first.status=='success' and len(calls)==3
    assert first.audit['fetched_at_epoch']==NOW and first.audit['cache_hit'] is True
    now[0]=NOW+late_age
    refreshed=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
    assert refreshed.status=='success' and len(calls)==6
    assert refreshed.audit['fetched_at_epoch']==now[0]
    assert refreshed.audit['cache_hit'] is False and refreshed.audit['http_request_count']==3
