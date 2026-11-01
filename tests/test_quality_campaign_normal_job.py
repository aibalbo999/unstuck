"""Normal job and true SDK with private SQLite and offline HTTP; not qualification."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from test_quality_campaign_graph import (
    DEV, HASHES, KEY, MODEL, install_mock_http, response_payload, setup_job,
)
from test_analysis_frozen_canary import source


@pytest.fixture
def normal_job(tmp_path, monkeypatch):
    import analysis_jobs, job_store, report_index
    from settings import storage
    ledger, transport, output, limiter, pings = setup_job(tmp_path, monkeypatch)
    monkeypatch.setenv('GIT_COMMIT', 'offline-fixture')
    monkeypatch.setenv('GIT_DIRTY', 'false')
    for owner, field, value in (
        (analysis_jobs, 'OUTPUT_DIR', str(output / 'reports')),
        (job_store, 'TASK_DB_PATH', str(output / 'operational.sqlite3')),
        (report_index, 'CACHE_DB_PATH', str(output / 'cache.sqlite3')),
        (storage, 'OUTPUT_DIR', str(output / 'reports')),
        (storage, 'CACHE_DB_PATH', str(output / 'cache.sqlite3')),
        (storage, 'LANGGRAPH_CHECKPOINT_PATH', str(output / 'checkpoint.sqlite3')),
        (storage, 'LANGGRAPH_CHECKPOINT_BACKEND', 'sqlite'),
        (storage, 'LANGGRAPH_CHECKPOINT_POSTGRES_DSN', 'isolated-postgres-disabled'),
        (storage, 'REPORT_STORAGE_BACKEND', 'local'),
        (storage, 'CACHE_BACKEND', 'memory'),
    ):
        monkeypatch.setattr(owner, field, value)
    monkeypatch.setattr(analysis_jobs, 'has_api_keys', lambda: True)
    def forbidden(*a, **k):
        raise AssertionError('fresh source, memory or retry renewal forbidden')
    monkeypatch.setattr(analysis_jobs, 'STOCK_DATA_SERVICE', SimpleNamespace(fetch_async=forbidden))
    monkeypatch.setattr(analysis_jobs, 'build_temporal_memory', forbidden)
    monkeypatch.setattr(analysis_jobs, 'prepare_analysis_retry', forbidden)
    from reporting import ReportRenderer
    class FixtureRenderer:
        async def render_async(self, request):
            return await ReportRenderer().render_async(replace(request, generated_at='2026-09-12T07:30:00+00:00'))
    monkeypatch.setattr(analysis_jobs, 'REPORT_RENDERER', FixtureRenderer())
    return SimpleNamespace(ledger=ledger, transport=transport, output=output,
        limiter=limiter, pings=pings, source={'pipeline_id': 'v4', 'data_snapshot': json.loads(source())})


def run(case):
    import quality_campaign_graph as campaign
    # Exercise the old path for a behavioral RED instead of a missing symbol.
    function = getattr(campaign, 'run_normal_job', campaign.run_graph_job)
    options = {'manifest_sha256': 'f' * 64} if hasattr(campaign, 'run_normal_job') else {}
    return asyncio.run(function(dev=DEV, source_job=case.source, output=case.output, job_id='job',
        mode=case.source['pipeline_id'], ledger=case.ledger, transport=case.transport,
        check_frozen=lambda: HASHES, secrets=(KEY,), **options))


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3', 'v4'])
def test_normal_job_keeps_original_cutoff_quant_and_real_graph_quality_veto(normal_job, monkeypatch, mode):
    import job_store, workflow_services, workflow_graph, llm_transport
    from google.genai import types
    case = normal_job
    case.source['pipeline_id'] = mode
    factory = workflow_services.create_default_workflow_services
    seen, calls = [], []
    install_mock_http(monkeypatch, lambda request: calls.append(request) or httpx.Response(200, json=response_payload()))
    async def diagnostic_agent(agent, state):
        if not calls:
            await llm_transport.generate_content_async(KEY, MODEL, 'offline normal job', types.GenerateContentConfig(max_output_tokens=64))
        return {'analyses': {str(agent): 'offline diagnostic not qualified'}}
    async def audit(state):
        return {'status': 'blocked', 'blocking_issues': ['offline_diagnostic_not_qualified']}
    def controlled(**kwargs):
        seen.append(kwargs.get('rotator'))
        return replace(factory(**kwargs), run_agent=diagnostic_agent, final_audit=audit)
    monkeypatch.setattr(workflow_services, 'create_default_workflow_services', controlled)
    monkeypatch.setattr(workflow_graph, 'create_default_workflow_services', controlled)
    result = run(case)
    durable = job_store.get_job('job')
    assert durable.get('status') == 'error', 'shared SDK must run through the normal persistent job'
    events = job_store.get_events_since('job')
    assert any(e['payload'].get('phase') == 'analysis_input_frozen' for e in events)
    data = json.loads(durable['data_snapshot'])
    assert data['analysis_input_cutoff'] == '2026-09-12T07:30:00+00:00' and data['quant_metrics']
    assert result['status'] == 'blocked' and result['qualified_for_campaign'] is False
    assert len(calls) == 1 and case.ledger.snapshot()['spent']['http'] == 1
    assert seen[0]._shared_limiter.limiter is case.limiter
    assert case.ledger.snapshot()['jobs']['job']['status'] == 'active'
    assert not list(case.output.rglob('*.html'))
    assert not llm_transport._client_cache and case.transport._restore is None
    assert (case.output / 'checkpoint.sqlite3').is_file()


def controlled_graph(monkeypatch, action):
    import workflow_services, workflow_graph
    factory = workflow_services.create_default_workflow_services
    async def agent(number, state):
        if number == 22:
            await action()
        return {'analyses': {str(number): 'offline diagnostic not qualified'}}
    async def audit(state):
        return {'status': 'blocked', 'blocking_issues': ['offline_diagnostic_not_qualified']}
    def services(**kwargs):
        return replace(factory(**kwargs), run_agent=agent, final_audit=audit)
    monkeypatch.setattr(workflow_services, 'create_default_workflow_services', services)
    monkeypatch.setattr(workflow_graph, 'create_default_workflow_services', services)


@pytest.mark.parametrize('kind', ['sync', 'async', 'stream'])
def test_normal_sdk_budget_exhaustion_stops_without_retry_renewal(normal_job, monkeypatch, kind):
    import llm_transport, job_store
    from google.genai import types
    from quality_campaign_budget import BudgetDenied
    case, calls, reserves = normal_job, [], []
    def handler(request):
        calls.append(request)
        if kind == 'stream':
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
                text='data: ' + json.dumps(response_payload()) + '\n\n')
        return httpx.Response(200, json=response_payload())
    install_mock_http(monkeypatch, handler)
    reserve = case.ledger.reserve_attempt
    def once(*args, **kwargs):
        if kwargs.get('transport') == 1:
            reserves.append(args)
            if len(reserves) > 1:
                raise BudgetDenied('offline exhausted shared campaign budget')
        return reserve(*args, **kwargs)
    monkeypatch.setattr(case.ledger, 'reserve_attempt', once)
    async def action():
        for index in range(3):
            options = types.GenerateContentConfig(max_output_tokens=64)
            if kind == 'sync':
                llm_transport.generate_content(KEY, MODEL, 'offline bounded calls', options)
            else:
                function = llm_transport.generate_content_stream_async if kind == 'stream' else llm_transport.generate_content_async
                await function(KEY, MODEL, 'offline bounded calls', options)
    controlled_graph(monkeypatch, action)
    result = run(case)
    assert result['status'] == 'partial' and result['failure']['error_type'] == 'ReplayAbort'
    assert result['failure']['boundary_reason'] == 'offline exhausted shared campaign budget'
    assert len(reserves) == 2 and len(calls) == 1
    assert case.ledger.snapshot()['spent']['http'] == case.ledger.snapshot()['spent']['transport'] == 1
    assert job_store.get_job('job')['status'] == 'running'  # Hard stop is not forged into DB completion.
    assert not any(e['payload']['type'] in ('done', 'report_done') for e in job_store.get_events_since('job'))
    assert not llm_transport._client_cache and case.transport._restore is None
    assert case.ledger.snapshot()['jobs']['job']['status'] == 'active'


@pytest.mark.parametrize('counter', ['http', 'transport'])
def test_normal_job_honors_real_shared_ledger_counter_limit(normal_job, monkeypatch, counter):
    import llm_transport
    from google.genai import types
    from test_quality_campaign_budget import RESERVATION
    case, calls = normal_job, []
    limit = case.ledger.limits['S1'][counter]
    for index in range(limit - 1):
        case.ledger.reserve_attempt('offline-consumed-' + str(index), 'job', **{
            **RESERVATION, 'transport': int(counter == 'transport'), 'http': int(counter == 'http'),
            'tokens': int(counter == 'http'), 'cost_microusd': int(counter == 'http')})
    install_mock_http(monkeypatch, lambda request: calls.append(request) or httpx.Response(200, json=response_payload()))
    async def action():
        for _ in range(3):
            await llm_transport.generate_content_async(KEY, MODEL, 'offline real ledger exhaustion',
                types.GenerateContentConfig(max_output_tokens=64))
    controlled_graph(monkeypatch, action)
    result = run(case)
    assert result['status'] == 'partial' and result['failure']['error_type'] == 'ReplayAbort'
    assert counter in result['failure']['boundary_reason']
    assert len(calls) == 1 and case.ledger.snapshot()['spent'][counter] == limit
    assert case.ledger.snapshot()['jobs']['job']['status'] == 'active'
    assert not llm_transport._client_cache and case.transport._restore is None


@pytest.mark.parametrize('change', ['missing_cutoff', 'wrong_mode', 'outside_db', 'missing_limiter', 'existing_job'])
def test_normal_admission_rejects_invalid_input_or_runtime_before_sdk(normal_job, monkeypatch, change):
    import job_store
    case, calls = normal_job, []
    install_mock_http(monkeypatch, lambda request: calls.append(request) or httpx.Response(200, json=response_payload()))
    if change == 'missing_cutoff':
        del case.source['data_snapshot']['analysis_input_cutoff']
    elif change == 'wrong_mode':
        case.source['pipeline_id'] = 'both'
    elif change == 'outside_db':
        monkeypatch.setattr(job_store, 'TASK_DB_PATH', str(case.output.parent / 'outside.sqlite3'))
    elif change == 'missing_limiter':
        case.limiter._client = None
    else:
        job_store.create_or_attach_active_job('2330.TW', 'v4', job_id='job')
    before = list(job_store.get_events_since('job')) if change == 'existing_job' else None
    result = run(case)
    assert result['status'] in ('error', 'partial') and not calls
    assert case.ledger.snapshot()['spent']['http'] == 0
    assert not list(case.output.rglob('*.html'))
    if before is not None:
        assert job_store.get_events_since('job') == before
    if change in ('missing_cutoff', 'wrong_mode', 'outside_db'):
        assert case.pings == [] and not (case.output / 'operational.sqlite3').exists()
    assert not (case.output.parent / 'outside.sqlite3').exists()


def test_lost_shared_quota_during_stream_stops_before_next_delta(normal_job, monkeypatch):
    import llm_transport
    from google.genai import types
    case, deltas = normal_job, []
    payload = 'data: ' + json.dumps(response_payload()) + '\n\n'
    install_mock_http(monkeypatch, lambda request: httpx.Response(200,
        headers={'Content-Type': 'text/event-stream'}, text=payload * 3))
    async def delta(text):
        deltas.append(text)
        case.limiter._client = None
    async def action():
        await llm_transport.generate_content_stream_async(KEY, MODEL, 'offline interrupted stream',
            types.GenerateContentConfig(max_output_tokens=64), on_delta=delta)
    controlled_graph(monkeypatch, action)
    result = run(case)
    assert result['status'] == 'partial'
    assert len(deltas) == 1, 'a lost shared limiter must not keep consuming public stream deltas'
    assert not list(case.output.rglob('*.html'))
    assert not llm_transport._client_cache and case.transport._restore is None


def diagnostic_legacy_pipeline(monkeypatch, *, extra_text=''):
    import analysis_jobs
    from agent_runtime import AnalysisResult
    async def run_pipeline(request):
        context = {'ticker': request.data['ticker'], 'data': request.data,
            'pipeline_id': request.pipeline_id, 'analyses': {}, 'final_audit': {'status': 'passed'}}
        if request.pipeline_id == 'v4':
            context['analyses'][24] = '## 極短線交易計畫\n本測試不建立部位；待補齊來源後重新評估。' + extra_text
            context['parsed'] = {'trade_setup': {'trade_direction': 'Neutral', 'entry_zone': 'N/A',
                'target_price': 'N/A', 'stop_loss': 'N/A', 'risk_level': 'High',
                'core_catalyst': '本測試不建立部位；待補齊來源後重新評估。'}}
        return AnalysisResult(context=context, pipeline_id=request.pipeline_id)
    monkeypatch.setattr(analysis_jobs, 'PIPELINE_RUNNER', SimpleNamespace(run_async=run_pipeline))


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3', 'v4'])
def test_normal_private_renderer_index_and_job_readback_without_quality_promotion(normal_job, monkeypatch, mode):
    import hashlib, job_store
    case = normal_job
    case.source['pipeline_id'] = mode
    diagnostic_legacy_pipeline(monkeypatch)
    result = run(case)
    assert result['status'] == 'published', result['failure']
    assert result['qualified_for_campaign'] is result['formal_publication'] is False
    assert job_store.get_job('job')['status'] == 'done'
    assert case.ledger.snapshot()['jobs']['job']['status'] == 'active'
    for artifact in result['artifacts'].values():
        payload = (case.output / 'reports' / artifact['key']).read_bytes()
        assert len(payload) == artifact['bytes'] and hashlib.sha256(payload).hexdigest() == artifact['sha256']
    snapshot = json.loads((case.output / 'reports' / result['artifacts']['data_key']['key']).read_text())
    assert snapshot['pipeline'] == mode and snapshot['data']['analysis_input_cutoff'] == '2026-09-12T07:30:00+00:00'
    assert not snapshot.get('generation_contract')  # No invented generation/model receipts.
    assert case.ledger.snapshot()['spent']['http'] == 0
    assert (case.output / 'normal-job.json').is_file() and (case.output / 'events.jsonl').is_file()


def test_normal_private_report_rejects_secret_before_any_artifact_write(normal_job, monkeypatch):
    diagnostic_legacy_pipeline(monkeypatch, extra_text=KEY)
    result = run(normal_job)
    assert result['status'] == 'partial'
    assert result['failure']['boundary_reason'] == 'Credential-shaped report rejected before private persistence'
    assert not list((normal_job.output / 'reports').rglob('*.html'))
    assert not list((normal_job.output / 'reports').rglob('*.attempt'))
    assert KEY not in (normal_job.output / 'outcome.json').read_text()


def test_normal_artifact_readback_failure_keeps_uncertain_bytes_and_no_success_claim(normal_job, monkeypatch):
    import analysis_jobs
    from report_persistence import report_bundle_keys_for_filename
    diagnostic_legacy_pipeline(monkeypatch)
    append = analysis_jobs.append_event
    corrupted = []
    def corrupt_after_persistence(job_id, event):
        append(job_id, event)
        if event.get('type') == 'report_done':
            path = normal_job.output / 'reports' / report_bundle_keys_for_filename(event['filename']).html_key
            path.write_text('offline simulated corruption')
            corrupted.append(path)
    monkeypatch.setattr(analysis_jobs, 'append_event', corrupt_after_persistence)
    result = run(normal_job)
    assert result['status'] == 'partial' and result['artifacts'] is None
    assert corrupted[0].read_text() == 'offline simulated corruption'
    assert normal_job.ledger.snapshot()['jobs']['job']['status'] == 'active'


@pytest.mark.parametrize('publish', [False, True])
def test_fresh_normal_child_uses_real_write_sqlite_sdk_guards(normal_job, publish):
    from test_quality_campaign_safety import fresh_guarded_child
    case = normal_job
    source_code = '''
import asyncio, importlib.util, traceback
from dataclasses import replace
os.umask(0o077)
denials = []
original_private_path = safety.private_path
def tracked_private_path(root, value):
    try:
        return original_private_path(root, value)
    except safety.ReplayAbort:
        denials.append({'path': str(value), 'stack': traceback.format_stack()})
        raise
safety.private_path = tracked_private_path
backend = Path(sys.argv[1]).parent / 'backend'
sys.path.insert(0, str(backend))
import canary_release_policy
# Explicit test-only mock, after real socket/write/SQLite boundaries above.
canary_release_policy.require_canary_enabled = lambda: None
# Explicit offline configuration; never read operator .env or perform DNS.
spec = importlib.util.spec_from_file_location('settings.env', backend / 'settings/env.py')
env_module = importlib.util.module_from_spec(spec)
sys.modules['settings.env'] = env_module
spec.loader.exec_module(env_module)
env_module.load_local_env = lambda **kw: None
os.environ.update(CACHE_DIR=str(output / 'cache'), CACHE_DB_PATH=str(output / 'cache.sqlite3'),
    OPERATIONAL_DB_PATH=str(output / 'operational.sqlite3'), TASK_DB_PATH=str(output / 'operational.sqlite3'),
    LANGGRAPH_CHECKPOINT_PATH=str(output / 'checkpoint.sqlite3'), LANGGRAPH_CHECKPOINT_BACKEND='sqlite',
    LANGGRAPH_CHECKPOINT_POSTGRES_DSN='isolated-postgres-disabled', CACHE_BACKEND='memory',
    OUTPUT_DIR=str(output / 'reports'), REPORT_STORAGE_BACKEND='local',
    LLM_SEMANTIC_CACHE_ENABLED='false', AGENT_STEP_CACHE_ENABLED='false', RAG_ENABLED='false',
    GEMMA_EVIDENCE_BATCHING_ENABLED='false', GEMINI_API_KEYS='offline-secret-key',
    GIT_COMMIT='offline-fixture', GIT_DIRTY='false',
    TMPDIR=str(output / 'tmp'), MPLCONFIGDIR=str(output / 'mpl'), XDG_CACHE_HOME=str(output / 'xdg'))
(output / 'tmp').mkdir(mode=0o700)
# Match owned_job's existing PostgreSQL import veto. Without it, peewee's
# optional driver probe invokes pg_config before the normal job can import.
class NoPostgres:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('psycopg', 'psycopg2', 'asyncpg', 'pg8000'):
            raise ImportError('PostgreSQL disabled in frozen campaign child')
        return None
sys.meta_path.insert(0, NoPostgres())
import config, analysis_jobs, workflow_services, workflow_graph, llm_client, llm_transport, httpx
from agent_runtime import routing, AnalysisResult
from google.genai import types
from quality_campaign_graph import run_normal_job
from quality_campaign_transport import CampaignTransport
model = 'gemini-3.6-flash'
key = 'offline-secret-key'
routing.get_agent_model_sequence = lambda agent: [model]
routing.get_audit_model_sequence = lambda: [model]
limiter = SimpleNamespace(_client=SimpleNamespace(ping=lambda: True))
llm_client.KeyRotator = lambda keys: SimpleNamespace(_shared_limiter=limiter)
calls = []
def reply(request):
    calls.append(request)
    return httpx.Response(200, json=RESPONSE_LITERAL)
mock = httpx.MockTransport(reply)
llm_transport._genai_http_options = lambda: types.HttpOptions(
    client_args={'transport': mock}, async_client_args={'transport': mock})
factory = workflow_services.create_default_workflow_services
async def agent(number, state):
    if number == 22:
        await llm_transport.generate_content_async(key, model, 'offline guarded normal graph',
            types.GenerateContentConfig(max_output_tokens=64))
    return {'analyses': {str(number): 'offline diagnostic'}}
async def audit(state):
    return {'status': 'blocked', 'blocking_issues': ['offline_not_qualified']}
def services(**kwargs):
    return replace(factory(**kwargs), run_agent=agent, final_audit=audit)
workflow_services.create_default_workflow_services = workflow_graph.create_default_workflow_services = services
if PUBLISH_LITERAL:
    async def legacy(request):
        return AnalysisResult(context={'ticker': request.data['ticker'], 'data': request.data,
            'pipeline_id': request.pipeline_id, 'analyses': {}, 'final_audit': {'status': 'passed'}},
            pipeline_id=request.pipeline_id)
    analysis_jobs.PIPELINE_RUNNER = SimpleNamespace(run_async=legacy)
source_job = SOURCE_LITERAL
if PUBLISH_LITERAL: source_job['pipeline_id'] = 'v1'
ledger = CampaignBudget(ledger_path, identity)
hashes = {k: v for k, v in identity.items() if k != 'campaign_id'}
transport = CampaignTransport(ledger, 'job', {model: POLICY_LITERAL}, actual_hashes=hashes,
    verify_frozen=lambda: hashes, secrets=(key,))
result = asyncio.run(run_normal_job(dev=backend.parent, source_job=source_job, output=output,
    job_id='job', mode=source_job['pipeline_id'], ledger=ledger, transport=transport,
    check_frozen=lambda: hashes, manifest_sha256='f' * 64, secrets=(key,)))
assert result['status'] == ('published' if PUBLISH_LITERAL else 'blocked'), (result['failure'], denials)
assert len(calls) == (0 if PUBLISH_LITERAL else 1)
assert result['qualified_for_campaign'] is False
assert ledger.snapshot()['jobs']['job']['status'] == 'active'
assert not llm_transport._client_cache and transport._restore is None
print('guarded normal child verified')
'''
    from test_quality_campaign_graph import POLICY
    for name, value in (('PUBLISH_LITERAL', publish), ('POLICY_LITERAL', POLICY),
                        ('SOURCE_LITERAL', case.source), ('RESPONSE_LITERAL', response_payload())):
        source_code = source_code.replace(name, repr(value))
    result = fresh_guarded_child(case.ledger, case.output, source_code, identity=case.ledger.identity)
    assert 'guarded normal child verified' in result
