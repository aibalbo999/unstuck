"""A normal missing auxiliary request must not evict or renew cached ratios."""
from copy import deepcopy
from datetime import date
from contextlib import contextmanager
import pytest
import cache_store
from provider_correlation import correlation_scope,source_operation
from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope
from data_fetch.market_sources import peer_recovery as m,peer_reference_evidence as e,starair_reference_evidence as individual
DAY=date(2026,11,5)

@contextmanager
def normal(enabled=True,provider='FinMind/yfinance',fetch_id='unit-gap',ticker='3324.TWO'):
    with correlation_scope(replace=True,ticker=ticker,fetch_id=fetch_id),source_operation('dynamic_peer_metrics',provider),receipt_observation_scope(enabled):yield

@pytest.fixture
def cached(monkeypatch):
    value={'metrics':{'pb':1.47},'status':'success','source':'TWSE/TPEx official peer valuation OpenAPI',
      'source_url':'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL',
      'official_company_name':'尼得科超眾','observed_at':'2026-11-04','fetched_at_epoch':1793850000,
      'attempts':[{'provider':'TWSE official peer reference income','status':'unavailable'}]}
    original=deepcopy(value);calls=[]
    monkeypatch.setattr(cache_store,'get_cache_json',lambda key:deepcopy(value))
    def no_write(*a,**kw):raise AssertionError('valid cached numeric value/TTL must not be written')
    monkeypatch.setattr(cache_store,'set_cache_json',no_write)
    from data_fetch.market_sources import official_peer_valuation
    monkeypatch.setattr(official_peer_valuation,'fetch_official_peer_valuation',no_write)
    def collect(ticker,observed,**kwargs):calls.append((ticker,observed,kwargs));return {'test_only_native_collector_result':True,'observed_at':observed}
    monkeypatch.setattr(e,'collect_reference_income',collect);monkeypatch.setattr(individual,'collect_reference_income',collect)
    return value,original,calls

def test_new_normal_invocation_can_fill_originally_missing_auxiliary_without_numeric_refetch(cached):
    value,original,calls=cached
    with normal():result=m.fetch_peer_valuation_fallback('6230.TW',today=DAY)
    assert len(calls)==1 and calls[0][:2]==('6230.TW','2026-11-04')
    assert result['metrics']==original['metrics']and result['fetched_at_epoch']==original['fetched_at_epoch']
    assert result['cache_hit']is True and result['pe_applicability_evidence']['test_only_native_collector_result']
    assert value==original and result['attempts'][0]==original['attempts'][0]

@pytest.mark.parametrize('enabled,provider,ticker',[(False,'FinMind/yfinance','3324.TWO'),(True,'Other','3324.TWO'),(True,'FinMind/yfinance',None)])
def test_read_only_foreign_or_unbound_call_does_not_collect(cached,enabled,provider,ticker):
    value,original,calls=cached
    with normal(enabled,provider,ticker=ticker):result=m.fetch_peer_valuation_fallback('6230.TW',today=DAY)
    assert not calls and 'pe_applicability_evidence'not in result and value==original

def test_no_native_frame_is_a_read_only_warm_delivery(cached):
    value,original,calls=cached;result=m.fetch_peer_valuation_fallback('6230.TW',today=DAY)
    assert not calls and result['metrics']==original['metrics']and value==original

@pytest.mark.parametrize('ticker,name',[('6558.TW','興能高'),('2723.TW','美食-KY'),('2646.TW','星宇航空')])
def test_only_previously_admitted_issuer_dispatch_preserves_observed_date(cached,ticker,name):
    value,_,calls=cached;value['official_company_name']=name;before=deepcopy(value)
    with normal():result=m.fetch_peer_valuation_fallback(ticker,today=DAY)
    assert calls[0][:2]==(ticker,'2026-11-04')and result['metrics']==before['metrics']and value==before

@pytest.mark.parametrize('change',['positive_PE','unsupported','wrong_name','empty_metrics','bad_PB'])
def test_unneeded_unqualified_or_empty_numeric_cache_never_creates_new_request(cached,change):
    value,_,calls=cached;ticker='6230.TW'
    if change=='positive_PE':value['metrics']['pe_ttm']=25
    elif change=='unsupported':ticker='3646.TWO'
    elif change=='wrong_name':value['official_company_name']='Other issuer'
    elif change=='empty_metrics':value['metrics']={}
    else:value['metrics']['pb']=True
    before=deepcopy(value)
    with normal():result=m.fetch_peer_valuation_fallback(ticker,today=DAY)
    assert not calls and value==before

@pytest.mark.parametrize('valid',[True,False])
def test_existing_auxiliary_valid_or_invalid_never_triggers_automatic_replacement(cached,monkeypatch,valid):
    from data_fetch.market_sources import peer_reference_applicability
    value,_,calls=cached;value['pe_applicability_evidence']={'original_proof':'keep'};before=deepcopy(value)
    monkeypatch.setattr(peer_reference_applicability,'verified_explanation',lambda *a,**kw:valid)
    with normal():result=m.fetch_peer_valuation_fallback('6230.TW',today=DAY)
    assert not calls and value==before
    assert ('pe_applicability_evidence'in result)is valid

