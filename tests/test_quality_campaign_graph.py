"""Offline graph/SDK/artifact boundaries; no provider or formal publication."""
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

DEV = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEV / 'backend'))


@pytest.fixture(autouse=True)
def isolated_runtime_identity(monkeypatch):
    # Do not ask this unit/integration lane to run Git provenance commands.
    monkeypatch.setenv('GIT_COMMIT', 'offline-campaign-fixture')
    monkeypatch.setenv('GIT_DIRTY', 'false')
    monkeypatch.setenv('AGENT_STEP_CACHE_ENABLED', 'false')
    monkeypatch.setenv('LLM_SEMANTIC_CACHE_ENABLED', 'false')


def test_frozen_services_disable_only_external_prepare_and_repair():
    from workflow_services import create_default_workflow_services
    from quality_campaign_graph import frozen_services
    original = create_default_workflow_services(rotator=object())
    frozen = frozen_services(original)
    assert frozen.prepare is not original.prepare, 'Original RAG preparation must not run against frozen input'
    assert frozen.repair is not original.repair
    for field in ('initialize', 'validate', 'run_agent', 'final_audit', 'chief_editor', 'tear_sheet', 'persist_report'):
        assert getattr(frozen, field) is getattr(original, field)
    state = {'input_data': {'ticker': 'TEST'}, 'circuit_breaker': {'status': 'open'}}
    assert asyncio.run(frozen.prepare(state))['rag_status']['status'] == 'unavailable'
    repair = asyncio.run(frozen.repair(state))
    assert 'input_data' not in repair and 'circuit_breaker' not in repair


MODEL = 'gemini-3.6-flash'
KEY = 'offline-secret-key'
IDENTITY = {'campaign_id': 'graph-fixture', 'code_sha256': 'a' * 64,
            'source_sha256': 'b' * 64, 'route_sha256': 'c' * 64}
HASHES = {key: value for key, value in IDENTITY.items() if key != 'campaign_id'}
POLICY = {'billing_status': 'verified_paid', 'billing_identity_sha256': 'd' * 64,
          'reservation_basis_sha256': 'e' * 64, 'maximum_total_tokens': 512,
          'maximum_output_tokens': 64, 'maximum_request_bytes': 200000,
          'maximum_microusd_per_million_tokens': 1000000}


def setup_job(tmp_path, monkeypatch, *, clock=None):
    import config, llm_client, llm_semantic_cache
    from quality_campaign_budget import CampaignBudget
    from quality_campaign_transport import CampaignTransport
    from agent_runtime import routing
    monkeypatch.setattr(config, 'LLM_API_KEYS_BY_PROVIDER', {'google': [KEY]})
    monkeypatch.setattr(config, 'GEMMA_EVIDENCE_BATCHING_ENABLED', False)
    monkeypatch.setattr(config, 'AGENT_STEP_CACHE_ENABLED', False)
    monkeypatch.setattr(config, 'LLM_SEMANTIC_CACHE_ENABLED', False)
    monkeypatch.setattr(llm_semantic_cache, 'LLM_SEMANTIC_CACHE_ENABLED', False)
    monkeypatch.setattr(routing, 'get_agent_model_sequence', lambda agent: [MODEL])
    monkeypatch.setattr(routing, 'get_audit_model_sequence', lambda: [MODEL])
    pings = []
    limiter = SimpleNamespace(_client=SimpleNamespace(ping=lambda: pings.append('ping') or True))
    monkeypatch.setattr(llm_client, 'KeyRotator', lambda keys: SimpleNamespace(_shared_limiter=limiter))
    output = tmp_path / 'job-output'
    output.mkdir(mode=0o700)
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', IDENTITY, clock=clock)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    ledger.reserve_job('job', 'batch')
    transport = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                                  verify_frozen=lambda: HASHES, secrets=(KEY,))
    return ledger, transport, output, limiter, pings


