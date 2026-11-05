from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from hashlib import sha256
import asyncio,json,time
import pytest
import shared_provider_cache
from provider_correlation import correlation_scope,source_operation
from data_fetch.types import FetchRequest,ProviderResult
from data_fetch import caa_operating_provider as module
from data_fetch.market_sources import caa_operating_evidence as evidence
from data_fetch.market_sources.caa_operating_parse import INDEX,DIRECTORY,TTL,select_dataset
from data_trust import source_record_count
from provider_acquisition import project_acquisition_events
from test_caa_operating_evidence import owned_dataset
from caa_operating_fixtures import index_page,directory,ods

@pytest.fixture
def world(owned_dataset,monkeypatch):
    now,owners,batch,data,mk=owned_dataset
    clock=SimpleNamespace(time=lambda:now+2,monotonic=time.monotonic)
    monkeypatch.setattr(module,'time',clock);monkeypatch.setattr(evidence,'time',clock)
    state={'mode':'warm','callbacks':0};bodies={INDEX:index_page(),DIRECTORY:directory(),'https://www.caa.gov.tw/FileAtt.ashx?lang=1&id=41753':ods()}
    class NativeBoundary:
        """Synthetic transport seam; all archive/owner/project validators remain real."""
        def __init__(self,*a,**kw):self.http_request_count=0;self.process_count=0;self.components=[];self.deadline=time.monotonic()+20
        def allow_attachment(self,r):return select_dataset(bodies[INDEX],date(2026,11,5))['url']
        def get(self,url):
            if state.get('fail_url')==url:
                from search_provider_runtime import SourceResponseError
                self.http_request_count+=1;self.process_count+=1
                self.components.append({'url':url,'http_request_sent':True,'http_request_count':1,'cache_hit':False,'http_status':429,'http_status_observed':True,'response_complete':False})
                raise SourceResponseError('rate_limited',status_code=429)
            fresh=state['mode']=='cold'or state['mode']=='metadata'and url==INDEX
            if fresh:
                raw=bodies[url];r=evidence.native_receipt(raw,url,now+1,evidence.transport_for(raw))
                owners[evidence.raw_key(url)]={'value':deepcopy(r),'fetched_at_epoch':now+1,'fresh_until_epoch':now+TTL}
                self.http_request_count+=1;self.process_count+=1
                d={'url':url,'http_request_sent':True,'http_request_count':1,'client_process_started':True,
                  'http_status_observed':True,'http_status':200,'response_complete':True,'cache_hit':False,
                  'response_bytes':len(raw),'response_sha256':sha256(raw).hexdigest()}
            else:r=deepcopy(owners[evidence.raw_key(url)]['value']);d={'url':url,'http_request_sent':False,'http_request_count':0,'cache_hit':True}
            self.components.append(d);return r
    monkeypatch.setattr(module,'AirlineOperatingHttp',NativeBoundary)
    def cache(key,callback,**kwargs):
        assert key==evidence.BATCH_PREFIX+INDEX and kwargs['use_cache']is True and 'force_refresh'not in kwargs
        if state['mode']=='warm':return deepcopy(owners[evidence.batch_key()]['value']),{'cache_hit':True}
        state['callbacks']+=1
        try:v=callback()
        except RuntimeError:
            if not state.get('stale_failure'):raise
            return deepcopy(owners[evidence.batch_key()]['value']),{'cache_hit':True,'stale':True,'error_kind':'rate_limited'}
        owners[evidence.batch_key()]={'value':deepcopy(v),'fetched_at_epoch':now+2,'fresh_until_epoch':now+TTL}
        return v,{'cache_hit':False}
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',cache)
    return now,owners,data,state

def fetch(data,**options):
    with correlation_scope(replace=True,ticker='2610.TW',fetch_id='unit-provider'),source_operation('alternative_data',evidence.PROVIDER):
        return module.AirlineOperatingMetricsProvider().fetch(FetchRequest.from_ticker('2610.TW',**options),{'data':data})

def acquisition(result,now):
    row={'source':'alternative_data','provider':result.provider,'status':result.status,'record_count':result.audit['record_count'],
      'message':result.audit.get('message',''),'created_at':now+2,'details_json':json.dumps(result.audit)}
    return project_acquisition_events([row],window='last_24h',now=now+2)['sources'][0]

