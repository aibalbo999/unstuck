"""Exact Jentech published originals, never a successful HTTP response cache.

The shared exchange master retains its own shorter TTL and CSV/JSON policy.
Issuer HTML uses existing admission, locking and private archive primitives.
"""
import base64
from hashlib import sha256
import json
import os
import re
import time
from urllib.parse import urlsplit

import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError, scope_key, remember_failure, observe_http_response
from shared_provider_cache import _shared_lock
from . import official_issuer_master as master
from .official_issuer_master_transport import IssuerMasterHttp
from .issuer_news_transport import PROVIDER as HTTP_PROVIDER, PROXY_ENV
from .lienhwa_conference_transport import (
    ConferenceHttp as PrivateHttp, _headers, _manifest_bytes, validation_ttl,
    valid_expiry, replay_expiry_valid, RECEIPT_FIELDS, META_FIELDS,
)
from .tcfhc_conference_transport import valid_epoch, RECEIPT_FIELDS as BASE_FIELDS

MASTER_URL = master.MASTER_URL
MASTER = MASTER_URL
INDEX_URL = 'https://www.jentech.com.tw/zh/institutional-investor-conference-information'
SITE_ID = '5d4fbe70-bf03-4c9c-9b1d-5e632fda0f7f'
PROVIDER = 'Jentech official conference presentation'
RAW_TTL = 1800
POLICY = 'always_native_no_success_cache'


def official_url(url):
    return isinstance(url,str) and re.fullmatch(r'https://www\.jentech\.com\.tw/zh/_files/ugd/4b19cc_[0-9a-f]{32}\.pdf',url) is not None


def pdf_url(url):
    return isinstance(url,str) and re.fullmatch(r'https://'+re.escape(SITE_ID)+r'\.filesusr\.com/ugd/4b19cc_[0-9a-f]{32}\.pdf',url) is not None


def cdn_url(url):
    if not official_url(url):raise ValueError('unpublished issuer redirect route')
    return 'https://'+SITE_ID+'.filesusr.com'+url.split('/zh/_files',1)[1]


