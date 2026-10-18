"""Two existing queries may retrieve verified brand news without security codes."""
from pathlib import Path
from datetime import datetime,timezone
from contextlib import asynccontextmanager
from hashlib import sha256
from copy import deepcopy
import asyncio,json,gzip,httpx
import pytest
F=Path(__file__).parent/'fixtures/source_acquisition'
M=json.loads((F/'gogolook_name_only_query_full_20261011.json').read_text());DATA=M['company_data'];NEW=gzip.open(F/'gogolook_name_only_query_full_20261011.xml.gz','rb').read();OLD=gzip.open(F/'gogolook_brand_query_native_20261011.xml.gz','rb').read()
assert len(NEW)==M['bytes']and sha256(NEW).hexdigest()==M['sha256']
NOW=datetime.fromtimestamp(M['retrieved_at'],timezone.utc)

def install(monkeypatch):
    import external_search_providers as search
    from external_search_provider_clients import fetch_provider_results
    from external_search_payloads import parse_news_rss_payload
    import data_fetch.market_sources.ltn_stock_news as ltn
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return NOW.astimezone(tz)if tz else NOW.replace(tzinfo=None)
    # Replayed selection and receipt freshness share the native acquisition
    # clock. Runtime gates still require a newly acquired, <=60s-old receipt.
    monkeypatch.setattr(search,'datetime',Clock)
    monkeypatch.setattr('time.time',lambda:NOW.timestamp())
    calls=[];publisher_calls=[]
    def response(request):
        q=request.url.params['q'];calls.append(q)
        return httpx.Response(200,content=NEW if q=='"Gogolook" when:30d'else OLD,headers={'Content-Type':'application/rss+xml'})
    @asynccontextmanager
    async def client():
        async with httpx.AsyncClient(transport=httpx.MockTransport(response))as c:yield c
    async def direct(c,engine,query,*,max_results,lookback_days):
        assert engine=='google_news_rss'and max_results==20 and lookback_days==30
        return await fetch_provider_results(c,engine,query,max_results=max_results,lookback_days=lookback_days)
    monkeypatch.setattr(search,'async_client',client);monkeypatch.setattr(search,'_provider_order',lambda:['google_news_rss']);monkeypatch.setattr(search,'_provider_configured',lambda _:True);monkeypatch.setattr(search,'_fetch_provider_results',direct)
    monkeypatch.setattr(ltn,'fetch_ltn_stock_news',lambda *a,**k:publisher_calls.append((a,k))or[])
    return calls,publisher_calls

def test_public_search_fills_real_saved_news_gap_from_same_two_query_budget(monkeypatch):
    from external_search_providers import fetch_alternative_search_catalysts_async
    calls,publisher_calls=install(monkeypatch);diagnostics={}
    rows=asyncio.run(fetch_alternative_search_catalysts_async(DATA['ticker'],DATA['company_name'],DATA['company_identity'],company_context=DATA,provider_allowlist={'google_news_rss'},diagnostics=diagnostics))
    assert len(rows)==8 and diagnostics['quality_status']=='sufficient_candidates'
    assert len(calls)==2 and calls[0].startswith('"Gogolook" 6902 when:30d')
    assert calls[1]=='"Gogolook" when:30d'and publisher_calls==[]
    assert diagnostics['search_queries_started']==2
    assert DATA['company_identity']['official_name']=='GOGOLOOK-創'

@pytest.mark.parametrize('field,value',[('ticker','6902.TWO'),('stock_id','6924'),('instrument_type','ETF'),('official_name','其他公司'),('legal_name','別家股份有限公司'),('official_ubn','00000001'),('forbidden_aliases',['Gogolook']),('forbidden_aliases',False)])
def test_conflicting_brand_context_cannot_remove_the_security_code(field,value):
    from company_news_queries import company_news_brand_fallback_query
    data=deepcopy(DATA);data['company_identity'][field]=value
    assert company_news_brand_fallback_query(data)==''

def test_unknown_company_and_already_name_only_bank_query_keep_original_routes():
    from company_news_queries import company_news_brand_fallback_query,company_news_query
    assert company_news_brand_fallback_query({'ticker':'2330.TW','company_name':'台積電','company_identity':{'official_name':'台積電'}})==''
    bank={'ticker':'2845.TW','company_name':'遠東銀','company_identity':{'ticker':'2845.TW','stock_id':'2845','official_name':'遠東銀'}}
    assert company_news_query(bank)=='"遠銀" when:30d'and company_news_brand_fallback_query(bank)==''

@pytest.mark.parametrize('kind',['ETF','UNKNOWN',False,[],{}])
def test_conflicting_root_instrument_type_keeps_the_existing_code_anchor(kind):
    from company_news_queries import company_news_brand_fallback_query
    data=deepcopy(DATA);data['instrument_type']=kind
    assert company_news_brand_fallback_query(data)==''

def test_new_brand_feed_still_needs_original_eight_records_and_three_publishers():
    from external_search_payloads import parse_news_rss_payload
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    from source_content_selection import select_company_records
    records=[{'title':r.title,'summary':r.snippet,'date':r.published_at,'source':r.source,'link':r.link,'source_type':'google_news_rss_search'}for r in parse_news_rss_payload(NEW.decode(),provider='google_news_rss',fallback_source='Google News RSS')[:20]]
    selected,_=select_company_records(records,DATA,cutoff=NOW,lookback_days=30);typed=[SearchResult(r['title'],r['summary'],r['link'],r['source'],r['date'])for r in selected]
    assert len(typed)==8
    assert not search_quality_satisfied(typed[:7],max_results=8,query='Gogolook',lookback_days=30,require_recent=True,cutoff=NOW)
    same=[SearchResult(r.title,r.snippet,'https://one-publisher.example/'+str(i),'One Publisher',r.published_at)for i,r in enumerate(typed[:8])]
    assert not search_quality_satisfied(same,max_results=8,query='Gogolook',lookback_days=30,require_recent=True,cutoff=NOW)

