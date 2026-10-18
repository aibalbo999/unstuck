"""Capped ordinary anonymous HTTPS to three qualified public originals."""
import json
import os
import time
from urllib.parse import urlsplit

import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                     remember_failure, scope_key)
from .twse_history_transport import _headers, PROXY_ENV, TDR_MASTER_URL

PROVIDER = 'PhilJobNet exact employer portal observation'
PROFILE = 'https://philjobnet.gov.ph/job-vacancies/company/medtecs-intl-corp-ltd-2912'
CONTACT = 'https://www.medtecs.com/contact/'


class PhilJobNetHttp:
    def __init__(self, deadline):
        self.deadline, self.http_request_count, self.components = deadline, 0, []

    def get(self, url, **kwargs):
        if url not in {PROFILE, CONTACT, TDR_MASTER_URL}:
            raise SourceResponseError('transport_url_invalid')
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
            raise SourceResponseError('test_network_disabled')
        if proxy_url_for_request(url, PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
            raise SourceResponseError('proxy_configuration_unsupported')
        key = scope_key(PROVIDER, endpoint=urlsplit(url).hostname)
        if cooldown_state(key):
            raise SourceResponseError('cooldown')
        remaining = min(5., self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError('timeout')
        limit = 2500000 if url == TDR_MASTER_URL else 600000
        diagnostic = {'url':url, 'http_request_sent':False}
        self.components.append(diagnostic)
        argv = ['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),
                '--connect-timeout',str(min(2.,remaining)),'--max-filesize',str(limit),
                '--proto','=https','--max-redirs','0','--retry','0',
                '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}',url]
        parts, rc, error = collect_capped_process(argv, min(self.deadline,time.monotonic()+remaining),
                                                 body_limit=limit,headers=True)
        diagnostic['http_request_sent'] = bool(parts.get('process_started'))
        self.http_request_count += int(diagnostic['http_request_sent'])
        status, headers = _headers(parts['headers'])
        try:
            meta = json.loads(parts['metadata'])
        except (ValueError,UnicodeDecodeError):
            meta = {}
        meta = meta if isinstance(meta,dict) else {}
        diagnostic['http_status'] = status
        response = httpx.Response(status, headers=headers, content=parts['body'], request=httpx.Request('GET',url)) if status else None
        if response is not None:
            observe_http_response(response)

        def fail(kind):
            diagnostic['error_kind'] = kind
            exc = SourceResponseError(kind,status_code=status)
            if response is not None:
                exc.response = response
            if status in {401,403,429} or status and status >= 500:
                remember_failure(key,exc)
            raise exc

        if status is not None and status != 200:
            fail({401:'authentication',403:'access_denied',429:'rate_limited'}.get(
                status,'server_error' if status >= 500 else 'http_error'))
        if error or rc:
            fail(error or ('timeout' if rc == 28 else 'response_too_large' if rc == 63 else 'transport_error'))
        if (status != 200 or meta.get('http_code') != status or meta.get('url_effective') != url
                or meta.get('num_redirects') != 0):
            fail('transport_metadata_invalid')
        expected = {'application/json','text/json'} if url == TDR_MASTER_URL else {'text/html','application/xhtml+xml'}
        if headers.get('content-type','').split(';')[0].strip().lower() not in expected:
            fail('unexpected_content_type')
        if headers.get('content-encoding','identity').lower() not in {'','identity'}:
            fail('unsupported_content_encoding')
        if time.monotonic() >= self.deadline:
            fail('timeout')
        return response
