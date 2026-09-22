"""Bounded hash receipts distinguish actual candidates from replay/transport."""
import functools
import inspect
import hashlib
import json
from contextlib import contextmanager

from data_trust_snapshot import sanitize_for_snapshot
from llm_cache_policy import fresh_repair_candidate, repair_cache_scope_active
from analysis_dependencies import upstream_input_hash

CONTRACT = 'repair-candidates:v1'
FIELD = 'repair_candidate_history'


def _hash(value):
    encoded = json.dumps(sanitize_for_snapshot(value), sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _entry(context, agent, data):
    identity = _hash({'agent': agent, 'input': data, 'contract': CONTRACT,
                      'prompt_version': context.get('prompt_version'),
                      'prompt_fingerprint': context.get('prompt_fingerprint'),
                      'upstream_input_hash': upstream_input_hash(agent, context),
                      'pipeline': context.get('pipeline_id')})
    history = context.setdefault(FIELD, {})
    key = str(agent)
    entry = history.get(key)
    if not isinstance(entry, dict) or entry.get('scope_hash') != identity:
        entry = {'contract': CONTRACT, 'scope_hash': identity, 'agent': agent,
                 'calls': 0, 'call_failures': 0, 'candidate_hashes': [],
                 'duplicate_candidates': 0, 'rejections': []}
        history[key] = entry
    return entry


def reject_candidate(context, agent, data, text, issues):
    if not text or not issues:
        return
    entry = _entry(context, agent, data)
    receipt = {'candidate_hash': _hash(text), 'issue_hash': _hash(sorted(map(str, issues)))}
    if receipt not in entry['rejections']:
        entry['rejections'] = (entry['rejections'] + [receipt])[-8:]


def observe_candidate(context, agent, data, text):
    from .routing import is_agent_execution_failure
    if not isinstance(text, str) or not text.strip() or is_agent_execution_failure(text):
        return
    entry = _entry(context, agent, data)
    fingerprint = _hash(text)
    if fingerprint in entry['candidate_hashes']:
        entry['duplicate_candidates'] += 1
    else:
        entry['candidate_hashes'] = (entry['candidate_hashes'] + [fingerprint])[-8:]


@contextmanager
def repair_candidate_call(context, agent, data):
    entry = _entry(context, agent, data)
    entry['calls'] += 1
    with fresh_repair_candidate(entry):
        try:
            yield
        except BaseException:
            entry['call_failures'] += 1
            raise


def fresh_candidate_for_retry(function):
    """Cover quality, identity and source repairs using the same routed entrypoint."""
    def needed(context):
        return not repair_cache_scope_active() and any(context.get(k) for k in (
            '_audit_retry_instruction', '_identity_retry_instruction', '_quality_retry_instruction'))
    if inspect.iscoroutinefunction(function):
        @functools.wraps(function)
        async def asynchronous(agent_num, data, context, *args, **kwargs):
            if not needed(context):
                return await function(agent_num, data, context, *args, **kwargs)
            with repair_candidate_call(context, agent_num, data):
                result = await function(agent_num, data, context, *args, **kwargs)
            observe_candidate(context, agent_num, data, result)
            return result
        return asynchronous
    @functools.wraps(function)
    def synchronous(agent_num, data, context, *args, **kwargs):
        if not needed(context):
            return function(agent_num, data, context, *args, **kwargs)
        with repair_candidate_call(context, agent_num, data):
            result = function(agent_num, data, context, *args, **kwargs)
        observe_candidate(context, agent_num, data, result)
        return result
    return synchronous


def validate_repair_candidate(agent, text, data, context, *, validators, contract):
    """Keep fatal identity/leak checks separate from retryable quality failures."""
    prompt, identity, quality = validators
    fatal = prompt(text) + identity(text, data)
    issues = [] if fatal else quality(agent, text, data) + contract(agent, {
        **context, 'data': data,
        'analyses': {**context.get('analyses', {}), agent: text},
    })
    reject_candidate(context, agent, data, text, fatal or issues)
    return fatal, issues
