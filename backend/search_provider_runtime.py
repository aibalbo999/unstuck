"""Bounded upstream search observations and persistent endpoint cooldowns.

No query, credential, or response body is persisted. A configured credential is
hashed only to prevent a replacement key inheriting a previous key's cooldown.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from email.utils import parsedate_to_datetime
from contextvars import ContextVar

from cache_store import get_cache_json, set_cache_json
from provider_correlation import current_correlation, provider_attempt
from provider_resilience import provider_circuit_state
from provider_sla import record_source_audit_entries
from search_admission import endpoint_admission


_HTTP_STATUS = ContextVar("search_upstream_http_status", default=None)


def observe_http_response(response):
    _HTTP_STATUS.set(getattr(response, "status_code", None))


class SourceResponseError(RuntimeError):
    retryable = False

    def __init__(self, error_kind: str, *, status_code=None, response_text='', parser_version=''):
        self.error_kind = error_kind
        self.status_code = status_code
        diagnostic = {'error_kind': error_kind, 'http_status': status_code}
        if response_text:
            diagnostic.update(response_sha256=hashlib.sha256(response_text.encode()).hexdigest(), response_bytes=len(response_text.encode()))
        if parser_version:
            diagnostic['parser_version'] = parser_version
        self.diagnostic = diagnostic
        # Reports consume str(exc); keep technical numbers in structured diagnostics.
        messages = {
            'access_denied': '來源拒絕存取，未取得資料。',
            'parse_error': '來源回應格式無法辨識，未取得可用資料。',
            'provider_error': '來源回報錯誤，未取得資料。',
            'authentication': '來源驗證失敗，未取得資料。',
            'payment_required': '來源要求付費授權，未取得資料。',
            'rate_limited': '來源請求受到限制，暫未取得資料。',
            'cooldown': '來源仍在冷卻期間，尚未重新取得資料。',
            'timeout': '來源回應逾時，未取得資料。',
        }
        super().__init__(messages.get(error_kind, '來源取得失敗，請查看來源診斷紀錄。'))


def scope_key(provider: str, credential: str = '', *, endpoint='search') -> str:
    fingerprint = hashlib.sha256(credential.encode()).hexdigest()[:16] if credential else 'public'
    return f'provider_endpoint_cooldown:{provider}:{endpoint}:{fingerprint}'


def cooldown_state(key: str) -> dict:
    try:
        state = get_cache_json(key)
        return state if isinstance(state, dict) and float(state.get('retry_at') or 0) > time.time() else {}
    except Exception:
        return {}


def error_details(exc: Exception) -> dict:
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', getattr(exc, 'status_code', None))
    kind = getattr(exc, 'error_kind', '')
    if not kind:
        kind = {401: 'authentication', 402: 'payment_required', 403: 'access_denied', 429: 'rate_limited', 432: 'provider_rejected'}.get(status, '')
    if not kind:
        kind = 'server_error' if status and status >= 500 else ('http_error' if status else ('parse_error' if isinstance(exc, ValueError) else 'timeout' if 'timeout' in type(exc).__name__.lower() else 'transport_error'))
    diagnostic = getattr(exc, 'diagnostic', {})
    return {'error_kind': kind, 'http_status': status if status is not None else _HTTP_STATUS.get(), **{name: diagnostic[name] for name in ('response_sha256', 'response_bytes', 'parser_version') if name in diagnostic}}


def remember_failure(key: str, exc: Exception) -> dict:
    details = error_details(exc)
    try:
        previous = get_cache_json(key) or {}
    except Exception:
        previous = {}
    failures = min(12, int(previous.get('consecutive_failures') or 0) + 1)
    seconds = {'authentication': 3600, 'payment_required': 3600, 'access_denied': 1800,
               'provider_rejected': 900, 'rate_limited': 300, 'parse_error': 300,
               'provider_error': 300}.get(details['error_kind'], 60)
    seconds = min(86400, seconds * 2 ** (failures - 1))
    response = getattr(exc, 'response', None)
    retry_header = getattr(response, 'headers', {}).get('Retry-After')
    if retry_header:
        try:
            retry_seconds = float(retry_header)
        except (ValueError, TypeError):
            try:
                retry_seconds = parsedate_to_datetime(retry_header).timestamp() - time.time()
            except (ValueError, TypeError, OverflowError):
                retry_seconds = 0
        if math.isfinite(retry_seconds) and retry_seconds > 0:
            seconds = max(seconds, retry_seconds)
    state = {**details, 'retry_at': max(time.time() + seconds, float(previous.get('retry_at') or 0)), 'consecutive_failures': failures}
    try:
        # Retain failure history after the retry deadline, including restarts.
        set_cache_json(key, state, ttl_seconds=math.ceil(max(state['retry_at'] - time.time(), 7 * 86400)))
    except Exception:
        pass
    return state


def record_observation(provider, started, *, outcome, count=0, details=None, source='search_upstream', sent=True):
    metadata = {'outcome': outcome, 'http_request_sent': sent, **(details or {})}
    entry = {
        **current_correlation(), **metadata, 'source': source, 'provider': provider,
        'event_kind': 'http_attempt' if sent else 'local_block',
        'status': 'success' if outcome == 'results' else ('degraded_enrichment' if outcome == 'valid_empty' else 'unavailable' if not sent or metadata.get('error_kind') in {'transport_error', 'timeout', 'server_error'} else 'error'),
        'duration_ms': max(0, int((time.monotonic() - started) * 1000)),
        'record_count': count,
        'message': ('skip: ' if not sent else '') + json.dumps(metadata, separators=(',', ':'))[:230],
    }
    try:
        record_source_audit_entries([entry])
    except Exception:
        # Observability failure must not discard successfully acquired evidence.
        pass


async def fetch_search_upstream(provider, credential, callback, *, endpoint='search',
                                min_interval_seconds=None, timeout_seconds=20):
    """One bounded call per endpoint; cooldown/busy steps immediately yield fallback."""
    key = scope_key(provider, credential, endpoint=endpoint)
    started = time.monotonic()
    timeout_seconds = max(0.001, min(float(timeout_seconds), 60))
    interval = (5.1 if provider == 'gdelt' else 0.25) if min_interval_seconds is None else max(0, float(min_interval_seconds))
    with endpoint_admission(key, timeout_seconds=timeout_seconds) as owns:
        if owns is None:
            record_observation(provider, started, outcome='busy', details={'error_kind': 'single_flight_busy', 'endpoint': endpoint}, sent=False)
            return []
        try:
            saved = get_cache_json(key) or {}
        except Exception:
            record_observation(provider, started, outcome='unavailable', details={'error_kind': 'guard_storage_unavailable', 'endpoint': endpoint}, sent=False)
            return []
        blocked = saved if float(saved.get('retry_at') or 0) > time.time() else {}
        if provider == 'gdelt':
            # Preserve cooldowns written by older international-news workers.
            try:
                legacy = get_cache_json('gdelt_rate_limit_cooldown:v1') or {}
                until = float(legacy.get('cooldown_until') or 0)
                if until > max(time.time(), float(blocked.get('retry_at') or 0)):
                    blocked = {'error_kind': 'rate_limited', 'retry_at': until}
            except Exception:
                record_observation(provider, started, outcome='unavailable', details={'error_kind': 'guard_storage_unavailable', 'endpoint': endpoint}, sent=False)
                return []
        if not blocked and float(saved.get('next_request_at') or 0) > time.time():
            blocked = {'error_kind': 'request_pacing', 'retry_at': saved['next_request_at']}
        if not blocked:
            circuit = provider_circuit_state(key)
            if circuit.get('open') and float(circuit.get('opened_until') or 0) > time.time():
                blocked = {'error_kind': 'circuit_open', 'retry_at': circuit['opened_until']}
        if blocked:
            record_observation(provider, started, outcome='cooldown', details={**blocked, 'endpoint': endpoint}, sent=False)
            return []
        status_token = _HTTP_STATUS.set(None)
        try:
            with provider_attempt(provider, 1):
                try:
                    # asyncio.timeout preserves HTTP observation ContextVars.
                    async with asyncio.timeout(timeout_seconds):
                        records = await callback()
                except Exception as exc:
                    state = remember_failure(key, exc) if owns() else {**error_details(exc), 'state_write_skipped': 'lease_lost'}
                    record_observation(provider, started, outcome='failure', details={**state, 'endpoint': endpoint})
                    raise
                if owns():
                    try:
                        set_cache_json(key, {'consecutive_failures': 0, 'next_request_at': time.time() + interval}, ttl_seconds=max(1, math.ceil(interval)))
                    except Exception:
                        pass  # Do not discard evidence already acquired.
                record_observation(provider, started, outcome='results' if records else 'valid_empty', count=len(records), details={'http_status': _HTTP_STATUS.get(), 'endpoint': endpoint})
                return records
        finally:
            _HTTP_STATUS.reset(status_token)
