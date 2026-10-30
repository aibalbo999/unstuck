"""RSS candidate truncation must not hide issuer-qualified evidence already read."""
import asyncio,json
from contextlib import asynccontextmanager
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from data_fetch.service import StockDataService
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.enrichment_search_providers import AlternativeSearchProvider
from external_search_types import SearchResult
from test_report_recent_catalyst_source_refresh import setup,run
from test_report_refresh_acquisition_audit import events


def install(monkeypatch,*,valid=8,publishers=3,provider='google_news_rss'):
    import external_search_providers as search
    date=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat();calls=[]
    wrong=[SearchResult(f'其他公司營收展望{i}','其他公司的業績資訊',f'https://other.example/{i}','other',date,provider=provider)for i in range(8)]
    right=[SearchResult(f'精誠營收展望{i}','精誠公布最新營運與展望。',f'https://news{i%publishers}.example/{i}',f'publisher{i%publishers}',date,provider=provider)for i in range(valid)]
    @asynccontextmanager
    async def client():yield object()
    async def fetch(client,engine,query,*,max_results,lookback_days):
        calls.append((engine,max_results));return [*wrong,*right][:max_results]
    monkeypatch.setattr(search,'async_client',client)
    monkeypatch.setattr(search,'_provider_order',lambda:[provider])
    monkeypatch.setattr(search,'_provider_configured',lambda engine:True)
    monkeypatch.setattr(search,'_fetch_provider_results',fetch)
    return calls


def test_public_news_repair_finds_eight_qualified_records_after_wrong_issuer_head_eight(tmp_path,monkeypatch):
    calls=install(monkeypatch);storage,name,keys,old,_fake,_=setup(monkeypatch)
    service=StockDataService(registry=ProviderRegistry([AlternativeSearchProvider()]))
    assert run(tmp_path,storage,name,service)['success']is True
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert len(saved['data']['recent_catalysts'])==8 and saved['data']['news_selection']['publisher_count']==3
    assert calls==[('google_news_rss',20)]  # One existing query suffices; no extra HTTP.
    assert saved['analysis_evidence']==old['analysis_evidence']and storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert len(events())==1 and events()[0]['status']=='success'and events()[0]['record_count']==8


@pytest.mark.parametrize('valid,publishers',[(7,3),(8,1)])
def test_more_candidates_do_not_lower_original_eight_or_publisher_gate(tmp_path,monkeypatch,valid,publishers):
    calls=install(monkeypatch,valid=valid,publishers=publishers);storage,name,keys,_old,_fake,_=setup(monkeypatch)
    before=storage.get_report(keys.data_key).content;service=StockDataService(registry=ProviderRegistry([AlternativeSearchProvider()]))
    with pytest.raises(HTTPException)as error:run(tmp_path,storage,name,service)
    assert error.value.status_code==502 and storage.get_report(keys.data_key).content==before
    assert len(calls)==2 and all(size==20 for _,size in calls)
    assert len(events())==1 and events()[0]['status']!='success'


@pytest.mark.parametrize('provider,recent,context',[('brave',True,True),('google_news_rss',False,False),('google_news_rss',True,False)])
def test_other_provider_and_unscoped_search_request_sizes_remain_unchanged(monkeypatch,provider,recent,context):
    calls=install(monkeypatch,provider=provider)
    import external_search_providers as search
    asyncio.run(search.fetch_web_search_results_async('精誠',max_results=8,require_recent=recent,
        company_context={'ticker':'6214.TW','company_name':'精誠'}if context else None))
    assert calls and all(size==8 for _,size in calls)