def test_source_only_report_merge_preserves_core_data_and_uses_same_two_queries(monkeypatch):
    from data_fetch.service import StockDataService
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.enrichment_search_providers import AlternativeSearchProvider
    from report_source_refresh import fetch_report_source_data
    calls,publisher_calls=install(monkeypatch);data=deepcopy(DATA);data.update(instrument_type='EQUITY',current_price=123.,revenue_ttm_raw=456000000,financial_currency='TWD',years=['2021','2022','2023','2024','2025'],recent_catalysts=[],social_sentiment=[{'text':'old social'}])
    audits=[{'source':'market_data','provider':'original','status':'success','record_count':1,'fetched_at_epoch':NOW.timestamp()-600},{'source':'financial_statements','provider':'original','status':'success','record_count':5,'fetched_at_epoch':NOW.timestamp()-700}]
    snap={'ticker':DATA['ticker'],'data':data,'source_audit':audits};before=deepcopy(snap)
    service=StockDataService(registry=ProviderRegistry([AlternativeSearchProvider()]));merged=asyncio.run(fetch_report_source_data(snap,'recent_catalysts',service))
    assert len(merged['recent_catalysts'])==8 and len(calls)==2 and calls[1]=='"Gogolook" when:30d'and not publisher_calls
    for k in ('current_price','revenue_ttm_raw','financial_currency','years','social_sentiment','company_identity'):assert merged[k]==data[k]
    assert snap==before and merged['source_audit'][:2]==audits

@pytest.mark.parametrize('root_type',['ETF',False])
def test_provider_preserves_root_type_conflict_for_new_brand_query(monkeypatch,root_type):
    from data_fetch.enrichment_search_providers import AlternativeSearchProvider
    from data_fetch.types import FetchRequest
    calls,_=install(monkeypatch);data=deepcopy(DATA);data['instrument_type']=root_type
    result=asyncio.run(AlternativeSearchProvider().fetch_async(
        FetchRequest.from_ticker(data['ticker']),{'data':data,'free_sources_only':True}))
    assert '"Gogolook" when:30d'not in calls and result.status=='degraded_enrichment'

def test_source_only_root_false_cannot_issue_new_brand_query_or_change_snapshot(monkeypatch):
    from data_fetch.service import StockDataService
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.enrichment_search_providers import AlternativeSearchProvider
    from report_source_refresh import fetch_report_source_data
    from fastapi import HTTPException
    calls,_=install(monkeypatch);data=deepcopy(DATA);data.update(instrument_type=False,current_price=123.,revenue_ttm_raw=456000000,financial_currency='TWD',recent_catalysts=[])
    snap={'ticker':data['ticker'],'data':data,'source_audit':[{'source':'market_data','provider':'original','status':'success','record_count':1,'fetched_at_epoch':NOW.timestamp()-600}]};before=deepcopy(snap)
    with pytest.raises(HTTPException)as error:
        asyncio.run(fetch_report_source_data(snap,'recent_catalysts',StockDataService(registry=ProviderRegistry([AlternativeSearchProvider()]))))
    assert error.value.status_code==502 and '"Gogolook" when:30d'not in calls and snap==before

@pytest.mark.parametrize('context',[None,{**DATA,'ticker':'2254.TW'}])
def test_legacy_or_conflicting_context_keeps_original_code_anchored_queries(monkeypatch,context):
    from external_search_providers import fetch_alternative_search_catalysts_async
    calls,_=install(monkeypatch)
    rows=asyncio.run(fetch_alternative_search_catalysts_async(
        DATA['ticker'],DATA['company_name'],DATA['company_identity'],
        company_context=context,provider_allowlist={'google_news_rss'}))
    assert len(rows)==6 and len(calls)==2 and '"Gogolook" when:30d'not in calls

def test_native_static_shareholder_index_is_archived_without_becoming_recent_news():
    from external_search_payloads import parse_news_rss_payload
    from source_content_selection import select_company_records
    parsed=parse_news_rss_payload(NEW.decode(),provider='google_news_rss',fallback_source='Google News RSS')
    r=next(x for x in parsed if x.source=='TradingView')
    row={'title':r.title,'summary':r.snippet,'date':r.published_at,'source':r.source,'link':r.link}
    before=deepcopy(row);rows,audit=select_company_records([row],DATA,cutoff=NOW,lookback_days=30)
    assert rows==[] and audit['rejected_reason_counts']=={'indexed_non_article_unverified':1}
    assert audit['source_record_archive']==[{'reason':'indexed_non_article_unverified','record':before}]
    assert row==before

def test_public_eight_news_slots_exclude_static_shareholder_index(monkeypatch):
    from external_search_providers import fetch_alternative_search_catalysts_async
    install(monkeypatch)
    rows=asyncio.run(fetch_alternative_search_catalysts_async(DATA['ticker'],DATA['company_name'],DATA['company_identity'],company_context=DATA,provider_allowlist={'google_news_rss'}))
    assert len(rows)==8 and not any(r['source']=='TradingView'and '股東人數'in r['title']for r in rows)

def test_tradingview_editorial_news_retains_existing_selection_path():
    from source_content_selection import select_company_records
    row={'title':'Gogolook 公布營運展望 - TradingView','summary':'Gogolook announces revenue outlook.','date':NOW.isoformat(),'source':'TradingView','link':'https://news.google.com/rss/articles/editorial'}
    rows,audit=select_company_records([row],DATA,cutoff=NOW,lookback_days=30)
    assert len(rows)==1 and audit['rejected_count']==0
