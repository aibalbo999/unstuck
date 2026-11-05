"""Immutable forward-only provenance for the existing public ranking stream.

An injected client and legacy archives keep their original unknown flags. This
capsule certifies transport only; the ranking parser still owns all semantics.
"""
from hashlib import sha256
import json
import math
import os
import time

import httpx
from official_response_evidence import archive_response, read_response

SCHEMA = 'published-peer-native-http.v1'
MAX_BODY = 1_000_000
MAX_MANIFEST = 16384
FLAGS = {'http_status_observed': True, 'response_complete': True,
         'cache_hit': False, 'request_method': 'GET'}
PROXY_ENV = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
             'http_proxy', 'https_proxy', 'all_proxy')


def _url(ticker):
    import re
    if not isinstance(ticker, str) or not re.fullmatch(r'[1-9]\d{3,5}\.TW(?:O)?', ticker):
        raise ValueError('invalid ranking capsule ticker')
    return f'https://tw.stock.yahoo.com/quote/{ticker}/compare'


def _binding(receipt, ticker):
    stamp = receipt.get('retrieved_at')
    if (receipt.get('status') != 'archived' or receipt.get('source_url') != _url(ticker)
            or type(receipt.get('http_status')) is not int or receipt['http_status'] != 200
            or receipt.get('evidence_kind') != 'decoded_complete_http_response_body'
            or type(stamp) not in (int, float) or not math.isfinite(stamp)
            or not 0 < stamp <= time.time()
            or any(type(receipt.get(k)) is not type(v) or receipt.get(k) != v
                   for k, v in FLAGS.items())):
        raise ValueError('native ranking receipt metadata differs')
    raw = read_response(receipt, max_bytes=MAX_BODY)
    if not 0 < len(raw) <= MAX_BODY or len(raw) != receipt.get('raw_response_bytes'):
        raise ValueError('native ranking original size differs')
    return {'schema': SCHEMA, 'ticker': ticker, 'source_url': _url(ticker),
            'body_sha256': sha256(raw).hexdigest(), 'body_bytes': len(raw),
            'received_at': stamp, 'http_status': 200, 'stream_consumed': True,
            **FLAGS}


def _manifest_bytes(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def validate_native_receipt(receipt, ticker):
    """Replay new metadata; absence never upgrades a legacy receipt."""
    if 'native_http_manifest' not in receipt and not set(FLAGS).intersection(receipt):
        return False
    expected = _binding(receipt, ticker)
    proof = receipt.get('native_http_manifest')
    if (not isinstance(proof, dict) or proof.get('status') != 'archived'
            or proof.get('source_url') != expected['source_url']
            or proof.get('retrieved_at') != expected['received_at']
            or proof.get('http_status') is not None
            or proof.get('evidence_kind') != 'private_acquisition_manifest'
            or proof.get('historical_point_in_time_verified') is not False
            or proof.get('finality_guaranteed') is not False):
        raise ValueError('native ranking manifest unavailable')
    raw = read_response(proof, max_bytes=MAX_MANIFEST)
    if raw != _manifest_bytes(expected) or proof.get('raw_response_bytes') != len(raw):
        raise ValueError('native ranking immutable metadata differs')
    return True


def bind_native_response(receipt, response, raw, ticker, *, owned_client):
    """Called only after the existing bounded iter_bytes loop exhausts cleanly."""
    from external_http_client import proxy_url_for_request
    url = _url(ticker)
    if (owned_client is not True or any(os.getenv(k) for k in PROXY_ENV)
            or proxy_url_for_request(url, 'Yahoo Taiwan published industry ranking')):
        return receipt
    if (type(response) is not httpx.Response or type(response.status_code) is not int
            or response.status_code != 200
            or response.history or str(response.url) != url
            or str(response.request.url) != url or response.request.method != 'GET'
            or getattr(response, 'from_cache', False) is not False
            or ('from_cache' in response.extensions and response.extensions['from_cache'] is not False)
            or response.is_stream_consumed is not True or response.is_closed is not True
            or any(response.request.headers.get(k) for k in
                   ('authorization', 'cookie', 'proxy-authorization'))
            or 'content-range' in response.headers
            or response.headers.get('content-type', '').split(';')[0].strip().lower() != 'text/html'
            or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BODY):
        raise ValueError('native ranking response identity or completeness invalid')
    encoding = response.headers.get('content-encoding', 'identity').lower()
    if encoding not in ('', 'identity', 'gzip', 'br', 'deflate', 'zstd'):
        raise ValueError('native ranking encoding unverified')
    length = response.headers.get('content-length')
    if encoding in ('', 'identity') and length is not None:
        if not length.isascii() or not length.isdecimal() or int(length) != len(raw):
            raise ValueError('native ranking declared length differs')
    result = {**receipt, **FLAGS}
    binding = _binding(result, ticker)
    if binding['body_sha256'] != sha256(raw).hexdigest():
        raise ValueError('native ranking archived stream differs')
    result['native_http_manifest'] = archive_response(
        _manifest_bytes(binding), source_url=url, retrieved_at=result['retrieved_at'],
        http_status=None, evidence_kind='private_acquisition_manifest', max_bytes=MAX_MANIFEST)
    validate_native_receipt(result, ticker)
    return result
