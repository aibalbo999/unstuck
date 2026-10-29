from copy import deepcopy
from datetime import datetime
import pytest
from market_calendar_store import load_market_calendar,session_day_status
from official_institutional_source import expected_sessions

def calendar(tmp_path):
    return load_market_calendar('tw',2026,calendar_dir=str(tmp_path))

def test_tpex_oct23_has_its_own_explicit_closure_evidence(tmp_path):
    c=calendar(tmp_path);r=session_day_status('2026-10-23',calendar=c,exchange='TPEX')
    assert r['state']=='closed'
    proof=r['exception_evidence']
    assert proof['exchanges']==['TPEX']
    assert proof['published_date']=='2026-10-22'
    assert proof['source_url']=='https://www.tpex.org.tw/zh-tw/about/company/press/detail.html?23117'
    assert '櫃檯買賣有價證券市場' in proof['title']
    assert len(proof['source_response_sha256'])==64
    assert c['historical_point_in_time_verified'] is False and c['official_price_verified'] is False

def test_each_exchange_keeps_its_own_evidence_and_missing_proof_is_unknown(tmp_path):
    c=calendar(tmp_path)
    tw=session_day_status('2026-10-23',calendar=c,exchange='TWSE')
    assert tw['state']=='closed' and tw['exception_evidence']['exchanges']==['TWSE']
    assert tw['exception_evidence']['source_url'].startswith('https://www.twse.com.tw/')
    july=session_day_status('2026-07-10',calendar=c,exchange='TPEX')
    assert july['state']=='closed' and july['exception_evidence']['exchanges']==['TPEX']
    assert july['exception_evidence']['source_url'].endswith('?22926')
    assert july['exception_evidence']['published_date']=='2026-07-09'
    c=deepcopy(c);c['session_exceptions']['2026-07-10'].pop('related_exchange_evidence')
    missing=session_day_status('2026-07-10',calendar=c,exchange='TPEX')
    assert missing['state']=='unknown' and missing['reason']=='closure_evidence_scope_unverified'

@pytest.mark.parametrize('mutation',[
    lambda x:x.update(exchanges=['TWSE']),
    lambda x:x.update(source_url='https://www.twse.com.tw/news/23117'),
    lambda x:x.update(published_date='2026-10-24'),
    lambda x:x.update(source_url='https://www.tpex.org.tw.evil.invalid/news'),
    lambda x:x.update(state='open'),
])
def test_missing_or_unbound_additional_market_proof_fails_closed(tmp_path,mutation):
    c=deepcopy(calendar(tmp_path));entry=c['session_exceptions']['2026-10-23']
    proof=entry.setdefault('related_exchange_evidence',{}).setdefault('TPEX',{})
    mutation(proof)
    assert session_day_status('2026-10-23',calendar=c,exchange='TPEX')['state']=='unknown'

def test_missing_additional_market_proof_is_not_inferred_from_twse(tmp_path):
    c=deepcopy(calendar(tmp_path));c['session_exceptions']['2026-10-23'].pop('related_exchange_evidence',None)
    r=session_day_status('2026-10-23',calendar=c,exchange='TPEX')
    assert r['state']=='unknown' and r['reason']=='closure_evidence_scope_unverified'

def test_real_recovery_calendar_can_traverse_oct23_without_querying_it(monkeypatch,tmp_path):
    import market_calendar_store as store
    c=calendar(tmp_path)
    monkeypatch.setattr(store,'load_market_calendar',lambda *a,**k:deepcopy(c))
    moment=datetime.fromisoformat('2026-10-30T06:50:00+08:00').timestamp()
    days=expected_sessions('5314.TWO',moment,5)
    assert days==['2026-10-29','2026-10-28','2026-10-27','2026-10-22','2026-10-21']
    window=expected_sessions('5314.TWO',moment,30)
    assert len(window)==30 and len(set(window))==30
    assert window[0]=='2026-10-29' and '2026-10-23' not in window

@pytest.mark.parametrize('with_tpex_proof',[False,True])
def test_native_recovery_dispatch_requires_proof_and_keeps_partial_window(monkeypatch,with_tpex_proof):
    import market_calendar_store as store
    import official_institutional_source as source
    import shared_provider_cache
    # Bind normal provider imports before mocking its shared-cache dependency.
    # Lazy imports must not capture the temporary callback beyond this test.
    import data_fetch.institutional_provider as provider
    assert provider.shared_fetch is shared_provider_cache.shared_fetch
    # Synthetic HTTP boundary responses test dispatch only, never native success.
    seeds=deepcopy(store.BUILTIN_SESSION_EXCEPTIONS)
    if not with_tpex_proof:seeds[('tw',2026)]['2026-10-23'].pop('related_exchange_evidence',None)
    monkeypatch.setattr(store,'BUILTIN_SESSION_EXCEPTIONS',seeds)
    calls=[]
    def fetch(market,day,timeout,**kw):
        calls.append((market,day))
        return {'rows':{'5314':{'foreign':1,'investment_trust':2,'dealer':3}},'date':day}
    def shared(key,callback,**kw):
        assert kw['force_refresh'] is False
        return callback(),{'cache_hit':False,'fetched_at_epoch':moment}
    monkeypatch.setattr(source,'_fetch_report',fetch)
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',shared)
    moment=datetime.fromisoformat('2026-10-30T06:50:00+08:00').timestamp()
    value,diagnostic=source.recover_institutional_observations('5314.TWO',{},now_epoch=moment,limit=30)
    if not with_tpex_proof:
        assert not calls and diagnostic['status']=='calendar_unknown' and value=={}
    else:
        assert len(calls)==5 and all(market=='TPEX' and day!='2026-10-23'for market,day in calls)
        assert len(diagnostic['required_window_dates'])==30
        assert value['window_coverage_status']!='complete'
        assert len(value['daily_category_observations'])==15
