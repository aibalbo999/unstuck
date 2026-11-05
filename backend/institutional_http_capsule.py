"""Forward-only evidence from the existing native official institutional GET.

This observes transport, never certifies a publication, issuer row or finality.
Cached/injected/research paths cannot create another native transport event.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import os
import re
import time
from uuid import uuid4

import httpx
from official_response_evidence import archive_response, read_response

_ACTIVE = ContextVar('official_institutional_native_get', default=None)
SCHEMA = 'official-institutional-native-http.v1'
MAX_BYTES = 8 * 1024 * 1024
FLAGS = {'http_status_observed': True, 'response_complete': True,
         'cache_hit': False, 'request_method': 'GET'}


def request_spec(market, day, url, provider):
    from official_institutional_source import _url, TWSE_SOURCE, TPEX_SOURCE
    from tpex_openapi_institutional import URL, SOURCE
    parsed = date.fromisoformat(day)
    if parsed.isoformat() != day or market not in ('TWSE', 'TPEX'):
        raise ValueError('invalid institutional request specification')
    primary = _url(market, day)
    allowed = {(TWSE_SOURCE, primary),
               (TWSE_SOURCE, primary.replace('www.twse.com.tw', 'wwwc.twse.com.tw'))} \
              if market == 'TWSE' else {(TPEX_SOURCE, primary), (SOURCE, URL)}
    if (provider, url) not in allowed:
        raise ValueError('institutional endpoint is not admitted')
    return {'market': market, 'request_day': day, 'url': url, 'provider': provider}


@contextmanager
def observe_get(spec):
    if spec != request_spec(spec['market'], spec['request_day'], spec['url'], spec['provider']):
        raise ValueError('institutional request specification differs')
    holder = {'spec': spec, 'received_at_epoch': None, 'receipt': None}
    token = _ACTIVE.set(holder)
    try:
        yield holder
    finally:
        _ACTIVE.reset(token)


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':'), allow_nan=False).encode()


def _binding(receipt):
    spec = receipt.get('source_spec')
    if not isinstance(spec, dict) or spec != request_spec(
            spec.get('market'), spec.get('request_day'), spec.get('url'), spec.get('provider')):
        raise ValueError('institutional receipt specification differs')
    origin = receipt.get('origin')
    if (not isinstance(origin, dict) or set(origin) != {'ticker', 'fetch_id', 'operation_id'}
            or any(not isinstance(v, str) or not 0 < len(v) <= 160 for v in origin.values())
            or not re.fullmatch(r'[1-9]\d{3,5}\.' + ('TW' if spec['market'] == 'TWSE' else 'TWO'), origin['ticker'])
            or not re.fullmatch(r'[0-9a-f]{32}', str(receipt.get('native_request_id') or ''))):
        raise ValueError('institutional native owner unavailable')
    stamp = receipt.get('retrieved_at')
    if (receipt.get('status') != 'archived' or receipt.get('source_url') != spec['url']
            or type(receipt.get('http_status')) is not int or receipt['http_status'] != 200
            or receipt.get('evidence_kind') != 'decoded_complete_http_response_body'
            or type(receipt.get('raw_response_bytes')) is not int
            or type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 < stamp <= time.time()
            or any(type(receipt.get(k)) is not type(v) or receipt.get(k) != v for k, v in FLAGS.items())):
        raise ValueError('institutional native receipt metadata differs')
    raw = read_response(receipt, max_bytes=MAX_BYTES)
    if not 0 < len(raw) <= MAX_BYTES or len(raw) != receipt['raw_response_bytes']:
        raise ValueError('institutional full original differs')
    binding = {'schema': SCHEMA, 'spec': spec, 'origin': origin,
               'native_request_id': receipt['native_request_id'], 'received_at': stamp,
               'body_sha256': sha256(raw).hexdigest(), 'body_bytes': len(raw), **FLAGS,
               'financial_semantics_verified': False, 'finality_guaranteed': False}
    return binding, raw


def validate_receipt(receipt, spec, raw_iso_evidence=None):
    binding, raw = _binding(receipt)
    if binding['spec'] != spec:
        raise ValueError('institutional expected request differs')
    manifest = receipt.get('native_http_manifest')
    if (not isinstance(manifest, dict) or manifest.get('status') != 'archived'
            or manifest.get('source_url') != spec['url']
            or manifest.get('retrieved_at') != receipt['retrieved_at']
            or manifest.get('http_status') is not None
            or manifest.get('evidence_kind') != 'private_acquisition_manifest'
            or type(manifest.get('raw_response_bytes')) is not int):
        raise ValueError('institutional immutable manifest unavailable')
    encoded = read_response(manifest, max_bytes=16384)
    if encoded != _encoded(binding) or len(encoded) != manifest['raw_response_bytes']:
        raise ValueError('institutional immutable manifest differs')
    if raw_iso_evidence is not None:
        expected_iso = datetime.fromtimestamp(receipt['retrieved_at'], timezone.utc).isoformat()
        if (raw_iso_evidence.get('source_url') != spec['url']
                or raw_iso_evidence.get('retrieved_at') != expected_iso
                or read_response(raw_iso_evidence, max_bytes=MAX_BYTES) != raw):
            raise ValueError('institutional original ISO evidence differs')
    return raw


def capture_native_get(url, response, *, provider, verify, proxy, received_at_epoch):
    """Only external_http_client.sync_get calls this after its native GET."""
    from finmind_transport_receipts import receipt_observation_enabled
    holder = _ACTIVE.get()
    if holder is None or not receipt_observation_enabled():
        return
    spec = holder['spec']
    if (url != spec['url'] or provider != spec['provider'] or proxy
            or verify is not None and verify is not True
            or any(os.getenv(k) for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
                                         'http_proxy', 'https_proxy', 'all_proxy'))):
        return
    from provider_correlation import current_correlation, current_source_identity
    context = current_correlation()
    origin = {k: context.get(k) for k in ('ticker', 'fetch_id', 'operation_id')}
    if (current_source_identity() != ('institutional_trading', 'FinMind')
            or any(not isinstance(v, str) or not 0 < len(v) <= 160 for v in origin.values())):
        return
    if (type(response) is not httpx.Response or type(response.status_code) is not int
            or response.status_code != 200 or response.history
            or str(response.url) != url or str(response.request.url) != url
            or response.request.method != 'GET' or getattr(response, 'from_cache', False) is not False
            or 'from_cache' in response.extensions and response.extensions['from_cache'] is not False
            or 'cache_hit' in response.extensions and response.extensions['cache_hit'] is not False
            or response.is_stream_consumed is not True or response.is_closed is not True
            or 'content-range' in response.headers
            or any(response.request.headers.get(k) for k in ('authorization', 'cookie', 'proxy-authorization'))):
        return
    raw = response.content
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        return
    encoding = response.headers.get('content-encoding', 'identity').lower()
    length = response.headers.get('content-length')
    if encoding in ('', 'identity') and length is not None and (
            not length.isascii() or not length.isdecimal() or int(length) != len(raw)):
        return
    if (type(received_at_epoch) not in (int, float) or not math.isfinite(received_at_epoch)
            or not 0 < received_at_epoch <= time.time()):
        return
    # Floor to the ISO evidence's microsecond precision, never move arrival later.
    stamp = math.floor(received_at_epoch * 1_000_000) / 1_000_000
    holder['received_at_epoch'] = stamp  # Preserve arrival even if optional archival fails.
    receipt = archive_response(raw, source_url=url, retrieved_at=stamp, http_status=200,
                               evidence_kind='decoded_complete_http_response_body', max_bytes=MAX_BYTES)
    receipt.update(FLAGS, source_spec=spec, origin=origin, native_request_id=uuid4().hex)
    binding, _ = _binding(receipt)
    receipt['native_http_manifest'] = archive_response(
        _encoded(binding), source_url=url, retrieved_at=stamp, http_status=None,
        evidence_kind='private_acquisition_manifest', max_bytes=16384)
    validate_receipt(receipt, spec)
    holder['receipt'] = receipt
    from provider_sla import record_source_audit_entries
    record_source_audit_entries([{**context, 'source': 'institutional_trading',
        'provider': provider + ' native HTTP', 'status': 'success', 'record_count': 0,
        'event_kind': 'http_transport_receipt', 'selection_policy': 'transport-receipt-only:v1',
        'http_request_sent': True, 'http_status': 200, 'http_status_observed': True,
        'response_complete': True, 'cache_hit': False, 'raw_http_receipt': receipt,
        'message': 'Official institutional transport only; no source success, row or publication admission added.'}])