def source_job(*, conflict=False):
    data = {'ticker': 'TEST', 'market': 'US', 'company_name': 'Offline Company'}
    if conflict:
        data['financial_metric_validation'] = {'comparisons': {'total_debt': {
            'source_a_value': 100, 'source_b_value': 300, 'source_a': 'one', 'source_b': 'two'}}}
    return {'pipeline_id': 'v4', 'data_snapshot': data, 'analyses': {'22': 'OLD OUTPUT NOT ADOPTED'}}


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3', 'v4'])
def test_real_graph_validator_blocks_conflicting_frozen_data_without_provider(tmp_path, mode):
    from quality_campaign_graph import frozen_services, execute_graph
    from quality_campaign_safety import Evidence
    from workflow_services import create_default_workflow_services, initialize_graph_state
    from workflow_context import input_data_from_state
    data = source_job(conflict=True)['data_snapshot']
    initial = initialize_graph_state(data, pipeline_id=mode)
    services = frozen_services(create_default_workflow_services(rotator=object()))
    result = asyncio.run(execute_graph(initial, services, mode, tmp_path, 'offline', 10, evidence=Evidence(tmp_path)))
    assert result['status'] == 'blocked' and input_data_from_state(result) == data
    assert (tmp_path / 'checkpoint-state.json').is_file()
    assert not list(tmp_path.rglob('*.html'))


def install_mock_http(monkeypatch, handler):
    import httpx, llm_transport
    from google.genai import types
    assert not llm_transport._client_cache
    mock = httpx.MockTransport(handler)
    monkeypatch.setattr(llm_transport, '_genai_http_options', lambda: types.HttpOptions(
        client_args={'transport': mock}, async_client_args={'transport': mock}))


def response_payload(text='公開回答'):
    return {'modelVersion': 'returned-model-v1',
        'candidates': [{'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [
            {'thought': True, 'text': 'PRIVATE_THOUGHT_MUST_NOT_BE_RECORDED'}, {'text': text}]}}],
        'usageMetadata': {'promptTokenCount': 5, 'candidatesTokenCount': 2, 'thoughtsTokenCount': 5,
                          'cachedContentTokenCount': 3, 'totalTokenCount': 12}}


@pytest.mark.parametrize('kind', ['sync', 'async', 'stream'])
def test_true_sdk_httpx_calls_capture_public_text_usage_and_restore_all_patches(tmp_path, monkeypatch, kind):
    import httpx, llm_transport
    from google.genai import types, _api_client
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    requests, deltas, verified = [], [], []
    def handler(request):
        requests.append(request)
        payload = response_payload('公開回答 ' + KEY)
        if kind == 'stream':
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                stream=httpx.ByteStream(('data: ' + json.dumps(payload) + '\n\n').encode()))
        return httpx.Response(200, json=payload)
    install_mock_http(monkeypatch, handler)
    owners = [(httpx.Client, 'send'), (httpx.AsyncClient, 'send'),
              (_api_client.BaseApiClient, '_use_aiohttp'), (transport, 'before_send'), (transport, 'evidence')]
    owners += [(llm_transport, name) for name in ('_genai_http_options', 'generate_content', 'generate_content_async',
                                                 'generate_content_stream_async', 'embed_content', 'embed_content_async')]
    before = [(owner, name, getattr(owner, name)) for owner, name in owners]
    async def invoke():
        with transport:
            async with sdk_context(transport, Evidence(output, (KEY,)), StrictSharedQuota(limiter),
                                   lambda: verified.append('frozen') or HASHES) as recorder:
                options = llm_transport._genai_http_options()
                assert options.retry_options.attempts == 1
                for kwargs in (options.client_args, options.async_client_args):
                    assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
                assert _api_client.BaseApiClient._use_aiohttp(None) is False
                with pytest.raises(ReplayAbort, match='embeddings'):
                    llm_transport.embed_content(KEY, MODEL, 'frozen', None)
                config = types.GenerateContentConfig(max_output_tokens=64)
                if kind == 'sync': response = llm_transport.generate_content(KEY, MODEL, 'frozen input', config)
                elif kind == 'async': response = await llm_transport.generate_content_async(KEY, MODEL, 'frozen input', config)
                else: response = await llm_transport.generate_content_stream_async(KEY, MODEL, 'frozen input', config, on_delta=deltas.append)
                assert llm_transport.response_text(response) == '公開回答 ' + KEY
                assert len(recorder.rows) == 1 and recorder.rows[0]['completed_response'] is True
                assert recorder.rows[0]['diagnostics']['usage']['total_tokens'] == 12
                # Current main's public diagnostics normalize three fields;
                # explicit provider reasoning usage remains on the raw wire.
                assert next(iter(transport.http_rows.values()))['usage']['reasoning_tokens'] == 5
    asyncio.run(invoke())
    assert len(requests) == 1 and verified == ['frozen']
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'transport': 1, 'http': 1, 'tokens': 12, 'cost_microusd': 12}
    for owner, name, original in before: assert getattr(owner, name) == original
    assert not llm_transport._client_cache
    evidence = '\n'.join(path.read_text() for path in output.glob('*.jsonl'))
    assert KEY not in evidence and 'PRIVATE_THOUGHT_MUST_NOT_BE_RECORDED' not in evidence
    assert '公開回答' in evidence and 'reasoning_tokens' in evidence
    if kind == 'stream': assert deltas == ['公開回答 ' + KEY]


