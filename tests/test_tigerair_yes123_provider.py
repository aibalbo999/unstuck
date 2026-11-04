"""Normal free-source assembly, immutable source cadence and merge contract."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
import json

import pytest
from test_tigerair_yes123_evidence import bound


def setup(monkeypatch):
    e,now,owners,issuer,data,jobs=bound(monkeypatch)
    monkeypatch.setattr(e.time,'time',lambda:now)
    return e,now,owners,issuer,data,jobs


@pytest.mark.parametrize('saved_label',[False,True])
def test_normal_job_provider_and_source_only_guard_replay_all_originals(saved_label,monkeypatch):
    from data_fetch import tigerair_yes123_provider as p
    from data_fetch.market_sources import official_company_legal_name as master
    from data_fetch.market_sources.tigerair_yes123_transport import TigerairCareersHttp
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count
    from alternative_source_refresh import guard_alternative_result
    import shared_provider_cache
    e,now,owners,issuer,data,jobs=setup(monkeypatch);calls=[]
    if saved_label:
        data['company_identity']['official_name']='台灣虎航-創'
        data['company_identity']['english_names']=['Tigerair Taiwan Co., Ltd.']
        data['company_name']='台灣虎航-創 / Tigerair Taiwan Co., Ltd.'
    monkeypatch.setattr(master,'get_official_legal_name',lambda *a:issuer)
    receipts=jobs['source_record_archive']['receipts'];byurl={r['url']:r for r in receipts}
    def read(self,url):
        calls.append(url);self.http_request_count+=1
        self.components.append({'cache_hit':False,'http_request_sent':True,'http_status':200})
        return deepcopy(byurl[url])
    monkeypatch.setattr(TigerairCareersHttp,'read',read)
    saved=[]
    def shared(key,fetch,**kwargs):
        assert key.startswith('optional-context:tigerair-yes123:v1:') and kwargs['use_cache']is True
        assert 'force_refresh'not in kwargs
        if not saved:saved.append(fetch());assert 1780<kwargs['result_ttl'](saved[0])<=1800
        return deepcopy(saved[0]),{'cache_hit':len(calls)>4,'stale':False}
    # This synthetic cache seam explicitly changes the second cache marker.
    hits=[False,True]
    def cached(key,fetch,**kwargs):
        payload,meta=shared(key,fetch,**kwargs);meta['cache_hit']=hits.pop(0);return payload,meta
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',cached)
    monkeypatch.setattr(AlternativeJobOpeningsProvider,'_fetch_uncached',lambda *a:pytest.fail('positive portal sample fell through'))
    request=FetchRequest.from_ticker(e.TICKER,force_refresh=True);before=asdict(request)
    first=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
    warm=AlternativeJobOpeningsProvider().fetch(request,{'data':data})
    assert asdict(request)==before and len(calls)==4
    assert first.status==warm.status=='success'
    assert first.audit['record_count']==source_record_count('alternative_data',{**data,'alternative_data':first.value})==1
    assert warm.audit['http_request_count']==0 and warm.audit['http_request_sent']is False and warm.audit['cache_hit']is True
    assert warm.audit['fetched_at_epoch']==first.audit['fetched_at_epoch']==jobs['fetched_at_epoch']
    assert guard_alternative_result(first,data).status==guard_alternative_result(warm,data).status=='success'
    from alternative_source_refresh import valid_alternative_receipt
    changed={**first.audit,'fetched_at_epoch':first.audit['fetched_at_epoch']+1}
    assert not valid_alternative_receipt(first.value,changed,data,require_fetch_id=False)
    assert not valid_alternative_receipt(first.value,{**first.audit,'actual_provider':'other'},data,require_fetch_id=False)
    from prompt_builder import format_data_for_prompt
    text=format_data_for_prompt({**data,'alternative_data':first.value})
    assert '合成測試工程職務'in text and '平台更新'in text
    assert 'raw_response_path'not in text and 'metadata_manifest'not in text
    assert first.value['job_openings_yes123']['job_count']is None


@pytest.mark.parametrize('change',[
    lambda d:d.update(company_name='華航'),lambda d:d.update(quote_type='ETF'),
    lambda d:d['company_identity'].update(official_ubn='12345678')])
def test_conflicting_context_never_loads_new_source_cache(change,monkeypatch):
    from data_fetch.tigerair_yes123_provider import tigerair_context_result
    from data_fetch.types import FetchRequest
    import shared_provider_cache
    e,now,owners,issuer,data,jobs=setup(monkeypatch);change(data)
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:pytest.fail('invalid context touched cache'))
    assert tigerair_context_result(FetchRequest.from_ticker(e.TICKER),{'data':data})is None


def test_expired_original_outer_cache_is_rejected_without_reacquisition(monkeypatch):
    from data_fetch import tigerair_yes123_provider as p
    from data_fetch.types import FetchRequest,ProviderResult
    import shared_provider_cache
    e,now,owners,issuer,data,jobs=setup(monkeypatch)
    payload=asdict(ProviderResult('alternative_data',p.CANONICAL_PROVIDER,'success',
        value={'company_legal_name_evidence':issuer,'job_openings_yes123':jobs},
        audit={'status':'success','record_count':1,'fetched_at_epoch':jobs['fetched_at_epoch']}))
    monkeypatch.setattr(e.time,'time',lambda:jobs['fetched_at_epoch']+1800)
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:(deepcopy(payload),{'cache_hit':True}))
    result=p.tigerair_context_result(FetchRequest.from_ticker(e.TICKER),{'data':data})
    assert result.status=='unavailable'and result.audit['record_count']==0
    assert result.audit['http_request_count']==0 and result.audit['http_request_sent']is False


def test_portal_failure_is_preserved_when_generic_fallback_runs(monkeypatch):
    from data_fetch import tigerair_yes123_provider as p
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest,ProviderResult
    from alternative_source_refresh import record_related_alternative_attempts
    import provider_sla
    failure=ProviderResult('alternative_data',p.CANONICAL_PROVIDER,'unavailable',value={},audit={
        'source':'alternative_data','status':'unavailable','record_count':0,'http_request_sent':True,'http_status':429})
    monkeypatch.setattr(p,'tigerair_context_result',lambda *a:deepcopy(failure))
    monkeypatch.setattr(AlternativeJobOpeningsProvider,'_fetch_uncached',lambda *a:ProviderResult(
        'alternative_data',p.CANONICAL_PROVIDER,'unavailable',value={'retained':'fallback'},audit={}))
    result=AlternativeJobOpeningsProvider().fetch(FetchRequest.from_ticker('6757.TW'))
    child,=result.audit['related_entries'];assert child['provider']==p.PROVIDER and child['http_status']==429
    rows=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda x:rows.extend(x))
    record_related_alternative_attempts(result);assert rows==[child]


def test_skip_optional_does_not_enter_portal(monkeypatch):
    from data_fetch import tigerair_yes123_provider as p
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest,ProviderResult
    monkeypatch.setattr(p,'tigerair_context_result',lambda *a:pytest.fail('skip_optional entered source'))
    monkeypatch.setattr(AlternativeJobOpeningsProvider,'_fetch_uncached',lambda *a:ProviderResult('alternative_data','fallback','unavailable'))
    assert AlternativeJobOpeningsProvider().fetch(FetchRequest.from_ticker('6757.TW',skip_optional_http=True)).provider=='fallback'


def test_live_legacy_context_is_not_bypassed_by_new_source_namespace(monkeypatch):
    from data_fetch.tigerair_yes123_provider import tigerair_context_result
    from data_fetch.types import FetchRequest
    import shared_provider_cache
    e,now,owners,issuer,data,jobs=setup(monkeypatch);seen=[]
    def peek(key):
        seen.append(key);return {'status':'unavailable','value':{}},{'cache_hit':True}
    monkeypatch.setattr(shared_provider_cache,'peek_fresh_shared',peek)
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:pytest.fail('valid legacy context bypassed'))
    assert tigerair_context_result(FetchRequest.from_ticker(e.TICKER),{'data':data})is None
    assert len(seen)==1 and seen[0].startswith('optional-context:v3:')


def test_legacy_negative_cache_cooldown_is_not_bypassed(monkeypatch):
    from data_fetch.tigerair_yes123_provider import tigerair_context_result
    from data_fetch.types import FetchRequest
    import shared_provider_cache,cache_store
    e,now,owners,issuer,data,jobs=setup(monkeypatch)
    monkeypatch.setattr(shared_provider_cache,'peek_fresh_shared',lambda *a:(None,{'cache_hit':False}))
    monkeypatch.setattr(cache_store,'peek_cache_json',lambda *a:{'value':None,'error_kind':'timeout',
        'fresh_until_epoch':0,'retry_after_epoch':now+60})
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:pytest.fail('legacy negative guard bypassed'))
    assert tigerair_context_result(FetchRequest.from_ticker(e.TICKER),{'data':data})is None


@pytest.mark.parametrize('corpus',['pre_midnight','post_midnight'])
def test_native_complete_corpus_replays_normal_protocol_and_preserves_analysis(corpus,monkeypatch):
    """Offline old originals are not new HTTP or formal acquisition evidence."""
    from pathlib import Path
    from hashlib import sha256
    from data_fetch.market_sources import tigerair_yes123_evidence as e
    from data_fetch.market_sources import official_company_legal_name as master
    from data_fetch.market_sources.tigerair_yes123_transport import TigerairCareersHttp
    from data_fetch.tigerair_yes123_provider import _acquire
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count
    from alternative_source_refresh import merge_alternative_source
    from official_response_evidence import archive_response
    import cache_store
    D=Path('/Volumes/X10 Pro Mac/stock-agent-archives/'+(
        'continuation-20261104-tigerair-yes123-research'if corpus=='pre_midnight'else
        'normal-free-tigerair-yes123-6757-20261105'))
    if not(D/'complete-master.body').exists():pytest.skip('Private complete native corpus intentionally not published')
    identity=json.loads((D/'identity-full-master-readonly.json').read_text())
    rows=(json.loads((D/'native-result.json').read_text())['results']+json.loads((D/'additional-selected-detail-results.json').read_text())['results']
          if corpus=='pre_midnight'else json.loads((D/'native-replay-index.json').read_text())['results'])
    now=max(r['at']for r in rows)+1;owners={}
    monkeypatch.setattr(e.time,'time',lambda:now)
    monkeypatch.setattr(cache_store,'get_cache_json',lambda key:deepcopy(owners.get(key)))
    raw=(D/'complete-master.body').read_bytes();anchor=deepcopy(identity['issuer']);anchor['fetched_at_epoch']=identity['original_cache_fetched_at']
    assert sha256(raw).hexdigest()==anchor['response_sha256']
    archive_response(raw,source_url=anchor['source_url'],retrieved_at=anchor['fetched_at_epoch'],http_status=200)
    owners[identity['source_cache_key']]={'value':master.parse_roster(raw,'.TW'),
        'fetched_at_epoch':anchor['fetched_at_epoch'],'fresh_until_epoch':identity['original_fresh_until']}
    receipts={}
    for row in rows:
        body=(D/(row['name']+'.body')).read_bytes()
        assert row['complete']is True and row['status']==200 and row['return_code']==0
        assert len(body)==row['bytes'] and sha256(body).hexdigest()==row['sha256']
        proof=e.native_receipt(body,row['url'],row['at'],{'http_status':200,'http_status_observed':True,
            'response_complete':True,'http_request_sent':True,'return_code':0,'ssl_verify_result':0,
            'proxy_used':0,'num_redirects':0,'response_bytes':len(body)})
        receipts[row['url']]=proof
        owners['shared_provider:v1:'+sha256((e.RAW_PREFIX+row['url']).encode()).hexdigest()]={
            'value':proof,'fetched_at_epoch':row['at'],'fresh_until_epoch':row['at']+e.TTL}
    monkeypatch.setattr(master,'get_official_legal_name',lambda *a:deepcopy(anchor))
    requested=[]
    def read(self,url):
        requested.append(url);self.components.append({'cache_hit':True,'http_request_sent':False})
        return deepcopy(receipts[url])
    monkeypatch.setattr(TigerairCareersHttp,'read',read)
    data={'ticker':e.TICKER,'quote_type':'EQUITY','company_name':'台灣虎航-創',
        'company_identity':{'ticker':e.TICKER,'instrument_type':'EQUITY','official_name':'台灣虎航-創'},
        'current_price':77,'analysis_completeness':{'original':True},'alternative_data':{'status':'unavailable'}}
    original=deepcopy(data)
    result=_acquire(FetchRequest.from_ticker(e.TICKER),data)
    assert result.status=='success' and result.audit['record_count']==5 and len(requested)==8
    assert result.audit['http_request_count']==0 and result.audit['cache_hit']is True
    assert source_record_count('alternative_data',{**data,'alternative_data':result.value})==5
    assert all(j['first_publication_date']is None and j['employer_application_deadline']is None
               for j in result.value['job_openings_yes123']['job_postings'])
    audit={**result.audit,'fetch_id':'isolated-old-native-replay'}
    merged=merge_alternative_source(data,[],result.value,[audit],e.TICKER)
    assert data==original and merged['current_price']==77 and merged['analysis_completeness']=={'original':True}
    assert merged['source_record_archive'][0]['record']==original['alternative_data']
    damaged=deepcopy(result.value);damaged['job_openings_yes123']['job_postings'][0]['description']='unsupported'
    assert source_record_count('alternative_data',{**data,'alternative_data':damaged})==0
