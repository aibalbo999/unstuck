"""Bounded originals for TEWC's published English presentation and explicit Drive redirect."""
from . import conference_issuer_master as master_identity
import base64
from hashlib import sha256
import json
import os
import re
import time
from urllib.parse import urlsplit

import httpx

from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError, scope_key
from . import issuer_news_transport as native
from .tcfhc_conference_transport import ConferenceHttp as BaseHttp, RECEIPT_FIELDS, valid_epoch

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL = 'https://tewc.com.tw/investor/shareholder/'
PROVIDER = 'TEWC official English conference presentation'
RAW_TTL = 1800
PDF_LIMIT = 16 * 1024 * 1024
HEADER_LIMIT = 65536
_ID = r'([A-Za-z0-9_-]{32,64})'
_VIEWER = re.compile(r'https://drive\.google\.com/file/d/' + _ID + r'/view\?usp=sharing')
_REDIRECT = re.compile(r'https://drive\.usercontent\.google\.com/uc\?id=' + _ID + r'&export=download')
_PDF = re.compile(r'https://drive\.usercontent\.google\.com/download\?id=' + _ID + r'&export=download')
_EMPTY_SHA = sha256(b'').hexdigest()
_REDIRECT_FIELDS = RECEIPT_FIELDS | {'response_body_bytes', 'response_body_sha256', 'redirect_location'}


def route_kind(url):
    if not isinstance(url, str):
        return None
    if url == MASTER_URL:
        return 'master'
    if url == INDEX_URL:
        return 'index'
    for kind, pattern in [('viewer', _VIEWER), ('redirect', _REDIRECT), ('pdf', _PDF)]:
        if pattern.fullmatch(url):
            return kind
    return None