def test_warm_projection_one_fact_zero_new_acquisition(world):
    now,owners,data,state=world;before=deepcopy((owners,data));r=fetch(data)
    assert r.status=='success'and source_record_count('alternative_data',{**data,'alternative_data':r.value})==1
    assert r.audit['cache_hit']is True and r.audit['http_request_sent']is False and r.audit['acquisition_record_count']==0
    assert r.value['operating_metrics_official']['fetched_at_epoch']==now
    assert acquisition(r,now)['fetched_count']==0 and state['callbacks']==0 and (owners,data)==before

def test_cold_complete_metrics_only_one_source_success(world):
    now,owners,data,state=world;state['mode']='cold';r=fetch(data)
    assert r.status=='success'and r.audit['http_request_count']==3 and r.audit['record_count']==1
    assert r.audit['cache_hit']is False and r.audit['acquisition_record_count']==1
    stats=acquisition(r,now);assert stats['fetched_count']==stats['fetch_attempts']==1
    assert r.value['status']=='partial'
    assert 'current_open_job_count'not in r.value or r.value['current_open_job_count']is None

def test_new_metadata_HTTP_with_cached_ODS_is_never_new_metrics_success(world):
    now,owners,data,state=world;state['mode']='metadata';r=fetch(data)
    assert r.status=='success'and r.audit['http_request_count']==1 and r.audit['http_request_sent']is True
    assert r.audit['cache_hit']is True and r.audit['acquisition_record_count']==0
    assert acquisition(r,now)['fetched_count']==0

def test_record_false_is_read_only_even_missing_owner(world,monkeypatch):
    now,owners,data,state=world
    def forbidden(*a,**kw):raise AssertionError('unrecorded call must not use shared_fetch/write cache or HTTP')
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',forbidden)
    r=fetch(data,record_provider_sla=False);assert r.status=='success'and r.audit['cache_hit']
    owners.pop(evidence.batch_key());before=deepcopy(owners);r=fetch(data,record_provider_sla=False)
    assert r.status=='unavailable'and r.audit['http_request_sent']is False and owners==before

@pytest.mark.parametrize('option',[{'force_refresh':True},{'skip_optional_http':True}])
def test_non_normal_mode_does_not_acquire(world,option):
    _,_,data,state=world;r=fetch(data,**option)
    assert r.status=='unavailable'and r.audit['http_request_sent']is False and state['callbacks']==0

def test_source_only_route_preserves_identity_and_job_only_contract(world,monkeypatch):
    from data_fetch.service import StockDataService
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    now,owners,data,state=world
    result=asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker('2610.TW',record_provider_sla=False),'airline_operating_metrics',context={'data':data}))
    assert result.data['company_identity']==data['company_identity']and result.data['alternative_data']['operating_metrics_official']['ticker']=='2610.TW'
    seen=[]
    def jobs(self,request,context):
        seen.append(context.get('_alternative_job_only'));return ProviderResult('alternative_data',self.name,'unavailable',value={},audit={'source':'alternative_data','provider':self.name,'status':'unavailable','record_count':0,'http_request_sent':False})
    monkeypatch.setattr(AlternativeJobOpeningsProvider,'fetch',jobs)
    asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker('2610.TW',record_provider_sla=False),'alternative_data',context={'data':data}))
    assert seen==[True]

def test_operating_payload_cannot_satisfy_job_refresh(world):
    from alternative_source_refresh import valid_alternative_receipt
    _,_,data,_=world;r=fetch(data)
    audit={**r.audit,'provider':'104 & 1111 job openings'}
    assert not valid_alternative_receipt(r.value,audit,data,require_fetch_id=False)

@pytest.mark.parametrize('status',[401,402,403,429])
def test_prior_access_refusal_never_triggers_fallback(world,monkeypatch,status):
    _,_,data,_=world
    old=ProviderResult('alternative_data','104 & 1111 job openings','unavailable',value={},audit={
      'http_status':status,'http_status_observed':True,'status':'unavailable','record_count':0})
    def forbidden(*a,**kw):raise AssertionError('refusal cannot trigger alternative source')
    monkeypatch.setattr(module.AirlineOperatingMetricsProvider,'fetch',forbidden)
    assert module.maybe_operating_fallback(FetchRequest.from_ticker('2610.TW'),{'data':data},old)is old