def contract(url):
    if url==INDEX_URL:return 2*1024*1024, {'text/html','application/xhtml+xml'}
    if official_url(url):return 65536, {''}
    if pdf_url(url):return 8*1024*1024, {'application/pdf','application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def redirect_headers(raw,url):
    # Archive the actual single 301 header block; no automatic redirect and
    # no inferred Location. Curl must independently prove an empty body.
    if (not isinstance(raw,bytes) or not 0<len(raw)<=65536 or not raw.endswith(b'\r\n\r\n')
            or raw.count(b'HTTP/')!=1 or b'\r\n\r\n' in raw[:-4]):raise ValueError('incomplete redirect headers')
    lines=raw[:-4].split(b'\r\n')
    if not re.fullmatch(rb'HTTP/(?:1\.[01]|2|3) 301(?: [^\r\n]*)?',lines[0]):raise ValueError('wrong redirect status')
    fields={}
    for line in lines[1:]:
        key,sep,value=line.partition(b':')
        if not sep or not re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+",key):raise ValueError('malformed redirect headers')
        if any(c<32 and c!=9 or c==127 for c in value):raise ValueError('invalid header value')
        fields.setdefault(key.decode('ascii').lower(),[]).append(value.decode('latin-1').strip())
    if fields.get('location')!=[cdn_url(url)] or fields.get('content-length')!=['0']:
        raise ValueError('redirect identity or empty body mismatch')
    if 'transfer-encoding' in fields or fields.get('content-encoding',['identity']) not in (['identity'],['']):
        raise ValueError('unsupported redirect body encoding')
    status,headers=_headers(raw)
    return headers


def metadata_valid(meta,raw,url):
    limit,types=contract(url);redirect=official_url(url)
    fields=META_FIELDS|{'location','response_body_sha256'} if redirect else META_FIELDS
    if not (isinstance(raw,bytes) and 0<len(raw)<=limit and isinstance(meta,dict) and set(meta)==fields
            and type(meta['http_status']) is int and meta['http_status']==(301 if redirect else 200)
            and meta['effective_url']==url and type(meta['num_redirects']) is int and meta['num_redirects']==0
            and type(meta['size_download']) in (int,float) and meta['size_download']==(0 if redirect else len(raw))
            and meta['content_type'] in types
            and (type(meta['content_length']) is int and meta['content_length']==0 if redirect else
                 meta['content_length'] is None or type(meta['content_length']) is int and meta['content_length']==len(raw))
            and meta['method']=='GET' and type(meta['proxy_used']) is int and meta['proxy_used']==0
            and all(isinstance(meta[k],str) for k in ('cache_control','pragma','expires','cf_cache_status'))
            and (meta['age'] is None or type(meta['age']) is int and meta['age']>=0)):return False
    if redirect:
        try:
            h=redirect_headers(raw,url)
            return (meta['location']==cdn_url(url) and meta['response_body_sha256']==sha256(b'').hexdigest()
                and all(meta[k]==h.get(k.replace('_','-'),'') for k in ('cache_control','pragma','expires','cf_cache_status'))
                and meta['age']==(int(h['age']) if 'age' in h else None))
        except (ValueError,TypeError,SourceResponseError):return False
    return True


def original_bytes(receipt, url, *, max_age=RAW_TTL):
    if url in (MASTER, master.JSON_URL):
        if not isinstance(receipt, dict) or receipt.get('source_url') != url:
            raise ValueError('Jentech master URL mismatch')
        return master.original_bytes(receipt, max_age=max_age)
    limit, _ = contract(url)
    if (not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS
            or receipt.get('status') != 'archived' or receipt.get('source_url') != url
            or receipt.get('cache_hit') is not False or receipt.get('request_method') != 'GET'
            or receipt.get('request_body') is not None or receipt.get('response_complete') is not True
            or receipt.get('http_status_observed') is not True or type(receipt.get('http_status')) is not int
            or receipt['http_status'] != (301 if official_url(url) else 200)
            or receipt.get('evidence_kind') != ('raw_http_response_headers' if official_url(url) else 'raw_http_response_bytes')
            or receipt.get('historical_point_in_time_verified') is not False or receipt.get('finality_guaranteed') is not False
            or receipt.get('retrieval_policy') != POLICY or not valid_epoch(receipt.get('retrieved_at'), max_age)
            or not replay_expiry_valid(receipt, max_age)):
        raise ValueError('Jentech original receipt invalid')
    raw = read_response(receipt, max_bytes=limit)
    if type(receipt['raw_response_bytes']) is not int or len(raw) != receipt['raw_response_bytes'] or not metadata_valid(receipt['response_metadata'], raw, url):
        raise ValueError('Jentech original metadata mismatch')
    proof = receipt['acquisition_manifest']
    if (not isinstance(proof, dict) or set(proof) != BASE_FIELDS - {'http_status_observed', 'request_method', 'response_complete', 'cache_hit'}
            or proof.get('status') != 'archived' or proof.get('source_url') != url
            or type(proof.get('retrieved_at')) not in (int, float) or proof['retrieved_at'] != receipt['retrieved_at']
            or proof.get('http_status') is not None or proof.get('evidence_kind') != 'private_acquisition_manifest'
            or proof.get('historical_point_in_time_verified') is not False or proof.get('finality_guaranteed') is not False
            or type(proof.get('raw_response_bytes')) is not int):
        raise ValueError('Jentech acquisition manifest invalid')
    manifest = read_response(proof, max_bytes=16384)
    if len(manifest) != proof['raw_response_bytes'] or manifest != _manifest_bytes(receipt):
        raise ValueError('Jentech immutable metadata mismatch')
    if not valid_epoch(receipt['retrieved_at'], max_age) or not replay_expiry_valid(receipt, max_age):
        raise ValueError('Jentech original expired during replay')
    return raw


class JentechConferenceHttp(PrivateHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'jentech-conference-raw:v1:GET:'
    admission_prefix = 'jentech-conference-admission:v1:GET:'

    def __init__(self, deadline, *, force_refresh=False, use_cache=True):
        super().__init__(deadline,force_refresh=force_refresh,use_cache=use_cache)
        self._authorized={MASTER,INDEX_URL}
        self._obtained={}

    def authorize_index_links(self,index_receipt):
        from .jentech_conference import select_presentation
        if not isinstance(index_receipt,dict) or self._obtained.get(INDEX_URL)!=index_receipt:raise SourceResponseError('original_unverified')
        selected=select_presentation(original_bytes(index_receipt,INDEX_URL),index_receipt['retrieved_at'])
        self._authorized.add(selected['official_pdf_url'])
        self._check()
        return selected

    def authorize_redirect(self,receipt,selected):
        # Selected metadata alone is not authority: replay this instance's
        # current index and require the actually obtained 301 receipt too.
        expected=self.authorize_index_links(self._obtained.get(INDEX_URL))
        if expected!=selected or self._obtained.get(selected['official_pdf_url'])!=receipt:
            raise SourceResponseError('original_unverified')
        original_bytes(receipt,selected['official_pdf_url'])
        if receipt['response_metadata']['location']!=selected['pdf_url']:raise SourceResponseError('transport_url_invalid')
        self._authorized.add(selected['pdf_url'])
        self._check()

    def _download(self,url,diagnostic):
        value=super()._download(url,diagnostic)
        return {**value,'http_status':value['response_metadata']['http_status']}

    def _retry_guard(self, url):
        # This namespace never stores successful raw responses. A malformed
        # leftover cannot be mistaken for permission to acquire another body.
        from cache_store import get_cache_json
        try:
            key = 'shared_provider:v1:' + sha256((self.raw_cache_prefix + url).encode()).hexdigest()
            row = get_cache_json(key)
            if row is not None and (not isinstance(row, dict) or not isinstance(row.get('error_kind'), str) or not row['error_kind']):
                raise ValueError('malformed Jentech raw guard')
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        super()._retry_guard(url)

    def download_original(self, url, diagnostic):
        # PrivateHttp's guards/admission are reused, never its issuer URL routes.
        if url not in self._authorized:raise SourceResponseError('transport_url_invalid')
        limit, _ = contract(url)
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
            raise SourceResponseError('test_network_disabled')
        if proxy_url_for_request(url, HTTP_PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
            raise SourceResponseError('proxy_configuration_unsupported')
        self._external_guards(url)
        remaining = min(5., self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError('timeout')
        stop = min(self.deadline, time.monotonic() + remaining)
        args = ['/usr/bin/curl', '--disable', '--silent', '--max-time', str(remaining),
                '--connect-timeout', str(min(2., remaining)), '--max-filesize', str(1 if official_url(url) else limit),
                '--proto', '=https', '--max-redirs', '0', '--retry', '0', '--dump-header',
                '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}', url]
        parts, rc, error = collect_capped_process(args, stop, body_limit=1 if official_url(url) else limit, headers=True)
        diagnostic['http_request_sent'] = bool(parts.get('process_started'))
        self.http_request_count += int(diagnostic['http_request_sent'])
        try:
            meta = json.loads(parts['metadata'])
        except (ValueError, UnicodeDecodeError):
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        observed = meta.get('http_code')
        if type(observed) is int and 100 <= observed <= 599:
            diagnostic['http_status'] = observed
        try:
            status, headers = _headers(parts['headers'])
        except SourceResponseError as exc:
            diagnostic['error_kind'] = exc.error_kind
            raise SourceResponseError(exc.error_kind, status_code=diagnostic.get('http_status')) from exc
        response = httpx.Response(status, headers=headers, request=httpx.Request('GET', url)) if status else None
        if response is not None:
            observe_http_response(response)

        def fail(kind):
            diagnostic.update(error_kind=kind, http_status=status)
            exc = SourceResponseError(kind, status_code=status)
            if response is not None:
                exc.response = response
            if status in {401, 403, 429} or status and status >= 500:
                remember_failure(scope_key(HTTP_PROVIDER, endpoint=urlsplit(url).hostname), exc)
            raise exc

        if status is not None and status != (301 if official_url(url) else 200):
            fail({401: 'authentication', 403: 'access_denied', 429: 'rate_limited'}.get(status, 'server_error' if status >= 500 else 'http_error'))
        if error or rc:
            fail(error or ('timeout' if rc == 28 else 'response_too_large' if rc == 63 else 'transport_error'))
        if time.monotonic() >= stop:
            fail('timeout')
        raw = parts['body']
        try:
            length = int(headers['content-length']) if 'content-length' in headers else None
            age = headers.get('age')
            if age is not None and not re.fullmatch(r'[0-9]+', age):
                raise ValueError('invalid age')
        except (ValueError, TypeError):
            fail('transport_metadata_invalid')
        ctype = headers.get('content-type', '').split(';')[0].strip().lower()
        metadata = {'http_status': meta.get('http_code'), 'effective_url': meta.get('url_effective'),
                    'num_redirects': meta.get('num_redirects'), 'size_download': meta.get('size_download'),
                    'content_type': ctype, 'content_length': length, 'method': meta.get('method'),
                    'proxy_used': meta.get('proxy_used'), 'cache_control': headers.get('cache-control', ''),
                    'pragma': headers.get('pragma', ''), 'expires': headers.get('expires', ''),
                    'age': int(age) if age is not None else None, 'cf_cache_status': headers.get('cf-cache-status', '')}
        if official_url(url):
            if (raw!=b'' or type(parts.get('body_bytes_read')) is not int or parts['body_bytes_read']!=0
                    or meta.get('size_download')!=0):fail('redirect_body_not_empty')
            raw=parts['headers']
            metadata.update(location=headers.get('location',''),response_body_sha256=sha256(b'').hexdigest())
        reported_content_type=meta.get('content_type')
        if reported_content_type is None:
            # curl writes null when a response (notably a bodyless 301) omits
            # Content-Type; the parsed response headers remain authoritative.
            reported_content_type=''
        if not isinstance(reported_content_type,str):fail('transport_metadata_invalid')
        reported_content_type=reported_content_type.split(';')[0].strip().lower()
        if status != (301 if official_url(url) else 200) or not metadata_valid(metadata, raw, url) or reported_content_type != ctype:
            fail('transport_metadata_invalid')
        if headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}:
            fail('unsupported_content_encoding')
        challenge_text=raw[:8192].decode('utf-8','ignore')
        if url==INDEX_URL:
            # Wix lists captcha as an available script feature on the saved
            # complete index. Only executable forms/visible denial are a gate;
            # the complete issuer/event/CDN chain is independently required.
            from bs4 import BeautifulSoup
            html=BeautifulSoup(raw,'html.parser')
            if html.select('[data-sitekey], .g-recaptcha, .h-captcha, iframe[src*=captcha]'):fail('access_denied')
            for node in html(['script','style']):node.decompose()
            challenge_text=html.get_text(' ',strip=True)
        if re.search(r'FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|captcha|access denied|驗證碼', challenge_text, re.I):
            fail('access_denied')
        diagnostic.update(http_status=status, response_bytes=len(raw), response_sha256=sha256(raw).hexdigest(), response_metadata=metadata)
        if official_url(url):
            diagnostic.update(response_bytes=0,response_sha256=sha256(b'').hexdigest(),
                response_header_bytes=len(raw),response_header_sha256=sha256(raw).hexdigest())
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                'request_method': 'GET', 'request_body': None, 'response_metadata': metadata}

    def get_receipt(self, url):
        self._check()
        if url not in self._authorized:raise SourceResponseError('transport_url_invalid')
        if url == MASTER:
            http = IssuerMasterHttp(self.deadline)
            try:
                return http.get_receipt(url)
            finally:
                self.components.extend(http.components)
                self.http_request_count += http.http_request_count
        limit, _ = contract(url)
        diagnostic = {'url': url, 'http_request_sent': False, 'cache_hit': False, 'request_method': 'GET', 'request_body': None}
        self.components.append(diagnostic)
        digest = sha256((self.raw_cache_prefix + url).encode()).hexdigest()
        with _shared_lock(digest, min(1., max(0., self.deadline - time.monotonic()))) as acquired:
            self._check()
            if not acquired:
                raise SourceResponseError('single_flight_busy')
            value = self._download(url, diagnostic)
            self._check()
            raw = base64.b64decode(value['body_b64'], validate=True)
            if sha256(raw).hexdigest() != value['sha256'] or not metadata_valid(value['response_metadata'], raw, url):
                raise SourceResponseError('transport_metadata_invalid')
            stamp = value['fetched_at_epoch']
            receipt = archive_response(raw, source_url=url, retrieved_at=stamp,
                evidence_kind='raw_http_response_headers' if official_url(url) else 'raw_http_response_bytes',
                http_status=value['response_metadata']['http_status'])
            if receipt.get('status') != 'archived':
                raise SourceResponseError('original_unverified')
            receipt.update(http_status_observed=True, request_method='GET', request_body=None, response_complete=True,
                           cache_hit=False, fresh_until_epoch=stamp + validation_ttl(value['response_metadata']),
                           response_metadata=value['response_metadata'], retrieval_policy=POLICY)
            receipt['acquisition_manifest'] = archive_response(_manifest_bytes(receipt), source_url=url, retrieved_at=stamp,
                                                               evidence_kind='private_acquisition_manifest', http_status=None)
            if original_bytes(receipt, url) != raw:
                raise SourceResponseError('original_unverified')
            diagnostic.update(fetched_at_epoch=stamp, original_receipt=receipt, http_status=receipt['http_status'], original_http_status_observed=True)
        self._check()
        if not valid_expiry(receipt):
            raise SourceResponseError('original_expired')
        self._obtained[url]=receipt
        return raw, receipt
