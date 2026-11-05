from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from hashlib import sha256
import asyncio,json,time
import pytest,shared_provider_cache
from provider_correlation import correlation_scope,source_operation
from data_fetch.types import FetchRequest
from data_fetch import delta_press_provider as m
from data_fetch.market_sources import delta_press_evidence as e
from data_fetch.market_sources.delta_press_parse import INDEX,TTL
from delta_press_fixtures import index,article,URL,TEXT
from test_delta_press_evidence import owned_statement
from data_trust import source_record_count
from provider_acquisition import project_acquisition_events

@pytest.fixture
def world(owned_statement,monkeypatch):
    now,owners,batch,data,mk=owned_statement
    clock=SimpleNamespace(time=lambda:now+2,monotonic=time.monotonic)
    monkeypatch.setattr(m,'time',clock);monkeypatch.setattr(e,'time',clock)
    state={'mode':'warm','callbacks':0};bodies={INDEX:index(),URL:article()}
    class NativeBoundary:
        """Synthetic seam; complete archival/replay/owner/project/count remain real."""
        def __init__(self,*a,**kw):self.http_request_count=0;self.process_count=0;self.components=[];self.deadline=time.monotonic()+20
        def allow_attachment(self,r):return URL
        def get(self,url):
            if state.get('fail_url')==url:
                from search_provider_runtime import SourceResponseError
                self.http_request_count+=1;self.process_count+=1
                self.components.append({'url':url,'http_request_sent':True,'http_request_count':1,'cache_hit':False,'http_status':429,'http_status_observed':True,'response_complete':False})
                raise SourceResponseError('rate_limited',status_code=429)
            fresh=state['mode']=='cold'or state['mode']=='index_only'and url==INDEX
            if fresh:
                raw=bodies[url];r=e.native_receipt(raw,url,now+1,e.transport_for(raw))
                owners[e.raw_key(url)]={'value':deepcopy(r),'fetched_at_epoch':now+1,'fresh_until_epoch':now+TTL}
                self.http_request_count+=1;self.process_count+=1
                d={'url':url,'http_request_sent':True,'http_request_count':1,'client_process_started':True,
                  'http_status_observed':True,'http_status':200,'response_complete':True,'cache_hit':False,
                  'response_bytes':len(raw),'response_sha256':sha256(raw).hexdigest()}
            else:r=deepcopy(owners[e.raw_key(url)]['value']);d={'url':url,'http_request_sent':False,'http_request_count':0,'cache_hit':True}
            self.components.append(d);return r
    monkeypatch.setattr(m,'DeltaPressHttp',NativeBoundary)
    def cache(key,callback,**kwargs):
        assert key==e.BATCH_PREFIX+INDEX and kwargs['use_cache']is True and 'force_refresh'not in kwargs
        if state['mode']=='warm':return deepcopy(owners[e.batch_key()]['value']),{'cache_hit':True}
        state['callbacks']+=1
        try:v=callback()
        except RuntimeError:
            if not state.get('stale_failure'):raise
            return deepcopy(owners[e.batch_key()]['value']),{'cache_hit':True,'stale':True,'error_kind':'rate_limited'}
        owners[e.batch_key()]={'value':deepcopy(v),'fetched_at_epoch':now+2,'fresh_until_epoch':now+TTL}
        return v,{'cache_hit':False}
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',cache)
    return now,owners,data,state

def fetch(data,**options):
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    with correlation_scope(replace=True,ticker='2308.TW',fetch_id='unit-provider'),source_operation('recent_catalysts',e.PROVIDER):
        return IssuerNewsProvider().fetch(FetchRequest.from_ticker('2308.TW',**options),{'data':data})

def acquisition(r,now):
    row={'source':r.source,'provider':r.provider,'status':r.status,'record_count':r.audit['record_count'],
      'message':r.audit.get('message',''),'created_at':now+2,'details_json':json.dumps(r.audit)}
    return project_acquisition_events([row],window='last_24h',now=now+2)['sources'][0]

def test_warm_complete_delivery_no_new_acquisition(world):
    now,owners,data,state=world;before=deepcopy((owners,data));r=fetch(data)
    assert r.status=='success'and len(r.value)==1 and r.value[0]['text']==TEXT
    assert r.audit['cache_hit']is True and r.audit['http_request_sent']is False
    assert r.audit['acquisition_record_count']==0 and acquisition(r,now)['fetched_count']==0
    assert (owners,data)==before and state['callbacks']==0
    assert source_record_count('recent_catalysts',{**data,'recent_catalysts':r.value})==1

def test_cold_body_only_one_source_acquisition(world):
    now,owners,data,state=world;state['mode']='cold';r=fetch(data)
    assert r.status=='success'and r.audit['http_request_count']==2 and r.audit['record_count']==1
    assert r.audit['cache_hit']is False and r.audit['acquisition_record_count']==1
    assert acquisition(r,now)['fetched_count']==acquisition(r,now)['fetch_attempts']==1
    assert r.value[0]['full30day_history_verified']is False

def test_fresh_index_and_cached_body_is_not_new_success(world):
    now,owners,data,state=world;state['mode']='index_only';r=fetch(data)
    assert r.status=='success'and r.audit['http_request_count']==1 and r.audit['cache_hit']is True
    assert acquisition(r,now)['fetched_count']==0

