"""One bounded ordinary curl GET for the public Yahoo Taiwan quote-news page."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import re
import selectors
import subprocess
import time

import httpx

from search_provider_runtime import SourceResponseError, observe_http_response

CURL = '/usr/bin/curl'
BODY_LIMIT = 2 * 1024 * 1024
HEADER_LIMIT = METADATA_LIMIT = 65536
PROXY_ENV = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')
SAFE_HEADERS = {'content-type', 'content-length', 'content-encoding', 'retry-after', 'date'}
_CURL_VERSION = None


from bounded_curl_process import collect_capped_process as _collect


def _curl_version(deadline):
    """Local non-network capability check, separate from the single data GET."""
    global _CURL_VERSION
    if _CURL_VERSION is not None:
        return _CURL_VERSION
    parts, rc, error = _collect([CURL, '--disable', '--version'], min(deadline, time.monotonic() + 1), body_limit=4096)
    match = re.match(rb'curl (\d+)\.(\d+)\.(\d+) ', parts['body'])
    if error == 'timeout':
        raise SourceResponseError('timeout')
    if error or rc != 0 or not match:
        raise SourceResponseError('curl_unavailable')
    version = tuple(int(part) for part in match.groups())
    # Earlier curl versions cannot enforce max-filesize on an unknown-size body.
    if version < (8, 4, 0):
        raise SourceResponseError('curl_body_cap_unsupported')
    _CURL_VERSION = '.'.join(map(str, version))
    return _CURL_VERSION


def _received_headers(raw):
    status, safe = None, {}
    for line in raw.replace(b'\r\n', b'\n').splitlines(keepends=True):
        if line.startswith(b'HTTP/'):
            match = re.match(rb'HTTP/\S+ +([2-5]\d{2})(?:[ \n]|$)', line)
            if match:
                status, safe = int(match[1]), {}
            continue
        # A partial Retry-After (e.g. 3600 cut to 36) must never be adopted.
        if status is None or not line.endswith(b'\n'):
            continue
        key, sep, value = line.partition(b':')
        name = key.decode('ascii', 'ignore').lower()
        if sep and name in SAFE_HEADERS:
            safe[name] = value.decode('latin-1').strip()
    return status, safe


@contextmanager
def curl_stream(method, url, *, deadline, diagnostics, proxy=None, **_compat):
    """HTTPX-compatible body seam, with explicit native-client capture provenance."""
    diagnostics.update(http_request_sent=False, transport_client='native_curl',
                       transport_request_profile='curl_default', transport_body_encoding='not_observed')
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
        raise SourceResponseError('test_network_disabled')
    if method != 'GET' or not re.fullmatch(r'https://tw\.stock\.yahoo\.com/quote/\d{4,6}/news', url):
        raise SourceResponseError('transport_url_invalid')
    # Conservatively refuse unsupported routing rather than silently going direct.
    if proxy or any(os.getenv(name) for name in PROXY_ENV):
        raise SourceResponseError('proxy_configuration_unsupported')
    if deadline - time.monotonic() <= 0:
        raise SourceResponseError('timeout')
    diagnostics['transport_client_version'] = _curl_version(deadline)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SourceResponseError('timeout')
    seconds = min(9.0, remaining)
    argv = [CURL, '--disable', '--silent', '--max-time', str(seconds), '--connect-timeout', str(min(3., seconds)),
            '--max-filesize', str(BODY_LIMIT), '--proto', '=https', '--max-redirs', '0', '--retry', '0',
            '--dump-header', '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}', url]
    parts, rc, failure = _collect(argv, min(deadline, time.monotonic() + 10), body_limit=BODY_LIMIT, headers=True)
    diagnostics.update(http_request_sent=parts['process_started'], transport_process_started=parts['process_started'])
    raw = parts['body']
    status, safe = _received_headers(parts['headers'])
    if status is not None:
        diagnostics['transport_body_encoding'] = ('identity' if safe.get('content-encoding', 'identity').lower()
                                                  in ('', 'identity') else 'unsupported')
    try:
        metadata = json.loads(parts['metadata'])
    except (ValueError, UnicodeDecodeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    if status is None and type(metadata.get('http_code')) is int and 200 <= metadata['http_code'] <= 599:
        status = metadata['http_code']
    diagnostics.update(transport_http_response_received=status is not None,
                       transport_http_version=str(metadata.get('http_version') or '')[:16])
    complete = rc == 0 and failure is None
    capture = {'response_bytes': len(raw), 'response_bytes_read': parts.get('body_bytes_read', len(raw)), 'response_complete': complete,
               'response_hash_scope': 'full_received_body' if complete else 'captured_prefix' if raw else 'not_read'}
    if complete:
        capture['response_sha256'] = hashlib.sha256(raw).hexdigest()
    elif raw:
        capture['captured_prefix_sha256'] = hashlib.sha256(raw).hexdigest()
    diagnostics.update(_transport_capture=capture, transport_returncode=rc,
                       transport_failure=failure or ('timeout' if rc == 28 else 'response_too_large' if rc == 63 else 'transport_error' if rc else ''),
                       transport_header_bytes=len(parts['headers']), transport_metadata_bytes=len(parts['metadata']))
    response = (httpx.Response(status, headers={key: value for key, value in safe.items() if key != 'content-encoding'},
                              content=b'', request=httpx.Request('GET', url)) if status is not None else None)
    if response is not None:
        observe_http_response(response)
    def fail(kind):
        error = SourceResponseError(kind, status_code=status)
        if response is not None:
            error.response = response
        raise error
    # Do not replace an already received 429/403/etc. with a body or process error.
    if status is not None and status != 200:
        yield response
        return
    if failure:
        fail(failure)
    if rc == 28:
        fail('timeout')
    if rc == 63:
        fail('response_too_large')
    if rc != 0:
        fail('transport_error')
    if safe.get('content-encoding', 'identity').lower() not in ('', 'identity'):
        diagnostics['transport_body_encoding'] = 'unsupported'
        fail('unsupported_content_encoding')
    if status != 200 or metadata.get('http_code') != status:
        fail('transport_metadata_invalid')
    if metadata.get('url_effective') != url or metadata.get('num_redirects') != 0:
        fail('transport_metadata_mismatch')
    response = httpx.Response(status, headers=safe, content=raw, request=httpx.Request('GET', url))
    try:
        yield response
    finally:
        response.close()