def test_run_graph_job_uses_real_blocked_graph_and_sanitized_private_outcome(tmp_path, monkeypatch):
    from quality_campaign_graph import run_graph_job
    ledger, transport, output, limiter, pings = setup_job(tmp_path, monkeypatch)
    result = asyncio.run(run_graph_job(dev=DEV, source_job=source_job(conflict=True), output=output,
        job_id='job', mode='v4', ledger=ledger, transport=transport, check_frozen=lambda: HASHES, secrets=(KEY,)))
    assert result['status'] == 'blocked', result
    assert result['job_id'] == 'job' and result['mode'] == 'v4'
    assert result['formal_publication'] is False and result['qualified_for_campaign'] is False
    assert json.loads((output / 'outcome.json').read_text()) == result
    graph = json.loads((output / 'graph-result.json').read_text())
    assert graph['analyses'] == {} and 'OLD OUTPUT NOT ADOPTED' not in json.dumps(graph)
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'
    assert ledger.snapshot()['spent']['http'] == 0 and pings == ['ping']
    assert transport._restore is None


def test_real_graph_with_controlled_agent_true_sdk_then_final_audit_blocks_publication(tmp_path, monkeypatch):
    import httpx, llm_transport, workflow_services
    from google.genai import types
    from quality_campaign_graph import run_graph_job
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    calls = []
    install_mock_http(monkeypatch, lambda request: calls.append(request) or httpx.Response(200, json=response_payload()))
    factory = workflow_services.create_default_workflow_services
    async def diagnostic_agent(agent, state):
        if agent == 22:
            response = await llm_transport.generate_content_async(KEY, MODEL, 'frozen diagnostic', types.GenerateContentConfig(max_output_tokens=64))
            return {'analyses': {str(agent): llm_transport.response_text(response)}}
        return {'analyses': {str(agent): 'offline diagnostic fixture'}}
    async def blocking_audit(state):
        return {'status': 'blocked', 'blocking_issues': ['offline_diagnostic_not_qualified']}
    def controlled_services(**kwargs):
        return replace(factory(**kwargs), run_agent=diagnostic_agent, final_audit=blocking_audit)
    monkeypatch.setattr(workflow_services, 'create_default_workflow_services', controlled_services)
    result = asyncio.run(run_graph_job(dev=DEV, source_job=source_job(), output=output, job_id='job', mode='v4',
        ledger=ledger, transport=transport, check_frozen=lambda: HASHES, secrets=(KEY,)))
    assert result['status'] == 'blocked', result
    assert len(calls) == 1 and ledger.snapshot()['spent']['http'] == 1
    assert (output / 'checkpoint-state.json').is_file() and (output / 'raw.jsonl').is_file()
    assert not list(output.rglob('*.html'))
    assert all(row['status'] == 'completed' for row in result['provider_transport_calls'])
    assert result['qualified_for_campaign'] is False


def test_real_renderer_generation_gate_rejects_done_label_without_contracts(tmp_path):
    from quality_campaign_graph import render_and_persist
    from report_publication_gate import ReportPublicationBlockedError
    context = {'pipeline_id': 'v4', 'data': {'ticker': 'TEST'}, 'analyses': {}, 'status': 'done',
               'numeric_claim_contract_version': 1, 'decision_contract_version': 1}
    with pytest.raises(ReportPublicationBlockedError):
        asyncio.run(render_and_persist(context, 'v4', tmp_path, 'blocked.html', lambda: None))
    assert not list(tmp_path.rglob('*.html'))


