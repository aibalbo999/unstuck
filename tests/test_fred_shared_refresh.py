from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
import pytest

@pytest.fixture
def environment(monkeypatch):
 import macro_fetcher as macro,shared_provider_cache as shared,cache_store
 clock=[1793521200.];cache={};calls=[]
 monkeypatch.setenv('FRED_API_KEY','unit-test-only')
 monkeypatch.setattr(macro,'time',SimpleNamespace(time=lambda:clock[0]))
 monkeypatch.setattr(shared,'time',SimpleNamespace(time=lambda:clock[0]))
 monkeypatch.setattr(shared,'_shared_lock',lambda *a,**k:nullcontext(True))
 monkeypatch.setattr(cache_store,'get_cache_json',lambda k:deepcopy(cache.get(k)))
 monkeypatch.setattr(cache_store,'set_cache_json',lambda k,v,**kw:cache.__setitem__(k,deepcopy(v)))
 def latest(session,key,series,**kw):calls.append(series);return {'date':'2026-10-30','value':4.2 if series=='DGS10'else 18.0}
 def cpi(*a,**kw):calls.append('CPIAUCSL');return {'date':'2026-09-01','prior_date':'2025-09-01','value':3.}
 monkeypatch.setattr(macro,'_latest_observation',latest);monkeypatch.setattr(macro,'_cpi_yoy_observation',cpi)
 return macro,clock,cache,calls

def test_company_force_refresh_does_not_bypass_global_series_cache(environment):
 from data_fetch.agent_context_providers import MacroIndicatorsProvider
 from data_fetch.types import FetchRequest
 macro,clock,cache,calls=environment;p=MacroIndicatorsProvider()
 first=p.fetch(FetchRequest.from_ticker('3653.TW',force_refresh=True))
 second=p.fetch(FetchRequest.from_ticker('5314.TWO',force_refresh=True))
 assert first.status==second.status=='success'
 assert calls==['DGS10','CPIAUCSL','VIXCLS']
 assert second.audit['cache_hit']is True
 assert all(v['fresh_until_epoch']-v['fetched_at_epoch']==900 for v in cache.values())

def test_failed_expired_refresh_remains_attempt_despite_retained_values(environment,monkeypatch):
 import macro_fetcher as macro
 from provider_acquisition import observation_kind
 macro,clock,cache,calls=environment
 first=macro.fetch_key_macro_indicators();old={k:v['fetched_at_epoch']for k,v in cache.items()};clock[0]+=901
 def fail(*a,**kw):calls.append('failed');raise RuntimeError('provider unavailable')
 monkeypatch.setattr(macro,'_latest_observation',fail);monkeypatch.setattr(macro,'_cpi_yoy_observation',fail)
 failed=macro.fetch_key_macro_indicators()
 assert failed['status']=='stale' and failed['stale']is True
 assert failed['cache_hit']is False
 assert all(item['stale']and item['cache_hit']for item in failed['indicators'].values())
 assert {k:v['fetched_at_epoch']for k,v in cache.items()}==old
 assert observation_kind({'source':'macro_indicators','provider':'FRED macro indicators','status':'degraded_enrichment','record_count':3,'message':'retained old observations','details':{'cache_hit':failed['cache_hit'],'stale':True}})=='degraded_count'
 before=len(calls);cooldown=macro.fetch_key_macro_indicators()
 assert len(calls)==before and cooldown['cache_hit']is True and cooldown['stale']is True


def test_expired_observation_never_becomes_fresh_by_company_refresh(environment):
 macro,clock,cache,calls=environment;macro.fetch_key_macro_indicators();clock[0]+=8*86400
 result=macro.fetch_key_macro_indicators()
 assert result['status']!='success' and result['stale']is True

def test_empty_shared_cooldown_is_not_a_second_provider_failure(environment,monkeypatch):
 from data_fetch.agent_context_providers import MacroIndicatorsProvider
 from data_fetch.types import FetchRequest
 from provider_acquisition import observation_kind
 macro,clock,cache,calls=environment
 def fail(*a,**kw):calls.append('failed');raise RuntimeError('provider unavailable')
 monkeypatch.setattr(macro,'_latest_observation',fail);monkeypatch.setattr(macro,'_cpi_yoy_observation',fail)
 p=MacroIndicatorsProvider();request=FetchRequest.from_ticker('3653.TW',force_refresh=True)
 first=p.fetch(request);second=p.fetch(request)
 assert calls==['failed']*3 and first.status==second.status=='unavailable'
 def kind(result):return observation_kind({'source':result.source,'provider':result.provider,'status':result.status,'record_count':result.audit['record_count'],'message':result.audit['message'],'details':result.audit})
 assert kind(first)=='failed_count'
 assert kind(second)=='local_block_count' and second.audit['http_request_count']==0
