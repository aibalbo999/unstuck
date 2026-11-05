"""One complete current issuer statement; not independent media or assessed catalyst."""
from copy import deepcopy
import math,time
from .types import ProviderResult
from .market_sources.delta_press_parse import INDEX,TTL
from .market_sources.delta_press_evidence import (PROVIDER,BATCH_PREFIX,batch_key,raw_key,native_batch,
    current_master,valid_context,project,verified_record)
from .market_sources.delta_press_transport import DeltaPressHttp,normal_flow

ERRORS=(ValueError,TypeError,KeyError,OSError,AttributeError,RuntimeError,OverflowError,UnicodeError)

def _result(status,*,records=None,kind='',client=None,cache_hit=False,correlation=None):
    count=client.http_request_count if client else 0
    sent=True if count else None if client and client.process_count else False
    audit={**(correlation or{}),'source':'recent_catalysts','provider':PROVIDER,'actual_provider':'Delta official press',
      'status':status,'record_count':0,'event_kind':'fetch'if sent is not False else'local_block',
      'http_request_sent':sent,'http_request_count':count,'http_process_count':client.process_count if client else 0,
      'cache_hit':bool(cache_hit),'stale':False,'error_kind':kind,
      'component_statuses':{str(i):p for i,p in enumerate(client.components if client else[])},
      'message':'台達電公司自行陳述；內嵌正文已核對，非獨立媒體、事件影響評估或完整30日歷史。'}
    return ProviderResult('recent_catalysts',PROVIDER,status,value=records or[],audit=audit)

def _remaining(batch):
    from cache_store import peek_cache_json
    ends=[]
    for r in batch.get('originals',[]):
        owner=peek_cache_json(raw_key(r['url']));end=owner.get('fresh_until_epoch')if isinstance(owner,dict)else None
        if type(end)not in(int,float)or not math.isfinite(end):return 0
        ends.append(end)
    return max(0,min(ends)-time.time())if len(ends)==2 else 0

def fetch_delta_press(request,context):
    from cache_store import peek_cache_json
    from shared_provider_cache import shared_fetch
    from provider_correlation import current_correlation
    data=context.get('data')if isinstance(context,dict)else None
    if request.ticker!='2308.TW'or not valid_context(data):return _result('unavailable',kind='delta_context_identity_mismatch')
    if request.options.force_refresh or request.options.skip_optional_http:return _result('unavailable',kind='delta_normal_source_only')
    if not normal_flow(request.ticker):return _result('unavailable',kind='delta_native_source_frame_missing')
    correlation=current_correlation();client=None
    try:
        current_master(time.time())
        if request.options.record_provider_sla:
            client=DeltaPressHttp(data,record_provider_sla=True)
            def acquire():
                index=client.get(INDEX);url=client.allow_attachment(index);article=client.get(url)
                if time.monotonic()>=client.deadline:raise ValueError('timeout')
                return native_batch([index,article],time.time())
            batch,meta=shared_fetch(BATCH_PREFIX+INDEX,acquire,freshness_seconds=TTL,retention_seconds=TTL,
                error_retry_seconds=120,use_cache=True,result_ttl=_remaining,lock_wait_seconds=1)
        else:
            owner=peek_cache_json(batch_key());batch=owner.get('value')if isinstance(owner,dict)else None
            meta={'cache_hit':True}
        if not isinstance(batch,dict)or meta.get('error_kind')or meta.get('stale'):
            return _result('unavailable',kind=meta.get('error_kind')or'delta_batch_owner_unavailable',client=client,
                cache_hit=bool(meta.get('cache_hit'))and not bool(client and client.process_count),correlation=correlation)
        record=project(batch,data,time.time())
        new_body=bool(client and any(p.get('url')==record['source_url']and p.get('http_request_sent')is True
            and p.get('response_complete')is True for p in client.components))
        result=_result('success',records=[record],client=client,cache_hit=not new_body,correlation=correlation)
        result.audit.update(record_count=1,raw_count=1,usable_count=1,coverage_status='partial',source_url=INDEX,
            fetched_at_epoch=record['fetched_at_epoch'],event_kind='fetch'if new_body else'cache_hit',
            acquisition_record_count=int(new_body),selection_policy='delta-native-inline-press:v1')
        return guard_delta_result(result,data)
    except ERRORS as exc:
        import re
        kind=getattr(exc,'error_kind',None)or str(exc)
        kind=kind if isinstance(kind,str)and re.fullmatch('[a-z0-9_]{1,100}',kind)else type(exc).__name__
        return _result('unavailable',kind=kind,client=client,correlation=correlation)

def guard_delta_result(result,data):
    """Each delivery replays originals and ties fresh success to this body request."""
    from provider_correlation import current_correlation
    audit=result.audit if isinstance(result.audit,dict)else{}
    values=result.value if isinstance(result.value,list)else[];valid=False
    if len(values)==1 and verified_record(values[0],data)=='台達電':
        record=values[0];originals={p['url']:p for p in record['delta_press_receipt']['originals']}
        c=current_correlation();count=audit.get('http_request_count');processes=audit.get('http_process_count')
        comp=audit.get('component_statuses');parts=list(comp.values())if isinstance(comp,dict)else[]
        sent=[p for p in parts if isinstance(p,dict)and p.get('http_request_sent')is True]
        new_body=any(p.get('url')==record['source_url']for p in sent)
        native=all(p.get('url')in originals and type(p.get('http_status'))is int and p['http_status']==200
          and p.get('http_status_observed')is True and p.get('response_complete')is True and p.get('cache_hit')is False
          and p.get('response_sha256')==originals[p['url']]['raw_receipt']['raw_response_sha256']
          and type(p.get('response_bytes'))is int and p['response_bytes']==originals[p['url']]['raw_receipt']['raw_response_bytes']
          and all(originals[p['url']]['acquisition'].get(k)==audit.get(k)for k in('ticker','fetch_id','operation_id'))for p in sent)
        valid=(result.source=='recent_catalysts'and result.provider==PROVIDER and result.status==audit.get('status')=='success'
          and audit.get('source')==result.source and audit.get('provider')==PROVIDER and audit.get('ticker')=='2308.TW'
          and (not c.get('fetch_id')or audit.get('fetch_id')==c['fetch_id'])
          and type(audit.get('record_count'))is int and audit['record_count']==1
          and audit.get('fetched_at_epoch')==record['fetched_at_epoch']and audit.get('stale')is False
          and type(count)is int and 0<=count<=2 and type(processes)is int and processes==count==len(sent)
          and len({p.get('url')for p in sent})==len(sent)and native
          and audit.get('http_request_sent')is bool(sent)and audit.get('cache_hit')is(not new_body)
          and type(audit.get('acquisition_record_count'))is int and audit['acquisition_record_count']==int(new_body)
          and audit.get('event_kind')==('fetch'if new_body else'cache_hit'))
    if valid:return result
    return ProviderResult('recent_catalysts',PROVIDER,'unavailable',value=[],audit={**audit,
      'status':'unavailable','record_count':0,'cache_hit':False,'error_kind':audit.get('error_kind')or'delta_result_unverified'})
