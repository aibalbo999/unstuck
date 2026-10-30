"""Normal, issuer-scoped career context; originals and application time own TTL."""
from dataclasses import asdict
from datetime import datetime
import json,time,math
from .types import ProviderResult
from .market_sources.cht_careers import (TICKER,SHORT,LEGAL,UBN,PROVIDER,INDEX_URL,LIST_URL,
    verified_issuer,verified_job_count,valid_context,receipt_body,parse_index,parse_listing,parse_receipts)


CANONICAL_PROVIDER = "104 & 1111 job openings"

def eligible(data,request):
    return request.ticker==TICKER and not request.options.force_refresh and valid_context(data)


def _acquire(request,data):
    from .market_sources.official_company_legal_name import get_official_legal_name
    from .market_sources.cht_careers_transport import ChtCareersHttp
    old=data.get('alternative_data');anchor=old.get('company_legal_name_evidence')if isinstance(old,dict)else None
    if not verified_issuer(anchor,TICKER,SHORT):anchor=get_official_legal_name(TICKER,SHORT)
    if not verified_issuer(anchor,TICKER,SHORT):
        return ProviderResult('alternative_data',CANONICAL_PROVIDER,'unavailable',value={},audit={
            'source':'alternative_data','provider':CANONICAL_PROVIDER,'actual_provider':PROVIDER,'status':'unavailable','record_count':0,
            'event_kind':'local_block','http_request_sent':False,'http_request_count':0,'error_kind':'issuer_original_unverified'})
    client=ChtCareersHttp(record_provider_sla=request.options.record_provider_sla)
    try:
        index=client.read(INDEX_URL);batch=parse_index(receipt_body(index,INDEX_URL,time.time()),now=time.time())
        listing=client.read(LIST_URL);jobs=parse_listing(receipt_body(listing,LIST_URL,time.time()),batch)
        receipts=[index,listing,*[client.read(job['url'])for job in jobs]]
        value=parse_receipts(receipts,now=time.time())
        count=verified_job_count(value,TICKER,LEGAL,UBN,anchor)
        if not count:raise ValueError('career_qualification_failed')
        payload={'status':'partial','coverage_status':'partial','company_legal_name_evidence':anchor,
                 'job_openings_official':value,'current_open_job_count_official':None,
                 'job_openings_104':[],'job_openings_1111':[],'job_openings_taiwanjobs':None,
                 'numeric_count_coverage':0,'recruitment_news_count':0,'recent_company_job_count_104':None,
                 'current_open_job_count_taiwanjobs':None,'recent_recruitment_news':[],
                 'component_statuses':{'official':{'status':'verified_company_postings','provider':PROVIDER,
                    'source_url':INDEX_URL,'response_sha256':value['response_sha256'],'usable_count':count}},
                 'coverage_notes':[value['message']]}
        audit={'source':'alternative_data','provider':CANONICAL_PROVIDER,'actual_provider':PROVIDER,'status':'success','event_kind':'fetch',
            'record_count':count,'raw_count':count,'usable_count':count,'coverage_status':'partial',
            'source_url':INDEX_URL,'response_sha256':value['response_sha256'],'fetched_at_epoch':value['fetched_at_epoch'],
            'http_request_count':client.http_request_count,'http_request_sent':client.http_request_count>0,
            'cache_hit':all(p.get('cache_hit')is True for p in client.components),'stale':False,
            'message':value['message'],'component_statuses':{str(i):p for i,p in enumerate(client.components)}}
        return ProviderResult('alternative_data',CANONICAL_PROVIDER,'success',value=payload,audit=audit)
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,RuntimeError)as exc:
        sent=True if client.http_request_count else None if any(p.get('http_request_sent')is None for p in client.components)else False
        return ProviderResult('alternative_data',CANONICAL_PROVIDER,'unavailable',value={},audit={
            'source':'alternative_data','provider':CANONICAL_PROVIDER,'actual_provider':PROVIDER,'status':'unavailable','record_count':0,'event_kind':'fetch',
            'http_request_sent':sent,'http_request_count':client.http_request_count,'cache_hit':bool(client.components)and all(p.get('cache_hit')is True for p in client.components),
            'error_kind':str(getattr(exc,'error_kind','')or type(exc).__name__),
            'message':'官方公開職缺本次未完整核對；保留其他來源與未知，不推論沒有職缺。',
            'component_statuses':{str(i):p for i,p in enumerate(client.components)}})


def _remaining(payload):
    try:
        p=payload['value'];jobs=p['job_openings_official'];now=time.time()
        stamps=[jobs['fetched_at_epoch']+3600,p['company_legal_name_evidence']['fetched_at_epoch']+86400,
                *[datetime.fromisoformat(j['application_end']).timestamp()for j in jobs['job_postings']]]
        if not stamps or any(type(x)not in(int,float)or not math.isfinite(x)for x in stamps):return 0
        return max(0,min(stamps)-now)
    except (ValueError,TypeError,KeyError,OverflowError):return 0


def cht_context_result(request,context):
    from shared_provider_cache import shared_fetch
    data=(context or{}).get('data')or{}
    if not isinstance(data,dict)or not eligible(data,request):return None
    identity=data['company_identity'];key=json.dumps([TICKER,data.get('quote_type'),
        *[data.get(k)for k in('ticker','stock_id','quoteType','instrument_type')],
        *[identity.get(k)for k in('ticker','official_name','legal_name','official_ubn','stock_id','instrument_type')]],ensure_ascii=False)
    payload,meta=shared_fetch('optional-context:cht-careers:v1:'+key,lambda:asdict(_acquire(request,data)),
        freshness_seconds=3600,retention_seconds=3600,error_retry_seconds=300,use_cache=True,
        result_ttl=lambda p:min(3600,_remaining(p))if p.get('status')=='success'else 300,lock_wait_seconds=1)
    if not isinstance(payload,dict):return None
    result=ProviderResult(**payload)
    if meta.get('cache_hit'):
        result.audit={**result.audit,'cache_hit':True,'http_request_sent':False,'http_request_count':0}
    if result.status=='success':
        value=result.value;count=verified_job_count(value['job_openings_official'],TICKER,LEGAL,UBN,value['company_legal_name_evidence'])
        if not count:return None
    return result
