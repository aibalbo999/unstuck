"""One normal anonymous CAA dataset flow; capped native reads and zero retries."""
from contextlib import suppress
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import json,math,os,re,sqlite3,time
import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import (SourceResponseError,cooldown_state,observe_http_response,remember_failure,scope_key)
from shared_provider_cache import shared_fetch
from .caa_operating_parse import INDEX,DIRECTORY,TTL,contract,select_dataset
from .caa_operating_identity import PROFILES
from .caa_operating_evidence import (PROVIDER,RAW_PREFIX,native_receipt,receipt_body,
    transport_for,current_master,valid_context,pathless,raw_key)

PROXY_ENV=('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')

def normal_flow(ticker):
    from provider_correlation import current_correlation,current_source_identity
    c=current_correlation()
    return (ticker in PROFILES and current_source_identity()==('alternative_data',PROVIDER)
        and c.get('ticker')==ticker and all(isinstance(c.get(k),str)and c[k]for k in('fetch_id','operation_id')))

class AirlineOperatingHttp:
    def __init__(self,data,*,record_provider_sla=False,deadline=None):
        self.ticker=data.get('ticker')if isinstance(data,dict)else None
        if not valid_context(data,self.ticker):raise SourceResponseError('caa_context_identity_mismatch')
        current_master(self.ticker,time.time())
        self.data=deepcopy({k:data[k]for k in('ticker','quote_type','company_name','company_identity','stock_id','quoteType','instrument_type','official_ubn')if k in data})
        start=time.monotonic()
        if deadline is not None and (type(deadline)not in(int,float)or not math.isfinite(deadline)):raise ValueError('caa_deadline_invalid')
        self.deadline=min(start+20,deadline)if deadline is not None else start+20
        self.record_provider_sla=record_provider_sla is True
        self.http_request_count=0;self.process_count=0;self.components=[];self.seen=set();self.staged={};self.attachment=None

    def _block(self,kind,diagnostic):
        diagnostic.update(error_kind=kind,http_status=None,http_status_observed=False,response_complete=False,
            http_request_sent=False,http_request_count=0)
        exc=SourceResponseError(kind);exc.diagnostic.update(http_status_observed=False,response_complete=False)
        raise exc

    def _emit(self,diagnostic,receipt=None):
        if not self.record_provider_sla or not normal_flow(self.ticker)or not diagnostic.get('client_process_started'):return
        from provider_correlation import current_correlation
        from provider_sla import record_source_audit_entries
        component=deepcopy(diagnostic)
        if receipt is not None:
            component['original_receipt']={**receipt['raw_receipt'],'http_status_observed':True,
                'response_complete':True,'request_method':'GET','cache_hit':False}
        with suppress(sqlite3.Error):
            record_source_audit_entries([{**current_correlation(),'source':'alternative_data',
              'provider':PROVIDER+' native HTTP','status':'success'if receipt else'error',
              'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1','record_count':0,
              'http_request_sent':diagnostic.get('http_request_sent'),'http_request_count':diagnostic.get('http_request_count'),
              'http_status_observed':diagnostic.get('http_status_observed'),'http_status':diagnostic.get('http_status'),
              'response_complete':bool(receipt),'source_url':diagnostic['url'],'component_statuses':[component],
              'message':'Native HTTP transport only; whole dataset, issuer, periods and operating metrics require separate replay.'}])

    def _consume(self,url,parts,rc,error,diagnostic):
        if not self.record_provider_sla or not normal_flow(self.ticker):self._block('caa_unrecorded_or_non_native_flow',diagnostic)
        limit,mimes=contract(url);status,headers,headers_complete=parse_headers(parts['headers'])
        try:meta=json.loads(parts['metadata'])
        except(ValueError,UnicodeError):meta={}
        meta=meta if isinstance(meta,dict)else{}
        if status is None and type(meta.get('http_code'))is int and 200<=meta['http_code']<=599:status=meta['http_code']
        started=parts.get('process_started')is True;raw=parts['body']
        observed=(started and type(status)is int and type(meta.get('http_code'))is int and status==meta['http_code']
          and 200<=status<=599 and meta.get('url_effective')==url and type(meta.get('ssl_verify_result'))is int
          and meta['ssl_verify_result']==0 and type(meta.get('proxy_used'))is int and meta['proxy_used']==0)
        # This request owns its status; unknown receipt metadata cannot inherit an earlier200/429/503.
        actual_status=status if observed else None
        diagnostic.update(client_process_started=started,http_request_sent=True if observed else None if started else False,
          http_request_count=int(observed),http_status=actual_status,http_status_observed=observed,response_complete=False,
          response_bytes=len(raw),response_sha256=sha256(raw).hexdigest(),request_method='GET')
        self.http_request_count+=int(observed);self.process_count+=int(started)
        response=httpx.Response(actual_status,headers=headers,request=httpx.Request('GET',url))if actual_status else None
        if response is not None:observe_http_response(response)
        def fail(kind):
            diagnostic['error_kind']=kind
            if started and raw and len(raw)<=limit:
                from official_response_evidence import archive_response
                proof=archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=actual_status,
                    evidence_kind='partial_or_rejected_transport_bytes',max_bytes=limit)
                diagnostic['rejected_original']=pathless(proof)
            self._emit(diagnostic)
            exc=SourceResponseError(kind,status_code=actual_status)
            exc.diagnostic.update(http_status_observed=observed,response_complete=False,
                response_bytes=len(raw),response_sha256=sha256(raw).hexdigest())
            if response is not None:exc.response=response
            if actual_status in{401,402,403,429}or actual_status and actual_status>=500:
                remember_failure(scope_key('Verified issuer news',endpoint=urlsplit(url).hostname),exc)
            raise exc
        if actual_status is not None and actual_status!=200:
            fail({401:'authentication',402:'payment_required',403:'access_denied',429:'rate_limited'}.get(actual_status,'server_error'if actual_status>=500 else'http_error'))
        if error or type(rc)is not int or rc!=0:fail(error or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
        if not observed or type(meta.get('num_redirects'))is not int or meta['num_redirects']!=0:fail('transport_metadata_invalid')
        if not headers_complete:fail('transport_headers_invalid')
        size=meta.get('size_download')
        if type(size)not in(int,float)or not math.isfinite(size)or not 0<len(raw)<=limit or size!=len(raw):fail('transport_body_incomplete')
        if headers.get('content-encoding','identity').lower()not in('','identity'):fail('unsupported_content_encoding')
        if headers.get('content-type','').split(';')[0].strip().lower()not in mimes:fail('unexpected_content_type')
        length=headers.get('content-length')
        if length is not None and (not re_full_length(length)or int(length)!=len(raw)):fail('transport_length_mismatch')
        if time.monotonic()>=self.deadline:fail('timeout')
        receipt=native_receipt(raw,url,time.time(),transport_for(raw));diagnostic['response_complete']=True
        self._emit(diagnostic,receipt);return receipt

    def _download(self,url,diagnostic):
        from cache_store import peek_cache_json
        if not self.record_provider_sla or not normal_flow(self.ticker):self._block('caa_unrecorded_or_non_native_flow',diagnostic)
        if proxy_url_for_request(url,'Verified issuer news')or any(os.getenv(k)for k in PROXY_ENV):self._block('proxy_configuration_unsupported',diagnostic)
        if any(cooldown_state(scope_key(p,endpoint='www.caa.gov.tw'))for p in(PROVIDER,'Verified issuer news')):self._block('cooldown',diagnostic)
        old=peek_cache_json('shared_provider:v1:'+sha256(('issuer-news-raw:v1:'+url).encode()).hexdigest())
        if isinstance(old,dict)and any(type(old.get(k))in(int,float)and math.isfinite(old[k])and old[k]>time.time()for k in('fresh_until_epoch','retry_after_epoch')):self._block('legacy_raw_cache_still_live',diagnostic)
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':self._block('test_network_disabled',diagnostic)
        limit,_=contract(url);remaining=min(5.,self.deadline-time.monotonic())
        if remaining<=0:self._block('timeout',diagnostic)
        argv=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
          '--max-filesize',str(limit),'--proto','=https','--max-redirs','0','--retry','0','--dump-header','/dev/fd/{HEADER_FD}',
          '--write-out','%{stderr}%{json}',url]
        parts,rc,error=collect_capped_process(argv,min(self.deadline,time.monotonic()+remaining),body_limit=limit,headers=True)
        return self._consume(url,parts,rc,error,diagnostic)

    def allow_attachment(self,index_receipt):
        if index_receipt!=self.staged.get(INDEX):raise SourceResponseError('caa_unowned_index_action')
        selected=select_dataset(receipt_body(index_receipt,INDEX,time.time()),datetime.now(ZoneInfo('Asia/Taipei')).date())
        self.attachment=selected['url'];return self.attachment

    def get(self,url):
        from cache_store import peek_cache_json
        contract(url)
        if url not in(INDEX,DIRECTORY,self.attachment)or url in self.seen or len(self.seen)>=3:raise SourceResponseError('caa_unpublished_or_duplicate_request')
        if url==DIRECTORY and INDEX not in self.staged or url not in(INDEX,DIRECTORY)and DIRECTORY not in self.staged:raise SourceResponseError('caa_required_publication_or_directory_missing')
        current_master(self.ticker,time.time())
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')
        self.seen.add(url);d={'url':url,'http_request_sent':False,'http_request_count':0,'http_status_observed':False,'cache_hit':False};self.components.append(d)
        if not self.record_provider_sla or not normal_flow(self.ticker):
            saved=peek_cache_json(raw_key(url));receipt=saved.get('value')if isinstance(saved,dict)else None
            if receipt is None:self._block('caa_unrecorded_or_non_native_flow',d)
            receipt_body(receipt,url,time.time());meta={'cache_hit':True}
        else:
            receipt,meta=shared_fetch(RAW_PREFIX+url,lambda:self._download(url,d),freshness_seconds=TTL,
                retention_seconds=TTL,error_retry_seconds=120,use_cache=True,lock_wait_seconds=min(1.,max(0.,self.deadline-time.monotonic())))
        d.update(cache_hit=bool(meta.get('cache_hit')),fetched_at_epoch=receipt.get('observed_at_epoch')if isinstance(receipt,dict)else None)
        if meta.get('error_kind')or meta.get('stale')or not isinstance(receipt,dict):raise SourceResponseError(d.get('error_kind')or meta.get('error_kind')or'caa_original_unavailable')
        receipt_body(receipt,url,time.time())
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')
        self.staged[url]=deepcopy(receipt);return receipt

