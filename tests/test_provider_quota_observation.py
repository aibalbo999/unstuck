"""Quota diagnostics belong to the shared transport, not a particular Agent."""
import asyncio
import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from google.genai import types

import config
import llm_transport as transport


class QuotaError(RuntimeError):
    code = 429
    message = 'private-error-and-key'
    details = [{'violations': [{
        'quotaId': 'GenerateContentInputTokensPerModelPerMinute-FreeTier',
        'quotaValue': '16000',
        'quotaDimensions': {'model': 'gemma-4-26b-a4b-it', 'consumer': 'private-project'},
    }]}, {'retryDelay': '28s'}]
    headers = {'Retry-After': '35', 'Authorization': 'private-header'}


@pytest.fixture
def rig(monkeypatch):
    events = []
    error = QuotaError('private-error-and-key')
    def fail(**kwargs):
        raise error
    async def afail(**kwargs):
        raise error
    async def stream(**kwargs):
        if False:
            yield None
        raise error
    client = SimpleNamespace(models=SimpleNamespace(generate_content=fail),
                             aio=SimpleNamespace(models=SimpleNamespace(
                                 generate_content=afail, generate_content_stream=stream)))
    monkeypatch.setattr(transport, 'get_cached_llm_response', lambda *a: None)
    monkeypatch.setattr(transport, 'generation_client', lambda *a: client)
    # Observation must remain available independently of admission/circuit guards.
    monkeypatch.setattr(transport, 'provider_attempt_scope', lambda *a, **k: nullcontext())
    monkeypatch.setattr(config, 'API_KEYS', ['other-key', 'private-key'])
    monkeypatch.setattr(config, 'LLM_API_KEYS_BY_PROVIDER', {'google': ['other-key', 'private-key']})
    monkeypatch.setattr('api_usage_store.record_api_usage', lambda **e: events.append(e))
    return events, error, client


@pytest.mark.parametrize('path', ['sync', 'async', 'stream', 'stream_fallback'])
def test_all_transport_paths_preserve_quota_details_once(rig, path):
    from provider_correlation import correlation_scope
    from workflow_telemetry_attribution import node_telemetry_scope
    events, error, client = rig
    if path == 'stream_fallback':
        del client.aio.models.generate_content_stream
    with correlation_scope(replace=True, job_id='job-fixture'), node_telemetry_scope('tear_sheet', None):
        with pytest.raises(QuotaError) as raised:
            args = ('private-key', 'gemma-4-26b-a4b-it', 'private-prompt', types.GenerateContentConfig())
            if path == 'sync':
                transport.generate_content(*args)
            elif path == 'async':
                asyncio.run(transport.generate_content_async(*args))
            else:
                asyncio.run(transport.generate_content_stream_async(*args))
    assert raised.value is error
    quota = [e for e in events if e['operation'] == 'llm_provider_quota_observation']
    assert len(quota) == 1
    assert quota[0]['units'] == 0 and quota[0]['status'] == 'observed'
    meta = quota[0]['metadata']
    assert meta['provider_status_code'] == 429
    assert meta['provider_quota']['violations'] == [
        {'kind': 'input_tpm', 'limit': 16000, 'model': 'gemma-4-26b-a4b-it'}]
    assert meta['provider_quota']['retry_delay_seconds'] == 35
    assert meta['key_slot'] == 2 and meta['key_count'] == 2
    assert meta['job_id'] == 'job-fixture' and meta['node_name'] == 'tear_sheet'
    for private in ('private-key', 'private-prompt', 'private-header', 'private-project', 'private-error'):
        assert private not in json.dumps(events)


def test_observation_failure_cannot_replace_provider_error(rig, monkeypatch):
    _, error, _ = rig
    def broken(**kwargs):
        raise RuntimeError('observation unavailable')
    monkeypatch.setattr('api_usage_store.record_api_usage', broken)
    with pytest.raises(QuotaError) as raised:
        transport.generate_content('private-key', 'gemma-4-26b-a4b-it', 'prompt', None)
    assert raised.value is error