def test_configured_key_is_redacted_from_source_copy_even_when_secrets_argument_is_empty(tmp_path, monkeypatch):
    from quality_campaign_graph import run_graph_job
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    source = source_job(conflict=True)
    source['data_snapshot']['offline_note'] = KEY
    result = asyncio.run(run_graph_job(dev=DEV, source_job=source, output=output, job_id='job', mode='v4',
        ledger=ledger, transport=transport, check_frozen=lambda: HASHES))
    assert result['status'] == 'blocked'
    assert KEY not in (output / 'source-copy.json').read_text()


def test_evidence_secret_cannot_reach_http_when_transport_secrets_were_empty(tmp_path, monkeypatch):
    import httpx, llm_transport
    from google.genai import types
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    transport.secrets = ()
    calls = []
    install_mock_http(monkeypatch, lambda request: calls.append(request) or httpx.Response(200, json=response_payload()))
    async def invoke():
        with transport:
            async with sdk_context(transport, Evidence(output, (KEY,)), StrictSharedQuota(limiter), lambda: HASHES):
                with pytest.raises(ReplayAbort, match='Credential'):
                    await llm_transport.generate_content_async(KEY, MODEL, 'untrusted source contains ' + KEY,
                        types.GenerateContentConfig(max_output_tokens=64))
    asyncio.run(invoke())
    assert calls == [] and transport.secrets == ()


@pytest.mark.parametrize('failure', ['quota', 'frozen'])
def test_every_physical_send_rechecks_quota_and_frozen_binding(tmp_path, monkeypatch, failure):
    import httpx, llm_transport
    from google.genai import types
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    calls = []
    install_mock_http(monkeypatch, lambda request: calls.append(request) or httpx.Response(200, json=response_payload()))
    def check(): return HASHES | {'source_sha256': '0' * 64} if failure == 'frozen' else HASHES
    async def invoke():
        with transport:
            async with sdk_context(transport, Evidence(output, (KEY,)), StrictSharedQuota(limiter), check):
                if failure == 'quota': limiter._client = None
                with pytest.raises(ReplayAbort):
                    await llm_transport.generate_content_async(KEY, MODEL, 'frozen input', types.GenerateContentConfig(max_output_tokens=64))
    asyncio.run(invoke())
    assert calls == []
    assert ledger.snapshot()['spent']['http'] == 1, 'A reserved but denied physical send is never refunded'
    assert ledger.snapshot()['spent']['tokens'] == 512