def test_failed_native_auxiliary_preserves_original_numeric_and_failure(cached,monkeypatch):
    value,original,calls=cached
    def refused(*a,**kw):calls.append(a);raise ValueError('native_guard_holds')
    monkeypatch.setattr(e,'collect_reference_income',refused)
    with normal():result=m.fetch_peer_valuation_fallback('6230.TW',today=DAY)
    assert len(calls)==1 and result['metrics']==original['metrics']and value==original
    assert 'pe_applicability_evidence'not in result and result['attempts'][-1]['status']=='unavailable'

@pytest.mark.parametrize('field,value',[('source','FinMind TaiwanStockPER'),('source_url','https://example.com/unbound'),('observed_at','2026-09-01'),('observed_at','2026-11-06'),('observed_at',None)])
def test_unverified_publisher_url_or_observation_does_not_collect(cached,field,value):
    original,_,calls=cached;original[field]=value;before=deepcopy(original)
    with normal():result=m.fetch_peer_valuation_fallback('6230.TW',today=DAY)
    assert not calls and original==before and 'pe_applicability_evidence'not in result

# Full synthetic native-boundary replay; no external I/O or fabricated formal SLA.
from test_peer_reference_evidence import evidence_environment,DAY as PROOF_DAY

def numeric_owner(store):
    key='peer_valuation:v2:6230.TW:'+PROOF_DAY.isoformat()
    value={'metrics':{'pb':1.47},'status':'success','source':'TWSE/TPEx official peer valuation OpenAPI',
      'source_url':'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL',
      'official_company_name':'尼得科超眾','observed_at':PROOF_DAY.isoformat(),'fetched_at_epoch':1793761200,
      'attempts':[{'provider':'TWSE official peer reference income','status':'unavailable'}]}
    store[key]=deepcopy(value);return key,value

def test_warm_missing_reason_replays_all_eight_full_originals_without_rewriting_numeric(evidence_environment):
    from data_fetch.market_sources.peer_reference_applicability import verified_explanation,reassess_reference_applicability
    from data_fetch.market_sources.peers import PEER_METRIC_FIELDS
    store,calls,_=evidence_environment;key,original=numeric_owner(store)
    with normal():result=m.fetch_peer_valuation_fallback('6230.TW',today=PROOF_DAY)
    assert len(calls)==8 and store[key]==original and result['cache_hit']is True
    reason=result['pe_applicability_evidence']
    assert verified_explanation(reason,'6230.TW',today=PROOF_DAY)and result['metrics']=={'pb':1.47}
    assert reason['source_record_archive']['derived']['net_income_twd']==-436407000
    row={f:1.0 for f in PEER_METRIC_FIELDS};row.update(ticker='6230.TW',pe_ttm=None,pe_applicability_evidence=reason)
    row['gross_margin_pct']=None;reassess_reference_applicability(row,today=PROOF_DAY)
    assert row['metrics_status']=='partial'and row['missing_metrics']==['gross_margin_pct']
    before=len(calls)
    # Repeated delivery of the already obtained proof stays warm and performs no new raw read.
    assert verified_explanation(reason,'6230.TW',today=PROOF_DAY)and len(calls)==before

def test_warm_missing_reason_still_holds_existing_annual_originals(evidence_environment):
    store,calls,_=evidence_environment;key,original=numeric_owner(store)
    store['financial_data:6230.TW']={'ticker':'6230.TW','source_audit':[{'source':'financial_statements','status':'success','documents':[{'year':2025}]}]}
    before=deepcopy(store)
    with normal():result=m.fetch_peer_valuation_fallback('6230.TW',today=PROOF_DAY)
    assert not calls and store==before and store[key]==original and 'pe_applicability_evidence'not in result

def test_warm_missing_reason_does_not_clear_or_bypass_live_raw_failure_guard(evidence_environment):
    from hashlib import sha256
    import time
    from data_fetch.market_sources.peer_reference_transport import raw_key,spec
    store,calls,_=evidence_environment;key,original=numeric_owner(store)
    guard_key='shared_provider:v1:'+sha256(raw_key(spec('reference',day=PROOF_DAY)).encode()).hexdigest()
    store[guard_key]={'error_kind':'rate_limited','retry_after_epoch':time.time()+120,'fresh_until_epoch':time.time()-1}
    before=deepcopy(store)
    with normal():result=m.fetch_peer_valuation_fallback('6230.TW',today=PROOF_DAY)
    assert not calls and store==before and store[key]==original and 'pe_applicability_evidence'not in result

def test_incomplete_period_is_not_accepted_merely_because_HTTP_succeeded(evidence_environment,monkeypatch):
    from data_fetch.market_sources import peer_reference_transport as t
    from test_peer_reference_transport import parts
    from test_peer_reference_income import income_body
    store,calls,_=evidence_environment;key,original=numeric_owner(store);old=t.PeerIncomeHttp._download
    def changed(self,request,diagnostic):
        if request['kind']=='income':
            calls.append(deepcopy(request));raw=income_body(2026,3,-1)
            return self._consume(request,request['url'],parts(request,body=raw),0,None,diagnostic)
        return old(self,request,diagnostic)
    monkeypatch.setattr(t.PeerIncomeHttp,'_download',changed)
    with normal():result=m.fetch_peer_valuation_fallback('6230.TW',today=PROOF_DAY)
    assert calls and store[key]==original and 'pe_applicability_evidence'not in result
    assert result['attempts'][-1]['status']=='unavailable'
