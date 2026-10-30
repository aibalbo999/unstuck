"""Anonymous capped CHT reads; no login, retries, redirects or unbound URLs."""
import json,math,os,time,sqlite3
from contextlib import suppress
from hashlib import sha256
import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response
from search_provider_runtime import SourceResponseError,cooldown_state,observe_http_response,remember_failure,scope_key
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers
from .cht_careers import INDEX_URL,LIST_URL,PROVIDER,TICKER,MAX_BYTES,MAX_POSTINGS,canonical_detail_url,receipt_body


def allowed_url(url):
    if url in(INDEX_URL,LIST_URL):return url
    if canonical_detail_url(url)!=url:raise ValueError('career_url_noncanonical')
    return url


class ChtCareersHttp:
    def __init__(self,deadline=None,*,record_provider_sla=False):
        self.deadline=time.monotonic()+10 if deadline is None else deadline
        self.http_request_count=0;self.components=[];self.seen=set()
        self.record_provider_sla=record_provider_sla is True

    def _consume(self,url,parts,rc,error,diagnostic):
        status,headers=_headers(parts['headers'])
        try:meta=json.loads(parts['metadata'])
        except (ValueError,UnicodeError):meta={}
        if not isinstance(meta,dict):meta={}
        if status is None and type(meta.get('http_code'))is int and 200<=meta['http_code']<=599:status=meta['http_code']
        observed=(parts.get('process_started')is True and type(meta.get('http_code'))is int and 200<=meta['http_code']<=599
                  and meta.get('url_effective')==url and type(meta.get('ssl_verify_result'))is int and meta['ssl_verify_result']==0
                  and type(meta.get('proxy_used'))is int and meta['proxy_used']==0)
        diagnostic.update(http_request_sent=True if observed else None,http_request_count=int(observed),http_status=status)
        self.http_request_count+=int(observed)
        key=scope_key(PROVIDER,endpoint=httpx.URL(url).host)
        response=httpx.Response(status,headers=headers,request=httpx.Request('GET',url))if status else None
        if response is not None:observe_http_response(response)
        if observed and self.record_provider_sla:
            from provider_correlation import current_correlation
            from provider_sla import record_source_audit_entries
            context=current_correlation()
            if context.get('ticker')==TICKER and context.get('fetch_id'):
                with suppress(sqlite3.Error):
                    record_source_audit_entries([{**context,'source':'alternative_data','provider':PROVIDER+' native HTTP',
                        'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
                        'record_count':0,'status':'success'if status==200 else'error','http_request_sent':True,
                        'http_status':status,'response_bytes':len(parts['body']),'response_sha256':sha256(parts['body']).hexdigest(),
                        'message':'Public career HTTP response only; complete issuer, batch and posting qualification is separate.'}])
        def fail(kind):
            diagnostic['error_kind']=kind;exc=SourceResponseError(kind,status_code=status)
            if response is not None:exc.response=response
            if status in{401,402,403,429}or status and status>=500:remember_failure(key,exc)
            raise exc
        if status is not None and status!=200:fail({401:'authentication',402:'payment_required',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
        if error or rc:fail(error or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
        if (not observed or status!=200 or meta.get('http_code')!=200 or type(meta.get('num_redirects'))is not int or meta['num_redirects']!=0):fail('transport_metadata_invalid')
        mime=headers.get('content-type','').lower();charset='utf-8'if url==INDEX_URL else'ms950'
        if mime.split(';')[0].strip()!='text/html'or not any(v.strip().replace(' ','')=='charset='+charset for v in mime.split(';')[1:]):fail('unexpected_content_type')
        if headers.get('content-encoding','identity').lower()not in{'','identity'}:fail('unsupported_content_encoding')
        raw=parts['body'];size=meta.get('size_download')
        if not 0<len(raw)<=MAX_BYTES or type(size)not in(int,float)or not math.isfinite(size)or size!=len(raw):fail('transport_body_incomplete')
        if time.monotonic()>=self.deadline:fail('timeout')
        stamp=time.time();proof=archive_response(raw,source_url=url,retrieved_at=stamp,http_status=200)
        return {'schema':'cht-careers-http.v1','url':url,'method':'GET','fetched_at_epoch':stamp,
                'encoding':'utf-8'if url==INDEX_URL else'cp950','raw_receipt':proof}

    def _download(self,url,diagnostic):
        allowed_url(url)
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
        if proxy_url_for_request(url,PROVIDER)or any(os.getenv(k)for k in('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')):raise SourceResponseError('proxy_configuration_unsupported')
        if cooldown_state(scope_key(PROVIDER,endpoint=httpx.URL(url).host)):raise SourceResponseError('cooldown')
        remaining=min(3.,self.deadline-time.monotonic())
        if remaining<=0:raise SourceResponseError('timeout')
        argv=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(1.5,remaining)),
              '--max-filesize',str(MAX_BYTES),'--proto','=https','--max-redirs','0','--retry','0','-H','Accept: text/html',
              '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}',url]
        parts,rc,error=collect_capped_process(argv,min(self.deadline,time.monotonic()+remaining),body_limit=MAX_BYTES,headers=True)
        return self._consume(url,parts,rc,error,diagnostic)

    def read(self,url):
        allowed_url(url)
        if url in self.seen or len(self.seen)>=2+MAX_POSTINGS:raise SourceResponseError('career_request_set_invalid')
        self.seen.add(url);diagnostic={'source_url':url,'provider':PROVIDER,'http_request_sent':False,'http_request_count':0};self.components.append(diagnostic)
        value,meta=shared_fetch('cht-careers-raw:v1:'+url,lambda:self._download(url,diagnostic),
            freshness_seconds=3600,retention_seconds=3600,error_retry_seconds=300,use_cache=True,lock_wait_seconds=1)
        diagnostic.update(cache_hit=bool(meta.get('cache_hit')),fetched_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('error_kind')or meta.get('stale')or not isinstance(value,dict):
            raise SourceResponseError(diagnostic.get('error_kind')or meta.get('error_kind')or'career_receipt_unavailable')
        receipt_body(value,url,time.time())
        return value
