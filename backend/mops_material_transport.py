"""Bounded anonymous POSTs for independently qualified MOPS originals.

Index selection, original archives, cache/admission and SLA belong to callers.
This module verifies request identity and complete wire responses only; a PDF
or PPTX signature does not certify text coverage, content or copying rights.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from io import BytesIO
import json
import math
import os
import re
import time
from urllib.parse import parse_qsl, urlencode
import zipfile

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import SourceResponseError, observe_http_response

DOWNLOAD_URL = 'https://mopsov.twse.com.tw/server-java/FileDownLoad'
INDEX_URL = 'https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1'
BODY_LIMIT = 16 * 1024 * 1024
INDEX_LIMIT = 1024 * 1024
PROVIDER = 'MOPS published presentation'
PROXY_ENV = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')
META_FIELDS = {'http_status', 'effective_url', 'num_redirects', 'size_download',
               'content_type', 'content_length', 'method', 'proxy_used'}
PPTX_TYPE = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
_TYPES = {'pdf': {'application/pdf', 'application/octet-stream'},
          'pptx': {PPTX_TYPE, 'application/octet-stream'},
          'html': {'text/html', 'application/xhtml+xml'}}
_CHALLENGE = re.compile(r'FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|captcha|'
                        r'access denied|Just a moment|challenge-platform|cf_chl_opt|'
                        r'Enable JavaScript and cookies|因為安全性考量|驗證碼', re.I)
_PROTECTED = {'content-length', 'content-type', 'content-encoding', 'retry-after', 'location',
              'content-disposition'}


def _ticker(ticker):
    match = re.fullmatch(r'([0-9]{4,6})\.(TW|TWO)', ticker) if isinstance(ticker, str) else None
    if match is None:
        raise SourceResponseError('transport_request_invalid')
    return match[1], match[2]


def _request_hash(method, url, body):
    return sha256((method + '\n' + url + '\n' + body).encode('ascii')).hexdigest()


def _common_request(descriptor, url, formats):
    if not isinstance(descriptor, dict):
        raise ValueError('request object')
    if descriptor.get('url') != url or descriptor.get('method') != 'POST' or descriptor.get('format') not in formats:
        raise ValueError('request route')
    symbol, market = _ticker(descriptor.get('ticker'))
    if descriptor.get('symbol') != symbol:
        raise ValueError('request issuer')
    body = descriptor.get('request_body')
    if not isinstance(body, str) or not 0 < len(body) <= 512:
        raise ValueError('request form size')
    body.encode('ascii')
    params = parse_qsl(body, keep_blank_values=True, strict_parsing=True, max_num_fields=16)
    if urlencode(params) != body or len({key for key, _ in params}) != len(params):
        raise ValueError('request form encoding')
    digest = descriptor.get('request_sha256')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or digest != _request_hash('POST', url, body):
        raise ValueError('request hash')
    return symbol, market, params


def validate_download_request(descriptor: dict) -> dict:
    """Validate only necessary transport fields; additional row context remains.

    This proves neither index publication nor issuer eligibility. The caller
    must replay its qualified index selection before using this request.
    """
    try:
        if isinstance(descriptor,dict) and descriptor.get('method') == 'GET':
            filename=descriptor.get('filename')
            match=re.fullmatch(r'2023(20\d{6})E\d{3}\.pdf',filename) if isinstance(filename,str) else None
            if (descriptor.get('ticker')!='2023.TW' or descriptor.get('symbol')!='2023'
                    or descriptor.get('format')!='pdf' or descriptor.get('language')!='en' or not match
                    or descriptor.get('url')!='https://mopsov.twse.com.tw/nas/STR/'+filename
                    or descriptor.get('request_body')!=''
                    or descriptor.get('request_sha256')!=_request_hash('GET',descriptor['url'],'')):
                raise ValueError('unqualified static request')
            date(int(match[1][:4]),int(match[1][4:6]),int(match[1][6:]))
            return dict(descriptor)
        symbol, _, params = _common_request(descriptor, DOWNLOAD_URL, {'pdf', 'pptx'})
        filename = descriptor.get('filename')
        match = re.fullmatch(re.escape(symbol) + r'([0-9]{8})[ME][0-9]{3}\.(pdf|pptx)', filename) if isinstance(filename, str) else None
        if match is None or match[2] != descriptor['format']:
            raise ValueError('request filename')
        stamp = match[1]
        if int(stamp[:4]) < 1912:
            raise ValueError('request file date')
        date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
        expected = [('step', '9'), ('filePath', '/home/html/nas/STR/'),
                    ('fileName', filename), ('functionName', 't100sb02_1')]
        if params != expected or descriptor['request_body'] != urlencode(expected):
            raise ValueError('request form parameters')
        return dict(descriptor)
    except (ValueError, TypeError, KeyError, UnicodeError, SourceResponseError):
        raise SourceResponseError('transport_request_invalid') from None


def static_material_request(published: dict) -> dict:
    """Derive only the qualified issuer's GET from an index-selected POST.

    Publication selection remains the collector's responsibility. The old POST
    identity is retained separately in its versioned proof, never rewritten.
    """
    selected=validate_download_request(published)
    if selected.get('method')!='POST' or selected.get('ticker')!='2023.TW':
        raise SourceResponseError('transport_request_invalid')
    spec={**selected,'method':'GET','url':'https://mopsov.twse.com.tw/nas/STR/'+selected['filename'],
          'request_body':''}
    spec['request_sha256']=_request_hash('GET',spec['url'],'')
    return validate_download_request(spec)


def index_request(ticker, year: int) -> dict:
    """Build one canonical year/market index POST without network or state."""
    symbol, market = _ticker(ticker)
    if type(year) is not int or not 1912 <= year <= 9999:
        raise SourceResponseError('transport_request_invalid')
    body = urlencode([('encodeURIComponent', '1'), ('step', '1'), ('firstin', '1'),
                      ('off', '1'), ('TYPEK', 'sii' if market == 'TW' else 'otc'),
                      ('co_id', symbol), ('year', str(year - 1911)), ('month', '')])
    return {'url': INDEX_URL, 'method': 'POST', 'request_body': body,
            'request_sha256': _request_hash('POST', INDEX_URL, body),
            'format': 'html', 'ticker': ticker, 'symbol': symbol, 'year': year}


def _validate_spec(descriptor):
    if isinstance(descriptor, dict) and descriptor.get('format') == 'html':
        try:
            _, _, params = _common_request(descriptor, INDEX_URL, {'html'})
            values = dict(params)
            year = values.get('year', '')
            if not re.fullmatch('[1-9][0-9]{0,3}', year):
                raise ValueError('index year')
            expected = index_request(descriptor['ticker'], int(year) + 1911)
            if params != parse_qsl(expected['request_body'], keep_blank_values=True):
                raise ValueError('index parameters')
            if 'year' in descriptor and (type(descriptor['year']) is not int or descriptor['year'] != expected['year']):
                raise ValueError('index year context')
            return dict(descriptor)
        except (ValueError, TypeError, KeyError, UnicodeError, SourceResponseError):
            raise SourceResponseError('transport_request_invalid') from None
    return validate_download_request(descriptor)


def _mime(value):
    return value.split(';', 1)[0].strip().lower() if isinstance(value, str) else ''


def _signature_valid(raw, fmt):
    if fmt == 'pdf':
        return re.match(rb'%PDF-[12]\.[0-9](?:\r|\n|\s)', raw[:16]) is not None
    if fmt == 'html':
        return b'<html' in raw[:4096].lower()
    if not raw.startswith(b'PK\x03\x04'):
        return False
    try:
        # Inspect directory names only; never inflate entries in the transport.
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
            return (2 <= len(names) <= 4096 and len(names) == len(set(names))
                    and '[Content_Types].xml' in names and 'ppt/presentation.xml' in names)
    except (ValueError, OSError, zipfile.BadZipFile):
        return False


def _is_challenge(raw, fmt):
    # Security words can be ordinary slide content; never classify binary
    # document text as a remote HTML access challenge. Readers still validate
    # the complete document and its copying/text gates after this transport.
    if fmt != 'html' and raw.startswith((b'%PDF-', b'PK\x03\x04')):
        return False
    return _CHALLENGE.search(raw[:8192].decode('utf-8', 'ignore')) is not None


def _blank_pptx_mime(meta, spec):
    # The public MOPS download servlet emits a blank MIME for some PPTX files.
    # Keep that actual MIME and require its exact published attachment name.
    return (spec['url'] == DOWNLOAD_URL and spec['format'] == 'pptx'
            and meta.get('content_type') == ''
            and meta.get('content_disposition') == 'attachment; filename="' + spec['filename'] + '"')


def validate_response_metadata(meta, raw: bytes, descriptor: dict) -> bool:
    """Pure admission check reused for exact cached-original receipt replay."""
    try:
        spec = _validate_spec(descriptor)
        limit = INDEX_LIMIT if spec['format'] == 'html' else BODY_LIMIT
        if not isinstance(meta, dict):
            return False
        blank_pptx = _blank_pptx_mime(meta, spec)
        fields = META_FIELDS | {'content_disposition'} if blank_pptx else META_FIELDS
        if (type(raw) is not bytes or not 0 < len(raw) <= limit or not isinstance(meta, dict)
                or set(meta) != fields or type(meta['http_status']) is not int or meta['http_status'] != 200
                or meta['effective_url'] != spec['url'] or meta['method'] != spec['method']
                or type(meta['num_redirects']) is not int or meta['num_redirects'] != 0
                or type(meta['proxy_used']) is not int or meta['proxy_used'] != 0
                or type(meta['size_download']) not in (int, float) or not math.isfinite(meta['size_download'])
                or meta['size_download'] != len(raw)
                or (meta['content_type'] not in _TYPES[spec['format']] and not blank_pptx)
                or (meta['content_length'] is not None and (type(meta['content_length']) is not int
                    or meta['content_length'] != len(raw)))):
            return False
        if _is_challenge(raw, spec['format']):
            return False
        return _signature_valid(raw, spec['format'])
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, SourceResponseError):
        return False


def _headers(raw):
    """Final status/headers plus invalidity, retaining HTTP truth on errors."""
    status = None
    headers = {}
    invalid = type(raw) is not bytes
    if invalid:
        return status, headers, True
    for line in raw.replace(b'\r\n', b'\n').split(b'\n'):
        if line.startswith(b'HTTP/'):
            match = re.fullmatch(rb'HTTP/[^ ]+ +([1-5][0-9]{2})(?: .*)?', line)
            if match is None:
                invalid = True
                continue
            if status is not None and status >= 200:
                invalid = True
            status = int(match[1])
            headers = {}
        elif line and status is not None:
            key, sep, value = line.partition(b':')
            if not sep or not re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key):
                invalid = True
                continue
            name = key.decode('ascii').lower()
            if name in _PROTECTED:
                if any(byte >= 127 or byte < 32 and byte != 9 for byte in value):
                    invalid = True
                    continue
                if name in headers:
                    invalid = True
                else:
                    headers[name] = value.decode('latin-1').strip()
    return status, headers, invalid


def _initialize(diagnostics):
    diagnostics.update(http_request_sent=False, response_complete=False, http_status=None,
                       response_bytes=0, response_sha256=sha256(b'').hexdigest(),
                       response_bytes_read=0, response_metadata=None, http_status_observed=False, error_kind=None)


def _fail(kind, diagnostics, response=None):
    diagnostics.update(error_kind=kind, response_complete=False)
    exc = SourceResponseError(kind, status_code=diagnostics.get('http_status'))
    exc.diagnostic.update(diagnostics)
    if response is not None:
        exc.response = response
    raise exc


def _perform(spec, *, deadline, diagnostics, wire_budget_seconds=10.):
    diagnostics.update(url=spec['url'], request_method=spec['method'], request_body=spec['request_body'],
                       request_sha256=spec['request_sha256'])
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        _fail('transport_deadline_invalid', diagnostics)
    started = time.monotonic()
    stop = min(deadline, started + (5. if spec['format'] == 'html' else wire_budget_seconds))
    def fail(kind, response=None):
        _fail('timeout' if time.monotonic() >= stop else kind, diagnostics, response)
    if started >= stop:
        fail('timeout')
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
        fail('test_network_disabled')
    if proxy_url_for_request(spec['url'], PROVIDER) or any(os.getenv(key) for key in PROXY_ENV):
        fail('proxy_configuration_unsupported')
    remaining = stop - time.monotonic()
    if remaining <= 0:
        fail('timeout')
    limit = INDEX_LIMIT if spec['format'] == 'html' else BODY_LIMIT
    args = ['/usr/bin/curl', '--disable', '--silent', '--proto', '=https', '--noproxy', '*',
            '--max-time', str(remaining), '--connect-timeout', str(min(2., remaining)),
            '--max-filesize', str(limit), '--max-redirs', '0', '--retry', '0',
            '--dump-header', '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}']
    if spec['method']=='POST':
        args.extend(['--data',spec['request_body']])
    args.append(spec['url'])
    parts, rc, error = collect_capped_process(args, stop, body_limit=limit, headers=True)
    diagnostics['http_request_sent'] = parts.get('process_started') is True
    raw = parts.get('body')
    if type(raw) is bytes:
        diagnostics.update(response_bytes=len(raw), response_sha256=sha256(raw).hexdigest(),
                           response_bytes_read=parts.get('body_bytes_read'))
    status, headers, invalid_headers = _headers(parts.get('headers'))
    try:
        native_meta = json.loads(parts.get('metadata', b''))
    except (ValueError, TypeError, UnicodeError):
        native_meta = {}
    if not isinstance(native_meta, dict):
        native_meta = {}
    observed = status
    if observed is None and type(native_meta.get('http_code')) is int and 100 <= native_meta['http_code'] <= 599:
        observed = native_meta['http_code']
    diagnostics.update(http_status=observed, http_status_observed=observed is not None)
    length = headers.get('content-length')
    length_valid = length is None or re.fullmatch('[0-9]{1,20}', length) is not None
    clen = int(length) if length is not None and length_valid else None
    meta = {'http_status': native_meta.get('http_code'), 'effective_url': native_meta.get('url_effective'),
            'num_redirects': native_meta.get('num_redirects'), 'size_download': native_meta.get('size_download'),
            'content_type': _mime(headers.get('content-type')), 'content_length': clen,
            'method': native_meta.get('method'), 'proxy_used': native_meta.get('proxy_used')}
    if spec['format'] == 'pptx' and meta['content_type'] == '' and 'content-type' in headers:
        meta['content_disposition'] = headers.get('content-disposition')
    diagnostics['response_metadata'] = meta
    response = httpx.Response(observed, headers=headers, request=httpx.Request(spec['method'], spec['url'])) if observed else None
    if response is not None:
        observe_http_response(response)
    # A late failure or local verification cannot escape the same wire deadline.
    if time.monotonic() >= stop:
        fail('timeout', response)
    if observed is not None and observed != 200:
        kind = {401: 'authentication', 402: 'payment_required', 403: 'access_denied', 429: 'rate_limited'}.get(
            observed, 'server_error' if observed >= 500 else 'http_error')
        fail(kind, response)
    if error or rc != 0:
        fail(error or ('timeout' if rc == 28 else 'response_too_large' if rc == 63 else 'transport_error'), response)
    if not diagnostics['http_request_sent'] or invalid_headers or not length_valid or status != 200:
        fail('transport_metadata_invalid', response)
    if headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}:
        fail('unsupported_content_encoding', response)
    if type(raw) is not bytes or not raw or len(raw) > limit:
        fail('response_too_large' if type(raw) is bytes and len(raw) > limit else 'empty_response', response)
    if _is_challenge(raw, spec['format']):
        fail('access_denied', response)
    if (not isinstance(native_meta.get('content_type'), str) or
            _mime(native_meta['content_type']) != meta['content_type'] or
            not validate_response_metadata(meta, raw, spec) or
            (parts.get('body_bytes_read') is not None and parts['body_bytes_read'] != len(raw))):
        fail('transport_metadata_invalid', response)
    if time.monotonic() >= stop:
        fail('timeout', response)
    diagnostics.update(response_complete=True, error_kind=None)
    return raw


def download_published_material(descriptor: dict, *, deadline: float, diagnostics: dict, wire_budget_seconds: float = 10.) -> bytes:
    _initialize(diagnostics)
    if type(wire_budget_seconds) not in (int, float) or not math.isfinite(wire_budget_seconds) or not 0 < wire_budget_seconds <= 15.:
        _fail('transport_budget_invalid', diagnostics)
    try:
        spec = validate_download_request(descriptor)
    except SourceResponseError:
        _fail('transport_request_invalid', diagnostics)
    return _perform(spec, deadline=deadline, diagnostics=diagnostics, wire_budget_seconds=wire_budget_seconds)


def download_conference_index(ticker, *, year: int, deadline: float, diagnostics: dict) -> bytes:
    _initialize(diagnostics)
    try:
        spec = index_request(ticker, year)
    except SourceResponseError:
        _fail('transport_request_invalid', diagnostics)
    return _perform(spec, deadline=deadline, diagnostics=diagnostics)
