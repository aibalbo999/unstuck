import asyncio
from pathlib import Path
import sys
import external_data_gdelt as g
import fed_policy_transport as f
class Client:
    async def __aenter__(self):return self
    async def __aexit__(self,*a):pass

def setup(monkeypatch,cache=False):
    calls=[]
    monkeypatch.setattr(g,'async_client',lambda:Client())
    monkeypatch.setattr(g,'_cached_gdelt_topics',lambda k:[])
    monkeypatch.setattr(g,'cooldown_state',lambda k:{'error_kind':'rate_limited'})
    monkeypatch.setattr(g,'_gdelt_rate_limited',lambda:False)
    async def rss(*a):return []
    monkeypatch.setattr(g,'_fetch_google_news_rss_fallback',rss)
    def load():calls.append(1);return {'raw':b'unused mock','cache_hit':cache,'fetched_at_epoch':1}
    monkeypatch.setattr(f,'load_policy_feed',load)
    monkeypatch.setattr(f,'policy_topics',lambda p,tag,lookback_days:[{'tag':tag,'source':'Federal Reserve Monetary Policy RSS','headline':'Official policy metadata','url':'https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm','article_body_verified':False}])
    return calls

def test_one_feed_read_for_two_macro_topics(monkeypatch):
    calls=setup(monkeypatch)
    result=asyncio.run(g.fetch_gdelt_international_news_context())
    assert calls==[1] and len(result['topics'])==1
    assert result['_retrieval']['kind']=='fresh_or_mixed'
    assert result['topics'][0]['article_body_verified'] is False

def test_cached_feed_cannot_be_native_success(monkeypatch):
    calls=setup(monkeypatch,cache=True)
    result=asyncio.run(g.fetch_gdelt_international_news_context())
    assert calls==[1] and result['_retrieval']['kind']=='cache_fallback'
    assert result['_retrieval']['fresh_topic_count']==0

def test_existing_rss_success_never_calls_policy_feed(monkeypatch):
    calls=setup(monkeypatch)
    async def rss(*a):return [{'headline':'Existing RSS','url':'https://example.test/news'}]
    monkeypatch.setattr(g,'_fetch_google_news_rss_fallback',rss)
    assert asyncio.run(g.fetch_gdelt_international_news_context())['topics']
    assert calls==[]

def test_sector_news_not_replaced_by_monetary_policy(monkeypatch):
    calls=setup(monkeypatch)
    result=asyncio.run(g.fetch_gdelt_international_news_context('Technology','Semiconductors'))
    assert calls==[] and result['topics']==[]

def test_feed_failure_is_single_attempt_and_preserves_empty(monkeypatch):
    calls=setup(monkeypatch)
    def fail():calls.append(1);raise TimeoutError('policy timeout')
    monkeypatch.setattr(f,'load_policy_feed',fail)
    result=asyncio.run(g.fetch_gdelt_international_news_context())
    assert calls==[1] and not result['topics'] and result['_retrieval']['kind']=='empty'


def test_feed_metadata_never_proves_policy_action_date():
    from policy_event_evidence import policy_event_date_issues
    from fed_policy_metadata import parse_policy_feed
    from datetime import datetime,timezone
    raw=(Path(__file__).parent/'fixtures/fed_monetary_20261031.xml').read_bytes()
    items=parse_policy_feed(raw,tag='macro',now=datetime(2026,10,31,tzinfo=timezone.utc))
    assert len(items)==1
    issues=policy_event_date_issues('聯準會2026年10月28日維持利率不變。',items)
    assert issues and issues[0]['reason_code']=='policy_action_date_unverified'
