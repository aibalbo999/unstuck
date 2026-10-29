"""IDs and monotonic intervals are diagnostic, isolated across concurrent roles."""
import asyncio
import json
from types import SimpleNamespace

import pytest


def test_retries_and_fallback_share_logical_id_with_distinct_attempts(monkeypatch):
    import llm_observation_context as obs
    events, calls = [], []
    monkeypatch.setattr('api_usage_store.record_api_usage', lambda **event: events.append(event))

    @obs.observe_attempt
    def call(agent_num, context, rotator, model_id, prompt):
        calls.append(obs.current_fields())
        return 'same-result'

    @obs.observe_agent
    def run(agent_num, data, context, rotator):
        for model in ('gemini-a', 'gemini-a', 'gemini-b'):
            assert call(agent_num, context, rotator, model, 'private-prompt') == 'same-result'
    run(22, {}, {'pipeline_id':'v4'}, None)
    assert len({c['logical_call_id'] for c in calls}) == 1
    assert len({c['attempt_id'] for c in calls}) == 3
    assert [c['attempt_number'] for c in calls] == [1,2,3]
    assert obs.current_fields() == {}
    assert 'private-prompt' not in json.dumps(events)


def test_wait_observation_records_actual_duration_and_original_exception(monkeypatch):
    import llm_observation_context as obs
    now, events = [100.0], []
    monkeypatch.setattr(obs.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr('api_usage_store.record_api_usage', lambda **event: events.append(event))
    error = RuntimeError('private-error')
    with pytest.raises(RuntimeError) as caught:
        with obs.wait_scope('key_admission', model='gemini-a', planned_seconds=390):
            now[0] += 2.5
            raise error
    assert caught.value is error
    event = events[-1]
    assert event['units'] == 0
    assert event['metadata']['elapsed_seconds'] == 2.5
    assert event['metadata']['planned_seconds'] == 390
    assert event['metadata']['outcome'] == 'interrupted'
    assert 'private-error' not in json.dumps(events)


def test_concurrent_agents_and_transport_ids_are_isolated(monkeypatch):
    import llm_observation_context as obs
    events=[]
    monkeypatch.setattr('api_usage_store.record_api_usage', lambda **event: events.append(event))
    @obs.observe_agent
    async def run(agent_num, data, context, rotator):
        with obs.attempt_scope('gemini-a', 'analysis'):
            with obs.transport_scope('gemini-a', 'private-key', 'generate_content') as span:
                await asyncio.sleep(0)
                span.response = SimpleNamespace(usage_metadata=SimpleNamespace(prompt_token_count=12))
    async def all_roles():
        await asyncio.gather(run(22,{}, {},None),run(23,{}, {},None))
    asyncio.run(all_roles())
    completed=[e['metadata'] for e in events if e['operation']=='llm_transport_observation' and e['status']=='success']
    assert len(completed)==2
    assert len({e['logical_call_id'] for e in completed})==2
    assert {e['agent_num'] for e in completed}=={22,23}
    assert all(e['input_tokens']==12 for e in completed)
    assert 'private-key' not in json.dumps(events)


def test_telemetry_failure_preserves_result_and_tracks_gap(monkeypatch):
    import llm_observation_context as obs
    def broken(**kwargs):raise RuntimeError('private-ledger-error')
    monkeypatch.setattr('api_usage_store.record_api_usage', broken)
    before=obs.telemetry_health()['dropped_events']
    with obs.transport_scope('gemini-a','private-key','generate_content') as span:
        span.response=SimpleNamespace()
    assert obs.telemetry_health()['dropped_events']==before+2


def test_retry_wait_after_attempt_unwinds_retains_failed_attempt(monkeypatch):
    import llm_observation_context as obs
    events=[]
    monkeypatch.setattr('api_usage_store.record_api_usage',lambda **event:events.append(event))
    monkeypatch.setattr(obs.time,'sleep',lambda _:None)
    with obs.logical_scope(22,'v4'):
        with obs.attempt_scope('gemini-a','analysis'):
            failed=obs.current_fields()
        obs.observed_sleep(2)
    event=events[-1]
    assert event['model_id']=='gemini-a'
    assert event['metadata']['attempt_id']==failed['attempt_id']
    assert event['metadata']['attempt_number']==1


def test_parallel_transports_in_one_attempt_keep_distinct_ids_and_keys(monkeypatch):
    import llm_observation_context as obs
    events=[]
    monkeypatch.setattr('api_usage_store.record_api_usage',lambda **event:events.append(event))
    async def send(key):
        with obs.transport_scope('gemini-a',key,'generate_content_async') as span:
            await asyncio.sleep(0)
            span.response=SimpleNamespace()
    async def run():
        with obs.attempt_scope('gemini-a','analysis'):
            await asyncio.gather(send('first-private-key'),send('second-private-key'))
    asyncio.run(run())
    starts={e['metadata']['transport_attempt_id']:e['metadata']['key_ref'] for e in events if e['status']=='attempt'}
    ends={e['metadata']['transport_attempt_id']:e['metadata']['key_ref'] for e in events if e['status']=='success'}
    assert len(starts)==len(ends)==2 and starts==ends
