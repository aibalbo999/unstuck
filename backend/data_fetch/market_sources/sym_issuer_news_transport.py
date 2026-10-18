"""Exact SYM HTML originals, never a successful HTTP response cache.

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

MASTER = master.MASTER_URL
CORPORATE = 'https://www.sanyang.com.tw/'
BRAND = 'https://www.sanyang.com.tw/sym-page67'
TAIWAN = 'https://tw.sym-global.com/'
GLOBAL = 'https://www.sym-global.com/'
INDEX = GLOBAL + 'newsroom'
ARTICLES = (GLOBAL + 'newsroom-page374', GLOBAL + 'newsroom-page368')
ARTICLE = re.compile(r'https://www\.sym-global\.com/newsroom-page[1-9][0-9]{0,7}\Z')
HTML_URLS = (CORPORATE, BRAND, TAIWAN, INDEX, *ARTICLES)
RAW_TTL = 1800
POLICY = 'always_native_no_success_cache'


def contract(url):
    if isinstance(url, str) and (url in HTML_URLS or ARTICLE.fullmatch(url)):
        return 1_048_576, {'text/html', 'application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')


def metadata_valid(meta, raw, url):
    limit, types = contract(url)
    return (isinstance(raw, bytes) and 0 < len(raw) <= limit
            and isinstance(meta, dict) and set(meta) == META_FIELDS
            and type(meta['http_status']) is int and meta['http_status'] == 200
            and meta['effective_url'] == url and type(meta['num_redirects']) is int and meta['num_redirects'] == 0
            and type(meta['size_download']) in (int, float) and meta['size_download'] == len(raw)
            and meta['content_type'] in types
            and (meta['content_length'] is None or type(meta['content_length']) is int and meta['content_length'] == len(raw))
            and meta['method'] == 'GET' and type(meta['proxy_used']) is int and meta['proxy_used'] == 0
            and all(isinstance(meta[k], str) for k in ('cache_control', 'pragma', 'expires', 'cf_cache_status'))
            and (meta['age'] is None or type(meta['age']) is int and meta['age'] >= 0))


def original_bytes(receipt, url, *, max_age=RAW_TTL):
    if url in (MASTER, master.JSON_URL):
        if not isinstance(receipt, dict) or receipt.get('source_url') != url:
            raise ValueError('SYM master URL mismatch')
        return master.original_bytes(receipt, max_age=max_age)
    limit, _ = contract(url)
    if (not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS
            or receipt.get('status') != 'archived' or receipt.get('source_url') != url
            or receipt.get('cache_hit') is not False or receipt.get('request_method') != 'GET'
            or receipt.get('request_body') is not None or receipt.get('response_complete') is not True
            or receipt.get('http_status_observed') is not True or type(receipt.get('http_status')) is not int
            or receipt['http_status'] != 200 or receipt.get('evidence_kind') != 'raw_http_response_bytes'
            or receipt.get('historical_point_in_time_verified') is not False or receipt.get('finality_guaranteed') is not False
            or receipt.get('retrieval_policy') != POLICY or not valid_epoch(receipt.get('retrieved_at'), max_age)
            or not replay_expiry_valid(receipt, max_age)):
        raise ValueError('SYM original receipt invalid')
    raw = read_response(receipt, max_bytes=limit)
    if type(receipt['raw_response_bytes']) is not int or len(raw) != receipt['raw_response_bytes'] or not metadata_valid(receipt['response_metadata'], raw, url):
        raise ValueError('SYM original metadata mismatch')
    proof = receipt['acquisition_manifest']
    if (not isinstance(proof, dict) or set(proof) != BASE_FIELDS - {'http_status_observed', 'request_method', 'response_complete', 'cache_hit'}
            or proof.get('status') != 'archived' or proof.get('source_url') != url
            or type(proof.get('retrieved_at')) not in (int, float) or proof['retrieved_at'] != receipt['retrieved_at']
            or proof.get('http_status') is not None or proof.get('evidence_kind') != 'private_acquisition_manifest'
            or proof.get('historical_point_in_time_verified') is not False or proof.get('finality_guaranteed') is not False
            or type(proof.get('raw_response_bytes')) is not int):
        raise ValueError('SYM acquisition manifest invalid')
    manifest = read_response(proof, max_bytes=16384)
    if len(manifest) != proof['raw_response_bytes'] or manifest != _manifest_bytes(receipt):
        raise ValueError('SYM immutable metadata mismatch')
    if not valid_epoch(receipt['retrieved_at'], max_age) or not replay_expiry_valid(receipt, max_age):
        raise ValueError('SYM original expired during replay')
    return raw


class SymNewsHttp(PrivateHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'sym-issuer-news-raw:v1:GET:'
    admission_prefix = 'sym-issuer-news-admission:v1:GET:'

    def _retry_guard(self, url):
        # This namespace never stores successful raw responses. A malformed
        # leftover cannot be mistaken for permission to acquire another body.
        from cache_store import get_cache_json
        try:
            key = 'shared_provider:v1:' + sha256((self.raw_cache_prefix + url).encode()).hexdigest()
            row = get_cache_json(key)
            if row is not None and (not isinstance(row, dict) or not isinstance(row.get('error_kind'), str) or not row['error_kind']):
                raise ValueError('malformed SYM raw guard')
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        super()._retry_guard(url)

    def download_original(self, url, diagnostic):
        # PrivateHttp's guards/admission are reused, never its issuer URL routes.
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
                '--connect-timeout', str(min(2., remaining)), '--max-filesize', str(limit),
                '--proto', '=https', '--max-redirs', '0', '--retry', '0', '--dump-header',
                '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}', url]
        parts, rc, error = collect_capped_process(args, stop, body_limit=limit, headers=True)
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

        if status is not None and status != 200:
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
        if status != 200 or not metadata_valid(metadata, raw, url) or meta.get('content_type', '').split(';')[0].strip().lower() != ctype:
            fail('transport_metadata_invalid')
        if headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}:
            fail('unsupported_content_encoding')
        if re.search(r'FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|captcha|access denied|驗證碼', raw[:8192].decode('utf-8', 'ignore'), re.I):
            fail('access_denied')
        diagnostic.update(http_status=status, response_bytes=len(raw), response_sha256=sha256(raw).hexdigest(), response_metadata=metadata)
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                'request_method': 'GET', 'request_body': None, 'response_metadata': metadata}

    def get_receipt(self, url):
        self._check()
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
            receipt = archive_response(raw, source_url=url, retrieved_at=stamp)
            if receipt.get('status') != 'archived':
                raise SourceResponseError('original_unverified')
            receipt.update(http_status_observed=True, request_method='GET', request_body=None, response_complete=True,
                           cache_hit=False, fresh_until_epoch=stamp + validation_ttl(value['response_metadata']),
                           response_metadata=value['response_metadata'], retrieval_policy=POLICY)
            receipt['acquisition_manifest'] = archive_response(_manifest_bytes(receipt), source_url=url, retrieved_at=stamp,
                                                               evidence_kind='private_acquisition_manifest', http_status=None)
            if original_bytes(receipt, url) != raw:
                raise SourceResponseError('original_unverified')
            diagnostic.update(fetched_at_epoch=stamp, original_receipt=receipt, http_status=200, original_http_status_observed=True)
        self._check()
        if not valid_expiry(receipt):
            raise SourceResponseError('original_expired')
        return raw, receipt
