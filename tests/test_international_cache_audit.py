import asyncio
import json
import httpx
import pytest
import external_data_gdelt as gdelt
import provider_sla
from data_fetch.enrichment_providers import InternationalNewsContextProvider
from data_fetch.types import FetchRequest

CACHED={'headline':'cached article','url':'https://example.test/cached','published_at':'2026-10-29'}
RSS=b'<rss><channel><item><title>Fresh article</title><link>https://example.test/fresh</link><pubDate>Fri, 30 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'
class Client:
 def __init__(self,body=RSS):self.calls=[];self.body=body
 async def get(self,*args,**kw):
  self.calls.append((args,kw));return httpx.Response(200,content=self.body,request=httpx.Request('GET',gdelt.GOOGLE_NEWS_RSS_URL))
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass

@pytest.fixture
def setup(monkeypatch):
 c=Client();monkeypatch.setattr(gdelt,'async_client',lambda:c)
 monkeypatch.setattr(gdelt,'_gdelt_rate_limited',lambda:True)
 monkeypatch.setattr(gdelt,'cooldown_state',lambda key:{'error_kind':'rate_limited'})
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:None)
 return c

def fetch(core_cache=False):
 return asyncio.run(InternationalNewsContextProvider().fetch_async(FetchRequest.from_ticker('2356.TW'),{'data':{'_cache_hit':core_cache}}))


def test_pure_internal_cache_is_not_new_acquisition(setup,monkeypatch):
 monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[CACHED])
 result=fetch(False)
 assert not setup.calls and result.value['topics']
 assert result.audit['cache_hit'] is True
 assert result.audit['fetched_at'] is None
 assert result.audit['cache_origin_unknown'] is True


def test_cached_core_does_not_hide_new_optional_http(setup,monkeypatch):
 monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[])
 result=fetch(True)
 assert len(setup.calls)==2 and result.value['topics']
 assert result.audit['cache_hit'] is False
 assert result.status=='success'


def test_only_cached_content_after_unsuccessful_attempt_preserves_denominator(setup,monkeypatch):
 monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[CACHED] if ':macro:' in key else [])
 setup.body=b'<rss><channel/></rss>'
 result=fetch(False)
 assert len(setup.calls)==1 and result.value['topics']==[CACHED]
 assert result.status=='degraded_enrichment'
 assert result.audit['cache_hit'] is False and result.audit['fetched_at'] is None


def test_mixed_cached_and_new_content_stays_new_acquisition(setup,monkeypatch):
 monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[CACHED] if ':macro:' in key else [])
 result=fetch(False)
 assert len(setup.calls)==1 and len(result.value['topics'])==2
 assert result.status=='success' and result.audit['cache_hit'] is False


def test_new_empty_result_is_not_hidden_by_core_cache_flag(setup,monkeypatch):
 monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[])
 setup.body=b'<rss><channel/></rss>'
 result=fetch(True)
 assert result.status=='degraded_enrichment' and result.audit['cache_hit'] is False


def test_cache_fallback_is_still_a_failed_acquisition_not_a_new_success(setup,monkeypatch,tmp_path):
 from provider_acquisition import get_provider_acquisition_summary
 monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[CACHED] if ':macro:' in key else [])
 setup.body=b'<rss><channel/></rss>'
 result=fetch(False)
 monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'audit.sqlite3'))
 # Use original database writer, not the no-op transport fixture.
 ORIGINAL_RECORD([result.audit])
 row,=get_provider_acquisition_summary()['sources']
 assert row['fetched_count']==0 and row['fetch_attempts']==1 and row['degraded_count']==1

ORIGINAL_RECORD=provider_sla.record_source_audit_entries


def test_source_exception_is_not_hidden_by_core_cache(setup,monkeypatch):
 def fail():raise ValueError('invalid source configuration')
 monkeypatch.setattr(gdelt,'async_client',fail)
 result=fetch(True)
 assert result.status=='error' and result.audit['cache_hit'] is False


def test_pure_cache_does_not_refresh_existing_ttl_or_content(setup,monkeypatch):
 import copy
 from types import SimpleNamespace
 import cache_store,cache_backends
 from cache_backends import InMemoryCache
 clock=[1000.0]
 monkeypatch.setattr(cache_backends,'time',SimpleNamespace(time=lambda:clock[0]))
 cache_store.set_cache_backend(InMemoryCache())
 try:
  keys=[gdelt._gdelt_topic_cache_key(tag,query,7,3) for tag,query in list(gdelt._topic_queries_for_context('','').items())[:2]]
  original={'topics':[copy.deepcopy(CACHED)]}
  for key in keys:cache_store.set_cache_json(key,original,ttl_seconds=600)
  clock[0]=1300
  result=fetch(False)
  assert result.audit['cache_hit'] is True and not setup.calls
  assert all(cache_store.get_cache_json(key)==original for key in keys)
  clock[0]=1601
  assert all(cache_store.get_cache_json(key) is None for key in keys)
 finally:cache_store.reset_cache_store_for_tests()


def test_existing_failure_denominator_survives_pure_cache_result(setup,monkeypatch,tmp_path):
 from provider_acquisition import get_provider_acquisition_summary
 monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'audit.sqlite3'))
 ORIGINAL_RECORD([{'source':'international_news_context','provider':'GDELT / Google News RSS','status':status,'record_count':count} for status,count in [('success',2),('error',0)]])
 before,=get_provider_acquisition_summary()['sources']
 monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[CACHED])
 result=fetch(False);ORIGINAL_RECORD([result.audit])
 after,=get_provider_acquisition_summary()['sources']
 for field in ['fetched_count','failed_count','fetch_attempts','nonempty_rate']:assert after[field]==before[field]
 assert after['failed_count']==1 and after['nonempty_rate']==.5 and after['fresh_cache_count']==1
