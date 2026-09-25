from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from data_fetch.types import FetchRequest

def record(title,days=1,link='https://publisher.test/story'):
    return {'title':title,'summary':title,'published_date':(datetime.now(timezone.utc)-timedelta(days=days)).isoformat(),'link':link,'source':'Publisher'}

def test_social_raw_nonempty_is_not_recent_company_evidence(monkeypatch):
    import news_fetchers
    from data_fetch.agent_context_providers import SocialSentimentProvider
    monkeypatch.setattr(news_fetchers,'fetch_google_news_rss',lambda *a,**k:[record('東訊產品測試',days=300),record('無關討論')])
    monkeypatch.setattr(news_fetchers,'fetch_ptt_stock_sentiment',lambda *a,**k:[])
    r=SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('2321.TW'),{'data':{'company_name':'東訊','ticker':'2321.TW'}})
    assert r.status=='degraded_enrichment'
    assert r.audit['raw_count']==6 and r.audit['usable_count']==0
    assert r.value['sample_count']==0
    assert r.audit['rejected_reason_counts']=={'historical':3,'issuer_unverified':3}

def test_free_news_counts_usable_and_retains_rejected_audit(monkeypatch):
    from data_fetch.enrichment_providers import FreeNewsWaterfallProvider
    import external_data_client
    class Client:
        last_news_audit=[]
        def get_news(self,*a,**k):return [record('東訊老新聞',days=300),record('東訊營收',link='https://publisher.test/current')]
    monkeypatch.setattr(external_data_client,'ExternalDataClient',Client)
    r=FreeNewsWaterfallProvider().fetch(FetchRequest.from_ticker('2321.TW'),{'data':{'ticker':'2321.TW','company_name':'東訊'}})
    assert len(r.value)==1 and r.value[0]['title']=='東訊營收'
    assert r.audit['raw_count']==2 and r.audit['usable_count']==1
    assert r.audit['source_record_archive'][0]['record']['title']=='東訊老新聞'

def test_nonempty_unrelated_search_still_expands_and_filters(monkeypatch):
    import external_search_providers as search
    from external_search_types import SearchResult
    calls=[]
    async def fetch(query,**kwargs):
        calls.append(query)
        title='Guardforce AI營收' if len(calls)==1 else '大聯大營收'
        return [SearchResult(title,title,'https://publisher.test/'+str(len(calls)),'Publisher',(datetime.now(timezone.utc)-timedelta(days=1)).isoformat())]
    monkeypatch.setattr(search,'fetch_web_search_results_async',fetch)
    result=asyncio.run(search.fetch_alternative_search_catalysts_async('3702.TW','大聯大',{'official_name':'大聯大'},max_results=2))
    assert len(calls)==2
    assert [r['title'] for r in result]==['大聯大營收']

def test_rejected_archive_is_retained_in_snapshot_but_not_prompt():
    from prompt_evidence import prompt_evidence_copy
    from data_trust_snapshot import build_data_snapshot
    data={'ticker':'2321.TW','source_audit':[{'source_record_archive':[{'record':record('REJECTED_EVIDENCE')}]}]}
    snapshot=build_data_snapshot({'data':data},max_bytes=200000)
    assert 'REJECTED_EVIDENCE' in str(snapshot)
    assert 'REJECTED_EVIDENCE' not in str(prompt_evidence_copy(data))

def test_issuer_gate_does_not_match_url_publisher_or_numeric_substring():
    from source_content_selection import select_company_records
    rows=[record('價格12321上升'),record('其他公司新聞',link='https://publisher.test/東訊?code=2321'),record('東訊合法營收')]
    rows[0]['source']='東訊'; rows[1]['summary']='<a href="https://example.test/東訊">別家公司</a>'
    accepted,audit=select_company_records(rows,{'ticker':'2321.TW','company_name':'東訊'})
    assert [r['title'] for r in accepted]==['東訊合法營收']
    assert audit['rejected_reason_counts']=={'issuer_unverified':2}

