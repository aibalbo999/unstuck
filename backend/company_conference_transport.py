"""Bounded ordinary GETs for the verified issuer's public conference documents."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time

import httpx

from bounded_curl_process import collect_capped_process
from search_provider_runtime import SourceResponseError, observe_http_response

CURL = '/usr/bin/curl'
PROXY_ENV = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')
PDF_URL = re.compile(r'https://www\.myson\.com\.tw/public/uploads/pdf/[A-Za-z0-9_-]+\.pdf')
INDEX_URL = 'https://www.myson.com.tw/gov_info'
_VERSION = None


def _version(deadline):
    global _VERSION
    if _VERSION is None:
        parts, rc, error = collect_capped_process([CURL, '--disable', '--version'],
            min(deadline, time.monotonic() + 1), body_limit=4096)
        match = re.match(rb'curl (\d+)\.(\d+)\.(\d+) ', parts['body'])
        if error or rc or not match or tuple(map(int, match.groups())) < (8, 4, 0):
            raise SourceResponseError('curl_body_cap_unsupported')
        _VERSION = '.'.join(part.decode() for part in match.groups())
    return _VERSION


def _headers(raw):
    status, safe = None, {}
    for line in raw.replace(b'\r\n', b'\n').splitlines(keepends=True):
        if line.startswith(b'HTTP/'):
            match = re.match(rb'HTTP/\S+ +([2-5]\d{2})(?:[ \n]|$)', line)
            if match:
                status, safe = int(match[1]), {}
        elif status is not None and line.endswith(b'\n'):
            key, sep, value = line.partition(b':')
            name = key.decode('ascii', 'ignore').lower()
            if sep and name in {'retry-after', 'content-type', 'content-encoding'}:
                safe[name] = value.decode('latin-1').strip()
    return status, safe


def download(url: str, *, deadline: float, diagnostics: dict) -> bytes:
    diagnostics.update(http_request_sent=False, source_url=url, transport_client='native_curl',
                       transport_request_profile='curl_default')
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
        raise SourceResponseError('test_network_disabled')
    if url != INDEX_URL and not PDF_URL.fullmatch(url):
        raise SourceResponseError('transport_url_invalid')
    from external_http_client import proxy_url_for_request
    if proxy_url_for_request(url, 'MYSON official conference presentation') or any(os.getenv(key) for key in PROXY_ENV):
        raise SourceResponseError('proxy_configuration_unsupported')
    diagnostics['transport_client_version'] = _version(deadline)
    remaining = min(15., deadline - time.monotonic())
    if remaining <= 0:
        raise SourceResponseError('timeout')
    limit = (2 if url == INDEX_URL else 16) * 1024 * 1024
    argv = [CURL, '--disable', '--silent', '--max-time', str(remaining),
            '--connect-timeout', str(min(5., remaining)), '--max-filesize', str(limit),
            '--proto', '=https', '--max-redirs', '0', '--retry', '0',
            '--dump-header', '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}', url]
    parts, rc, error = collect_capped_process(argv, deadline, body_limit=limit, headers=True)
    raw = parts['body']
    status, headers = _headers(parts['headers'])
    try:
        metadata = json.loads(parts['metadata'])
    except (ValueError, UnicodeDecodeError):
        metadata = {}
    metadata = metadata if isinstance(metadata, dict) else {}
    if status is None and type(metadata.get('http_code')) is int and 200 <= metadata['http_code'] <= 599:
        status = metadata['http_code']
    complete = rc == 0 and error is None
    diagnostics.update(http_request_sent=parts['process_started'], http_status=status,
                       response_bytes=len(raw), response_complete=complete,
                       response_hash_scope='full_received_body' if complete else 'captured_prefix',
                       transport_returncode=rc, transport_failure=error or '',
                       transport_http_version=str(metadata.get('http_version') or '')[:16])
    diagnostics['response_sha256' if complete else 'captured_prefix_sha256'] = hashlib.sha256(raw).hexdigest()
    response = httpx.Response(status, headers=headers, request=httpx.Request('GET', url)) if status else None
    if response is not None:
        observe_http_response(response)
    def fail(kind):
        exc = SourceResponseError(kind, status_code=status)
        if response is not None:
            exc.response = response
        exc.diagnostic.update(diagnostics)
        raise exc
    # Preserve a received refusal and Retry-After before considering body errors.
    if status is not None and status != 200:
        fail({401: 'authentication', 402: 'payment_required', 403: 'access_denied', 429: 'rate_limited'}.get(status, 'server_error' if status >= 500 else 'http_error'))
    if error or rc:
        fail(error or ('timeout' if rc == 28 else 'response_too_large' if rc == 63 else 'transport_error'))
    if status != 200 or metadata.get('http_code') != status or metadata.get('url_effective') != url or metadata.get('num_redirects') != 0:
        fail('transport_metadata_invalid')
    if headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
        fail('unsupported_content_encoding')
    kind = headers.get('content-type', '').split(';')[0].strip().lower()
    if url == INDEX_URL:
        if kind not in {'text/html', 'application/xhtml+xml'}:
            fail('unexpected_content_type')
    elif kind != 'application/pdf' or not raw.startswith(b'%PDF-'):
        fail('unexpected_content_type')
    return raw
