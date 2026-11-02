import asyncio
from datetime import datetime,timezone


def test_wrapper_republication_does_not_stop_search_before_eight_distinct_stories(monkeypatch):
    import external_search_providers as search
    from data_fetch.market_sources import ltn_stock_news
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2026,11,2,14,tzinfo=timezone.utc)
    monkeypatch.setattr(search,'datetime',FrozenDatetime)
    monkeypatch.setattr(ltn_stock_news,'fetch_ltn_stock_news',lambda *a,**k:[])
    calls=[]
    def story(i,title=None,url=None,publisher=None):
        return search.SearchResult(title or f'大東電公布營運事件{i}', '公司近期正式營運消息',url or f'https://publisher{i}.example/story',publisher or f'報社{i}','2026-10-26T10:00:00+00:00',provider='google_news_rss')
    first=[story(i)for i in range(6)]
    first += [story(i,title=f'大東電公布營運事件{i} - 報社{i}',url=f'https://news.google.com/rss/articles/{i}',publisher=f'報社{i}')for i in range(2)]
    async def acquire(query,**options):
        calls.append(query)
        return first if len(calls)==1 else [story(6),story(7)]
    monkeypatch.setattr(search,'fetch_web_search_results_async',acquire)
    diagnostics={}
    result=asyncio.run(search.fetch_alternative_search_catalysts_async('1623.TW','大東電',{'official_name':'大東電','allowed_aliases':['大東電']},max_results=8,diagnostics=diagnostics))
    assert len(calls)==2
    assert len(result)==8
    assert diagnostics['quality_status']=='sufficient_candidates'
    duplicates=[r for r in diagnostics['source_record_archive']if r['reason']=='duplicate_recent_story']
    assert len(duplicates)==2
    assert all('news.google.com' in r['record']['link'] for r in duplicates)
