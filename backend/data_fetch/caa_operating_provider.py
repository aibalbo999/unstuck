"""Independent named-carrier operating observations; never job-count substitutes."""
from contextlib import nullcontext
from copy import deepcopy
import math,time,zipfile,xml.etree.ElementTree as ET
from .provider_base import DataProvider
from .types import ProviderResult
from .market_sources.caa_operating_parse import INDEX,DIRECTORY,TTL
from .market_sources.caa_operating_identity import PROFILES
from .market_sources.caa_operating_evidence import (PROVIDER,BATCH_PREFIX,batch_key,native_batch,
    project,current_master,valid_context,verified_count)
from .market_sources.caa_operating_transport import AirlineOperatingHttp,normal_flow

ERRORS=(ValueError,TypeError,KeyError,OSError,AttributeError,RuntimeError,OverflowError,UnicodeError,zipfile.BadZipFile,ET.ParseError)

def _kind(exc):
    import re
    value=getattr(exc,'error_kind',None)or str(exc)
    return value if isinstance(value,str)and re.fullmatch('[a-z0-9_]{1,100}',value)else type(exc).__name__

def _result(status,*,value=None,kind='',client=None,cache_hit=False,correlation=None):
    components=client.components if client else[];count=client.http_request_count if client else 0
    sent=True if count else None if client and client.process_count else False
    audit={**(correlation or{}),'source':'alternative_data','provider':PROVIDER,'actual_provider':PROVIDER,
      'status':status,'record_count':0,'event_kind':'fetch'if sent is not False else'local_block',
      'http_request_sent':sent,'http_request_count':count,'http_process_count':client.process_count if client else 0,
      'cache_hit':bool(cache_hit),'stale':False,'error_kind':kind,'component_statuses':{str(i):p for i,p in enumerate(components)},
      'message':'僅核對具名航空公司營運數據；職缺、實際招聘、集團財報與分析結論保持各自證據門檻。'}
    return ProviderResult('alternative_data',PROVIDER,status,value={}if value is None else value,audit=audit)

def _batch_remaining(batch):
    from cache_store import peek_cache_json
    from .market_sources.caa_operating_evidence import raw_key
    now=time.time();ends=[]
    for r in batch.get('originals',[]):
        owner=peek_cache_json(raw_key(r['url']));end=owner.get('fresh_until_epoch')if isinstance(owner,dict)else None
        if type(end)not in(int,float)or not math.isfinite(end):return 0
        ends.append(end)
    return max(0,min(ends)-now)if len(ends)==3 else 0

def _payload(observation,data):
    old=data.get('alternative_data');value=deepcopy(old)if isinstance(old,dict)else{}
    value['operating_metrics_official']=observation;value['status']='partial';value['coverage_status']='partial'
    notes=value.get('coverage_notes');value['coverage_notes']=[*(notes if isinstance(notes,list)else[]),*observation['coverage_notes']]
    components=value.get('component_statuses');value['component_statuses']={**(components if isinstance(components,dict)else{}),
      'CAA_operating':{'status':'verified_named_carrier_operating_metrics','provider':PROVIDER,
        'source_url':INDEX,'latest_month':observation['latest_month'],'report_year':observation['year'],
        'job_count':None,'message':'客貨運量與載客／載貨率，非職缺或人數。'}}
    return value

