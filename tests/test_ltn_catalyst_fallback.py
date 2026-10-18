"""Publisher originals fill a verified evidence shortage within the original budget."""
import asyncio
from datetime import datetime,timezone
import sys,types
import pytest
import external_search_providers as search
from external_search_types import SearchResult

DATA={'ticker':'5314.TWO','company_name':'世紀*','quote_type':'EQUITY','exchange':'TWO','company_identity':{'ticker':'5314.TWO','stock_id':'5314','official_name':'世紀*','legal_name':'世紀民生科技股份有限公司','instrument_type':'EQUITY'}}

def test_current_publisher_original_fills_shortage_without_lowering_the_eight_item_gate(monkeypatch):
    stamp=datetime.now(timezone.utc).isoformat();calls=[]
    rows=[SearchResult('世紀民生營收新資料'+str(i),'世紀民生說明公司營運',f'https://publisher{i}.test/story',f'Publisher {i}',stamp,'google_news_rss') for i in range(7)]
    async def web(query,**kwargs):
        return rows
    module=types.ModuleType('data_fetch.market_sources.ltn_stock_news')
    def originals(data,*,deadline,diagnostics,max_records):
        calls.append((data,deadline,max_records));return [{'title':'世紀*企業新聞','summary':'世紀*（5314）公司營運','text':'世紀*（5314）公司營運的完整原文。','date':stamp,'source':'自由財經','link':'https://ec.ltn.com.tw/article/breakingnews/5574307'}]
    module.fetch_ltn_stock_news=originals;monkeypatch.setitem(sys.modules,module.__name__,module);monkeypatch.setattr(search,'fetch_web_search_results_async',web)
    diagnostic={};result=asyncio.run(search.fetch_alternative_search_catalysts_async(DATA['ticker'],DATA['company_name'],DATA['company_identity'],diagnostics=diagnostic))
    assert len(result)==8 and len(calls)==1
    assert calls[0][2]==1
    assert diagnostic['quality_status']=='sufficient_candidates'
    assert any(v.get('text')=='世紀*（5314）公司營運的完整原文。' for v in result)


def test_sufficient_current_evidence_does_not_call_publisher_fallback(monkeypatch):
    stamp=datetime.now(timezone.utc).isoformat()
    async def web(query,**kwargs):
        return [SearchResult('世紀民生營收'+str(i),'世紀民生營運',f'https://publisher{i}.test/story',f'Publisher {i}',stamp) for i in range(8)]
    module=types.ModuleType('data_fetch.market_sources.ltn_stock_news');module.fetch_ltn_stock_news=lambda *a,**k:pytest.fail('unnecessary publisher request')
    monkeypatch.setitem(sys.modules,module.__name__,module);monkeypatch.setattr(search,'fetch_web_search_results_async',web)
    result=asyncio.run(search.fetch_alternative_search_catalysts_async(DATA['ticker'],DATA['company_name'],DATA['company_identity']))
    assert len(result)==8

def test_same_publisher_wrapper_and_original_do_not_become_two_independent_sources():
    from external_search_quality import result_source_key
    stamp=datetime.now(timezone.utc).isoformat()
    wrapper=SearchResult('新聞 - 自由財經','摘要','https://news.google.com/rss/articles/ABC','自由財經',stamp)
    original=SearchResult('新聞','摘要','https://ec.ltn.com.tw/article/breakingnews/5574307','自由財經',stamp)
    assert result_source_key(wrapper)==result_source_key(original)


def test_matching_publisher_original_replaces_same_day_wrapper_instead_of_filling_gate_with_duplicates(monkeypatch):
    stamp=datetime.now(timezone.utc).isoformat();rows=[SearchResult('世紀民生營收','世紀民生營運','https://news.google.com/rss/articles/ABC','自由財經',stamp,'google_news_rss')]
    rows += [SearchResult('世紀民生營收'+str(i),'世紀民生營運',f'https://publisher{i}.test/story',f'Publisher {i}',stamp) for i in range(6)]
    rows[0]=SearchResult('世紀民生營收 - 自由財經',rows[0].snippet,rows[0].link,rows[0].source,stamp,rows[0].provider)
    async def web(query,**kwargs):return rows
    module=types.ModuleType('data_fetch.market_sources.ltn_stock_news')
    module.fetch_ltn_stock_news=lambda *a,**k:[{'title':'世紀民生營收','summary':'世紀*（5314）營收原文','text':'世紀*（5314）營收原文與公司資料。','date':stamp,'source':'自由財經','link':'https://ec.ltn.com.tw/article/breakingnews/5574307'}]
    monkeypatch.setitem(sys.modules,module.__name__,module);monkeypatch.setattr(search,'fetch_web_search_results_async',web)
    diag={};result=asyncio.run(search.fetch_alternative_search_catalysts_async(DATA['ticker'],DATA['company_name'],DATA['company_identity'],diagnostics=diag))
    assert len(result)==7 and diag['quality_status']=='insufficient_candidates'
    assert any(v['reason']=='replaced_by_publisher_original' for v in diag['source_record_archive'])

def test_oversized_raw_cache_epoch_does_not_discard_seven_existing_records(monkeypatch):
    import shared_provider_cache,base64
    from hashlib import sha256
    stamp=datetime.now(timezone.utc).isoformat()
    async def web(query,**kwargs):
        return [SearchResult('世紀民生營收'+str(i),'世紀民生營運',f'https://publisher{i}.test/story',f'Publisher {i}',stamp) for i in range(7)]
    raw=b'public source bytes';monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:({'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()},{'cache_hit':True,'stale':False,'fetched_at_epoch':10**400}))
    monkeypatch.setattr(search,'fetch_web_search_results_async',web)
    result=asyncio.run(search.fetch_alternative_search_catalysts_async(DATA['ticker'],DATA['company_name'],DATA['company_identity']))
    assert len(result)==7