def test_record_false_cannot_create_HTTP_owner_or_guard(world,monkeypatch):
    now,owners,data,state=world
    def forbidden(*a,**kw):raise AssertionError('record_false is read-only')
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',forbidden)
    before=deepcopy(owners);r=fetch(data,record_provider_sla=False)
    assert r.status=='success'and r.audit['cache_hit']and before==owners
    owners.pop(e.batch_key());before=deepcopy(owners);r=fetch(data,record_provider_sla=False)
    assert r.status=='unavailable'and r.audit['http_request_sent']is False and before==owners

@pytest.mark.parametrize('options',[{'force_refresh':True},{'skip_optional_http':True}])
def test_force_or_optional_block_does_not_call(world,options):
    _,_,data,state=world;r=fetch(data,**options)
    assert r.status=='unavailable'and r.audit['http_request_sent']is False and state['callbacks']==0

@pytest.mark.parametrize('stale',[True,False])
def test_new_failure_keeps_denominator_even_with_old_batch(world,stale):
    now,owners,data,state=world;state.update(mode='cold',fail_url=URL,stale_failure=stale);r=fetch(data)
    assert r.status=='unavailable'and r.audit['record_count']==0 and r.audit['cache_hit']is False
    assert r.audit['http_request_count']==2 and acquisition(r,now)['failed_count']==1

def test_copied_native_flags_cannot_count_cached_body(world):
    _,_,data,_=world;r=fetch(data);raw=r.value[0]['delta_press_receipt']['originals'][1]
    r.audit.update(cache_hit=False,http_request_sent=True,http_request_count=1,http_process_count=1,event_kind='fetch',acquisition_record_count=1,
      component_statuses={'0':{'url':URL,'http_request_sent':True,'http_status':200,'http_status_observed':True,
      'response_complete':True,'cache_hit':False,'response_sha256':raw['raw_receipt']['raw_response_sha256'],'response_bytes':raw['raw_receipt']['raw_response_bytes']}})
    assert m.guard_delta_result(r,data).status=='unavailable'

def test_source_only_context_kept_and_private_proof_hidden(world):
    from data_fetch.service import StockDataService
    from prompt_evidence import prompt_evidence_copy
    now,owners,data,_=world;before=deepcopy(data)
    r=asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker('2308.TW',record_provider_sla=False),'issuer_news',context={'data':data}))
    assert r.data['company_identity']==data['company_identity']and r.data['quote_type']=='EQUITY'
    assert r.data['recent_catalysts'][0]['text']==TEXT and data==before
    view=prompt_evidence_copy(r.data)
    assert view['recent_catalysts'][0]['text']==TEXT and 'delta_press_receipt'not in json.dumps(view)
    assert 'raw_response_path'not in json.dumps(view)

@pytest.mark.parametrize('change',['wrong_code','wrong_context','absent_context'])
def test_provider_rejects_invalid_context_before_transport(world,change):
    _,owners,data,state=world
    if change=='wrong_code':data['ticker']='2308.TWO'
    elif change=='wrong_context':data['company_identity']['official_name']='泰達電'
    else:data={}
    r=fetch(data);assert r.status=='unavailable'and r.audit['http_request_sent']is False and state['callbacks']==0

def test_single_statement_does_not_waive_general_news_quality(world):
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    _,_,data,_=world;r=fetch(data);rec=r.value[0]
    assert not search_quality_satisfied([SearchResult(rec['title'],rec['text'],rec['link'],rec['source'])],max_results=8)

@pytest.mark.parametrize('context',[None,{}, {'data':{}},{'data':[] }])
def test_source_only_rejects_missing_identity_without_HTTP(context):
    from data_fetch.service import StockDataService
    from fastapi import HTTPException
    with pytest.raises(HTTPException)as error:
        asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker('2308.TW'),'issuer_news',context=context))
    assert error.value.status_code==400

def test_freshness_policy_preserves_exact_proof_and_statement_role(world):
    from news_freshness_policy import apply_news_freshness
    from prompt_evidence import prompt_evidence_copy
    now,_,data,_=world;r=fetch(data);view=deepcopy(data)
    apply_news_freshness(view,records=r.value,cutoff=now+2)
    assert len(view['recent_catalysts'])==1
    assert e.verified_record(view['recent_catalysts'][0],data,now=now+3)=='台達電'
    assert source_record_count('recent_catalysts',view)==1
    public=prompt_evidence_copy(view)['recent_catalysts'][0]
    assert public['text']==TEXT and public['source_role']=='issuer_statement'
    assert public['catalyst_assessment']=='not_assessed'and 'delta_press_receipt'not in public

def test_normal_agent_prompt_keeps_full_body_and_hides_private_proof(world):
    from agent_runtime.prompting import data_for_agent_prompt
    _,_,data,_=world;r=fetch(data);data={**data,'recent_catalysts':r.value,'source_audit':[r.audit]}
    for role in(6,7):
        view=data_for_agent_prompt(role,data)
        encoded=json.dumps(view,ensure_ascii=False)
        assert TEXT in encoded and 'delta_press_receipt'not in encoded
        assert 'private_acquisition_manifest'not in encoded
