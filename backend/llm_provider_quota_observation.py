"""Secret-safe 429 observations for every public LLM transport entry point.

These zero-unit observations are diagnostics, never request/error accounting or
evidence of a particular quota being exhausted. They do not alter retry policy.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from functools import wraps
import inspect
import threading

_active = ContextVar('provider_quota_observation', default=None)


def _execution():
    try:
        return asyncio.current_task()
    except RuntimeError:
        return threading.get_ident()


def _record(error, api_key, model_id, entry_point):
    try:
        from api_usage_store import record_api_usage
        import config
        from llm_congestion import _actual_provider_status
        from llm_provider_routes import split_model_provider, normalize_provider_keys
        from llm_quota_details import extract_quota_details
        from provider_correlation import current_correlation
        from workflow_telemetry_attribution import current_node_invocation, safe_model_label

        if _actual_provider_status(error) != 429:
            return
        provider, model = split_model_provider(model_id)
        model = safe_model_label(model)
        if model is None or provider not in {'google', 'openai', 'anthropic'}:
            return
        quota = extract_quota_details(error)
        from llm_quota_observation_details import observe_quota_details
        from llm_observation_context import current_fields, key_identity
        metadata = {
            'schema_version': 1, 'provider_status_code': 429,
            'provider_quota': quota,
            'quota_detail_status': 'provided' if quota['violations'] else 'unspecified',
            'entry_point': entry_point,
            'key_slot_basis': 'executing_process_config',
            'quota_observation': observe_quota_details(error),
            **current_fields(), **key_identity(api_key, model_id),
        }
        keys_by_provider = normalize_provider_keys(config.LLM_API_KEYS_BY_PROVIDER)
        keys = [key for group in keys_by_provider.values() for key in group]
        metadata['key_count'] = len(keys)
        if api_key in keys_by_provider.get(provider, []):
            metadata['key_slot'] = keys.index(api_key) + 1
        for field in ('job_id', 'ticker'):
            value = current_correlation().get(field)
            if isinstance(value, str) and value:
                metadata[field] = value[:160]
        node = current_node_invocation() or {}
        label = safe_model_label(node.get('node_name'))
        if label:
            metadata['node_name'] = label
        if type(node.get('agent_num')) is int:
            metadata['agent_num'] = node['agent_num']
        record_api_usage(
            service='Gemini / Google AI' if provider == 'google' else provider.title(),
            provider='google_ai' if provider == 'google' else provider,
            operation='llm_provider_quota_observation', status='observed', units=0,
            model_id=model, metadata=metadata,
        )
    except Exception:
        # The exact provider exception and existing fallback must take precedence.
        from llm_observation_context import note_dropped
        note_dropped('llm_provider_quota_observation')
        return


def observe_provider_quota(function):
    """Record once when stream fallback delegates to the non-stream entry point."""
    def identity(api_key, model_id):
        return (_execution(), api_key, model_id)

    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def asynchronous(api_key, model_id, *args, **kwargs):
            scope = identity(api_key, model_id)
            if _active.get() == scope:
                return await function(api_key, model_id, *args, **kwargs)
            token = _active.set(scope)
            try:
                return await function(api_key, model_id, *args, **kwargs)
            except Exception as error:
                _record(error, api_key, model_id, function.__name__)
                raise
            finally:
                _active.reset(token)
        return asynchronous

    @wraps(function)
    def synchronous(api_key, model_id, *args, **kwargs):
        scope = identity(api_key, model_id)
        if _active.get() == scope:
            return function(api_key, model_id, *args, **kwargs)
        token = _active.set(scope)
        try:
            return function(api_key, model_id, *args, **kwargs)
        except Exception as error:
            _record(error, api_key, model_id, function.__name__)
            raise
        finally:
            _active.reset(token)
    return synchronous
