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


def _collect(argv, deadline, *, body_limit, headers=False):
    """Nonblocking capped pipes; stop/reap our exact child before returning."""
    buffers = {'body': bytearray(), 'headers': bytearray(), 'metadata': bytearray()}
    limits = {'body': body_limit, 'headers': HEADER_LIMIT, 'metadata': METADATA_LIMIT}
    proc = None
    selector = selectors.DefaultSelector()
    header_read = header_write = None
    error = None
    body_bytes_read = 0
    try:
        if time.monotonic() >= deadline:
            raise TimeoutError
        if headers:
            header_read, header_write = os.pipe()
            argv = [part.replace('{HEADER_FD}', str(header_write)) for part in argv]
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                shell=False, close_fds=True, pass_fds=(header_write,) if headers else (),
                                env={key: value for key, value in os.environ.items()
                                     if key in {'PATH', 'LANG', 'LC_ALL', 'CURL_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}})
        if header_write is not None:
            os.close(header_write)
            header_write = None
        streams = [(proc.stdout.fileno(), 'body'), (proc.stderr.fileno(), 'metadata')]
        if header_read is not None:
            streams.append((header_read, 'headers'))
        for fd, name in streams:
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_READ, name)
        while selector.get_map() or proc.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            # Read available headers first, so refusal identity survives body failures.
            for key, _ in sorted(selector.select(min(remaining, .05)), key=lambda item: item[0].data != 'headers'):
                chunk = os.read(key.fd, 16384)
                if not chunk:
                    selector.unregister(key.fd)
                    continue
                name = key.data
                if name == 'body':
                    body_bytes_read += len(chunk)
                space = limits[name] - len(buffers[name])
                buffers[name].extend(chunk[:space])
                if len(chunk) > space:
                    error = {'body': 'response_too_large', 'headers': 'response_headers_too_large',
                             'metadata': 'transport_metadata_too_large'}[name]
                    raise OverflowError
            if not selector.get_map() and proc.poll() is None:
                time.sleep(min(.01, remaining))
    except TimeoutError:
        error = 'timeout'
    except OverflowError:
        pass
    except Exception:
        error = 'transport_error'
    finally:
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
            except Exception:
                error = error or 'transport_cleanup_failed'
            # A complete refusal header can still be queued when body/read fails.
            if header_read is not None:
                try:
                    while len(buffers['headers']) < HEADER_LIMIT:
                        chunk = os.read(header_read, min(16384, HEADER_LIMIT - len(buffers['headers'])))
                        if not chunk:
                            break
                        buffers['headers'].extend(chunk)
                except (BlockingIOError, OSError):
                    pass
            for pipe in (proc.stdout, proc.stderr):
                try:
                    pipe.close()
                except Exception:
                    error = error or 'transport_cleanup_failed'
        for fd in (header_read, header_write):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        try:
            selector.close()
        except Exception:
            error = error or 'transport_cleanup_failed'
    return {**{key: bytes(value) for key, value in buffers.items()}, 'process_started': proc is not None, 'body_bytes_read': body_bytes_read}, proc.returncode if proc else None, error


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
