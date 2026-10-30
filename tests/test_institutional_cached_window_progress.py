"""Synthetic HTTP boundaries test normal cache progression, never native success."""
import json
from datetime import datetime,timezone
from copy import deepcopy
import pytest

NOW=datetime.fromisoformat('2026-10-30T07:00:00+08:00').timestamp()

@pytest.fixture
def isolated(monkeypatch,tmp_path):
    import cache_store,runtime_paths
    import data_fetch.institutional_provider
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    paths=runtime_paths.RuntimePaths.from_values(cache_dir=tmp_path,output_dir=tmp_path/'output')
    monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:paths)
    monkeypatch.setattr('time.time',lambda:NOW)
    yield
    cache_store.reset_cache_store_for_tests()


def install_reports(monkeypatch):
    import official_institutional_source as source
    from official_response_evidence import archive_response
    calls=[]
    def fetch(market,day,timeout,**kwargs):
        assert market=='TWSE'
        calls.append(day)
        payload={'stat':'OK','date':day.replace('-',''),'fields':source.TWSE_FIELDS,
                 'hints':'單位：股','data':[['2330','台積電',100,90,10,0,0,0,50,48,2,3,100,99,1,100,98,2,15]]}
        raw=json.dumps(payload,ensure_ascii=False).encode()
        report=source._parse_report(payload,market,day)
        report['raw_evidence']=archive_response(raw,source_url=source._url(market,day),
            retrieved_at=datetime.fromtimestamp(NOW,timezone.utc).isoformat(),http_status=200)
        report['source']=source.TWSE_SOURCE
        return report
    monkeypatch.setattr(source,'_fetch_report',fetch)
    return calls


def test_normal_recovery_moves_past_five_cached_reports_without_refetch(monkeypatch,isolated):
    import official_institutional_source as source
    calls=install_reports(monkeypatch)
    first,one=source.recover_institutional_observations('2330.TW',{},now_epoch=NOW,limit=30)
    assert len(calls)==5 and len(first['daily_category_observations'])==15
    initial=tuple(calls)
    second,two=source.recover_institutional_observations('2330.TW',{},now_epoch=NOW,limit=30)
    assert 5<len(calls)<=10
    assert len(calls)==len(set(calls)) and tuple(calls[:5])==initial
    assert len(second['daily_category_observations'])>15


def test_normal_requests_can_accumulate_full_window_and_then_use_cache_only(monkeypatch,isolated):
    import official_institutional_source as source
    calls=install_reports(monkeypatch)
    # Eight isolated normal acquisitions simulate future users, not a live retry schedule.
    for _ in range(8):
        count=len(calls)
        value,diagnostic=source.recover_institutional_observations('2330.TW',{},now_epoch=NOW,limit=30)
        assert len(calls)-count<=source.MAX_REPORTS==5
    assert value['observed_date_count']==30 and value['window_coverage_status']=='complete'
    assert len(calls)==30 and len(set(calls))==30
    assert len(value['daily_category_observations'])==90
    value,diagnostic=source.recover_institutional_observations('2330.TW',{},now_epoch=NOW,limit=30)
    assert len(calls)==30 and all(r['cache_hit'] for r in diagnostic['reports'])
    assert len({r['date']for r in diagnostic['reports']})==len(diagnostic['reports'])