def _fetch(request,context):
    from cache_store import peek_cache_json
    from shared_provider_cache import shared_fetch
    from provider_correlation import current_correlation,current_source_identity,source_operation
    data=(context or{}).get('data');ticker=request.ticker
    if not isinstance(data,dict)or not valid_context(data,ticker):return _result('unavailable',kind='caa_context_identity_mismatch')
    if request.options.force_refresh or request.options.skip_optional_http:return _result('unavailable',kind='caa_normal_source_only')
    c=current_correlation();source=current_source_identity()
    if c.get('ticker')!=ticker or not c.get('fetch_id')or source not in{('alternative_data',PROVIDER),('alternative_data','104 & 1111 job openings')}:
        return _result('unavailable',kind='caa_native_fetch_frame_missing')
    manager=nullcontext()if normal_flow(ticker)else source_operation('alternative_data',PROVIDER)
    with manager:
        correlation=current_correlation();client=None
        try:
            # A live complete official master is a prerequisite, not a hidden new request.
            current_master(ticker,time.time())
            if request.options.record_provider_sla:
                client=AirlineOperatingHttp(data,record_provider_sla=True)
                def acquire():
                    index=client.get(INDEX);attachment=client.allow_attachment(index)
                    directory=client.get(DIRECTORY);ods=client.get(attachment)
                    if time.monotonic()>=client.deadline:raise ValueError('timeout')
                    return native_batch([index,directory,ods],time.time())
                batch,meta=shared_fetch(BATCH_PREFIX+INDEX,acquire,freshness_seconds=TTL,retention_seconds=TTL,
                    error_retry_seconds=120,use_cache=True,result_ttl=_batch_remaining,lock_wait_seconds=1)
            else:
                owner=peek_cache_json(batch_key());batch=owner.get('value')if isinstance(owner,dict)else None
                meta={'cache_hit':True}
            if not isinstance(batch,dict)or meta.get('error_kind')or meta.get('stale'):
                return _result('unavailable',kind=meta.get('error_kind')or'caa_dataset_owner_unavailable',client=client,
                    cache_hit=bool(meta.get('cache_hit'))and not bool(client and client.process_count),correlation=correlation)
            observation=project(batch,data,time.time())
            if verified_count(observation,data)!=1:raise ValueError('caa_complete_projection_unverified')
            value=_payload(observation,data)
            # Cache callback reuse can be a genuine warm read even with a new batch wrapper.
            new_metric=bool(client and any(p.get('url')==observation['attachment_url']and p.get('http_request_sent')is True
                and p.get('response_complete')is True for p in client.components))
            warm=not new_metric
            result=_result('success',value=value,client=client,cache_hit=warm,correlation=correlation)
            from data_trust import source_record_count
            result.audit.update(record_count=source_record_count('alternative_data',{**data,'alternative_data':value}),
                raw_count=1,usable_count=1,coverage_status='partial',source_url=INDEX,
                fetched_at_epoch=observation['fetched_at_epoch'],
                event_kind='cache_hit'if warm else'fetch',
                acquisition_record_count=int(new_metric),
                selection_policy='caa-named-carrier-operating:v1')
            return guard_operating_result(result,data)
        except ERRORS as exc:
            return _result('unavailable',kind=_kind(exc),client=client,
                cache_hit=bool(client and not client.process_count and client.components and all(p.get('cache_hit')is True for p in client.components)),correlation=correlation)