def test_accepted_jobs_are_not_replaced_or_refetched(world,monkeypatch):
    _,_,data,_=world
    old=ProviderResult('alternative_data','104 & 1111 job openings','success',value={'job_openings_104':{'status':'success','job_count':2}},audit={'status':'success','record_count':1})
    def forbidden(*a,**kw):raise AssertionError('valid jobs must retain priority')
    monkeypatch.setattr(module.AirlineOperatingMetricsProvider,'fetch',forbidden)
    assert module.maybe_operating_fallback(FetchRequest.from_ticker('2610.TW'),{'data':data},old)is old

def test_empty_job_attempt_and_input_are_preserved_when_fallback_succeeds(world):
    _,_,data,_=world;before=deepcopy(data)
    audit={'source':'alternative_data','provider':'104 & 1111 job openings','status':'degraded_enrichment','record_count':0,'http_request_sent':True,'http_request_count':1,'cache_hit':False,'fetched_at_epoch':123.0}
    old=ProviderResult('alternative_data','104 & 1111 job openings','degraded_enrichment',value={'status':'unavailable','job_openings_104':{'status':'unavailable','job_count':None}},audit=deepcopy(audit))
    with correlation_scope(replace=True,ticker='2610.TW',fetch_id='unit-fallback'),source_operation('alternative_data','104 & 1111 job openings'):
        r=module.maybe_operating_fallback(FetchRequest.from_ticker('2610.TW'),{'data':data},old)
    assert r.status=='success'and r.audit['related_entries'][0]==audit
    assert r.value['job_openings_104']==old.value['job_openings_104']and data==before

def test_prompt_routing_replays_before_hiding_private_envelope(world):
    from agent_runtime.prompting import data_for_agent_prompt,_verification_data_for_agent
    from prompt_builder import format_data_for_prompt
    _,_,data,_=world;r=fetch(data);data={**data,'alternative_data':r.value,'source_audit':[r.audit]};before=deepcopy(data)
    for role in(1,5,6,7,12,13,14,16,18,19,21):
        view=data_for_agent_prompt(role,data);observation=view['alternative_data']['operating_metrics_official']
        assert observation['year_to_date']['frequency']=='year_to_date'and observation['monthly_history'][0]['values']['cargo_tonnes']['unit']=='公噸'
        assert 'caa_operating_receipt'not in json.dumps(view)
    for role in(20,22,23,24):assert 'alternative_data'not in data_for_agent_prompt(role,data)
    server=_verification_data_for_agent(5,data);encoded=format_data_for_prompt(server,compact_json=True)
    payload=json.loads(encoded.split('【財務資料 JSON】\n',1)[1].split('\n\n【使用規則】',1)[0])
    assert payload['agent_context']['alternative_data']['operating_metrics_official']['year']==2026
    assert 'caa_operating_receipt'not in encoded and data==before

def test_public_flag_is_not_routed_to_new_roles(world):
    from agent_runtime.prompting import data_for_agent_prompt
    _,_,data,_=world;fake={**data,'alternative_data':{'operating_metrics_official':{'ticker':'2610.TW','response_complete':True}}}
    assert source_record_count('alternative_data',fake)==0 and 'alternative_data'not in data_for_agent_prompt(5,fake)

@pytest.mark.parametrize('stale',[False,True])
def test_new_failed_request_is_not_hidden_by_retained_batch(world,stale):
    now,owners,data,state=world;state.update(mode='cold',fail_url=DIRECTORY,stale_failure=stale)
    r=fetch(data)
    assert r.status=='unavailable'and r.audit['http_request_count']==2 and r.audit['http_request_sent']is True
    assert r.audit['cache_hit']is False and r.audit['record_count']==0
    stats=acquisition(r,now);assert stats['failed_count']==1 and stats['fetched_count']==0