def re_full_length(text):
    return isinstance(text,str)and re.fullmatch(r'\d{1,9}',text)is not None

def parse_headers(raw):
    """Keep only bounded critical fields from the last complete response block."""
    if not isinstance(raw,bytes)or len(raw)>65536:return None,{},False
    status=None;headers={};inside=False;complete=False;invalid=False;duplicates=set()
    for line in raw.replace(b'\r\n',b'\n').splitlines(keepends=True):
        if line.startswith(b'HTTP/'):
            match=re.fullmatch(rb'HTTP/\S+ +([2-5]\d{2})(?: +[^\n]*)?\n',line)
            status=int(match[1])if match else None;headers={};inside=status is not None;complete=False;invalid=False;duplicates=set()
        elif inside and line==b'\n':inside=False;complete=True
        elif inside:
            key,sep,value=line.partition(b':')
            if not sep or not line.endswith(b'\n'):invalid=True;continue
            try:name=key.decode('ascii').lower()
            except UnicodeError:invalid=True;continue
            if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-z-]+",name):invalid=True;continue
            if any(n<32 and n not in(9,10)or n==127 for n in value):invalid=True;continue
            if name in{'content-type','content-encoding','content-length','retry-after'}:
                if name in headers or name in duplicates:
                    invalid=True;duplicates.add(name);headers.pop(name,None)
                else:headers[name]=value.decode('latin-1').strip()
    return status,headers,bool(complete and not invalid)
