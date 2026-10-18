"""Exact Sigurd GET/POST originals, independent deadlines and existing MOPS guards."""
import base64
from hashlib import sha256
import json
import math
import os
import re
import time
from urllib.parse import urlsplit
from uuid import uuid4
import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError, scope_key, remember_failure, remember_success, observe_http_response
from shared_provider_cache import shared_fetch
from .issuer_news_transport import PROVIDER as HTTP_PROVIDER, PROXY_ENV
from .tcfhc_conference_transport import ConferenceHttp as _ConferenceHttp, valid_epoch, RECEIPT_FIELDS as BASE_FIELDS

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL = 'https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1'
PDF_URL = 'https://mopsov.twse.com.tw/nas/STR/625720261006E001.pdf'
INDEX_FORM = 'encodeURIComponent=1&step=1&firstin=1&off=1&TYPEK=sii&co_id=6257&year=115&month='
PROVIDER = 'Sigurd official conference presentation'
MOPS_GUARD = scope_key('MOPS', endpoint='mopsov_investor_conference')
RAW_TTL = 1800
RECEIPT_FIELDS = BASE_FIELDS | {'fresh_until_epoch','request_body','response_metadata'}
VALUE_FIELDS = {'url','body_b64','sha256','http_status','response_complete','request_method','request_body',
                'http_status_observed','fetched_at_epoch','response_metadata'}
META_FIELDS = {'http_status','effective_url','num_redirects','size_download','content_type','content_length','method','proxy_used'}


def _headers(raw):
    """Preserve final response lengths; reject ambiguous protected headers."""
    status=None;headers={}
    for line in raw.replace(b'\r\n',b'\n').splitlines():
        if line.startswith(b'HTTP/'):
            match=re.fullmatch(rb'HTTP/[^ ]+ +([1-5][0-9]{2})(?: .*)?',line)
            if not match:raise SourceResponseError('transport_metadata_invalid')
            status=int(match[1]);headers={}
        elif line and status:
            key,sep,value=line.partition(b':')
            if not sep:raise SourceResponseError('transport_metadata_invalid')
            name=key.decode('ascii','strict').lower()
            if name in {'content-length','content-type','content-encoding','retry-after'}:
                if name in headers:raise SourceResponseError('transport_metadata_invalid')
                headers[name]=value.decode('latin-1').strip()
    return status,headers


def route_kind(url):
    return {MASTER_URL:'master',INDEX_URL:'index',PDF_URL:'pdf'}.get(url) if isinstance(url,str) else None