def guard_operating_result(result,data):
    """Count a new metrics acquisition only when this call actually fetched the ODS."""
    from provider_correlation import current_correlation
    from data_trust import source_record_count
    audit=result.audit if isinstance(result.audit,dict)else{}
    value=result.value if isinstance(result.value,dict)else{}
    observation=value.get('operating_metrics_official');valid=False
    if isinstance(observation,dict)and verified_count(observation,data)==1:
        count=source_record_count('alternative_data',{**data,'alternative_data':value});c=current_correlation()
        raw_count=audit.get('http_request_count');processes=audit.get('http_process_count')
        comp=audit.get('component_statuses');components=list(comp.values())if isinstance(comp,dict)else[]
        sent=[p for p in components if isinstance(p,dict)and p.get('http_request_sent')is True]
        originals={p['url']:p for p in observation['caa_operating_receipt']['originals']}
        new_metric=any(p.get('url')==observation['attachment_url']for p in sent)
        native_matches=all(p.get('url')in originals and p.get('http_status')==200 and type(p.get('http_status'))is int
          and p.get('http_status_observed')is True and p.get('response_complete')is True and p.get('cache_hit')is False
          and p.get('response_sha256')==originals[p['url']]['raw_receipt']['raw_response_sha256']
          and p.get('response_bytes')==originals[p['url']]['raw_receipt']['raw_response_bytes']and type(p.get('response_bytes'))is int
          and all(originals[p['url']]['acquisition'].get(k)==audit.get(k)for k in('ticker','fetch_id','operation_id'))for p in sent)
        valid=(result.source=='alternative_data'and result.provider==PROVIDER and result.status==audit.get('status')=='success'
          and audit.get('source')==result.source and audit.get('provider')==PROVIDER and audit.get('ticker')==data.get('ticker')
          and (not c.get('fetch_id')or audit.get('fetch_id')==c['fetch_id'])
          and type(audit.get('record_count'))is int and audit['record_count']==count>0
          and audit.get('fetched_at_epoch')==observation['fetched_at_epoch']and audit.get('stale')is False
          and type(raw_count)is int and 0<=raw_count<=3 and type(processes)is int and processes==raw_count==len(sent)
          and len({p.get('url')for p in sent})==len(sent)and native_matches
          and audit.get('http_request_sent')is bool(sent)and type(audit.get('cache_hit'))is bool
          and audit['cache_hit']is(not new_metric)and type(audit.get('acquisition_record_count'))is int
          and audit['acquisition_record_count']==int(new_metric)
          and audit.get('event_kind')==('fetch'if new_metric else'cache_hit'))
    if valid:return result
    failed=result.status if result.status in{'unavailable','error','degraded_enrichment'}else'unavailable'
    return ProviderResult('alternative_data',PROVIDER,failed,value={},audit={**audit,'source':'alternative_data',
        'provider':PROVIDER,'status':failed,'record_count':0,'error_kind':audit.get('error_kind')or'caa_result_unverified',
        'cache_hit':False if audit.get('http_request_sent')is True else bool(audit.get('cache_hit')),
        'message':'航空營運原件、身分、期間、數值或這次取得憑據未通過重播；保留未知。'})

class AirlineOperatingMetricsProvider(DataProvider):
    name=PROVIDER;source='alternative_data';markets={'tw'};cost_tier='free'
    capabilities={'alternative_data','airline_operating_metrics'}
    execute_in_workflow=False;primary_source_provider=False
    def supports(self,request):return request.ticker in PROFILES
    def fetch(self,request,context=None):return _fetch(request,context)

def blocked_prior_access(value,depth=0):
    """A different-data fallback must not be triggered by an access/quota refusal."""
    if depth>8:return False
    if isinstance(value,dict):
        if value.get('http_status_observed')is not False and any(type(value.get(k))is int and value[k]in{401,402,403,429}for k in('http_status','status_code')):return True
        if any(value.get(k)in{'authentication','payment_required','access_denied','rate_limited'}for k in('error_kind','reason_code','failure_kind')if isinstance(value.get(k),str)):return True
        return any(blocked_prior_access(v,depth+1)for v in list(value.values())[:100])
    if isinstance(value,list):return any(blocked_prior_access(v,depth+1)for v in value[:100])
    return False

def maybe_operating_fallback(request,context,result):
    if request.ticker not in PROFILES or request.options.skip_optional_http or request.options.force_refresh or(context or{}).get('_alternative_job_only')is True:return result
    if blocked_prior_access({'audit':result.audit,'value':result.value}):return result
    from data_trust import source_record_count
    data=(context or{}).get('data')or{}
    if not isinstance(data,dict)or source_record_count('alternative_data',{**data,'alternative_data':result.value})>0:return result
    delegated={**(context or{}),'data':{**data,'alternative_data':deepcopy(result.value)if isinstance(result.value,dict)else{}}}
    alternative=AirlineOperatingMetricsProvider().fetch(request,delegated)
    if alternative.status=='success':
        alternative.audit['related_entries']=[deepcopy(result.audit),*deepcopy(result.audit.get('related_entries')or[]),*(alternative.audit.get('related_entries')or[])]
        return alternative
    result.audit={**result.audit,'related_entries':[*(result.audit.get('related_entries')or[]),alternative.audit]}
    return result
