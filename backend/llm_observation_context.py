"""Diagnostic identities and measured intervals; never influence execution policy."""
from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import hashlib
import hmac
import inspect
import itertools
import os
import re
import threading
import time
import uuid

_logical = ContextVar('llm_observation_logical', default=None)
_attempt = ContextVar('llm_observation_attempt', default=None)
_transport = ContextVar('llm_observation_transport', default=None)
_health_lock = threading.Lock()
_dropped = Counter()
_started_at = time.time()


def _label(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}', value) else None


def telemetry_health():
    with _health_lock:
        return {'process_id': os.getpid(), 'process_started_at': _started_at,
                'dropped_events': sum(_dropped.values()), 'dropped_by_operation': dict(_dropped),
                'scope': 'this_process_only'}


def note_dropped(operation):
    with _health_lock:
        _dropped[operation] += 1


def record_observation(operation, model, status='observed', *, created_at=None, db_path=None, **metadata):
    try:
        from api_usage_store import record_api_usage
        from llm_provider_routes import split_model_provider
        from provider_correlation import current_correlation
        provider, actual = split_model_provider(model)
        if _label(actual) is None:
            return
        correlation = {k: v for k, v in current_correlation().items() if k in {'job_id', 'ticker'} and _label(v)}
        health = telemetry_health()
        record_api_usage(service='Gemini / Google AI' if provider == 'google' else provider.title(),
                         provider='google_ai' if provider == 'google' else provider,
                         operation=operation, model_id=actual, status=status, units=0,
                         created_at=created_at, db_path=db_path,
                         metadata={**correlation, **current_fields(), **metadata,
                                   'observer_process_id':health['process_id'],
                                   'observer_process_started_at':health['process_started_at'],
                                   'telemetry_dropped_events_before':health['dropped_events']})
    except Exception:
        note_dropped(operation)


def key_identity(api_key, model):
    """Stable pseudonym across slot reordering; no raw key or plain key hash."""
    if not isinstance(api_key, str) or not api_key:
        return {'project_mapping_status': 'unknown', 'project_ref': None}
    result = {'key_ref': hmac.new(api_key.encode(), b'stock-agent-observation-v1', hashlib.sha256).hexdigest()[:24],
              'key_ref_version': 1, 'project_mapping_status': 'unknown', 'project_ref': None}
    try:
        import config
        from llm_provider_routes import normalize_provider_keys, provider_for_model
        keys = normalize_provider_keys(config.LLM_API_KEYS_BY_PROVIDER).get(provider_for_model(model), [])
        if api_key in keys:
            result['key_slot'] = keys.index(api_key)+1
        result['key_count'] = len(keys)
    except Exception:
        pass
    return result


@dataclass
class Logical:
    logical_call_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    agent_num: int | None = None
    pipeline_id: str | None = None
    declared_model: str | None = None
    attempts: object = field(default_factory=lambda: itertools.count(1))
    last_attempt: object = None


@dataclass
class Attempt:
    model: str
    purpose: str
    attempt_number: int
    attempt_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.monotonic)
    transport_attempt_id: str | None = None
    source_sha256: str | None = None
    key_fields: dict = field(default_factory=dict)
    transport_ids: list = field(default_factory=list)


def current_fields(*, include_previous=False):
    logical = _logical.get()
    attempt = _attempt.get() or (logical.last_attempt if logical and include_previous else None)
    if logical is None:
        return {}
    result = {'observation_schema_version': 1, 'logical_call_id': logical.logical_call_id}
    try:
        from agent_effective_settings import process_settings_sha256
        result['effective_settings_sha256'] = process_settings_sha256()
    except Exception:
        pass
    for key in ('agent_num', 'pipeline_id', 'declared_model'):
        value = getattr(logical, key)
        if value is not None:
            result[key] = value
    if attempt is not None:
        result.update(attempt_id=attempt.attempt_id, attempt_number=attempt.attempt_number,
                      call_purpose=attempt.purpose, actual_model=attempt.model,
                      attempt_elapsed_seconds=max(0.0, time.monotonic()-attempt.started),
                      **(attempt.key_fields if len(attempt.transport_ids) <= 1 else {}))
        if len(attempt.transport_ids) == 1:
            result['transport_attempt_id'] = attempt.transport_ids[0]
        elif attempt.transport_ids:
            result['transport_attempt_ids'] = attempt.transport_ids[:16]
        if _transport.get() is not None:
            result.update(_transport.get())
        if attempt.source_sha256:
            result['source_sha256'] = attempt.source_sha256
    return result


@contextmanager
def logical_scope(agent_num=None, pipeline_id=None, declared_model=None):
    declared = None
    if type(agent_num) is int:
        try:
            import config
            declared = _label(declared_model) or _label(config.AGENT_MODELS.get(agent_num))
        except Exception:
            pass
    token = _logical.set(Logical(agent_num=agent_num if type(agent_num) is int else None,
                                 pipeline_id=_label(pipeline_id), declared_model=declared))
    try:
        yield
    finally:
        _logical.reset(token)


