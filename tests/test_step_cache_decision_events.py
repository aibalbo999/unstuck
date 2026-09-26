"""Real lookup decisions are observable without changing cache/admission policy."""
import asyncio
import copy
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from agent_runtime import single_agent as runtime, step_cache
from llm_cache_policy import fresh_repair_candidate
from test_research_cache_assessment import assessed

SECRET = 'secret-cached-content-credential-do-not-emit'
KEY = 'agent_step:' + 'a' * 64


def entry(kind='valid_unassessed'):
    context, text = assessed(kind)
    return {'agent_num': 7, 'model_id': 'offline', 'text': text,
            'structured_output': copy.deepcopy(context['structured_outputs'][7]),
            'research_completion_receipt': copy.deepcopy(context['_research_completion_receipt']),
            'research_text_sha256': hashlib.sha256(text.encode()).hexdigest()}


@pytest.mark.parametrize('case,expected,reads', [
    ('none', ('miss', 'no_entry'), 1),
    ('disabled', ('bypass', 'disabled'), 0),
    ('repair', ('bypass', 'repair_bypass'), 0),
    ('read_error', ('error', 'read_error'), 1),
    ('invalid', ('reject', 'invalid_entry'), 1),
    ('known_failure', ('reject', 'a7_known_assessment_failure'), 1),
    ('a7_invalid', ('reject', 'a7_invalid_entry'), 1),
])
def test_public_lookup_reports_only_bounded_reason_without_extra_reads(monkeypatch, case, expected, reads):
    value = None
    if case == 'invalid':
        value = {'text': '', 'private': SECRET}
    elif case == 'known_failure':
        value = entry('wrong_role')
        value['structured_output']['assumption_reconciliation_assessment']['issues'] = [SECRET]
        value['text'] = SECRET
    elif case == 'a7_invalid':
        value = entry()
        value['structured_output']['assumption_reconciliation_assessment']['issues'] = {SECRET: True}
    called = []
    def read(key):
        called.append(key)
        if case == 'read_error':
            raise RuntimeError(SECRET)
        return value
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', case != 'disabled')
    monkeypatch.setattr(step_cache, 'get_cache_json', read)
    observation = {}
    counters = {}
    if case == 'repair':
        with fresh_repair_candidate(counters):
            result = step_cache.get_cached_agent_step(KEY, observation)
        assert counters['step_cache_reads_skipped'] == 1
    else:
        result = step_cache.get_cached_agent_step(KEY, observation)
    assert result is None
    assert observation == {'decision': expected[0], 'reason': expected[1]}
    assert len(called) == reads
    assert SECRET not in json.dumps(observation)


def configure_runner(monkeypatch, case, callback=None):
    state = {'data': {'ticker': '6488.TWO'}, 'pipeline_id': 'v1', 'analyses': {}, 'structured_outputs': {}}
    calls = []; reads = []; events = []
    value = entry('wrong_role') if case == 'known_failure' else entry() if case in {'hit', 'manifest'} else None
    if case == 'known_failure':
        value['structured_output']['assumption_reconciliation_assessment']['issues'] = [SECRET]
        value['text'] = SECRET
    if case == 'manifest':
        from market_context_manifest import CONTRACT_VERSION
        state['market_context_contract_version'] = CONTRACT_VERSION
        value['market_context_manifest'] = {'private': SECRET}
    if case == 'repair':
        state['_audit_retry_instruction'] = 'Generate a fresh repair.'
    def read(key):
        reads.append(key)
        if case == 'read_error':
            raise RuntimeError(SECRET)
        return value
    def event(event):
        events.append(copy.deepcopy(event))
        if callback:
            return callback(event)
    state['_runtime_event_callback'] = event
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', case != 'disabled')
    monkeypatch.setattr(step_cache, 'get_cache_json', read)
    monkeypatch.setattr(step_cache, 'set_cache_json', lambda *args: None)
    monkeypatch.setattr(runtime, 'get_runtime_model_sequence', lambda *args: ['offline'])
    monkeypatch.setattr(runtime, 'unavailable_model', lambda *args: None)
    monkeypatch.setattr(runtime, '_build_model_prompt', lambda *args: 'private prompt ' + SECRET)
    monkeypatch.setattr(runtime, 'model_key_count', lambda *args: 1)
    monkeypatch.setattr(runtime, 'record_model_success', lambda *args: None)
    monkeypatch.setattr(runtime, 'adopt_market_context_result', lambda context, agent, data, prompt, text: text)
    def admit(*args, **kwargs):
        calls.append('admission')
        assert any(e['phase'] == 'agent_step_cache_decision' for e in events)
        return SimpleNamespace(call_provider=case != 'denied', evidence_notes='', last_error='denied')
    async def aadmit(*args, **kwargs):
        return admit(*args, **kwargs)
    def provider(*args, **kwargs):
        calls.append('provider')
        return 'fresh response'
    async def aprovider(*args, **kwargs):
        return provider(*args, **kwargs)
    monkeypatch.setattr(runtime, 'admit_model_input_sync', admit)
    monkeypatch.setattr(runtime, 'admit_model_input_async', aadmit)
    monkeypatch.setattr(runtime, '_run_agent_once', provider)
    monkeypatch.setattr(runtime, '_run_agent_once_async', aprovider)
    monkeypatch.setattr(runtime, 'failed_route_result', lambda *args: 'denied')
    return state, calls, reads, events


