"""Bounded anonymous JPX reads; cached originals never become new HTTP."""
from hashlib import sha256
import json,math,os,re,tempfile,time
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from uuid import uuid4

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError,scope_key,cooldown_state,observe_http_response,remember_failure
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers
from .issuer_news_transport import PROVIDER,PROXY_ENV
from .jpx_company_schema import (ENTRY_URL,SEARCH_URL,DETAIL_URL,LIMIT,common_code,
                                 search_form,parse_listing,detail_form,parse_details)

TTL=1800


def _run_curl(argv,deadline,*,body_limit,headers):
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
    return collect_capped_process(argv,deadline,body_limit=body_limit,headers=headers)


def _number(value):return type(value)in(int,float)and math.isfinite(value)


def _current(proof,canonical,method,code):
    now=time.time();stamp=proof.get('retrieved_at')if isinstance(proof,dict)else None
    until=proof.get('fresh_until_epoch')if isinstance(proof,dict)else None
    if(not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=canonical
            or proof.get('request_method')!=method or proof.get('query_common_code')!=code
            or proof.get('http_status')!=200 or type(proof.get('http_status'))is not int
            or proof.get('http_status_observed')is not True or proof.get('response_complete')is not True
            or proof.get('cache_hit')is not False or proof.get('evidence_kind')!='raw_http_response_bytes'
            or proof.get('historical_point_in_time_verified')is not False or proof.get('finality_guaranteed')is not False
            or not _number(stamp)or not _number(until)or not 0<stamp<=now<until<=stamp+TTL
            or proof.get('url_normalization')!='anonymous_url_session_omitted'):
        raise ValueError('jpx_original_unverified_or_expired')
    raw=read_response(proof)
    if type(proof.get('raw_response_bytes'))is not int or not 100<len(raw)<=LIMIT or len(raw)!=proof['raw_response_bytes']:
        raise ValueError('jpx_original_size_invalid')
    return raw


def verify_bundle(value,code,*,details):
    common_code(code)
    if not isinstance(value,dict)or value.get('code')!=code or value.get('details_included')is not details:raise ValueError('jpx_bundle_identity_invalid')
    proofs=value.get('originals')
    if not isinstance(proofs,list)or len(proofs)!=(3 if details else 2):raise ValueError('jpx_original_set_invalid')
    raw=[_current(p,u,m,code)for p,u,m in zip(proofs,[ENTRY_URL,SEARCH_URL,DETAIL_URL],['GET','POST','POST'])]
    actual,fields=search_form(raw[0],code);urls=[ENTRY_URL,actual];bodies=['',urlencode(fields)]
    listing=parse_listing(raw[1],code)
    if value.get('listing')!=listing:raise ValueError('jpx_cached_identity_disagrees')
    if details:
        actual,fields=detail_form(raw[1],code);urls.append(actual);bodies.append(urlencode(fields));parse_details(raw[2],listing)
    for proof,url,body in zip(proofs,urls,bodies):
        if (proof.get('actual_request_url_sha256')!=sha256(url.encode()).hexdigest()
                or proof.get('request_body_sha256')!=sha256(body.encode()).hexdigest()):raise ValueError('jpx_request_binding_invalid')
    return value


def _emit(code,diagnostic,proof,*,complete):
    from .ncc_mobile_peer_transport import peer_receipt_observation_enabled
    if not peer_receipt_observation_enabled():return
    from provider_correlation import current_correlation,current_source_identity
    from provider_sla import record_source_audit_entries
    context=current_correlation()
    if not all(context.get(k)for k in('ticker','fetch_id','operation_id'))or current_source_identity()!=('dynamic_peer_metrics','FinMind/yfinance'):return
    row={**context,'source':'dynamic_peer_metrics','provider':'JPX listed company native HTTP',
         'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1','record_count':0,
         'status':'success'if complete else'error','http_request_sent':diagnostic.get('http_request_sent'),
         'http_status':diagnostic.get('http_status'),'request_method':diagnostic['request_method'],
         'response_bytes':diagnostic.get('response_bytes',0),'response_sha256':diagnostic.get('response_sha256'),
         'error_kind':diagnostic.get('error_kind'),'component_statuses':{code[:4]+'.T':{
             'status':'transport_received'if complete else'transport_unverified','http_status':diagnostic.get('http_status')}},
         'message':'Anonymous official company transport only; issuer, period and financial comparability are checked separately.'}
    if proof:row['raw_http_receipt']=proof
    with suppress(sqlite3.Error):record_source_audit_entries([row])