def test_cached_news_and_social_are_reselected_without_mutation():
    from copy import deepcopy
    from news_freshness_policy import apply_news_freshness
    data={'ticker':'2321.TW','company_name':'東訊','recent_catalysts':[record('其他公司最新消息')],
          'social_sentiment':{'dcard':[record('東訊舊討論',days=300)],'sample_count':1,'status':'success'}}
    prior=deepcopy(data)
    apply_news_freshness(data)
    assert data['recent_catalysts']==[]
    assert data['news_selection']['identity_rejected_count']==1
    assert data['social_sentiment']['sample_count']==0
    assert data['social_sentiment']['status']!='success'
    assert prior['social_sentiment']['sample_count']==1
    snapshot=deepcopy(data)
    apply_news_freshness(data,cutoff=data['news_selection']['cutoff'])
    assert data==snapshot

def test_identity_only_peers_do_not_count_as_available_metrics():
    from data_trust import source_record_count
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    import data_fetch.market_sources.peers as peers
    from unittest.mock import patch
    value={'peers':[{'ticker':'2801.TW','metrics_status':'unavailable','pe_ttm':None}],
           'audit':{'usable_count':0,'identity_count':1,'coverage_status':'unavailable'}}
    with patch.object(peers,'fetch_dynamic_peer_metrics_with_diagnostics',return_value=value):
        result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('2892.TW'))
    assert result.status=='degraded_enrichment'
    assert result.audit['record_count']==0
    assert source_record_count('dynamic_peer_metrics',{'dynamic_peer_metrics':result.value})==0

def test_direct_prompt_does_not_include_social_rejection_archive():
    from prompt_builder import format_data_for_prompt
    payload={'ticker':'2321.TW','social_sentiment':{'status':'partial','sample_count':0,'source_record_archive':[{'record':record('DO_NOT_USE_REJECTED_SOCIAL')} ]}}
    assert 'DO_NOT_USE_REJECTED_SOCIAL' not in format_data_for_prompt(payload)

def test_cached_unrelated_historical_and_undated_news_are_archived():
    from news_freshness_policy import apply_news_freshness
    from prompt_evidence import prompt_evidence_copy
    unknown = record('UNRELATED_UNDATED', link='https://publisher.test/undated')
    unknown.pop('published_date')
    data = {'ticker':'2321.TW', 'company_name':'東訊',
            'historical_catalysts':[record('UNRELATED_OLD', days=300)],
            'unverified_catalysts':[unknown]}
    apply_news_freshness(data)
    assert len(data['identity_rejected_catalysts']) == 2
    assert data['historical_catalysts'] == data['unverified_catalysts'] == []
    assert 'UNRELATED_' not in str(prompt_evidence_copy(data))

def test_forbidden_identity_alias_cannot_accept_wrong_company():
    from source_content_selection import select_company_records
    data = {'ticker':'1623.TW', 'company_name':'大東電 / 大亞',
            'company_identity':{'official_name':'大東電', 'allowed_aliases':['大東電','大亞'],
                                'forbidden_aliases':['大亞']}}
    rows = [record('大亞營收成長'), record('大東電與大亞營收比較', link='https://publisher.test/comparison')]
    selected, audit = select_company_records(rows, data)
    assert [r['title'] for r in selected] == ['大東電與大亞營收比較']
    assert audit['rejected_reason_counts'] == {'issuer_unverified':1}

def test_cached_ticker_only_context_requires_explicit_issuer_evidence():
    from news_freshness_policy import apply_news_freshness
    data = {'ticker':'2321.TW', 'recent_catalysts':[record('Other company news'),
             record('東訊(2321)營收', link='https://publisher.test/exact')]}
    apply_news_freshness(data)
    assert [r['title'] for r in data['recent_catalysts']] == ['東訊(2321)營收']
    assert data['news_selection']['identity_rejected_count'] == 1
