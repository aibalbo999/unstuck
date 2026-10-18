"""Ordinary anonymous, capped POST reads for one verified issuer's careers."""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import math
import os
import re
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

PROVIDER = 'President Securities official careers'
LISTING_URL = 'https://ehrweb.104.com.tw/job.do?uno=23218183'
LIST_API = 'https://ehrweb.104.com.tw/dwr/call/plaincall/normalAjaxService.searchJobs.dwr'
DETAIL_API = 'https://ehrweb.104.com.tw/dwr/call/plaincall/normalAjaxService.getJobDetailByCustId.dwr'
JOB_ID = re.compile(r'[1-9]\d{9,24}')
PROXY_ENV = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')


def request_contract(job_id=None):
    if job_id is not None and (not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id)):
        raise SourceResponseError('job_identity_invalid')
    method = 'getJobDetailByCustId' if job_id is not None else 'searchJobs'
    params = (['number:9900000736', 'string:' + job_id] if job_id is not None else
              ['number:9900000736', 'string:', 'string:0', 'string:0', 'number:0', 'string:' + uuid4().hex])
    body = '\n'.join(['callCount=1', 'nextReverseAjaxIndex=0', 'c0-scriptName=normalAjaxService',
                       'c0-methodName=' + method, 'c0-id=0',
                       *['c0-param' + str(i) + '=' + v for i, v in enumerate(params)],
                       'batchId=0', 'instanceId=0', 'page=' + quote('/job.do?uno=23218183', safe=''),
                       'scriptSessionId=', ''])
    return (DETAIL_API if job_id is not None else LIST_API), body


class PscCareersHttp:
    def __init__(self, deadline):
        self.deadline, self.http_request_count, self.components = deadline, 0, []

    def _download(self, job_id, diagnostic):
        url, body = request_contract(job_id)
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
            raise SourceResponseError('test_network_disabled')
        if proxy_url_for_request(url, PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
            raise SourceResponseError('proxy_configuration_unsupported')
        key = scope_key(PROVIDER, endpoint='ehrweb.104.com.tw')
        if cooldown_state(key):
            raise SourceResponseError('cooldown')
        remaining = min(5., self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError('timeout')
        argv = ['/usr/bin/curl', '--disable', '--silent', '--max-time', str(remaining),
                '--connect-timeout', str(min(2., remaining)), '--max-filesize', str(MAX_BYTES),
                '--proto', '=https', '--max-redirs', '0', '--retry', '0',
                '-H', 'Content-Type: text/plain;charset=UTF-8', '--data-binary', body,
                '--dump-header', '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}', url]
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
        response = httpx.Response(status, headers=headers, request=httpx.Request('POST', url)) if status else None
        if response is not None:
            observe_http_response(response)

        def fail(kind):
            diagnostic['error_kind'] = kind
            exc = SourceResponseError(kind, status_code=status)
            if response is not None:
                exc.response = response
            if status in {401, 403, 429} or status and status >= 500:
                remember_failure(key, exc)
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
        if headers.get('content-type', '').split(';')[0].strip().lower() not in {
                'text/javascript', 'application/javascript', 'text/plain'}:
            fail('unexpected_content_type')
        if time.monotonic() >= self.deadline:
            fail('timeout')
        return {'url': url, 'method': 'POST', 'request_identity': {'cust_id': '9900000736', 'job_id': job_id},
                'body_b64': base64.b64encode(parts['body']).decode('ascii'), 'sha256': sha256(parts['body']).hexdigest()}

    def get_receipt(self, job_id=None):
        url, _ = request_contract(job_id)
        diagnostic = {'url': url, 'job_id': job_id, 'http_request_sent': False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        value, meta = shared_fetch(
            'psc-careers-raw:v1:' + (job_id or 'listing'), lambda: self._download(job_id, diagnostic),
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
                or value.get('method') != 'POST'
                or value.get('request_identity') != {'cust_id': '9900000736', 'job_id': job_id}):
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
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return {**value, 'fetched_at_epoch': stamp}