class JpxCompanyGateway:
    def __init__(self,deadline):
        self.deadline=deadline;self.components=[];self.http_request_count=0

    def _request(self,url,jar,code,canonical,body=None):
        method='GET'if body is None else'POST';host=urlsplit(url).hostname
        parts=urlsplit(url)
        if method=='GET':
            if canonical!=ENTRY_URL or url!=ENTRY_URL:raise ValueError('jpx_request_route_invalid')
        elif(canonical not in{SEARCH_URL,DETAIL_URL}or parts.scheme!='https'or parts.netloc!='www2.jpx.co.jp'
                or parts.query or parts.fragment or not re.fullmatch(re.escape(urlsplit(canonical).path)+r'(?:;jsessionid=[0-9A-F]{33})?',parts.path)):
            raise ValueError('jpx_request_route_invalid')
        diagnostic={'source_url':canonical,'request_method':method,'peer_symbol':code[:4]+'.T','http_request_sent':False}
        self.components.append(diagnostic)
        if proxy_url_for_request(url,PROVIDER)or any(os.getenv(k)for k in PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
        key=scope_key(PROVIDER,endpoint=host)
        if cooldown_state(key):raise SourceResponseError('cooldown')
        left=min(5.,self.deadline-time.monotonic())
        if left<=0:raise SourceResponseError('timeout')
        argv=['/usr/bin/curl','--disable','--silent','--max-time',str(left),'--connect-timeout',str(min(2.,left)),
              '--max-filesize',str(LIMIT),'--proto','=https','--max-redirs','0','--retry','0',
              '--cookie-jar',str(jar),'--cookie',str(jar),'--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}']
        if body is not None:argv+=['-H','Content-Type: application/x-www-form-urlencoded','--data-raw',body]
        argv.append(url)
        chunks,rc,error=_run_curl(argv,min(self.deadline,time.monotonic()+left),body_limit=LIMIT,headers=True)
        status,headers=_headers(chunks['headers'])
        try:meta=json.loads(chunks['metadata'])
        except(ValueError,UnicodeError):meta={}
        if not isinstance(meta,dict):meta={}
        known=(chunks.get('process_started')is True and type(status)is int and 100<=status<=599
               and type(meta.get('http_code'))is int and meta['http_code']==status and meta.get('url_effective')==url
               and type(meta.get('ssl_verify_result'))is int and meta['ssl_verify_result']==0
               and type(meta.get('proxy_used'))is int and meta['proxy_used']==0)
        diagnostic.update(http_request_sent=True if known else None,http_status=status,
                          response_bytes=len(chunks['body']),response_sha256=sha256(chunks['body']).hexdigest())
        self.http_request_count+=int(known)
        response=httpx.Response(status,headers=headers,request=httpx.Request(method,canonical))if status else None
        if response is not None:observe_http_response(response)
        def fail(kind):
            diagnostic['error_kind']=kind;_emit(code,diagnostic,None,complete=False)
            exc=SourceResponseError(kind,status_code=status)
            if response is not None:exc.response=response
            if status in{401,403,429}or status and status>=500:remember_failure(key,exc)
            raise exc
        if status is not None and status!=200:fail({401:'authentication',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
        if rc or error:fail(error or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
        if not known or type(meta.get('num_redirects'))is not int or meta['num_redirects']!=0:fail('transport_metadata_invalid')
        if(headers.get('content-type','').split(';')[0].strip().lower()not in{'text/html','application/xhtml+xml'}
                or headers.get('content-encoding','identity').lower()not in{'','identity'}):fail('unexpected_content_type')
        raw=chunks['body'];size=meta.get('size_download')
        if not 100<len(raw)<=LIMIT or not _number(size)or size!=len(raw):fail('transport_body_incomplete')
        stamp=time.time();proof=archive_response(raw,source_url=canonical,retrieved_at=stamp)
        if proof.get('status')!='archived':fail('original_archive_unavailable')
        proof.update(request_method=method,http_status_observed=True,response_complete=True,cache_hit=False,
                     query_common_code=code,fresh_until_epoch=stamp+TTL,url_normalization='anonymous_url_session_omitted',
                     actual_request_url_sha256=sha256(url.encode()).hexdigest(),request_body_sha256=sha256((body or'').encode()).hexdigest())
        diagnostic['original_receipt']=proof;_emit(code,diagnostic,proof,complete=True)
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')
        return raw,proof

    def _collect(self,code,details):
        from runtime_paths import current_runtime_paths
        root=current_runtime_paths().cache_dir/'tmp';root.mkdir(parents=True,exist_ok=True)
        proofs=[]
        with tempfile.TemporaryDirectory(prefix='jpx-anonymous-',dir=root)as folder:
            jar=Path(folder)/'cookies.txt';jar.touch(mode=0o600)
            raw,proof=self._request(ENTRY_URL,jar,code,ENTRY_URL);proofs.append(proof)
            url,fields=search_form(raw,code)
            raw,proof=self._request(url,jar,code,SEARCH_URL,urlencode(fields));proofs.append(proof)
            listing=parse_listing(raw,code)
            if details:
                url,fields=detail_form(raw,code)
                raw,proof=self._request(url,jar,code,DETAIL_URL,urlencode(fields));proofs.append(proof)
                parse_details(raw,listing)
        value={'code':code,'details_included':details,'listing':listing,'originals':proofs}
        verify_bundle(value,code,details=details)
        return value

    def get(self,code,*,details=False):
        common_code(code)
        if type(details)is not bool:raise ValueError('jpx_details_flag_invalid')
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')
        key='jpx-company-originals:v1:'+code+(':basic'if details else':listed')
        def collect():
            from cache_store import get_cache_json,set_cache_json
            admission='jpx-company-admission:v1:'+sha256(key.encode()).hexdigest()
            state=get_cache_json(admission)
            if state is not None:
                until=state.get('retry_at')if isinstance(state,dict)else None
                if not _number(until)or until<0:raise SourceResponseError('guard_storage_unavailable')
                if until>time.time():raise SourceResponseError('cooldown')
            marker={'token':uuid4().hex,'retry_at':time.time()+120}
            set_cache_json(admission,marker,ttl_seconds=120)
            if get_cache_json(admission)!=marker:raise SourceResponseError('guard_storage_unavailable')
            value=self._collect(code,details)
            if get_cache_json(admission)==marker:set_cache_json(admission,{**marker,'retry_at':0},ttl_seconds=1)
            return value
        def remaining(value):
            verify_bundle(value,code,details=details)
            result=math.floor(min(p['fresh_until_epoch']for p in value['originals'])-time.time())
            if result<1:raise SourceResponseError('original_expired')
            return result
        failure=[]
        def callback():
            try:return collect()
            except Exception as exc:failure.append(exc);raise
        value,meta=shared_fetch(key,callback,freshness_seconds=TTL,retention_seconds=TTL,result_ttl=remaining,
                               error_retry_seconds=120,lock_wait_seconds=min(1.,max(0.,self.deadline-time.monotonic())))
        if meta.get('error_kind')or meta.get('stale'):
            if failure:raise failure[0]
            raise SourceResponseError('cooldown'if meta.get('error_kind')=='SourceResponseError'else'original_unavailable')
        verify_bundle(value,code,details=details)
        if meta.get('cache_hit'):
            self.components.append({'peer_symbol':code[:4]+'.T','cache_hit':True,'http_request_sent':False,
                                    'original_fetched_at_epoch':min(p['retrieved_at']for p in value['originals'])})
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')
        return value