def test_primary_empty_and_only_cached_data_is_not_a_new_acquisition(monkeypatch,isolated):
    import data_fetch.institutional_provider as provider
    import official_institutional_source as source
    import report_source_admission
    from data_fetch.types import FetchRequest
    from provider_observation_details import observation_details
    from provider_acquisition import observation_kind
    value={'source':'TWSE T86','latest_date':'2026-10-29','window_coverage_status':'partial',
           'daily_category_observations':[{'date':'2026-10-29','category':'foreign','net_buy_shares':1,'source':'TWSE T86','unit':'shares'}]}
    monkeypatch.setattr(provider,'shared_fetch',lambda *a,**k:({}, {'cache_hit':False,'stale':False,'fetched_at_epoch':NOW,'http_request_sent':True,'provider_attempts':[{'attempt_id':'synthetic-primary','status':'success'}]}))
    recovery={'added_observation_count':1,'reports':[{'status':'available','date':'2026-10-29','cache_hit':True,'fetched_at_epoch':NOW-100}]}
    monkeypatch.setattr(source,'recover_institutional_observations',lambda *a,**k:(deepcopy(value),deepcopy(recovery)))
    monkeypatch.setattr(report_source_admission,'institutional_admission',lambda *a:{'eligible':True,'reason':'test_boundary_only'})
    result=provider.fetch_institutional_result(FetchRequest.from_ticker('2330.TW'))
    assert result.status=='success' and result.audit['record_count']>0
    assert result.audit['fetched_at_epoch']==NOW-100
    row={**result.audit,'details':observation_details(result.audit)}
    assert observation_kind(row)=='empty_count'
    assert row['details']['acquisition_record_count']==0


def test_fresh_peek_preserves_cache_bytes_clock_and_ttl(monkeypatch,isolated):
    import shared_provider_cache as shared
    import cache_store
    from hashlib import sha256
    value,meta=shared.shared_fetch('read-only-test',lambda:{'rows':[1]},freshness_seconds=60,retention_seconds=120)
    key=shared._PREFIX+sha256(b'read-only-test').hexdigest()
    before=deepcopy(cache_store.get_cache_json(key))
    monkeypatch.setattr(cache_store,'set_cache_json',lambda *a,**k:pytest.fail('peek must not write/renew cache'))
    result,peek=shared.peek_fresh_shared('read-only-test')
    assert result==value and peek['cache_hit'] and peek['fetched_at_epoch']==meta['fetched_at_epoch']
    result['rows'].append(2)
    assert cache_store.get_cache_json(key)==before
    monkeypatch.setattr('time.time',lambda:NOW+61)
    assert shared.peek_fresh_shared('read-only-test')[0] is None
    assert cache_store.get_cache_json(key)==before


@pytest.mark.parametrize('mutate',[
    lambda r:r.update(fetched_at_epoch=NOW+1),
    lambda r:r.update(fetched_at_epoch=True),
    lambda r:r.update(fresh_until_epoch=float('nan')),
    lambda r:r.update(fresh_until_epoch=NOW),
])
def test_peek_rejects_unknown_future_or_expired_clocks(monkeypatch,isolated,mutate):
    import cache_store
    from shared_provider_cache import peek_fresh_shared
    row={'value':{'rows':[1]},'fetched_at_epoch':NOW-10,'fresh_until_epoch':NOW+50}
    mutate(row)
    monkeypatch.setattr(cache_store,'peek_cache_json',lambda key:deepcopy(row))
    assert peek_fresh_shared('bad')[0] is None


@pytest.mark.parametrize('mutate',[
    lambda r:r.update(source='financial_statements'),
    lambda r:r.update(provider='Other provider'),
    lambda r:r['details'].update(acquisition_count_policy='unknown'),
    lambda r:r['details'].update(acquisition_record_count=False),
])
def test_acquisition_override_cannot_change_other_or_unbound_observations(mutate):
    from provider_acquisition import observation_kind
    row={'source':'institutional_trading','provider':'FinMind','status':'success','record_count':10,'message':'',
         'details':{'event_kind':'aggregate','acquisition_count_policy':'institutional-primary-and-official-new:v1','acquisition_record_count':0}}
    mutate(row)
    assert observation_kind(row)=='fetched_count'


@pytest.mark.parametrize('status',['error','unavailable','degraded_enrichment'])
def test_acquisition_marker_never_removes_existing_failure_denominators(status):
    from provider_acquisition import observation_kind
    row={'source':'institutional_trading','provider':'FinMind','status':status,'record_count':10,'message':'',
         'details':{'event_kind':'aggregate','acquisition_count_policy':'institutional-primary-and-official-new:v1','acquisition_record_count':0}}
    assert observation_kind(row) in ('failed_count','degraded_count')


