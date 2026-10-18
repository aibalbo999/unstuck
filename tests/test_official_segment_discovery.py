from copy import deepcopy
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import asyncio,json,time
import pytest

TODAY=datetime.now(ZoneInfo('Asia/Taipei')).date()
IDENTITIES={'9945':'潤泰新','2535':'達欣工','2546':'根基','5515':'建國','2597':'潤弘',
            '1216':'統一','1229':'聯華','1225':'福懋油','1232':'大統益','1702':'南僑'}
MASTER=[{'stock_id':code,'stock_name':name,'type':'twse','date':TODAY.isoformat(),
         'industry_category':'其他' if code=='9945' else '食品工業' if code in {'1216','1229','1225','1232','1702'} else '建材營造'}for code,name in IDENTITIES.items()]


@pytest.fixture(autouse=True)
def isolate():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache());yield;cache_store.reset_cache_store_for_tests()


def collect(ticker='9945.TW',*,master=None,change=None):
    from data_fetch.market_sources.official_segment_discovery import fetch_segment_discovery,PROFILES
    from hashlib import sha256
    base=Path(__file__).parent/'fixtures/source_acquisition';profile=PROFILES[ticker]
    raw={profile['issuer_url']:(base/f'official_segment_{ticker[:4]}_chain_20261010.html').read_bytes(),
         profile['segment_url']:(base/f'official_segment_{profile["chain"]}_20261010.html').read_bytes()}
    if change=='target':raw[profile['issuer_url']]=raw[profile['issuer_url']].replace(ticker[:4].encode(),b'9999')
    elif change=='group':raw[profile['segment_url']]=raw[profile['segment_url']].replace(profile['group_id'].encode(),b'companyList_9999')
    class Http:
        def __init__(self,deadline):self.components=[];self.http_request_count=0
        def get(self,url):
            self.http_request_count+=1
            self.components.append({'url':url,'fetched_at_epoch':time.time(),'cache_hit':False,'http_request_sent':True})
            return raw[url]
    return fetch_segment_discovery(ticker,MASTER if master is None else master,today=TODAY,http_cls=Http)


@pytest.mark.parametrize('ticker',['9945.TW','1216.TW'])
def test_actual_undated_official_pages_provide_only_segment_discovery(ticker):
    from data_fetch.market_sources.official_segment_discovery import is_segment_discovery_record
    result=collect(ticker)
    assert result['audit']['status']=='success' and len(result['records'])==4
    for r in result['records']:
        assert is_segment_discovery_record(r,ticker)
        assert r['membership_effective_date_verified'] is False
        assert r['business_comparability_verified'] is False and r['numeric_comparability_verified'] is False
        assert r['observation_date_basis']=='original_page_retrieved_at'
        assert 'published_date' not in r and 'date' not in r


@pytest.mark.parametrize('change',['target','group'])
def test_missing_exact_issuer_membership_or_group_does_not_admit_candidates(change):
    result=collect(change=change)
    assert result['records']==[] and result['audit']['status']=='error'


@pytest.mark.parametrize('change',['wrong_name','wrong_market','old','future','conflicting'])
def test_unverified_target_master_does_not_admit_candidates(change):
    master=deepcopy(MASTER)
    if change=='wrong_name':master[0]['stock_name']='其他公司'
    elif change=='wrong_market':master[0]['type']='tpex'
    elif change=='old':master[0]['date']=(TODAY-timedelta(days=8)).isoformat()
    elif change=='future':master[0]['date']=(TODAY+timedelta(days=1)).isoformat()
    else:master.append({**master[0],'stock_name':'不一致'})
    result=collect(master=master)
    assert result['records']==[] and result['audit']['http_request_sent'] is False


@pytest.mark.parametrize('change',['false_bool','changed_peer','changed_scope','changed_source','missing_receipt','wrong_date','missing_file','changed_master'])
def test_changed_saved_candidate_cannot_satisfy_public_fallback_gate(monkeypatch,change):
    from data_fetch.market_sources.official_segment_discovery import is_segment_discovery_record
    from data_fetch.workflow import _sufficient_published_peer_candidates
    from data_fetch.types import ProviderResult
    rows=collect()['records'];r=deepcopy(rows[0])
    if change=='false_bool':r['business_comparability_verified']=0
    elif change=='changed_peer':r['counterparty']['ticker']='2330.TW'
    elif change=='changed_scope':r['comparison_scope']='whole_company'
    elif change=='changed_source':r['source_type']='published_industry_peer_ranking'
    elif change=='missing_receipt':r.pop('source_record_archive')
    elif change=='wrong_date':r['observed_at']=(TODAY+timedelta(days=1)).isoformat()
    elif change=='missing_file':
        def missing(*a):raise OSError('missing')
        monkeypatch.setattr('data_fetch.market_sources.official_segment_discovery.read_response',missing)
    else:r['source_record_archive']['sdk_master_mapping'][0]['stock_name']='其他公司'
    assert not is_segment_discovery_record(r,'9945.TW')
    assert not _sufficient_published_peer_candidates([ProviderResult('peer_discovery','TPEx official segment discovery','success',value=[r,r])],'9945.TW')


def test_public_merge_and_prompt_keep_candidate_scope_and_original_receipts():
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from prompt_builder import format_data_for_prompt
    result=collect();rows=result['records']
    data={'ticker':'9945.TW','company_name':'潤泰新','peer_discovery_results':[]}
    merged=_merge_optional_http_bundle(data,{'official_segment_peer_discovery':rows},refreshed_sources=('peer_discovery',))
    assert len(merged['peer_discovery_results'])==4
    text=format_data_for_prompt(merged);payload,_=json.JSONDecoder().raw_decode(text[text.index('{'):]);public=payload['peer_context']['search_discovery_results']
    assert len(public)==4 and all('source_record_archive' not in r for r in public)
    assert all('source_record_archive' in r for r in merged['peer_discovery_results'])
    assert payload['peer_context']['dynamic_peer_metrics']==[]


