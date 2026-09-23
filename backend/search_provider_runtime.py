"""Bounded upstream search observations and persistent endpoint cooldowns.

No query, credential, or response body is persisted. A configured credential is
hashed only to prevent a replacement key inheriting a previous key's cooldown.
"""
from __future__ import annotations

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
        super().__init__(json.dumps(diagnostic, ensure_ascii=False, separators=(',', ':')))


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
    seconds = {'authentication': 3600, 'payment_required': 3600, 'access_denied': 1800,
               'provider_rejected': 900, 'rate_limited': 300, 'parse_error': 300,
               'provider_error': 300}.get(details['error_kind'], 60)
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
            seconds = max(seconds, min(retry_seconds, 86400))
    state = {**details, 'retry_at': time.time() + seconds}
    try:
        set_cache_json(key, state, ttl_seconds=math.ceil(seconds))
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


async def fetch_search_upstream(provider, credential, callback):
    """One actual call per route step; cooling providers never delay fallbacks."""
    key = scope_key(provider, credential)
    started = time.monotonic()
    blocked = cooldown_state(key)
    if not blocked:
        circuit = provider_circuit_state(key)
        if circuit.get('open') and float(circuit.get('opened_until') or 0) > time.time():
            blocked = {'error_kind': 'circuit_open', 'retry_at': circuit['opened_until']}
    if blocked:
        record_observation(provider, started, outcome='cooldown', details=blocked, sent=False)
        return []
    status_token = _HTTP_STATUS.set(None)
    try:
        with provider_attempt(provider, 1):
            try:
                records = await callback()
            except Exception as exc:
                state = remember_failure(key, exc)
                record_observation(provider, started, outcome='failure', details=state)
                raise
            record_observation(provider, started, outcome='results' if records else 'valid_empty', count=len(records), details={'http_status': _HTTP_STATUS.get()})
            return records
    finally:
        _HTTP_STATUS.reset(status_token)