def test_true_sdk_stream_cancellation_keeps_public_delta_and_partial_usage(tmp_path, monkeypatch):
    import httpx, llm_transport
    from google.genai import types
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    payload = response_payload('partial public text')
    del payload['candidates'][0]['finishReason']
    class Interrupted(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield ('data: ' + json.dumps(payload) + '\n\n').encode()
            raise asyncio.CancelledError()
    install_mock_http(monkeypatch, lambda request: httpx.Response(200,
        headers={'content-type': 'text/event-stream'}, stream=Interrupted()))
    async def invoke():
        with transport:
            async with sdk_context(transport, Evidence(output, (KEY,)), StrictSharedQuota(limiter), lambda: HASHES) as recorder:
                with pytest.raises(asyncio.CancelledError):
                    await llm_transport.generate_content_stream_async(KEY, MODEL, 'frozen', types.GenerateContentConfig(max_output_tokens=64))
                assert recorder.rows[0]['status'] == 'interrupted'
                assert recorder.rows[0]['completed_response'] is False
                assert recorder.rows[0]['diagnostics']['usage']['total_tokens'] == 12
                assert next(iter(transport.http_rows.values()))['usage']['reasoning_tokens'] == 5
    asyncio.run(invoke())
    raw = (output / 'raw.jsonl').read_text()
    assert 'partial public text' in raw and 'completed_public_text' not in raw
    assert ledger.snapshot()['spent']['tokens'] == 512
    assert transport._restore is None and not llm_transport._client_cache


def test_real_persistence_and_exact_readback_of_explicit_synthetic_render_bundle(tmp_path, monkeypatch):
    from quality_campaign_graph import render_and_persist
    import reporting.renderer
    bundle = SimpleNamespace(html='<h1>Offline I/O fixture</h1>', markdown='# Offline I/O fixture',
                             data_snapshot={'ticker': 'TEST', 'pipeline_id': 'v4'})
    class FixtureRenderer:
        async def render_async(self, request): return bundle
    monkeypatch.setattr(reporting.renderer, 'ReportRenderer', FixtureRenderer)
    checked = []
    persisted, returned, artifacts = asyncio.run(render_and_persist({}, 'v4', tmp_path, 'fixture.html', lambda: checked.append(True)))
    assert returned is bundle and len(checked) == 4
    assert set(artifacts) == {'html_key', 'md_key', 'data_key'}
    for field, receipt in artifacts.items():
        content = (tmp_path / 'reports' / persisted[field]).read_bytes()
        assert len(content) == receipt['bytes']
    assert json.loads((tmp_path / 'reports' / persisted['data_key']).read_text())['ticker'] == 'TEST'


def test_artifact_mismatch_or_deadline_after_persist_is_not_accepted(tmp_path, monkeypatch):
    from quality_campaign_graph import render_and_persist
    from quality_campaign_safety import ReplayAbort
    import reporting.renderer
    class FixtureRenderer:
        async def render_async(self, request):
            return SimpleNamespace(html='<h1>Original</h1>', markdown='# Original', data_snapshot={'ticker': 'TEST'})
    monkeypatch.setattr(reporting.renderer, 'ReportRenderer', FixtureRenderer)
    count = []
    def check():
        count.append(True)
        if len(count) == 3:
            next(path for path in (tmp_path / 'reports').rglob('*.html') if path.is_file()).write_text('different private bytes')
    with pytest.raises(ReplayAbort, match='readback'):
        asyncio.run(render_and_persist({}, 'v4', tmp_path, 'fixture.html', check))


def test_existing_sdk_clients_are_not_adopted_or_closed(tmp_path, monkeypatch):
    import llm_transport
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    closed = []
    existing = {'existing-key': SimpleNamespace(close=lambda: closed.append(True))}
    monkeypatch.setattr(llm_transport, '_client_cache', existing)
    async def invoke():
        with transport:
            with pytest.raises(ReplayAbort, match='Fresh SDK'):
                async with sdk_context(transport, Evidence(output), StrictSharedQuota(limiter), lambda: HASHES):
                    pytest.fail('Old clients cannot enter SDK context')
    asyncio.run(invoke())
    assert llm_transport._client_cache is existing and not closed


def test_graph_hard_stop_keeps_real_checkpoint_and_no_report_done(tmp_path, monkeypatch):
    import workflow_services
    from quality_campaign_graph import run_graph_job
    from quality_campaign_safety import ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    original = workflow_services.create_default_workflow_services
    async def stopped(agent, state): raise ReplayAbort('offline hard boundary')
    monkeypatch.setattr(workflow_services, 'create_default_workflow_services',
                        lambda **kwargs: replace(original(**kwargs), run_agent=stopped))
    result = asyncio.run(run_graph_job(dev=DEV, source_job=source_job(), output=output, job_id='job', mode='v4',
        ledger=ledger, transport=transport, check_frozen=lambda: HASHES, secrets=(KEY,)))
    assert result['status'] == 'partial' and result['failure']['error_type'] == 'ReplayAbort'
    assert (output / 'checkpoint-state.json').is_file()
    assert not list(output.rglob('*.html'))
    assert 'report_done' not in (output / 'events.jsonl').read_text()
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'


@pytest.mark.parametrize('kind', ['sync', 'async', 'stream'])
def test_original_call_stop_survives_secondary_evidence_failure(tmp_path, kind):
    from contextvars import ContextVar
    from quality_campaign_graph import _PublicCalls
    from quality_campaign_safety import Evidence, ReplayAbort
    evidence = Evidence(tmp_path, maximum_bytes=4096)
    transport = SimpleNamespace(active=ContextVar('reserved', default={'id': 'attempt', 'model': MODEL}),
                                check_stream=lambda: None)
    recorder, primary = _PublicCalls(transport, evidence), ReplayAbort('original frozen stop')
    def stop(*args, **kwargs):
        evidence.maximum_bytes = evidence.written
        raise primary
    async def stop_async(*args, **kwargs): return stop()
    with pytest.raises(ReplayAbort) as caught:
        if kind == 'sync': recorder.wrap_sync(stop)(None, MODEL, 'frozen', None)
        else: asyncio.run(recorder.wrap_async(stop_async, stream=kind == 'stream')(None, MODEL, 'frozen', None))
    assert caught.value is primary and recorder.active.get() is None
    assert recorder.rows[0]['error_type'] == 'ReplayAbort'


def test_original_graph_stop_survives_checkpoint_evidence_failure(tmp_path):
    from quality_campaign_graph import execute_graph, frozen_services
    from quality_campaign_safety import Evidence, ReplayAbort
    from workflow_services import create_default_workflow_services, initialize_graph_state
    primary = ReplayAbort('original graph boundary')
    async def stop(agent, state): raise primary
    services = frozen_services(replace(create_default_workflow_services(rotator=object()), run_agent=stop))
    initial = initialize_graph_state(source_job()['data_snapshot'], pipeline_id='v4')
    with pytest.raises(ReplayAbort) as caught:
        asyncio.run(execute_graph(initial, services, 'v4', tmp_path, 'job', 10,
                                  evidence=Evidence(tmp_path, maximum_bytes=1)))
    assert caught.value is primary


def test_original_sdk_stop_survives_cleanup_failure_with_hooks_restored(tmp_path, monkeypatch):
    import llm_transport
    from google.genai import _api_client
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    primary = ReplayAbort('original campaign deadline')
    async def failed_close(): raise RuntimeError('offline close failure')
    monkeypatch.setattr(llm_transport, 'close_cached_clients_async', failed_close)
    old_send, old_call, old_stack = transport.before_send, llm_transport.generate_content, _api_client.BaseApiClient._use_aiohttp
    async def invoke():
        with transport:
            async with sdk_context(transport, Evidence(output), StrictSharedQuota(limiter), lambda: HASHES):
                raise primary
    with pytest.raises(ReplayAbort) as caught: asyncio.run(invoke())
    assert caught.value is primary
    assert transport.before_send == old_send and llm_transport.generate_content is old_call
    assert _api_client.BaseApiClient._use_aiohttp is old_stack and transport._restore is None
    assert json.loads((output / 'cleanup-error.json').read_text())['error_type'] == 'RuntimeError'


@pytest.mark.parametrize('primary_failure', [False, True])
@pytest.mark.parametrize('cancel_count', [1, 2])
def test_first_cancellation_during_sdk_cleanup_closes_once_before_propagating(tmp_path, monkeypatch,
                                                                          primary_failure, cancel_count):
    import httpx, llm_transport
    from google.genai import types
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    install_mock_http(monkeypatch, lambda request: httpx.Response(200, json=response_payload()))
    real_close = llm_transport.close_cached_clients_async
    calls, recorders, owner = [], [], []
    primary = TimeoutError('original job deadline')
    async def interrupted_close():
        calls.append('entered')
        for _ in range(cancel_count):
            owner[0].cancel()
            await asyncio.sleep(0)
        await real_close()
        calls.append('closed')
    monkeypatch.setattr(llm_transport, 'close_cached_clients_async', interrupted_close)
    async def invoke():
        owner.append(asyncio.current_task())
        with transport:
            async with sdk_context(transport, Evidence(output), StrictSharedQuota(limiter), lambda: HASHES) as recorder:
                recorders.append(recorder)
                await llm_transport.generate_content_async(KEY, MODEL, 'offline', types.GenerateContentConfig(max_output_tokens=64))
                if primary_failure:
                    raise primary
    try:
        with pytest.raises(TimeoutError if primary_failure else asyncio.CancelledError) as caught:
            asyncio.run(invoke())
        if primary_failure:
            assert caught.value is primary
        assert calls == ['entered', 'closed']
        assert not llm_transport._client_cache and recorders[0].cleanup_verified
        assert not (output / 'cleanup-error.json').exists() and transport._restore is None
        assert ledger.snapshot()['spent']['http'] == ledger.snapshot()['spent']['transport'] == 1
    finally:
        # Failure-side test cleanup, never substituted for the scope's proof.
        asyncio.run(real_close())


@pytest.mark.parametrize('failure', ['cancel', 'timeout'])
def test_owned_sdk_close_terminal_failure_is_not_repeated_or_certified(tmp_path, monkeypatch, failure):
    import llm_transport
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    calls, recorders = [], []
    async def failed_close():
        calls.append(True)
        if failure == 'cancel':
            raise asyncio.CancelledError()
        await asyncio.Event().wait()  # Real unchanged ten-second close deadline.
    monkeypatch.setattr(llm_transport, 'close_cached_clients_async', failed_close)
    async def invoke():
        with transport:
            async with sdk_context(transport, Evidence(output), StrictSharedQuota(limiter), lambda: HASHES) as recorder:
                recorders.append(recorder)
    with pytest.raises(ReplayAbort, match='cleanup'):
        asyncio.run(invoke())
    assert calls == [True] and not recorders[0].cleanup_verified
    assert transport._restore is None
    error = json.loads((output / 'cleanup-error.json').read_text())
    assert error['error_type'] == ('CancelledError' if failure == 'cancel' else 'TimeoutError')


def test_local_evidence_exhaustion_still_persists_real_http_usage_overrun(tmp_path, monkeypatch):
    import httpx
    from quality_campaign_graph import _WireEvidence
    from quality_campaign_safety import Evidence, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    class FullAfterUsageParsed(Evidence):
        def append(self, name, value):
            if name == 'wire.jsonl': self.maximum_bytes = self.written
            return super().append(name, value)
    transport.evidence = _WireEvidence(transport.evidence, FullAfterUsageParsed(output))
    payload = response_payload()
    payload['usageMetadata']['totalTokenCount'] = 513
    calls = []
    def send(client, model):
        return client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            json={'contents': [{'parts': [{'text': 'frozen source'}]}], 'generationConfig': {'maxOutputTokens': 64}})
    with transport, httpx.Client(transport=httpx.MockTransport(lambda request:
            calls.append(request) or httpx.Response(200, json=payload))) as client:
        with pytest.raises(ReplayAbort): transport.wrap_sync(send)(client, MODEL)
    state = ledger.snapshot()
    physical = next(row for row in state['attempts'].values() if row['http'])
    assert len(calls) == 1 and physical['actual_tokens'] == 513
    assert state['blocked'] == 'actual usage exceeded conservative reservation'
    assert state['spent']['tokens'] == 513