def invoke(mode, state):
    async def run():
        if mode == 'sync':
            # A synchronous call inside a live event loop takes the real sync branch.
            return runtime.run_single_agent(7, state['data'], state, None)
        return await runtime.run_single_agent_async(7, state['data'], state, None)
    return asyncio.run(run())


@pytest.mark.parametrize('mode', ['sync', 'async'])
@pytest.mark.parametrize('case,reason', [
    ('none', 'no_entry'), ('repair', 'repair_bypass'), ('disabled', 'disabled'),
    ('read_error', 'read_error'), ('known_failure', 'a7_known_assessment_failure'),
    ('manifest', 'context_contract_mismatch'), ('denied', 'no_entry'),
])
def test_routed_miss_event_precedes_admission_and_never_becomes_a_provider_call(monkeypatch, mode, case, reason):
    state, calls, reads, events = configure_runner(monkeypatch, case)
    expected_key = runtime.build_agent_step_cache_key(7, state['data'], state, 'offline', 'private prompt ' + SECRET)
    assert invoke(mode, state) == ('denied' if case == 'denied' else 'fresh response')
    decisions = [event for event in events if event['phase'] == 'agent_step_cache_decision']
    assert len(decisions) == 1
    metadata = decisions[0]['metadata']
    assert metadata['cache_key'] == expected_key
    assert metadata['reason'] == reason
    assert set(metadata) == {'model_id', 'cache_key', 'decision', 'reason'}
    assert SECRET not in json.dumps(decisions)
    assert calls == (['admission'] if case == 'denied' else ['admission', 'provider'])
    assert len(reads) == (0 if case in {'repair', 'disabled'} else 1)
    assert state.get('agent_step_cache', {}).get('misses', 0) == (0 if case == 'denied' else 1)
    if case == 'repair':
        assert state['repair_candidate_history']['7']['step_cache_reads_skipped'] == 1


@pytest.mark.parametrize('mode', ['sync', 'async'])
def test_hit_keeps_existing_event_and_bypasses_provider(monkeypatch, mode):
    state, calls, reads, events = configure_runner(monkeypatch, 'hit')
    assert invoke(mode, state) == entry()['text']
    assert calls == [] and len(reads) == 1
    assert [event['phase'] for event in events] == ['agent_step_cache_hit']
    assert events[0]['metadata']['cache_hit'] is True
    assert state['agent_step_cache']['hits'] == 1


@pytest.mark.parametrize('mode', ['sync', 'async'])
def test_ordinary_decision_telemetry_failure_cannot_block_provider(monkeypatch, mode):
    def fail(event):
        if event['phase'] == 'agent_step_cache_decision':
            raise RuntimeError(SECRET)
    state, calls, reads, events = configure_runner(monkeypatch, 'none', fail)
    assert invoke(mode, state) == 'fresh response'
    assert calls == ['admission', 'provider'] and len(reads) == 1
    assert SECRET not in json.dumps(state['_runtime_events'])


