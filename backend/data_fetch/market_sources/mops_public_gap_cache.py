"""Reuse a verified public-JSON validation failure for one annual-data day.

Warm reads replay either a complete short index or nineteen complete originals
through the same collector. Four filings may supply five periods and are not
short gaps. Cache hits still have no data, HTTP or new provider attempt.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import math
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

from cache_store import get_cache_json, set_cache_json
from provider_correlation import current_audit_correlation, source_operation, correlation_metadata
from search_provider_runtime import SourceResponseError
from .official_xbrl_financial import FilingError
from .annual_filing_index_gap import confirmed_short_annual_index
from .mops_public_annual import (
    INDEX_URL, PROVIDER, _receipt, fetch_public_annual_histories,
    _fetch_public_financial_result_uncached,
)

SCHEMA = 'mops-public-annual-validation-gap.v1'
GAP_RETRY_SECONDS = 24 * 60 * 60
SHORT_INDEX_MESSAGE = 'fewer than five contiguous published consolidated annual filings'
CORRELATION_KEYS = {'job_id', 'fetch_id', 'operation_id', 'attempt_id', 'provider_attempts',
                    'provider_attempt_count', 'provider_sla_event_id', 'ticker',
                    'data_fingerprint', 'event_kind'}


def _fingerprint():
    directory = Path(__file__).resolve().parent
    paths = [Path(__file__).resolve(), directory / 'mops_public_annual.py',
             directory / 'official_xbrl_financial.py', directory / 'official_mopsfin_financial.py',
             directory / 'annual_filing_index_gap.py']
    return sha256(b''.join(p.read_bytes() for p in paths)).hexdigest()


def _gap_reason(message):
    if message == SHORT_INDEX_MESSAGE:
        return True
    match = re.fullmatch(r'(?:annual XBRL facts are incomplete|conflicting incomplete comparative statement) for (20\d{2})', str(message))
    return bool(match and 2013 <= int(match[1]) < datetime.now(ZoneInfo('Asia/Taipei')).year)


class _RecordingTransport:
    def __init__(self, inner):
        self.inner = inner; self.originals = []

    @property
    def deadline(self): return self.inner.deadline

    @property
    def components(self): return self.inner.components

    def batch(self): return self.inner.batch()

    def request(self, url, **kwargs):
        raw, receipt = self.inner.request(url, **kwargs)
        self.originals.append({'url': url, 'request': deepcopy(kwargs), 'raw_receipt': deepcopy(receipt)})
        return raw, receipt


class _ReplayTransport:
    def __init__(self, originals):
        self.originals = originals; self.position = 0; self.components = []
        self.deadline = time.monotonic() + 45

    @contextmanager
    def batch(self): yield self

    def request(self, url, **kwargs):
        item = self.originals[self.position]; self.position += 1
        if item['url'] != url or item['request'] != kwargs:
            raise FilingError('public gap original request mismatch')
        limit = 2_500_000 if 'ajax_t203sb01' in url else 250_000
        raw = _receipt(item['raw_receipt'], url, limit)
        return raw, deepcopy(item['raw_receipt'])


def _valid(stored, ticker, fingerprint):
    try:
        if (not isinstance(stored, dict) or stored.get('schema') != SCHEMA
                or stored.get('ticker') != ticker or stored.get('parser_fingerprint') != fingerprint): return False
        a = stored['audit']; originals = stored['originals']
        if (not isinstance(a, dict) or a.get('source') != 'financial_statements' or a.get('provider') != PROVIDER
                or a.get('status') != 'error' or a.get('error_kind') != 'FilingError'
                or type(a.get('record_count')) is not int or a['record_count'] != 0
                or not _gap_reason(a.get('message')) or a.get('cache_hit') is not False or a.get('stale') is not False
                or a.get('http_request_sent') is not True or type(a.get('http_request_count')) is not int
                or a['http_request_count'] not in (1, 19) or not isinstance(originals, list)
                or len(originals) != a['http_request_count']): return False
        stamp = a['fetched_at_epoch']; iso = datetime.fromisoformat(a['fetched_at'])
        if (type(stamp) not in (int, float) or not math.isfinite(stamp) or iso.tzinfo is None
                or abs(iso.timestamp() - stamp) >= .000001 or not 0 <= time.time() - stamp < GAP_RETRY_SECONDS): return False
        components = a['component_statuses']
        if not isinstance(components, dict) or len(components) != len(originals): return False
        for i, original in enumerate(originals):
            if not isinstance(original, dict): return False
            if not isinstance(original.get('raw_receipt'), dict) or not isinstance(components.get(str(i)), dict): return False
            receipt = original['raw_receipt']; component = components[str(i)]; fetched = receipt['retrieved_at']
            if (type(fetched) not in (int, float) or not math.isfinite(fetched) or not 0 <= stamp - fetched < 45
                    or component.get('url') != original['url'] or component.get('http_request_sent') is not True
                    or type(component.get('http_status')) is not int or component['http_status'] != 200
                    or component.get('response_sha256') != receipt['raw_response_sha256']
                    or type(component.get('response_bytes')) is not int
                    or component['response_bytes'] != receipt['raw_response_bytes']): return False
        replay = _ReplayTransport(originals)
        if len(originals) == 1:
            if a['message'] != SHORT_INDEX_MESSAGE or originals[0]['url'] != INDEX_URL:
                return False
            raw = _receipt(originals[0]['raw_receipt'], INDEX_URL, 2_500_000)
            if time.monotonic() >= replay.deadline:
                return False
            short = confirmed_short_annual_index(raw, ticker.split('.')[0])
            if short is None or len(short['available_consolidated_annual_years']) >= 4:
                return False
        try:
            fetch_public_annual_histories(ticker, transport=replay)
        except FilingError as exc:
            return (replay.position == len(originals) and str(exc) == a['message'] and _gap_reason(str(exc))
                    and time.monotonic() < replay.deadline
                    and 0 <= time.time() - stamp < GAP_RETRY_SECONDS)
        return False
    except (KeyError, TypeError, ValueError, OverflowError, OSError, EOFError, IndexError, AttributeError, SourceResponseError): return False


def fetch_cached_public_result(ticker, *, transport=None):
    started = time.monotonic(); key = None; stored = None; fingerprint = None
    cache_read_failed = False
    if isinstance(ticker, str) and re.fullmatch(r'[1-9]\d{3}\.TW(?:O)?', ticker):
        try:
            fingerprint = _fingerprint()
            key = f'mops-public-annual-validation-gap:{fingerprint}:{datetime.now(ZoneInfo("Asia/Taipei")).year}:{ticker}'
            stored = get_cache_json(key)
        except Exception: cache_read_failed = True
    if key and _valid(stored, ticker, fingerprint):
        with source_operation('financial_statements', PROVIDER):
            old_keys = CORRELATION_KEYS | set(correlation_metadata(stored['audit']))
            a = {k: deepcopy(v) for k, v in stored['audit'].items() if k not in old_keys}
            original_message = a['message']
            a.update(current_audit_correlation(), ticker=ticker, cache_hit=True, stale=False,
                event_kind='cache_hit', http_request_sent=False, http_request_count=0, http_status=None,
                original_status='error', original_http_request_count=stored['audit']['http_request_count'], component_statuses={},
                provider_attempts=[], provider_attempt_count=0,
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                retry_at=a['fetched_at_epoch'] + GAP_RETRY_SECONDS,
                message=original_message + '；完整原件重播確認同股票年度缺口，暫不重複下載。')
            return {'value': None, 'audit': a}
    from . import mops_public_annual as native
    http = _RecordingTransport(transport or native.PublicMopsHttp())
    result = _fetch_public_financial_result_uncached(ticker, transport=http)
    audit = result.get('audit') or {}
    if key and result.get('value') is not None and audit.get('status') == 'success' and (stored is not None or cache_read_failed):
        try: set_cache_json(key, None, 1)
        except Exception: pass
    if key and result.get('value') is None and audit.get('status') == 'error' and _gap_reason(audit.get('message')):
        try:
            original = deepcopy(audit)
            stamp = datetime.fromisoformat(original['fetched_at'])
            if stamp.tzinfo is None: raise ValueError('unverified original gap timestamp')
            original['fetched_at_epoch'] = stamp.timestamp()
            proof = {'schema': SCHEMA, 'ticker': ticker, 'parser_fingerprint': fingerprint,
                     'audit': original, 'originals': deepcopy(http.originals)}
            if _valid(proof, ticker, fingerprint): set_cache_json(key, proof, GAP_RETRY_SECONDS)
        except Exception: pass
    return result