def contract(url):
    kind=route_kind(url)
    if kind=='master':return 2_500_000, {'text/csv','application/csv','application/octet-stream'}
    if kind=='index':return 1_048_576, {'text/html','application/xhtml+xml'}
    if kind=='pdf':return 8*1024*1024, {'application/pdf','application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def request_spec(url):
    contract(url)
    return {'request_method':'POST' if url==INDEX_URL else 'GET','request_body':INDEX_FORM if url==INDEX_URL else None}


def valid_expiry(receipt, observed=None):
    try:
        stamp,expiry=receipt['retrieved_at'],receipt['fresh_until_epoch']
        return (type(stamp) in (int,float) and type(expiry) in (int,float) and math.isfinite(stamp) and math.isfinite(expiry)
                and 0<stamp<expiry<=stamp+RAW_TTL and stamp<=(time.time() if observed is None else observed)<expiry)
    except (ValueError,TypeError,KeyError,OverflowError):return False


def _metadata_valid(meta,raw,url):
    _,types=contract(url)
    return (isinstance(meta,dict) and set(meta)==META_FIELDS
            and type(meta['http_status']) is int and meta['http_status']==200 and meta['effective_url']==url
            and type(meta['num_redirects']) is int and meta['num_redirects']==0
            and type(meta['size_download']) in (int,float) and meta['size_download']==len(raw)
            and meta['content_type'] in types and (meta['content_length'] is None or type(meta['content_length']) is int and meta['content_length']==len(raw))
            and meta['method']==request_spec(url)['request_method'] and type(meta['proxy_used']) is int and meta['proxy_used']==0)


def _saved_value(raw,url,original_epoch):
    from cache_store import get_cache_json
    try:
        limit,_=contract(url)
        key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest()
        row=get_cache_json(key)
        if not isinstance(row,dict) or set(row)!={'value','fetched_at_epoch','fresh_until_epoch','retained_until_epoch'}:
            raise ValueError('saved observation unavailable')
        for key in ('fetched_at_epoch','fresh_until_epoch','retained_until_epoch'):
            if type(row[key]) not in (int,float) or not math.isfinite(row[key]) or row[key]<=0:raise ValueError('invalid saved time')
        value=row['value']
        if (not isinstance(value,dict) or set(value)!=VALUE_FIELDS or value['url']!=url
                or value['sha256']!=sha256(raw).hexdigest() or type(value['http_status']) is not int or value['http_status']!=200
                or value['response_complete'] is not True or value['http_status_observed'] is not True
                or any(value[k]!=v for k,v in request_spec(url).items())
                or not _metadata_valid(value['response_metadata'],raw,url)
                or not valid_epoch(value['fetched_at_epoch'],RAW_TTL) or value['fetched_at_epoch']!=original_epoch
                or not original_epoch<=row['fetched_at_epoch']<=time.time()
                or not row['fetched_at_epoch']<row['fresh_until_epoch']<=row['retained_until_epoch']):
            raise ValueError('saved original metadata mismatch')
        encoded=value['body_b64']
        if not isinstance(encoded,str) or len(encoded)>(limit+2)//3*4 or base64.b64decode(encoded,validate=True)!=raw:
            raise ValueError('saved complete original bytes mismatch')
        return value,min(row['fresh_until_epoch'],original_epoch+RAW_TTL)
    except Exception as exc:raise ValueError('Sigurd saved original deadline unverified') from exc


def original_bytes(receipt,url,*,max_age=86400):
    limit,_=contract(url)
    if (not isinstance(receipt,dict) or set(receipt)!=RECEIPT_FIELDS or receipt.get('status')!='archived'
            or receipt.get('source_url')!=url or not valid_epoch(receipt.get('retrieved_at'),max_age) or not valid_expiry(receipt)
            or type(receipt.get('http_status')) is not int or receipt['http_status']!=200
            or receipt.get('historical_point_in_time_verified') is not False or receipt.get('finality_guaranteed') is not False
            or receipt.get('evidence_kind')!='raw_http_response_bytes' or receipt.get('http_status_observed') is not True
            or receipt.get('response_complete') is not True or type(receipt.get('cache_hit')) is not bool
            or any(receipt.get(k)!=v for k,v in request_spec(url).items())):raise ValueError('Sigurd original receipt unverified')
    raw=read_response(receipt)
    if type(receipt.get('raw_response_bytes')) is not int or not 0<len(raw)<=limit or len(raw)!=receipt['raw_response_bytes']:
        raise ValueError('Sigurd original size unverified')
    saved,expiry=_saved_value(raw,url,receipt['retrieved_at'])
    if (receipt['fresh_until_epoch']!=expiry or not _metadata_valid(receipt['response_metadata'],raw,url)
            or json.dumps(receipt['response_metadata'],sort_keys=True)!=json.dumps(saved['response_metadata'],sort_keys=True)):
        raise ValueError('Sigurd original saved observation mismatch')
    if not valid_epoch(receipt['retrieved_at'],max_age) or not valid_expiry(receipt):raise ValueError('Sigurd original expired during replay')
    return raw


class ConferenceHttp(_ConferenceHttp):
    route_contract=staticmethod(contract)
    # Include the exact request method/form policy, in addition to each URL.
    raw_cache_prefix='sigurd-conference-raw:v1:'+sha256(('POST\n'+INDEX_FORM).encode()).hexdigest()+':'
    admission_prefix='sigurd-conference-admission:v1:'+sha256(('POST\n'+INDEX_FORM).encode()).hexdigest()+':'

    def _check(self):
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')

    def _external_guards(self,url):
        from cache_store import get_cache_json
        keys=[scope_key(HTTP_PROVIDER,endpoint=urlsplit(url).hostname)]
        if url==INDEX_URL:keys.append(MOPS_GUARD)
        try:
            for key in keys:
                state=get_cache_json(key)
                if state is None:continue
                until=state.get('retry_at',0) if isinstance(state,dict) else None
                if type(until) not in (int,float) or not math.isfinite(until) or until<0:raise ValueError('invalid cooldown')
                if until>time.time():raise SourceResponseError('cooldown')
                pacing=state.get('next_request_at',0)
                if type(pacing) not in (int,float) or not math.isfinite(pacing) or pacing<0:raise ValueError('invalid pacing')
                if pacing>time.time():raise SourceResponseError('request_pacing')
        except SourceResponseError:raise
        except Exception as exc:raise SourceResponseError('guard_storage_unavailable') from exc
        self._check()

    def download_original(self,url,diagnostic):
        limit,types=contract(url);spec=request_spec(url)
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
        if proxy_url_for_request(url,HTTP_PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
        self._external_guards(url)
        remaining=min(5.,self.deadline-time.monotonic())
        if remaining<=0:raise SourceResponseError('timeout')
        stop=min(self.deadline,time.monotonic()+remaining)
        args=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
              '--max-filesize',str(limit),'--proto','=https','--max-redirs','0','--retry','0',
              '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}']
        if spec['request_method']=='POST':args+=['--data',spec['request_body']]
        args.append(url)
        diagnostic['request_started_at']=time.time()
        parts,rc,error=collect_capped_process(args,stop,body_limit=limit,headers=True)
        diagnostic.update(http_request_sent=bool(parts.get('process_started')),**spec)
        self.http_request_count+=int(diagnostic['http_request_sent'])
        status,headers=_headers(parts['headers'])
        try:meta=json.loads(parts['metadata'])
        except (ValueError,UnicodeDecodeError):meta={}
        if not isinstance(meta,dict):meta={}
        response=httpx.Response(status,headers=headers,request=httpx.Request(spec['request_method'],url)) if status else None
        if response is not None:observe_http_response(response)
        def fail(kind):
            diagnostic.update(error_kind=kind,http_status=status)
            exc=SourceResponseError(kind,status_code=status)
            if response is not None:exc.response=response
            if status in {401,403,429} or status and status>=500:
                remember_failure(scope_key(HTTP_PROVIDER,endpoint=urlsplit(url).hostname),exc)
            if url==INDEX_URL:remember_failure(MOPS_GUARD,exc)
            raise exc
        if status is not None and status!=200:fail({401:'authentication',403:'access_denied',429:'rate_limited'}.get(status,'server_error' if status>=500 else 'http_error'))
        if error or rc:fail(error or ('timeout' if rc==28 else 'response_too_large' if rc==63 else 'transport_error'))
        if time.monotonic()>=stop:fail('timeout')
        raw=parts['body']
        if not isinstance(raw,bytes) or not 0<len(raw)<=limit:fail('response_too_large')
        ctype=headers.get('content-type','').split(';')[0].strip().lower()
        try:clen=int(headers['content-length']) if 'content-length' in headers else None
        except (TypeError,ValueError):fail('transport_metadata_invalid')
        metadata={'http_status':meta.get('http_code'),'effective_url':meta.get('url_effective'),'num_redirects':meta.get('num_redirects'),
                  'size_download':meta.get('size_download'),'content_type':ctype,'content_length':clen,'method':meta.get('method'),'proxy_used':meta.get('proxy_used')}
        if (status!=200 or not _metadata_valid(metadata,raw,url)
                or meta.get('content_type','').split(';')[0].strip().lower()!=ctype):fail('transport_metadata_invalid')
        if headers.get('content-encoding','identity').lower() not in {'','identity'}:fail('unsupported_content_encoding')
        if re.search(r'FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|captcha|access denied|因為安全性考量|驗證碼',raw[:8192].decode('utf-8','ignore'),re.I):fail('access_denied')
        diagnostic.update(http_status=status,response_bytes=len(raw),response_sha256=sha256(raw).hexdigest(),response_metadata=metadata)
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),**spec,'response_metadata':metadata}

    def _download(self,url,diagnostic):
        self._check();self._retry_guard(url);self._external_guards(url)
        from cache_store import get_cache_json,set_cache_json
        key=self._admission_key(url);marker={'token':uuid4().hex,'retry_at':time.time()+120}
        try:
            set_cache_json(key,marker,ttl_seconds=120)
            if get_cache_json(key)!=marker:raise SourceResponseError('lease_lost')
        except SourceResponseError:raise
        except Exception as exc:raise SourceResponseError('guard_storage_unavailable') from exc
        self._check()
        value=self.download_original(url,diagnostic)
        fetched_at=time.time()
        self._check()
        try:
            if get_cache_json(key)==marker:set_cache_json(key,{**marker,'retry_at':0},ttl_seconds=1)
        except Exception:diagnostic['admission_release_failed']=True
        self._check()
        return {**value,'http_status':200,'response_complete':True,'http_status_observed':True,'fetched_at_epoch':fetched_at}

    def get_receipt(self,url,*,parser=None):
        limit,_=contract(url);spec=request_spec(url)
        diagnostic={'url':url,'http_request_sent':False,**spec};self.components.append(diagnostic);self._check()
        if self.force_refresh:self._retry_guard(url)
        failure=[]
        def collect():
            try:return self._download(url,diagnostic)
            except SourceResponseError as exc:failure.append(exc);raise
        def remaining_ttl(value):
            stamp=value.get('fetched_at_epoch') if isinstance(value,dict) else None
            if not valid_epoch(stamp,RAW_TTL):raise SourceResponseError('original_expired')
            remaining=math.floor(stamp+RAW_TTL-time.time())
            if remaining<1:raise SourceResponseError('original_expired')
            return remaining
        value,meta=shared_fetch(self.raw_cache_prefix+url,collect,freshness_seconds=RAW_TTL,retention_seconds=RAW_TTL,
            result_ttl=remaining_ttl,error_retry_seconds=120,force_refresh=self.force_refresh,
            lock_wait_seconds=min(1.,max(0.,self.deadline-time.monotonic())))
        diagnostic.update(cache_hit=bool(meta.get('cache_hit')),fetched_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('error_kind') or meta.get('stale'):
            if failure:raise failure[0]
            kind=meta.get('error_kind') or 'stale_receipt'
            raise SourceResponseError('cooldown' if kind=='SourceResponseError' else kind)
        try:
            if not isinstance(value,dict) or set(value)!=VALUE_FIELDS:raise ValueError('invalid value fields')
            encoded=value['body_b64']
            if not isinstance(encoded,str) or len(encoded)>(limit+2)//3*4:raise ValueError('invalid encoded size')
            raw=base64.b64decode(encoded,validate=True)
            if not 0<len(raw)<=limit:raise ValueError('invalid raw size')
            saved,expiry=_saved_value(raw,url,value['fetched_at_epoch'])
            if saved!=value:raise ValueError('saved original replaced')
        except (ValueError,KeyError,TypeError) as exc:raise SourceResponseError('cache_receipt_invalid') from exc
        receipt=archive_response(raw,source_url=url,retrieved_at=value['fetched_at_epoch'])
        if receipt.get('status')!='archived':raise SourceResponseError('original_unverified')
        receipt.update(http_status_observed=True,response_complete=True,cache_hit=bool(meta.get('cache_hit')),
                       fresh_until_epoch=expiry,response_metadata=value['response_metadata'],**spec)
        if original_bytes(receipt,url,max_age=RAW_TTL)!=raw:raise SourceResponseError('original_unverified')
        self._check()
        diagnostic.update(fetched_at_epoch=value['fetched_at_epoch'],original_receipt=receipt,http_status=200,original_http_status_observed=True)
        parsed=parser(raw,receipt) if parser is not None else raw
        self._check()
        if (url==INDEX_URL and parser is not None and diagnostic.get('http_request_sent') is True
                and not receipt['cache_hit']):
            remember_success(MOPS_GUARD,request_started_at=diagnostic.get('request_started_at'))
        self._check()
        return parsed,receipt
