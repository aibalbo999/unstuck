"""One bounded normal batch through the existing anonymous HTTP route.

No credentials, redirects, retries or alternate browser route. Outer optional
context cache remains first; this distinct API's batch owner never refreshes TTL
on reuse. An enabled advertisement is not evidence of hiring intent/headcount.
"""
import time
import httpx

from external_http_client import sync_get
from . import current_104_evidence as e
from .current_104_postings import MAX_LIST_BYTES,MAX_DETAIL_BYTES


def fetch_current_advertisements(request, data, issuer, *, primary=None):
    """Return a qualified ProviderResult, or leave existing unrelated fallbacks."""
    from provider_correlation import current_correlation,current_source_identity
    from data_fetch.types import ProviderResult
    from shared_provider_cache import shared_fetch
    if ((primary or {}).get('transport_failed') is True
            or request.options.record_provider_sla is not True or request.options.force_refresh
            or not e.valid_context(data,issuer) or not e.verified_issuer(issuer)):
        return None
    correlation=current_correlation()
    if (correlation.get('ticker')!=request.ticker
            or not all(isinstance(correlation.get(k),str)and correlation[k]for k in('fetch_id','operation_id'))
            or current_source_identity()!=('alternative_data',e.PROVIDER)):
        return None
    components=[];deadline=time.monotonic()+25

    def read(url,maximum):
        from alternative_data_fetcher import DEFAULT_HEADERS
        from provider_resilience import _check_provider_state,call_provider_component_once
        from provider_throttle import provider_throttle_state
        from provider_transport_receipt import record_job_transport_receipt
        from search_provider_runtime import cooldown_state,scope_key,remember_failure
        provider='104 Company Jobs API'
        _check_provider_state(e.PROVIDER)
        if provider_throttle_state(e.PROVIDER).get('open')or cooldown_state(scope_key(provider,endpoint='www.104.com.tw')):
            raise ValueError('104 original provider guard active')
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ValueError('104 batch deadline')
        if len(components)>=6:raise ValueError('104 batch request cap')
        started=time.monotonic();response=None
        try:
            response=call_provider_component_once(provider,sync_get,kwargs={
                'url':url,'params':{},'headers':{**DEFAULT_HEADERS,'Accept':'application/json',
                'Referer':('https://www.104.com.tw/company/'+e.list_url(issuer).split('/')[-2]
                    if url==e.list_url(issuer)else 'https://www.104.com.tw/job/'+url.rsplit('/',1)[-1])},
                'timeout':min(5,remaining),'provider':provider})
        except Exception as error:
            response=getattr(error,'response',None)
            record_job_transport_receipt(provider,started,response=response,native_call=True)
            if response is not None and (response.status_code in {401,402,403,429} or response.status_code>=500):
                remember_failure(scope_key(provider,endpoint='www.104.com.tw'),error)
            raise
        record_job_transport_receipt(provider,started,response=response,native_call=True)
        if (type(response)is not httpx.Response or response.status_code!=200 or str(response.url)!=url
                or response.request.method!='GET'or response.history or getattr(response,'from_cache',False)
                or not response.is_stream_consumed or response.headers.get('content-type','').split(';')[0].strip().lower()!='application/json'
                or time.monotonic()>=deadline or not 0<len(response.content)<=maximum):
            raise ValueError('104 complete native response invalid')
        receipt=e.archive_original(response.content,url,time.time(),correlation)
        components.append(receipt)
        return response.content

    def acquire():
        listing=read(e.list_url(issuer),MAX_LIST_BYTES)
        for ident in e.selected_ids(listing):read(e.detail_url(ident),MAX_DETAIL_BYTES)
        return e.make_batch(components,issuer)

    batch,meta=shared_fetch(e.PREFIX+e.list_url(issuer),acquire,freshness_seconds=e.TTL,
                          retention_seconds=e.TTL,error_retry_seconds=300,use_cache=True,lock_wait_seconds=1,
                          result_ttl=lambda value:max(0,e.TTL-(time.time()-value['manifest']['retrieved_at'])))
    if meta.get('error_kind')or meta.get('stale')or not isinstance(batch,dict):return None
    try:
        value=e.replay_batch(batch,issuer)
        count=e.verified_count(value,data,issuer)
        if not count:return None
    except (ValueError,KeyError,TypeError,OSError):return None
    stamp=value['fetched_at_epoch'];http_count=len(components)
    payload={'status':'partial','job_openings_104_current':value,'company_legal_name_evidence':issuer,
        'job_openings_104':[],'job_openings_1111':[],'recent_recruitment_news':[],
        'current_open_job_count_official':None,'recent_company_job_count_104':None,
        'coverage_notes':[value['message']],
        'component_statuses':{'104_primary':{'status':(primary or{}).get('status'),
            'reason_code':(primary or{}).get('reason_code')}}}
    audit={**correlation,'source':'alternative_data','provider':e.PROVIDER,'status':'success','record_count':count,
        'actual_provider':value['source'],'coverage_status':'bounded_enabled_advertisement_sample',
        'record_unit':'advertised_posting','cache_hit':bool(meta.get('cache_hit')),'stale':False,
        'fetched_at_epoch':stamp,'http_request_count':http_count,'http_request_sent':http_count>0,
        'response_sha256':batch['manifest']['raw_response_sha256'],
        'source_record_archive':batch,'message':value['message']}
    return ProviderResult(source='alternative_data',provider=e.PROVIDER,status='success',value=payload,audit=audit)