def contract(url):
    kind = route_kind(url)
    if kind == 'master':
        return 2_500_000, {'text/csv', 'application/csv', 'application/octet-stream'}
    if kind in {'index', 'viewer'}:
        return 500_000, {'text/html', 'application/xhtml+xml'}
    if kind == 'redirect':
        return HEADER_LIMIT, {'application/binary', 'application/octet-stream'}
    if kind == 'pdf':
        return PDF_LIMIT, {'application/pdf', 'application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def _download_url(uc_url):
    match = _REDIRECT.fullmatch(uc_url) if isinstance(uc_url, str) else None
    if not match:
        raise ValueError('Unpublished Drive redirect route')
    return 'https://drive.usercontent.google.com/download?id=' + match[1] + '&export=download'


def _redirect_headers(raw, expected_url):
    # No combined header blocks, folded fields, duplicate Location/length or
    # partial header capture can establish the published redirect identity.
    if not isinstance(raw, bytes) or not 0 < len(raw) <= HEADER_LIMIT or not raw.endswith(b'\r\n\r\n'):
        raise ValueError('Incomplete redirect headers')
    lines = raw[:-4].split(b'\r\n')
    if not re.fullmatch(rb'HTTP/(?:1\.[01]|2|3) 303(?: [^\r\n]*)?', lines[0]):
        raise ValueError('Redirect status unverified')
    fields = {}
    for line in lines[1:]:
        name, sep, value = line.partition(b':')
        if not sep or not re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
            raise ValueError('Malformed redirect headers')
        if any(c < 32 and c != 9 or c == 127 for c in value):
            raise ValueError('Malformed redirect field')
        fields.setdefault(name.decode('ascii').lower(), []).append(value.decode('latin-1').strip())
    if fields.get('location') != [expected_url] or fields.get('content-length') != ['0']:
        raise ValueError('Redirect location or empty body unverified')
    if 'transfer-encoding' in fields or fields.get('content-encoding', ['identity']) not in (['identity'], ['']):
        raise ValueError('Redirect body encoding unverified')
    types = fields.get('content-type', [])
    if len(types) != 1 or types[0].split(';')[0].strip().lower() not in {'application/binary', 'application/octet-stream'}:
        raise ValueError('Redirect content type unverified')


def _receipt(receipt, url, max_age, *, redirect=False):
    fields = _REDIRECT_FIELDS if redirect else RECEIPT_FIELDS
    status = 303 if redirect else 200
    kind = 'raw_http_response_headers' if redirect else 'raw_http_response_bytes'
    if (not isinstance(receipt, dict) or set(receipt) != fields or receipt.get('status') != 'archived'
            or receipt.get('source_url') != url or not valid_epoch(receipt.get('retrieved_at'), max_age)
            or receipt.get('historical_point_in_time_verified') is not False
            or receipt.get('finality_guaranteed') is not False
            or type(receipt.get('http_status')) is not int or receipt['http_status'] != status
            or receipt.get('evidence_kind') != kind or receipt.get('http_status_observed') is not True
            or receipt.get('request_method') != 'GET' or receipt.get('response_complete') is not True
            or type(receipt.get('cache_hit')) is not bool):
        raise ValueError('TEWC original receipt unverified')


def _legacy_original_bytes(receipt, url, *, max_age=86400):
    if route_kind(url) not in {'master', 'index', 'viewer', 'pdf'}:
        raise ValueError('TEWC original body route unverified')
    limit, _ = contract(url)
    _receipt(receipt, url, max_age)
    raw = read_response(receipt, max_bytes=limit)
    if (type(receipt.get('raw_response_bytes')) is not int or not 0 < len(raw) <= limit
            or len(raw) != receipt['raw_response_bytes'] or not valid_epoch(receipt['retrieved_at'], max_age)):
        raise ValueError('TEWC original size or final age unverified')
    return raw


def _redirect_bytes(receipt, uc_url, expected_download_url, max_age):
    if expected_download_url != _download_url(uc_url):
        raise ValueError('Redirect changed the published Drive identity')
    _receipt(receipt, uc_url, max_age, redirect=True)
    if (type(receipt.get('response_body_bytes')) is not int or receipt['response_body_bytes'] != 0
            or receipt.get('response_body_sha256') != _EMPTY_SHA
            or receipt.get('redirect_location') != expected_download_url):
        raise ValueError('Redirect empty response unverified')
    raw = read_response(receipt, max_bytes=HEADER_LIMIT)
    if type(receipt.get('raw_response_bytes')) is not int or receipt['raw_response_bytes'] != len(raw):
        raise ValueError('Redirect original size unverified')
    _redirect_headers(raw, expected_download_url)
    if not valid_epoch(receipt['retrieved_at'], max_age):
        raise ValueError('Redirect original expired during verification')
    return raw


def verify_redirect_receipt(receipt, uc_url, expected_download_url, *, max_age=86400):
    _redirect_bytes(receipt, uc_url, expected_download_url, max_age)
    return True


def original_bytes(receipt, url, *, max_age=86400):
    if url in (MASTER_URL, master_identity.JSON_URL):
        return master_identity.read_master(receipt, url, _legacy_original_bytes, max_age=max_age)
    return _legacy_original_bytes(receipt, url, max_age=max_age)


class ConferenceHttp(BaseHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'tewc-conference-raw:v1:'
    admission_prefix = 'tewc-conference-admission:v1:'

    def request_timeout_seconds(self, url):
        return 12. if route_kind(url) == 'pdf' else 5.

    def native_status(self, url):
        return 303 if route_kind(url) == 'redirect' else 200

    def archive_original(self, raw, url, value):
        limit, _ = contract(url)
        if route_kind(url) == 'redirect':
            expected = _download_url(url)
            if (type(value.get('response_body_bytes')) is not int or value['response_body_bytes'] != 0
                    or value.get('response_body_sha256') != _EMPTY_SHA
                    or value.get('redirect_location') != expected):
                raise SourceResponseError('cache_receipt_invalid')
            _redirect_headers(raw, expected)
            receipt = archive_response(raw, source_url=url, retrieved_at=value['fetched_at_epoch'],
                                       evidence_kind='raw_http_response_headers', http_status=303, max_bytes=limit)
            receipt.update(response_body_bytes=0, response_body_sha256=_EMPTY_SHA, redirect_location=expected)
            return receipt
        return archive_response(raw, source_url=url, retrieved_at=value['fetched_at_epoch'], max_bytes=limit)

    def read_original(self, receipt, url, *, max_age):
        if route_kind(url) == 'redirect':
            return _redirect_bytes(receipt, url, _download_url(url), max_age)
        return original_bytes(receipt, url, max_age=max_age)

    def _checked_receipt(self, url):
        try:
            result = super().get_receipt(url)
        except (ValueError, TypeError, OSError, EOFError) as exc:
            raise SourceResponseError('original_unverified') from exc
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        if not valid_epoch(result[1]['retrieved_at'], RAW_TTL):
            raise SourceResponseError('original_expired')
        return result

    def get_receipt(self, url):
        if url == MASTER_URL:
            return master_identity.request_master(self)
        if route_kind(url) not in {'master', 'index', 'viewer', 'pdf'}:
            raise SourceResponseError('transport_url_invalid')
        return self._checked_receipt(url)

    def get_redirect_receipt(self, uc_url, expected_download_url):
        try:
            if expected_download_url != _download_url(uc_url):
                raise ValueError('Redirect changed the published Drive identity')
        except ValueError as exc:
            raise SourceResponseError('transport_url_invalid') from exc
        return self._checked_receipt(uc_url)[1]

    def download_original(self, url, diagnostic):
        if route_kind(url) != 'redirect':
            return super().download_original(url, diagnostic)
        # This is an explicit, capped GET of the published UC URL. No redirect
        # is followed here; a caller separately admits and GETs the Location.
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
            raise SourceResponseError('test_network_disabled')
        if native.proxy_url_for_request(url, native.PROVIDER) or any(os.getenv(k) for k in native.PROXY_ENV):
            raise SourceResponseError('proxy_configuration_unsupported')
        key = scope_key(native.PROVIDER, endpoint=urlsplit(url).hostname)
        if native.cooldown_state(key):
            raise SourceResponseError('cooldown')
        remaining = min(5., self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError('timeout')
        argv = ['/usr/bin/curl', '--disable', '--silent', '--max-time', str(remaining),
                '--connect-timeout', str(min(2., remaining)), '--max-filesize', '1', '--proto', '=https',
                '--max-redirs', '0', '--retry', '0', '--dump-header', '/dev/fd/{HEADER_FD}',
                '--write-out', '%{stderr}%{json}', url]
        parts, rc, error = native.collect_capped_process(
            argv, min(self.deadline, time.monotonic() + remaining), body_limit=1, headers=True)
        diagnostic['http_request_sent'] = bool(parts.get('process_started'))
        self.http_request_count += int(diagnostic['http_request_sent'])
        status, headers = native._headers(parts['headers'])
        try:
            meta = json.loads(parts['metadata'])
        except (ValueError, UnicodeDecodeError):
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        if status is None and type(meta.get('http_code')) is int and 200 <= meta['http_code'] <= 599:
            status = meta['http_code']
        response = httpx.Response(status, headers=headers, request=httpx.Request('GET', url)) if status else None
        if response is not None:
            native.observe_http_response(response)

        def fail(kind):
            diagnostic['error_kind'] = kind
            exc = SourceResponseError(kind, status_code=status)
            if response is not None:
                exc.response = response
            if status in {401, 403, 429} or status and status >= 500:
                native.remember_failure(key, exc)
            raise exc

        if status is not None and status != 303:
            fail({401: 'authentication', 403: 'access_denied', 429: 'rate_limited'}.get(
                status, 'server_error' if status >= 500 else 'http_error'))
        if error or rc:
            fail(error or ('timeout' if rc == 28 else 'transport_error'))
        if (parts.get('process_started') is not True or status != 303
                or type(meta.get('http_code')) is not int or meta['http_code'] != 303
                or meta.get('url_effective') != url or type(meta.get('num_redirects')) is not int
                or meta['num_redirects'] != 0):
            fail('transport_metadata_invalid')
        if (parts.get('body') != b'' or type(parts.get('body_bytes_read')) is not int
                or parts['body_bytes_read'] != 0):
            fail('redirect_body_not_empty')
        expected = _download_url(url)
        try:
            _redirect_headers(parts['headers'], expected)
        except ValueError:
            fail('redirect_headers_invalid')
        if time.monotonic() >= self.deadline:
            fail('timeout')
        raw = parts['headers']
        return {'url': url, 'body_b64': base64.b64encode(raw).decode('ascii'), 'sha256': sha256(raw).hexdigest(),
                'response_body_bytes': 0, 'response_body_sha256': _EMPTY_SHA, 'redirect_location': expected}