def test_registry_and_request_context_market_boundary(monkeypatch):
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import FetchRequest
    from data_fetch.enrichment_search_providers import OfficialSegmentDiscoveryProvider
    name='TPEx official segment discovery';registry=ProviderRegistry()
    assert name in registry.provider_names(FetchRequest.from_ticker('9945.TW'),'peer_discovery')
    assert name in registry.provider_names(FetchRequest.from_ticker('1216.TW'),'peer_discovery')
    for code in ('9945.TWO','1216.TWO','AAPL','2330.TW'):
        assert name not in registry.provider_names(FetchRequest.from_ticker(code),'peer_discovery')
    calls=[]
    monkeypatch.setattr('data_fetch.market_sources.official_segment_discovery.fetch_segment_discovery',lambda *a,**k:calls.append(a))
    p=OfficialSegmentDiscoveryProvider();r=p.fetch(FetchRequest.from_ticker('9945.TW'),{'data':{'ticker':'1216.TW'}})
    assert not calls and r.audit['http_request_sent'] is False and r.audit['record_count']==0


@pytest.mark.parametrize('mode',['published_enough','segment_enough','segment_insufficient','segment_invalid'])
def test_workflow_only_uses_segment_for_gap_and_then_search_for_remaining_gap(monkeypatch,mode):
    from types import SimpleNamespace
    from data_fetch import workflow
    from data_fetch.types import FetchRequest,ProviderResult
    from data_fetch.market_sources.yahoo_peer_ranking import POLICY as YAHOO_POLICY
    result=collect();segment=result['records']
    published=[{'source_type':'published_industry_peer_ranking','selection_policy':YAHOO_POLICY,
                'counterparty':{'ticker':code},'fixture_verified':True}for code in ('2535.TW','2546.TW')]
    # Publisher verification is its own tested boundary; this slice tests route order.
    monkeypatch.setattr('data_fetch.market_sources.yahoo_peer_ranking.is_published_peer_record',lambda r,t:r.get('fixture_verified') is True)
    if mode=='segment_insufficient':segment=segment[:1]
    elif mode=='segment_invalid':
        segment=deepcopy(segment)
        for r in segment:r['membership_effective_date_verified']=True
    names=('Alternative Search','Yahoo Taiwan published industry ranking','TPEx official segment discovery')
    providers=[SimpleNamespace(source='peer_discovery',name=n)for n in names]
    monkeypatch.setattr(workflow,'collect_optional_providers',lambda *a,**k:(providers,{'peer_discovery':True}))
    monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda d,b,**k:d)
    monkeypatch.setattr(workflow,'finalize_data_trust',lambda d:None)
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *a:None)
    calls=[]
    async def fetch(request,batch,context):
        calls.extend(p.name for p in batch);out=[]
        for p in batch:
            rows=published if p.name==names[1] and mode=='published_enough' else segment if p.name==names[2] else []
            status='success' if rows else 'unavailable'
            out.append(ProviderResult('peer_discovery',p.name,status,value=rows,
                       audit={'source':'peer_discovery','provider':p.name,'status':status,'record_count':len(rows)}))
        return out
    monkeypatch.setattr(workflow,'fetch_provider_results',fetch)
    data=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('9945.TW'),None,{'ticker':'9945.TW','source_audit':[]}))
    if mode=='published_enough':
        assert calls==[names[1]]
        skipped=next(a for a in data['source_audit']if a['provider']==names[2])
        assert skipped['event_kind']=='local_block' and skipped['http_request_sent'] is False
    elif mode=='segment_enough':assert calls==[names[1],names[2]]
    else:assert calls==[names[1],names[2],names[0]]


def test_deadline_exhausted_by_final_receipt_revalidation_cannot_publish_success(monkeypatch):
    from data_fetch.market_sources import official_segment_discovery as source
    original=source.is_segment_discovery_record;clock=[100.]
    monkeypatch.setattr(source.time,'monotonic',lambda:clock[0])
    def slow(*a,**k):
        valid=original(*a,**k);clock[0]=114.;return valid
    monkeypatch.setattr(source,'is_segment_discovery_record',slow)
    result=collect()
    assert result['records']==[] and result['audit']['status']=='error'
    assert result['audit']['http_request_sent'] is True


def test_invalid_original_is_cooldown_cached_without_positive_page_ttl(monkeypatch):
    import base64
    from data_fetch.market_sources.official_segment_discovery import SegmentHttp,PROFILES
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    from search_provider_runtime import SourceResponseError
    calls=[]
    def wrong(http,url,diagnostic):
        calls.append(url);http.http_request_count+=1;diagnostic['http_request_sent']=True
        return {'body_b64':base64.b64encode(b'<html>'+b'x'*200+b'</html>').decode()}
    monkeypatch.setattr(IssuerNewsHttp,'_download',wrong)
    for attempt in range(2):
        http=SegmentHttp(time.monotonic()+12)
        with pytest.raises(SourceResponseError):http.get(PROFILES['9945.TW']['issuer_url'])
        assert http.components[0]['cache_hit'] is False
    assert len(calls)==1


def test_invalid_segment_cannot_enter_merge_even_without_a_policy_audit():
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    row=deepcopy(collect()['records'][0]);row['membership_effective_date_verified']=True
    merged=_merge_optional_http_bundle({'ticker':'9945.TW'},{'official_segment_peer_discovery':[row]})
    assert merged['peer_discovery_results']==[]
    assert merged['source_record_archive'][0]['reason']=='incoming_peer_relationship_unverified'