def test_actual_owned_client_close_failure_is_not_suppressed_by_shutdown_helper(tmp_path, monkeypatch):
    import llm_transport
    from quality_campaign_graph import sdk_context
    from quality_campaign_safety import Evidence, StrictSharedQuota, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    closed = []
    def failed_close():
        closed.append(True)
        raise RuntimeError('actual owned client close failure')
    async def invoke():
        with transport:
            async with sdk_context(transport, Evidence(output), StrictSharedQuota(limiter), lambda: HASHES):
                llm_transport._client_cache[KEY] = SimpleNamespace(close=failed_close)
    with pytest.raises(ReplayAbort, match='cleanup'): asyncio.run(invoke())
    assert closed == [True] and not llm_transport._client_cache and transport._restore is None
    assert json.loads((output / 'cleanup-error.json').read_text())['error_type'] == 'RuntimeError'


def test_original_job_stop_survives_final_outcome_evidence_failure(tmp_path, monkeypatch):
    import quality_campaign_safety
    from quality_campaign_graph import run_graph_job
    from quality_campaign_safety import Evidence, ReplayAbort
    ledger, transport, output, limiter, _ = setup_job(tmp_path, monkeypatch)
    primary = ReplayAbort('original frozen data drift')
    def failed_check(): raise primary
    monkeypatch.setattr(quality_campaign_safety, 'Evidence', lambda root, secrets: Evidence(root, secrets, maximum_bytes=1))
    with pytest.raises(ReplayAbort) as caught:
        asyncio.run(run_graph_job(dev=DEV, source_job=source_job(), output=output, job_id='job', mode='v4',
            ledger=ledger, transport=transport, check_frozen=failed_check, secrets=(KEY,)))
    assert caught.value is primary
    assert not (output / 'outcome.json').exists()
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'