@pytest.mark.parametrize('mutate',[
    lambda r:r['rows']['2330'].update(foreign=999),
    lambda r:r.update(date='2026-10-27'),
    lambda r:r['raw_evidence'].update(source_url='https://example.invalid/T86'),
    lambda r:r['raw_evidence'].update(retrieved_at='2026-10-30T08:00:00+08:00'),
    lambda r:r['raw_evidence'].update(retrieved_at='2026-10-28T10:00:00+08:00'),
    lambda r:r['rows'].pop('2330'),
])
def test_cached_window_requires_exact_raw_body_date_endpoint_and_issuer(monkeypatch,isolated,mutate):
    import official_institutional_source as source
    import shared_provider_cache as shared
    from institutional_cached_window import reuse_cached_window
    from market_evidence_policy import calendar_cache_token
    import time
    calls=install_reports(monkeypatch)
    source.recover_institutional_observations('2330.TW',{},now_epoch=NOW,limit=30)
    token=calendar_cache_token('2330.TW',datetime.fromtimestamp(NOW,timezone.utc))
    key=f'official-institutional:TWSE:2026-10-28:v3:{token}:post_cutoff'
    report,meta=shared.peek_fresh_shared(key)
    assert report is not None
    mutate(report)
    monkeypatch.setattr(shared,'peek_fresh_shared',lambda key:(deepcopy(report),deepcopy(meta)))
    merged={}
    receipts,added=reuse_cached_window('2330.TW',['2026-10-29','2026-10-28'],merged,
        now_epoch=NOW,calendar_token=token,deadline=time.monotonic()+12)
    assert receipts==[] and added==0 and merged=={} and len(calls)==5


def test_cached_window_deadline_does_not_read_or_fetch(monkeypatch,isolated):
    import shared_provider_cache as shared
    from institutional_cached_window import reuse_cached_window
    import time
    monkeypatch.setattr(shared,'peek_fresh_shared',lambda *a:pytest.fail('expired budget must not read'))
    assert reuse_cached_window('2330.TW',['2026-10-29','2026-10-28'],{},now_epoch=NOW,
        calendar_token='test',deadline=time.monotonic()-1)==([],0)


def test_force_refresh_retains_existing_bounded_path_and_never_uses_prescan(monkeypatch,isolated):
    import official_institutional_source as source
    import institutional_cached_window
    calls=install_reports(monkeypatch)
    monkeypatch.setattr(institutional_cached_window,'reuse_cached_window',lambda *a,**k:pytest.fail('force path must not reuse'))
    source.recover_institutional_observations('2330.TW',{},now_epoch=NOW,limit=30,force_refresh=True)
    assert len(calls)==5


def test_sqlite_peek_never_creates_or_deletes_expired_corrupt_rows(tmp_path):
    import sqlite3
    from cache_backends import SqliteCacheBackend
    path=tmp_path/'read-only.sqlite3'
    backend=SqliteCacheBackend(path)
    assert backend.peek_json('absent') is None and not path.exists()
    backend.set_json('expired',{'rows':[1]},ttl_seconds=60)
    backend.set_json('bad',{'rows':[2]},ttl_seconds=60)
    with sqlite3.connect(path) as c:
        c.execute("UPDATE cache_entries SET expires_at=? WHERE cache_key='expired'",(0,))
        c.execute("UPDATE cache_entries SET value='not-json' WHERE cache_key='bad'")
        before=c.execute('SELECT * FROM cache_entries ORDER BY cache_key').fetchall()
    assert backend.peek_json('expired') is None and backend.peek_json('bad') is None
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
        assert c.execute('SELECT * FROM cache_entries ORDER BY cache_key').fetchall()==before
    backend.close()
