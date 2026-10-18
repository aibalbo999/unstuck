"""Two fixed anonymous SYSTEX endpoints; no credentials, redirects or retries."""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
from urllib.parse import parse_qsl, urlsplit

import httpx
from bounded_curl_process import collect_capped_process
from company_conference_transport import _headers, _version, PROXY_ENV
from search_provider_runtime import SourceResponseError, observe_http_response

HOME_URL = 'https://tw.systex.com/systex/ch/index'
API_URL = 'https://tw.systex.com/api/v2/systex/ch/api/tabfolder/22344'
PROVIDER = 'SYSTEX official investor conference index'
NONCE = re.compile(r'[A-Za-z0-9_.+/=-]{24,256}')


def download(url: str, *, deadline: float, diagnostics: dict) -> bytes:
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    api = (parsed.scheme == 'https' and parsed.netloc == 'tw.systex.com'
           and parsed.path == '/api/v2/systex/ch/api/tabfolder/22344' and not parsed.fragment
           and len(query) == 1 and query[0][0] == 'cspstr' and NONCE.fullmatch(query[0][1]))
    if url != HOME_URL and not api:
        raise SourceResponseError('transport_url_invalid')
    safe_url = API_URL if api else HOME_URL
    diagnostics.update(source_url=safe_url, request_query_names=['cspstr'] if api else [],
                       http_request_sent=False, transport_client='native_curl')
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
        raise SourceResponseError('test_network_disabled')
    from external_http_client import proxy_url_for_request
    if proxy_url_for_request(safe_url, PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
        raise SourceResponseError('proxy_configuration_unsupported')
    _version(deadline)
    request_deadline = min(deadline, time.monotonic() + 5.)
    remaining = request_deadline-time.monotonic()
    if remaining <= 0:
        raise SourceResponseError('timeout')
    limit = 512_000 if api else 64_000
    args = ['/usr/bin/curl', '--disable', '--silent', '--max-time', str(remaining),
            '--connect-timeout', str(min(3., remaining)), '--max-filesize', str(limit),
            '--proto', '=https', '--max-redirs', '0', '--retry', '0',
            '--dump-header', '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}', url]
    parts, rc, failure = collect_capped_process(args, request_deadline, body_limit=limit, headers=True)
    if time.monotonic() >= request_deadline:
        failure = 'timeout'
    raw = parts['body']; status, headers = _headers(parts['headers'])
    try:
        meta = json.loads(parts['metadata'])
    except (ValueError, UnicodeError):
        meta = {}
    complete = rc == 0 and failure is None
    diagnostics.update(http_request_sent=parts['process_started'], http_status=status,
        response_complete=complete, response_bytes=len(raw), transport_returncode=rc,
        response_hash_scope='full_received_body' if complete else 'captured_prefix')
    diagnostics['response_sha256' if complete else 'captured_prefix_sha256'] = hashlib.sha256(raw).hexdigest()
    response = httpx.Response(status, headers=headers, request=httpx.Request('GET', safe_url)) if status else None
    observe_http_response(response)
    def refuse(kind):
        exc = SourceResponseError(kind, status_code=status)
        exc.response = response; exc.diagnostic.update(diagnostics)
        raise exc
    if status is not None and status != 200:
        refuse({401: 'authentication', 402: 'payment_required', 403: 'access_denied', 429: 'rate_limited'}
               .get(status, 'server_error' if status >= 500 else 'http_error'))
    if failure or rc:
        refuse(failure or ('timeout' if rc == 28 else 'response_too_large' if rc == 63 else 'transport_error'))
    if (not isinstance(meta, dict) or status != 200 or meta.get('http_code') != status
            or meta.get('url_effective') != url or meta.get('num_redirects') != 0):
        refuse('transport_metadata_invalid')
    if headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
        refuse('unsupported_content_encoding')
    kind = headers.get('content-type', '').split(';')[0].lower()
    allowed = {'application/json', 'text/json'} if api else {'text/html', 'application/xhtml+xml'}
    if kind not in allowed or not raw:
        refuse('unexpected_content_type')
    return raw