@pytest.mark.parametrize('mode', ['sync', 'async'])
@pytest.mark.parametrize('kind', ['async_cancel', 'job_cancel', 'rerun_cancel', 'admission_cancel'])
def test_decision_telemetry_cancellation_is_not_swallowed(monkeypatch, mode, kind):
    from analysis_jobs import AnalysisJobCancelled
    from report_rerun_jobs import ReportRerunJobCancelled
    from llm_key_admission import KeyAdmissionCancelled
    errors = {'async_cancel': asyncio.CancelledError(), 'job_cancel': AnalysisJobCancelled('cancelled'),
              'rerun_cancel': ReportRerunJobCancelled('cancelled'),
              'admission_cancel': KeyAdmissionCancelled(AnalysisJobCancelled('cancelled'))}
    error = errors[kind]
    def cancel(event):
        if event['phase'] == 'agent_step_cache_decision':
            raise error
    state, calls, reads, events = configure_runner(monkeypatch, 'none', cancel)
    expected_error = type(error.original) if kind == 'admission_cancel' else type(error)
    with pytest.raises(expected_error):
        invoke(mode, state)
    assert calls == [] and len(reads) == 1


def test_event_survives_real_progress_adapter_and_sqlite_persistence(monkeypatch, tmp_path):
    from analysis_job_progress import make_pipeline_progress_callback
    path = tmp_path / 'events.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE events (payload TEXT)')
    def append(job_id, event):
        with sqlite3.connect(path) as db:
            db.execute('INSERT INTO events VALUES (?)', (json.dumps(event),))
    callback = make_pipeline_progress_callback(job_id='offline', pipeline_def={'short_label': 'A', 'label': 'A'},
        current_pipeline_id='v1', sequence_total=1, total_agents=1, completed_agent_offset=0,
        agent_count=1, cancel_check=lambda: None, append_event_func=append)
    state, calls, reads, events = configure_runner(monkeypatch, 'none', callback)
    invoke('async', state)
    with sqlite3.connect(path) as db:
        saved = [json.loads(row[0]) for row in db.execute('SELECT payload FROM events')]
    assert saved[0]['phase'] == 'agent_step_cache_decision'
    assert saved[0]['metadata'] == events[0]['metadata']
    assert saved[0]['metadata']['reason'] == 'no_entry'


@pytest.mark.parametrize('mode', ['sync', 'async'])
def test_callback_failure_rechecks_cooperative_cancellation(monkeypatch, mode):
    class CooperativeCancellation(Exception):
        pass
    cancelled = []
    def callback(event):
        if event['phase'] == 'agent_step_cache_decision':
            cancelled.append(True)
            raise RuntimeError(SECRET)
    def cancel_check():
        if cancelled:
            raise CooperativeCancellation()
    state, calls, reads, events = configure_runner(monkeypatch, 'none', callback)
    state['_cancel_check'] = cancel_check
    with pytest.raises(CooperativeCancellation):
        invoke(mode, state)
    assert calls == []


def test_decision_emitter_uses_only_fixed_enums_and_opaque_cache_key():
    from agent_runtime.single_agent_events import emit_sync_cache_decision
    state = {}
    emit_sync_cache_decision(state, 7, 'offline', KEY,
        {'decision': 'miss', 'reason': 'no_entry', 'raw_text': SECRET, 'issues': [SECRET]})
    assert state['_runtime_events'][0]['metadata'] == {
        'model_id': 'offline', 'cache_key': KEY, 'decision': 'miss', 'reason': 'no_entry'}
    emit_sync_cache_decision(state, 7, 'offline', SECRET, {'decision': 'miss', 'reason': 'no_entry'})
    emit_sync_cache_decision(state, 7, 'offline', KEY, {'decision': 'miss', 'reason': SECRET})
    assert len(state['_runtime_events']) == 1
    assert SECRET not in json.dumps(state)
