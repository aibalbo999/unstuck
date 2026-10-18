"""ZDT exact public GETs; immutable original receipts, no success cache reuse."""
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
from search_provider_runtime import SourceResponseError, scope_key, remember_failure, observe_http_response
from shared_provider_cache import _shared_lock
from .issuer_news_transport import PROVIDER as HTTP_PROVIDER, PROXY_ENV
from . import official_issuer_master
from .official_issuer_master_transport import IssuerMasterHttp
from .tcfhc_conference_transport import ConferenceHttp as _ConferenceHttp, valid_epoch, RECEIPT_FIELDS as BASE_FIELDS

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL = 'https://www.zdtco.com/public/tw/investor/events'
PDF_URL = 'https://www.zdtco.com/public/download/upload2026_10_052202610051657040600z5S6a1pdf'
PROVIDER = 'ZDT official conference presentation'
RAW_TTL = 1800
RECEIPT_FIELDS = BASE_FIELDS | {'fresh_until_epoch','request_body','response_metadata','acquisition_manifest','retrieval_policy'}
VALUE_FIELDS = {'url','body_b64','sha256','http_status','response_complete','request_method','request_body',
                'http_status_observed','fetched_at_epoch','response_metadata'}
META_FIELDS = {'http_status','effective_url','num_redirects','size_download','content_type','content_length','method','proxy_used','cache_control','pragma','expires','age','cf_cache_status'}


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
            if name in {'content-length','content-type','content-encoding','retry-after','cache-control','location','age','pragma','expires','cf-cache-status'}:
                if name in headers:raise SourceResponseError('transport_metadata_invalid')
                headers[name]=value.decode('latin-1').strip()
    return status,headers


def route_kind(url):
    return {MASTER_URL:'master',INDEX_URL:'index',PDF_URL:'pdf'}.get(url) if isinstance(url,str) else None