def test_copied_public_flags_cannot_turn_old_ODS_into_new_HTTP(world):
    now,owners,data,state=world;r=fetch(data);v=deepcopy(r)
    raw=v.value['operating_metrics_official']['caa_operating_receipt']['originals'][2]
    v.audit.update(cache_hit=False,http_request_sent=True,http_request_count=1,http_process_count=1,event_kind='fetch',acquisition_record_count=1,
      component_statuses={'0':{'url':raw['url'],'http_request_sent':True,'http_status':200,'http_status_observed':True,
      'response_complete':True,'cache_hit':False,'response_sha256':raw['raw_receipt']['raw_response_sha256'],'response_bytes':raw['raw_receipt']['raw_response_bytes']}})
    assert module.guard_operating_result(v,data).status=='unavailable'

def test_report_checks_named_monthly_passengers_against_complete_originals(world):
    from evidence_exit_gate import evaluate_report_evidence
    _,_,data,_=world;r=fetch(data)
    text='民航局 華航 2026年9月 全球旅客人數：1 人。'
    checked=evaluate_report_evidence(text,{'data':{**data,'alternative_data':r.value}})
    assert checked['claim_count']==1 and checked['verified_count']==1

@pytest.mark.parametrize('text,status',[
 ('民航局 華航 2026年1至9月累計 全球旅客人數：9 人。','verified'),
 ('民航局 華航 2026年9月 全球載客率：50.00 %。','verified'),
 ('民航局 華航 2026年9月 全球貨運噸數（含郵件、貨物及行李）：100 公噸。','verified'),
 ('民航局 華航 2026年9月 全球載貨率：50.00 %。','verified'),
 ('民航局 華航 2026年9月 全球旅客人數：9 人。','mismatch'),
 ('民航局 華航 2026年1至9月累計 全球旅客人數：1 人。','mismatch'),
 ('民航局 華航 2026年9月 全球載客率：50.01 %。','mismatch'),
 ('民航局 華航 2025年9月 全球旅客人數：1 人。','unverifiable'),
 ('民航局 長榮航 2026年9月 全球旅客人數：1 人。','unverifiable'),
 ('民航局 華航集團 2026年9月 全球旅客人數：1 人。','unverifiable'),
 ('民航局 華航 2026年9月 國際旅客人數：1 人。','unverifiable'),
 ('民航局 華航 2026年9月 全球旅客人數：1 千人。','unverifiable'),
 ('民航局 華航 2026年9月 全球貨運噸數：100 公噸。','unverifiable'),
 ('民航局 華航 2026年1至9月 全球旅客人數：9 人。','unverifiable'),
 ('民航局 華航 2026年9月累計 全球旅客人數：9 人。','unverifiable'),
 ('民航局 華航 全球旅客人數：1 人。','unverifiable'),
 ('民航局 華航 2026年9月 全球旅客人數：1 人，證明未來營收增加。','unverifiable'),
])
def test_report_period_unit_precision_and_inference_boundaries(world,text,status):
    from evidence_exit_gate import evaluate_report_evidence
    _,_,data,_=world;r=fetch(data)
    checked=evaluate_report_evidence(text,{'data':{**data,'alternative_data':r.value}})
    assert checked['claim_count']==1 and checked['sampled_claims'][0]['status']==status

@pytest.mark.parametrize('change',['flags','missing_original','refresh_without_analysis'])
def test_report_cannot_adopt_uncaptured_refreshed_or_incomplete_operating_data(world,change):
    from evidence_exit_gate import evaluate_report_evidence
    from runtime_paths import current_runtime_paths
    _,_,data,_=world;r=fetch(data);snapshot={'data':{**data,'alternative_data':r.value}}
    if change=='flags':r.value['operating_metrics_official'].pop('caa_operating_receipt')
    elif change=='refresh_without_analysis':snapshot['refreshed_without_analysis_rerun']=True
    else:
        digest=r.value['operating_metrics_official']['original_sha256']['ods']
        (current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz')).unlink()
    checked=evaluate_report_evidence('民航局 華航 2026年9月 全球旅客人數：1 人。',snapshot)
    assert checked['claim_count']==1 and checked['verified_count']==0 and checked['unverifiable_count']==1

def test_operating_extractor_does_not_change_unrelated_claims_or_read_code_blocks():
    from evidence_airline_operating_claims import extract_operating_claims
    old=[{'id':7,'line_number':5,'label':'營收','reported_value':100}]
    assert extract_operating_claims('EPS：2 元。',old)is old
    assert extract_operating_claims('```\n民航局 華航 2026年9月 全球旅客人數：1 人。\n```',old)is old