@contextmanager
def attempt_scope(model, purpose, *, prompt=None):
    if _logical.get() is None:
        with logical_scope():
            with attempt_scope(model, purpose, prompt=prompt) as attempt:
                yield attempt
        return
    attempt = Attempt(model=_label(model) or 'unknown', purpose=_label(purpose) or 'unknown',
                      attempt_number=next(_logical.get().attempts),
                      source_sha256=hashlib.sha256(prompt.encode()).hexdigest() if isinstance(prompt, str) else None)
    token = _attempt.set(attempt)
    try:
        yield attempt
    finally:
        _logical.get().last_attempt = attempt
        _attempt.reset(token)


def _decorate_scope(function, factory):
    signature = inspect.signature(function)
    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def asynchronous(*args, **kwargs):
            with factory(signature.bind_partial(*args, **kwargs).arguments):
                return await function(*args, **kwargs)
        return asynchronous
    @wraps(function)
    def synchronous(*args, **kwargs):
        with factory(signature.bind_partial(*args, **kwargs).arguments):
            return function(*args, **kwargs)
    return synchronous


def observe_agent(function):
    def factory(args):
        context=args.get('context') or {};agent=args.get('agent_num')
        override=context.get('_model_sequence_override')
        models=override.get(agent) if isinstance(override,dict) else None
        declared=next((value for value in models if _label(value)),None) if isinstance(models,(list,tuple)) else None
        return logical_scope(agent,context.get('pipeline_id'),declared_model=declared)
    return _decorate_scope(function, factory)


def observe_purpose(purpose):
    return lambda function: _decorate_scope(function, lambda args: attempt_scope(
        args.get('model_id','unknown'),purpose,prompt=args.get('prompt')))


def observe_attempt(function):
    def factory(args):
        if 'batch' in args:
            from gemma_evidence_batches import MODEL
            return attempt_scope(MODEL, 'evidence_batch', prompt=args['batch'].get('batch_id'))
        return attempt_scope(args.get('model_id', 'unknown'), 'analysis', prompt=args.get('prompt'))
    return _decorate_scope(function, factory)


def ensure_transport_attempt(function):
    @contextmanager
    def factory(args):
        if _attempt.get() is not None:
            yield
        else:
            purpose = 'embedding' if function.__name__.startswith('embed_') else 'auxiliary_generation_unspecified'
            with attempt_scope(args.get('model_id', 'unknown'), purpose, prompt=args.get('prompt')):
                yield
    return _decorate_scope(function, factory)


@dataclass
class Transport:
    response: object = None


@contextmanager
def transport_scope(model, api_key, entry_point):
    if _attempt.get() is None:
        with attempt_scope(model, 'auxiliary_generation_unspecified'):
            with transport_scope(model, api_key, entry_point) as span:
                yield span
        return
    attempt = _attempt.get()
    transport_fields = {'transport_attempt_id': uuid.uuid4().hex, **key_identity(api_key, model)}
    attempt.transport_ids.append(transport_fields['transport_attempt_id'])
    attempt.key_fields.update(key_identity(api_key, model))
    token = _transport.set(transport_fields)
    start, wall = time.monotonic(), time.time()
    span, outcome, error = Transport(), 'success', None
    fields = {**current_fields(), **transport_fields, 'entry_point': entry_point,
              'transport_basis': 'sdk_callback_not_delivery_receipt', 'started_at': wall}
    if entry_point.startswith('embed_'):
        fields['call_purpose']='embedding'
    record_observation('llm_transport_observation', model, 'attempt', **fields)
    try:
        yield span
    except BaseException as exc:
        outcome, error = 'cancelled' if isinstance(exc, asyncio.CancelledError) else 'error', exc
        raise
    finally:
        try:
            from llm_usage import extract_usage
            from llm_quota_observation_details import observe_quota_details
            from agent_runtime.retry_error_classification import provider_status_code
            details = {'ended_at': time.time(), 'elapsed_seconds': max(0.0, time.monotonic()-start),
                       'provider_status_code': provider_status_code(error) if error else None,
                       'usage': extract_usage(span.response, include_missing=False)}
            if details['usage'] and 'input_tokens' in details['usage']:
                details['input_tokens'] = details['usage']['input_tokens']
            if details['provider_status_code'] == 429:
                details['quota_observation'] = observe_quota_details(error)
            record_observation('llm_transport_observation', model, outcome, **fields, **details)
        except Exception:
            with _health_lock:
                _dropped['llm_transport_observation'] += 1
        finally:
            _transport.reset(token)


@contextmanager
def wait_scope(reason, *, model=None, planned_seconds=None):
    start, wall, outcome = time.monotonic(), time.time(), 'completed'
    try:
        yield
    except BaseException:
        outcome = 'interrupted'
        raise
    finally:
        logical = _logical.get()
        attempt = _attempt.get() or (logical.last_attempt if logical and reason == 'retry_backoff' else None)
        record_observation('llm_wait_interval', model or (attempt.model if attempt else 'unknown'),
                           **(current_fields(include_previous=True) if reason == 'retry_backoff' else {}),
                           wait_id=uuid.uuid4().hex, reason=reason, started_at=wall, ended_at=time.time(),
                           elapsed_seconds=max(0.0, time.monotonic()-start), planned_seconds=planned_seconds,
                           outcome=outcome, duration_basis='monotonic_clock')


def observed_sleep(seconds):
    with wait_scope('retry_backoff', planned_seconds=seconds):
        time.sleep(seconds)


async def observed_sleep_async(seconds):
    with wait_scope('retry_backoff', planned_seconds=seconds):
        await asyncio.sleep(seconds)