def contract(url):
    kind=route_kind(url)
    if kind=='master':return 2_500_000, {'text/csv','application/csv','application/octet-stream'}
    if kind=='index':return 1_048_576, {'text/html','application/xhtml+xml'}
    if kind=='pdf':return 10_837_119, {'application/pdf','application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def request_spec(url):
    contract(url)
    return {'request_method':'GET','request_body':None}


def validation_ttl(meta):
    # Validation lifetime is not permission to reuse this no-cache response.
    _,ttl=official_issuer_master._cache_policy({'cache_control':meta['cache_control'],
        'age':None if meta['age'] is None else str(meta['age'])})
    return ttl


def valid_expiry(receipt, observed=None):
    try:
        stamp,expiry=receipt['retrieved_at'],receipt['fresh_until_epoch']
        return (type(stamp) in (int,float) and type(expiry) in (int,float) and math.isfinite(stamp) and math.isfinite(expiry)
                and 0<stamp<expiry<=stamp+RAW_TTL and expiry==stamp+validation_ttl(receipt['response_metadata']) and stamp<=(time.time() if observed is None else observed)<expiry)
    except (ValueError,TypeError,KeyError,OverflowError):return False


def replay_expiry_valid(receipt, max_age, observed=None):
    # 1800 seconds is the live delivery deadline, not permission to reuse HTTP.
    # Longer replay only proves an immutable historical acquisition; it cannot
    # feed get_receipt(), which always performs a new native request.
    if isinstance(receipt,dict) and receipt.get('retrieval_policy') in (official_issuer_master.POLICY,official_issuer_master.JSON_POLICY):
        return official_issuer_master.live_or_historical_expiry_valid(receipt,max_age,observed)
    at = time.time() if observed is None else observed
    return valid_expiry(receipt, at if max_age <= RAW_TTL else receipt.get('retrieved_at'))


def _metadata_valid(meta,raw,url):
    if url == MASTER_URL and isinstance(meta,dict) and 'content_encoding' in meta:
        return official_issuer_master.valid_metadata(meta,raw)
    _,types=contract(url)
    return (isinstance(meta,dict) and set(meta)==META_FIELDS
            and type(meta['http_status']) is int and meta['http_status']==200 and meta['effective_url']==url
            and type(meta['num_redirects']) is int and meta['num_redirects']==0
            and type(meta['size_download']) in (int,float) and meta['size_download']==len(raw)
            and meta['content_type'] in types and (meta['content_length'] is None or type(meta['content_length']) is int and meta['content_length']==len(raw))
            and isinstance(meta['cache_control'],str)
            and isinstance(meta['pragma'],str) and isinstance(meta['expires'],str)
            and (meta['age'] is None or type(meta['age']) is int and meta['age'] >= 0)
            and isinstance(meta['cf_cache_status'],str)
            and meta['method']==request_spec(url)['request_method'] and type(meta['proxy_used']) is int and meta['proxy_used']==0)


class ConferenceHttp(_ConferenceHttp):
    route_contract=staticmethod(contract)
    # This source uses only exact anonymous GET URLs, including the published query.
    raw_cache_prefix='zdt-conference-raw:v1:GET:'
    admission_prefix='zdt-conference-admission:v1:GET:'

    _guarded_download = IssuerMasterHttp._guarded_download

    def _check(self):
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')

    def _external_guards(self,url):
        from cache_store import get_cache_json
        keys=[scope_key(HTTP_PROVIDER,endpoint=urlsplit(url).hostname)]
        try:
            for key in keys:
                state=get_cache_json(key)
                if state is None:continue
                if not isinstance(state,dict) or not {'retry_at','next_request_at'} & set(state):
                    raise ValueError('malformed host guard')
                until=state.get('retry_at',0)
                if type(until) not in (int,float) or not math.isfinite(until) or until<0:raise ValueError('invalid cooldown')
                if until>time.time():raise SourceResponseError('cooldown')
                pacing=state.get('next_request_at',0)
                if type(pacing) not in (int,float) or not math.isfinite(pacing) or pacing<0:raise ValueError('invalid pacing')
                if pacing>time.time():raise SourceResponseError('request_pacing')
        except SourceResponseError:raise
        except Exception as exc:raise SourceResponseError('guard_storage_unavailable') from exc
        self._check()

    def download_original(self,url,diagnostic):
        if url == official_issuer_master.JSON_URL:
            from .official_issuer_master_json import download_original
            return download_original(self,diagnostic,parse_headers=_headers)
        limit,types=contract(url);spec=request_spec(url)
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
        if proxy_url_for_request(url,HTTP_PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
        self._external_guards(url)
        remaining=min(20. if url == PDF_URL else 5.,self.deadline-time.monotonic())
        if remaining<=0:raise SourceResponseError('timeout')
        stop=min(self.deadline,time.monotonic()+remaining)
        args=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
              '--max-filesize',str(limit),'--proto','=https','--max-redirs','0','--retry','0',
              '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}']
        args.append(url)
        parts,rc,error=collect_capped_process(args,stop,body_limit=limit,headers=True)
        diagnostic.update(http_request_sent=bool(parts.get('process_started')),**spec)
        self.http_request_count+=int(diagnostic['http_request_sent'])
        try:meta=json.loads(parts['metadata'])
        except (ValueError,UnicodeDecodeError):meta={}
        if not isinstance(meta,dict):meta={}
        observed=meta.get('http_code')
        if type(observed) is int and 100<=observed<=599:diagnostic['http_status']=observed
        try:status,headers=_headers(parts['headers'])
        except SourceResponseError as exc:
            diagnostic['error_kind']=exc.error_kind
            raise SourceResponseError(exc.error_kind,status_code=diagnostic.get('http_status')) from exc
        response=httpx.Response(status,headers=headers,request=httpx.Request(spec['request_method'],url)) if status else None
        if response is not None:observe_http_response(response)
        def fail(kind):
            diagnostic.update(error_kind=kind,http_status=status)
            exc=SourceResponseError(kind,status_code=status)
            if response is not None:exc.response=response
            if status in {401,403,429} or status and status>=500:
                remember_failure(scope_key(HTTP_PROVIDER,endpoint=urlsplit(url).hostname),exc)
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
                  'size_download':meta.get('size_download'),'content_type':ctype,'content_length':clen,'method':meta.get('method'),'proxy_used':meta.get('proxy_used'),'cache_control':headers.get('cache-control','')}
        if url != MASTER_URL:
            age = headers.get('age')
            if age is not None and not re.fullmatch(r'[0-9]+',age):fail('transport_metadata_invalid')
            metadata.update(pragma=headers.get('pragma',''),expires=headers.get('expires',''),
                            age=int(age) if age is not None else None,cf_cache_status=headers.get('cf-cache-status',''))
        if url == MASTER_URL:
            metadata = official_issuer_master.master_metadata(metadata,raw,headers)
        if (status!=200 or not _metadata_valid(metadata,raw,url)
                or meta.get('content_type','').split(';')[0].strip().lower()!=ctype):fail('transport_metadata_invalid')
        if headers.get('content-encoding','identity').lower() not in {'','identity'}:fail('unsupported_content_encoding')
        challenge_text = raw[:8192].decode('utf-8','ignore')
        if re.search(r'FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|captcha|access denied|因為安全性考量|驗證碼',challenge_text,re.I):fail('access_denied')
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

    def get_receipt(self, url):
        if url == MASTER_URL:
            return IssuerMasterHttp.get_receipt(self,url)
        limit, _ = contract(url)
        diagnostic = {'url': url, 'http_request_sent': False, 'cache_hit': False, **request_spec(url)}
        self.components.append(diagnostic)
        self._check()
        # A lock serializes acquisition, but never supplies an earlier response.
        digest = sha256((self.raw_cache_prefix + url).encode()).hexdigest()
        with _shared_lock(digest, min(1., max(0., self.deadline-time.monotonic()))) as acquired:
            self._check()
            if not acquired:
                raise SourceResponseError('single_flight_busy')
            value = self._download(url, diagnostic)
            self._check()
            raw = base64.b64decode(value['body_b64'], validate=True)
            if (not 0 < len(raw) <= limit or sha256(raw).hexdigest() != value['sha256']
                    or not _metadata_valid(value['response_metadata'], raw, url)):
                raise SourceResponseError('transport_metadata_invalid')
            stamp = value['fetched_at_epoch']
            receipt = archive_response(raw, source_url=url, retrieved_at=stamp, max_bytes=limit)
            if receipt.get('status') != 'archived':
                raise SourceResponseError('original_unverified')
            receipt.update(http_status_observed=True, request_method='GET', request_body=None,
                           response_complete=True, cache_hit=False, fresh_until_epoch=stamp+validation_ttl(value['response_metadata']),
                           response_metadata=value['response_metadata'],
                           retrieval_policy='always_native_no_success_cache')
            # Immutable manifest binds the original epoch and validation deadline.
            # It is provenance for saved reports, never an HTTP/cache response.
            manifest = _manifest_bytes(receipt)
            receipt['acquisition_manifest'] = archive_response(
                manifest, source_url=url, retrieved_at=stamp,
                evidence_kind='private_acquisition_manifest', http_status=None)
            if original_bytes(receipt, url, max_age=RAW_TTL) != raw:
                raise SourceResponseError('original_unverified')
            self._check()
            diagnostic.update(fetched_at_epoch=stamp, original_receipt=receipt,
                              http_status=200, original_http_status_observed=True)
        # Lock cleanup and final delivery are part of this request's budget.
        self._check()
        if not valid_expiry(receipt):
            raise SourceResponseError('original_expired')
        return raw, receipt