@pytest.mark.parametrize('asynchronous', [False, True])
def test_actual_summary_fallback_retains_quota_without_raw_error(rig, monkeypatch, asynchronous):
    import tear_sheet_tasks as summary
    import agent_runtime.llm_waiting as waiting
    events, _, _ = rig
    runtime_events = []
    class Rotator:
        keys = ['other-key', 'private-key']
    async def acquire_async(*args, **kwargs):
        return 'private-key'
    monkeypatch.setattr(summary, 'KeyRotator', Rotator)
    monkeypatch.setattr(summary, '_build_tear_sheet_prompt', lambda c: 'private-prompt')
    monkeypatch.setattr(summary, '_tear_sheet_model_sequence', lambda: ['gemma-4-26b-a4b-it'])
    monkeypatch.setattr(waiting, 'acquire_key', lambda *a, **k: 'private-key')
    monkeypatch.setattr(waiting, 'acquire_key_async', acquire_async)
    monkeypatch.setattr(summary, 'emit_context_event', lambda c, e, *a: runtime_events.append(e))
    async def emit_async(c, e, *args):
        runtime_events.append(e)
    monkeypatch.setattr(summary, 'emit_context_event_async', emit_async)
    context = {'pipeline_id': 'v1'}
    if asynchronous:
        asyncio.run(summary.ensure_tear_sheet_summary_async(context, Rotator()))
    else:
        summary.ensure_tear_sheet_summary(context, Rotator())
    fallback = [e for e in runtime_events if e.get('phase') == 'tear_sheet_fallback']
    assert len(fallback) == 1
    meta = fallback[0]['metadata']
    assert meta['provider_status_code'] == 429
    assert meta['provider_quota']['violations'][0]['limit'] == 16000
    assert meta['provider_quota']['retry_delay_seconds'] == 35
    assert meta['key_slot'] == 2
    assert len([e for e in events if e['operation'] == 'llm_provider_quota_observation']) == 1
    assert 'tear_sheet_summary' not in context
    assert 'private-error' not in json.dumps(runtime_events)


def test_unknown_quota_and_unregistered_key_are_not_invented(rig):
    events, error, _ = rig
    error.details = []
    error.headers = {}
    with pytest.raises(QuotaError):
        transport.generate_content('unregistered-key', 'gemma-4-26b-a4b-it', 'prompt', None)
    meta = events[0]['metadata']
    assert meta['provider_quota'] == {'violations': [], 'retry_delay_seconds': None}
    assert meta['quota_detail_status'] == 'unspecified' and 'key_slot' not in meta


def test_non_429_error_does_not_create_quota_observation(rig):
    events, error, _ = rig
    error.code = 503
    with pytest.raises(QuotaError):
        transport.generate_content('private-key', 'gemma-4-26b-a4b-it', 'prompt', None)
    assert events == []


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
@pytest.mark.parametrize('asynchronous', [False, True])
def test_alternate_provider_routes_are_observed(rig, monkeypatch, provider, asynchronous):
    events, error, _ = rig
    def fail(*args, **kwargs):
        raise error
    async def afail(*args, **kwargs):
        raise error
    monkeypatch.setattr(transport, f'generate_{provider}_content', fail)
    monkeypatch.setattr(transport, f'generate_{provider}_content_async', afail)
    with pytest.raises(QuotaError):
        args = ('unregistered-key', provider + ':fixture-model', 'prompt', None)
        if asynchronous:
            asyncio.run(transport.generate_content_async(*args))
        else:
            transport.generate_content(*args)
    assert len(events) == 1 and events[0]['provider'] == provider


def test_parallel_tasks_and_subsequent_calls_do_not_share_suppression(rig):
    events, _, _ = rig
    async def fail():
        with pytest.raises(QuotaError):
            await transport.generate_content_async('private-key', 'gemma-4-26b-a4b-it', 'prompt', None)
    async def run():
        await asyncio.gather(fail(), fail())
        await fail()
    asyncio.run(run())
    assert len(events) == 3


def test_persisted_observation_does_not_inflate_existing_usage_counts():
    import api_usage_store as usage
    # The boundary runner supplies a fresh SQLite DB; no provider is called here.
    from llm_provider_quota_observation import _record
    before = usage.summarize_llm_usage_since(0)
    _record(QuotaError('private-error'), 'unregistered-key', 'gemma-4-26b-a4b-it', 'generate_content')
    after = usage.summarize_llm_usage_since(0)
    assert after == before
    with usage._connect() as db:
        rows = db.execute("SELECT units,status,metadata_json FROM api_usage_events WHERE operation='llm_provider_quota_observation'").fetchall()
    assert len(rows) == 1 and rows[0]['units'] == 0 and rows[0]['status'] == 'observed'
    assert json.loads(rows[0]['metadata_json'])['provider_status_code'] == 429
