"""Final-only public service forwards real attempt events through job callbacks."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

import report_rerun_service as service
from agent_runtime import audit_repair, llm_calls
from data_trust import data_snapshot_filename_for_report
from runtime_events import emit_status_async
from test_final_rerun_credibility import snapshot_for


class OfflineRotator:
    keys = ['synthetic-secret-key']

    async def async_get_key(self, *args, **kwargs):
        return self.keys[0]

    def penalize(self, *args, **kwargs):
        pass


@pytest.fixture
def rerun(monkeypatch, tmp_path):
    state = SimpleNamespace(calls=[], rendered=[], contexts=[], attempts=1, short_first=False,
                            repair=False, repairing=False, cancel_provider=False,
                            provider_started=None, provider_closed=False)

    async def provider(api_key, model, agent, prompt, *, on_delta=None):
        state.calls.append((prompt, bool(on_delta)))
        if state.cancel_provider:
            state.provider_started.set()
            try:
                await asyncio.Future()
            finally:
                state.provider_closed = True
        if on_delta:
            await on_delta('chunk:' + prompt.rsplit(':', 1)[-1] + ':one')
            await asyncio.sleep(0)
            await on_delta('chunk:two')
        text = 'short' if state.short_first and len(state.calls) == 1 else 'verified output ' * 20
        return SimpleNamespace(text=text, usage_metadata=SimpleNamespace(
            prompt_token_count=100, candidates_token_count=20, total_token_count=120))

    async def call(context, rotator):
        return await llm_calls._run_agent_once_async(
            7, context, rotator, 'google:test-model', 'private-source:' + context['ticker'], timeout_seconds=2)

    # Policy behavior is covered separately; keep the real service/audit and actual
    # attempt/event/stream implementation, replacing only orchestration of fixture calls.
    async def final_agent(agent, data, context, rotator, progress_callback=None):
        state.contexts.append(context)
        await emit_status_async(progress_callback, 'fixture agent starts', phase='agent_boundary')
        for _ in range(state.attempts):
            try:
                result = await call(context, rotator)
            except llm_calls.AgentShortResponseError:
                continue
            context['analyses'][agent] = result
        return agent, context['analyses'].get(agent, '')

    async def repair(agent, data, context, rotator, issues):
        state.repairing = True
        context['analyses'][agent] = await call(context, rotator)
        return True, 'fixture repaired'

    def audit(context, append_section=True):
        critical = state.repair and not state.repairing
        return {'status': 'blocked' if critical else 'passed',
                'critical': ['fixture final repair'] if critical else [], 'warnings': [],
                'repair_agent_issues': {7: ['fixture final repair']} if critical else {}}

    async def render(**kwargs):
        state.rendered.append(kwargs['context'])
        return {'success': True}

    monkeypatch.setattr(service, 'KeyRotator', lambda *args: OfflineRotator())
    monkeypatch.setattr(service, 'run_agent_with_quality_gates_async', final_agent)
    monkeypatch.setattr(service, 'run_final_report_audit', audit)
    monkeypatch.setattr(service, 'parse_structured_data', lambda context: {})
    monkeypatch.setattr(service, 'render_and_save_rerun_report', render)
    monkeypatch.setattr(audit_repair, '_repair_agent_output_async', repair)
    monkeypatch.setattr(audit_repair, 'MAX_REPAIR_ITERATIONS', 1)
    monkeypatch.setattr(llm_calls, '_generate_content_async', provider)
    monkeypatch.setattr(llm_calls, '_generate_content_stream_async', provider)

    async def run(callback=None, *, ticker='TEST', job_id='test-job', cancel_check=None):
        filename = f'{ticker}_v1_report_20260923_210000.html'
        snapshot = snapshot_for('v1')
        snapshot['ticker'] = snapshot['data']['ticker'] = ticker
        (tmp_path / filename).write_text('<html>original</html>')
        (tmp_path / data_snapshot_filename_for_report(filename)).write_text(json.dumps(snapshot))
        return await service.rerun_report_analysis(
            filename, scope='final_recommendation', output_dir=str(tmp_path),
            pipeline_runner=object(), report_renderer=object(), progress_callback=callback,
            job_id=job_id, cancel_check=cancel_check)
    state.run = run
    return state


def phases(events):
    return [event.get('phase') for event in events]


@pytest.mark.parametrize('asynchronous', [False, True])
def test_final_service_forwards_every_attempt_once_with_anonymous_key_slot(rerun, asynchronous):
    events = []
    rerun.attempts, rerun.short_first = 3, True
    async def async_callback(event):
        await asyncio.sleep(0)
        events.append(copy.deepcopy(event))
    callback = async_callback if asynchronous else events.append
    assert asyncio.run(rerun.run(callback))['success']
    observed = phases(events)
    assert observed.count('llm_model_call') == 3
    assert observed.count('llm_provider_request') == 3
    assert observed.count('llm_model_error') == 1
    assert observed.count('llm_model_response') == 2
    assert observed.count('llm_stream_delta') == 6
    assert observed.count('agent_boundary') == 1
    assert observed[0] == 'rerun_final_agent' and observed[-1] == 'completed'
    assert len(rerun.calls) == 3 and all(stream for _, stream in rerun.calls)
    for event in events:
        if event.get('phase') in {'llm_provider_request', 'llm_model_response', 'llm_model_error', 'llm_stream_delta'}:
            assert event['metadata']['key_slot'] == 1
            assert event['metadata']['key_count'] == 1
    serialized = json.dumps(events)
    assert 'synthetic-secret-key' not in serialized and 'private-source:' not in serialized
    deltas = [event for event in events if event.get('phase') == 'llm_stream_delta']
    assert [event['metadata']['stream_sequence'] for event in deltas] == [1, 2, 1, 2, 1, 2]


def test_final_audit_repair_attempt_uses_same_callback_without_duplicate_events(rerun):
    events = []
    rerun.repair = True
    assert asyncio.run(rerun.run(events.append))['success']
    assert len(rerun.calls) == 2
    assert phases(events).count('llm_model_call') == 2
    assert phases(events).count('llm_model_response') == 2
    assert phases(events).count('llm_stream_delta') == 4
    assert len(rerun.rendered) == 1


def test_concurrent_jobs_keep_their_official_progress_scope(monkeypatch, rerun):
    import report_rerun_jobs as jobs
    records = {'job-A': [], 'job-B': []}
    monkeypatch.setattr(jobs, 'is_job_cancel_requested', lambda job: False)
    monkeypatch.setattr(jobs, 'append_event', lambda job, event: records[job].append(copy.deepcopy(event)))
    def callback(job, ticker):
        return lambda event: jobs._append_progress_event(job, f'{ticker}_v1_report_20260923_210000.html',
                                                        'final_recommendation', event)
    async def run_both():
        await asyncio.gather(rerun.run(callback('job-A', 'AAA'), ticker='AAA', job_id='job-A'),
                             rerun.run(callback('job-B', 'BBB'), ticker='BBB', job_id='job-B'))
    asyncio.run(run_both())
    for job, ticker, foreign in [('job-A', 'AAA', 'BBB'), ('job-B', 'BBB', 'AAA')]:
        assert phases(records[job]).count('llm_model_call') == 1
        deltas = [event['delta'] for event in records[job] if event.get('phase') == 'llm_stream_delta']
        assert deltas == [f'chunk:{ticker}:one', 'chunk:two']
        assert foreign not in json.dumps(records[job])
        assert all(event['rerun_scope'] == 'final_recommendation' for event in records[job])


def test_async_callback_cancellation_is_awaited_before_provider_or_render(rerun):
    events = []
    async def cancelled(event):
        events.append(event)
        await asyncio.sleep(0)
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(rerun.run(cancelled))
    assert phases(events) == ['rerun_final_agent']
    assert not rerun.calls and not rerun.rendered


def test_cancelled_provider_keeps_error_event_and_never_emits_completion(rerun):
    events = []
    async def run_cancelled():
        rerun.cancel_provider = True
        rerun.provider_started = asyncio.Event()
        task = asyncio.create_task(rerun.run(events.append))
        await rerun.provider_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run_cancelled())
    assert rerun.provider_closed and not rerun.rendered
    assert phases(events).count('llm_model_error') == 1
    assert 'completed' not in phases(events)
    error = next(event for event in events if event.get('phase') == 'llm_model_error')
    assert error['metadata']['error_category'] == 'cancelled'


def test_no_callback_preserves_single_nonstreaming_call(rerun):
    assert asyncio.run(rerun.run())['success']
    assert len(rerun.calls) == 1 and rerun.calls[0][1] is False
    assert len(rerun.rendered) == 1