def _manifest_bytes(receipt):
    return json.dumps({k:v for k,v in receipt.items() if k != 'acquisition_manifest'},
                      sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode()


def original_bytes(receipt, url, *, max_age=86400):
    if url == official_issuer_master.JSON_URL:
        if not isinstance(receipt,dict) or receipt.get('source_url') != url:
            raise ValueError('JSON master URL mismatch')
        return official_issuer_master.original_bytes(receipt,max_age=max_age)
    if url == MASTER_URL and isinstance(receipt,dict) and receipt.get('retrieval_policy') == official_issuer_master.POLICY:
        return official_issuer_master.original_bytes(receipt,max_age=max_age)
    limit, _ = contract(url)
    if (not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS
            or receipt.get('status') != 'archived' or receipt.get('source_url') != url
            or receipt.get('cache_hit') is not False or receipt.get('request_method') != 'GET'
            or receipt.get('request_body') is not None or receipt.get('response_complete') is not True
            or receipt.get('http_status_observed') is not True or type(receipt.get('http_status')) is not int
            or receipt['http_status'] != 200 or receipt.get('evidence_kind') != 'raw_http_response_bytes'
            or receipt.get('historical_point_in_time_verified') is not False
            or receipt.get('finality_guaranteed') is not False
            or receipt.get('retrieval_policy') != 'always_native_no_success_cache'
            or not valid_epoch(receipt.get('retrieved_at'), max_age) or not replay_expiry_valid(receipt,max_age)):
        raise ValueError('ZDT original receipt unverified')
    raw = read_response(receipt, max_bytes=limit)
    if (type(receipt.get('raw_response_bytes')) is not int or not 0 < len(raw) <= limit
            or len(raw) != receipt['raw_response_bytes'] or not _metadata_valid(receipt['response_metadata'], raw, url)):
        raise ValueError('ZDT original metadata mismatch')
    proof = receipt['acquisition_manifest']
    if (not isinstance(proof, dict) or set(proof) != BASE_FIELDS - {'http_status_observed','request_method','response_complete','cache_hit'}
            or proof.get('status') != 'archived' or proof.get('source_url') != url
            or type(proof.get('retrieved_at')) not in (int,float) or proof['retrieved_at'] != receipt['retrieved_at']
            or proof.get('http_status') is not None or proof.get('evidence_kind') != 'private_acquisition_manifest'
            or proof.get('historical_point_in_time_verified') is not False or proof.get('finality_guaranteed') is not False
            or type(proof.get('raw_response_bytes')) is not int):
        raise ValueError('ZDT independent acquisition manifest invalid')
    manifest = read_response(proof, max_bytes=16384)
    if len(manifest) != proof['raw_response_bytes'] or manifest != _manifest_bytes(receipt):
        raise ValueError('ZDT original epoch/deadline differs from immutable acquisition manifest')
    if not valid_epoch(receipt['retrieved_at'],max_age) or not replay_expiry_valid(receipt,max_age):
        raise ValueError('ZDT original expired during archive replay')
    return raw
