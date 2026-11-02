"""Anonymous, capped reads of THSRC's issuer page and public recruiting tenant."""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import math
import os
import time
from urllib.parse import quote
from uuid import uuid4

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                     remember_failure, scope_key)
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers
from .psc_careers_literals import MAX_BYTES
from .thsrc_careers import request_identity, PROVIDER, UBN, CUST_ID

PROXY_ENV = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')


def request_contract(key):
    url, method, identity = request_identity(key)
    if method == 'GET':
        return url, method, None
    job_id = identity['job_id']
    method_name = 'getJobDetailByCustId' if job_id is not None else 'searchJobs'
    params = (['number:' + CUST_ID, 'string:' + job_id] if job_id is not None else
              ['number:' + CUST_ID, 'string:', 'string:0', 'string:0', 'number:0', 'string:' + uuid4().hex])
    body = '\n'.join(['callCount=1', 'nextReverseAjaxIndex=0', 'c0-scriptName=normalAjaxService',
                       'c0-methodName=' + method_name, 'c0-id=0',
                       *['c0-param' + str(i) + '=' + v for i, v in enumerate(params)],
                       'batchId=0', 'instanceId=0', 'page=' + quote('/job.do?uno=' + UBN, safe=''),
                       'scriptSessionId=', ''])
    return url, method, body


class ThsrcCareersHttp:
    def __init__(self, deadline):
        self.deadline, self.http_request_count, self.components = deadline, 0, []

    def _download(self, key, diagnostic):
        url, method, body = request_contract(key)
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
            raise SourceResponseError('test_network_disabled')
        if proxy_url_for_request(url, PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
            raise SourceResponseError('proxy_configuration_unsupported')
        cooldown_key = scope_key(PROVIDER, endpoint='ehrweb.104.com.tw')
        if cooldown_state(cooldown_key):
            raise SourceResponseError('cooldown')
        remaining = min(5., self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError('timeout')
        argv = ['/usr/bin/curl', '--disable', '--silent', '--max-time', str(remaining),
                '--connect-timeout', str(min(2., remaining)), '--max-filesize', str(MAX_BYTES),
                '--proto', '=https', '--max-redirs', '0', '--retry', '0',
                '--dump-header', '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}']
        if body is not None:
            argv += ['-H', 'Content-Type: text/plain;charset=UTF-8', '--data-binary', body]
        argv.append(url)
        parts, rc, error = collect_capped_process(argv, min(self.deadline, time.monotonic() + remaining),
                                                 body_limit=MAX_BYTES, headers=True)
        diagnostic['http_request_sent'] = bool(parts.get('process_started'))
        self.http_request_count += int(diagnostic['http_request_sent'])
        status, headers = _headers(parts['headers'])
        try:
            meta = json.loads(parts['metadata'])
        except (ValueError, UnicodeDecodeError):
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        if status is None and type(meta.get('http_code')) is int and 200 <= meta['http_code'] <= 599:
            status = meta['http_code']
        diagnostic['http_status'] = status
        response = httpx.Response(status, headers=headers, request=httpx.Request(method, url)) if status else None
        if response is not None:
            observe_http_response(response)

        def fail(kind):
            diagnostic['error_kind'] = kind
            exc = SourceResponseError(kind, status_code=status)
            if response is not None:
                exc.response = response
            if status in {401, 403, 429} or status and status >= 500:
                remember_failure(cooldown_key, exc)
            raise exc

        if status is not None and status != 200:
            fail({401: 'authentication', 403: 'access_denied', 429: 'rate_limited'}.get(
                status, 'server_error' if status >= 500 else 'http_error'))
        if error or rc:
            fail(error or ('timeout' if rc == 28 else 'response_too_large' if rc == 63 else 'transport_error'))
        if (status != 200 or meta.get('http_code') != status or meta.get('url_effective') != url
                or meta.get('num_redirects') != 0):
            fail('transport_metadata_invalid')
        if headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}:
            fail('unsupported_content_encoding')
        allowed_types = {'text/html'} if method == 'GET' else {'text/javascript', 'application/javascript', 'text/plain'}
        if headers.get('content-type', '').split(';')[0].strip().lower() not in allowed_types:
            fail('unexpected_content_type')
        if time.monotonic() >= self.deadline:
            fail('timeout')
        return {'url': url, 'method': method, 'request_identity': request_identity(key)[2],
                'http_status': status, 'response_complete': True, 'response_bytes': len(parts['body']),
                'body_b64': base64.b64encode(parts['body']).decode('ascii'), 'sha256': sha256(parts['body']).hexdigest()}

    def get_receipt(self, key):
        url, method, identity = request_identity(key)
        diagnostic = {'url': url, 'component': key, 'http_request_sent': False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        value, meta = shared_fetch(
            'thsrc-careers-raw:v1:' + key, lambda: self._download(key, diagnostic),
            freshness_seconds=1800, retention_seconds=1800, error_retry_seconds=120, lock_wait_seconds=1)
        diagnostic.update(cache_hit=bool(meta.get('cache_hit')), fetched_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('error_kind') or meta.get('stale'):
            raise SourceResponseError(diagnostic.get('error_kind') or meta.get('error_kind') or 'stale_receipt')
        stamp = meta.get('fetched_at_epoch')
        try:
            valid_stamp = type(stamp) in (int, float) and math.isfinite(stamp) and 0 <= time.time() - stamp <= 1800
        except (ValueError, OverflowError):
            valid_stamp = False
        if (not valid_stamp or not isinstance(value, dict) or value.get('url') != url
                or value.get('method') != method
                or value.get('request_identity') != identity):
            raise SourceResponseError('cache_receipt_invalid')
        encoded = value.get('body_b64')
        if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
            raise SourceResponseError('cache_receipt_invalid')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, UnicodeError) as exc:
            raise SourceResponseError('cache_receipt_invalid') from exc
        if not 0 < len(raw) <= MAX_BYTES or sha256(raw).hexdigest() != value.get('sha256'):
            raise SourceResponseError('cache_receipt_invalid')
        diagnostic.update(response_sha256=value['sha256'], response_bytes=len(raw),
                          response_complete=value.get('response_complete'))
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return {**value, 'fetched_at_epoch': stamp}
