"""Frozen job runner boundaries; fixtures are not billing or source evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

import quality_campaign_runner as runner
from quality_campaign_budget import CampaignBudget, manifest_identity
from quality_campaign_wire import ReplayAbort


def put(path, value):
    path.write_text(json.dumps(value, sort_keys=True))
    path.chmod(0o600)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(tmp_path):
    dev = tmp_path / 'dev'
    (dev / 'backend').mkdir(parents=True)
    (dev / 'backend' / 'unit.py').write_text('ANSWER = 42\n')
    storage = dev / 'backend' / 'storage';storage.mkdir()
    (storage / '__init__.py').write_text('')
    # Only the exact capability source used by this synthetic frozen child.
    for name in ('capacity.py', 'capacity_delegation.py'):
        (storage / name).write_bytes((Path(__file__).resolve().parents[1] / 'backend' / 'storage' / name).read_bytes())
    source = put(tmp_path / 'database-job.json', {'pipeline_id': 'v4',
        'job_id': 'original', 'data_snapshot': {'ticker': '2330.TW', 'fetch_date': '2026-09-12',
            'data_trust': {'status': 'unknown'}, 'analysis_input_cutoff': '2026-09-12T07:30:00+00:00'},
        'analyses': {'24': 'NEVER-ADOPT'}, 'publication': {'passed': True}})
    routes = put(tmp_path / 'routes.json', {'routes': 'fixture-only'})
    env = tmp_path / 'explicit.env'
    env.write_text('REDIS_URL=redis://127.0.0.1:6379/0\nGEMINI_API_KEYS=dummy-test-key\n'
                   'MODEL_ROUTES_FILE=' + routes['path'] + '\n')
    env.chmod(0o600)
    environment = {'path': str(env), 'sha256': hashlib.sha256(env.read_bytes()).hexdigest()}
    billing = put(tmp_path / 'billing-review.json', {'schema': 'campaign.billing_review.v1',
        'decision': 'approved', 'status': 'verified_paid', 'key_slots': ['anonymous-slot-1'],
        'reviewed_models': ['gemini-fixture'], 'reviewed_at_ms': int(time.time() * 1000),
        'expires_at_ms': int(time.time() * 1000) + 600000,
        'limitations': 'OFFLINE FIXTURE NOT REAL BILLING VERIFICATION'})
    basis = put(tmp_path / 'reservation-review.json', {'schema': 'campaign.reservation_review.v1',
        'decision': 'approved', 'models': {'gemini-fixture': {'maximum_total_tokens': 1000,
        'maximum_output_tokens': 100, 'maximum_request_bytes': 4000,
        'maximum_microusd_per_million_tokens': 2000000}},
        'limitations': 'OFFLINE FIXTURE NOT OFFICIAL PRICING'})
    source_review = put(tmp_path / 'source-review.json', {'schema': 'campaign.source_review.v1',
        'decision': 'diagnostic_only', 'mode': 'v4', 'source_sha256': source['sha256'],
        'limitations': ['not full research qualified']})
    policies = put(tmp_path / 'policies.json', {'gemini-fixture': {
        **json.loads(Path(basis['path']).read_text())['models']['gemini-fixture'],
        'billing_status': 'verified_paid', 'billing_identity_sha256': billing['sha256'],
        'reservation_basis_sha256': basis['sha256']}})
    manifest = {'schema': 'campaign.frozen_job.v1', 'campaign_id': 'fixture', 'binding_id': 'v4-one',
        'stage': 'S1', 'mode': 'v4', 'role': 'candidate', 'purpose': 'diagnostic',
        'dev': str(dev), 'code_files': runner.code_inventory(dev),
        'harness_files': runner.harness_inventory(), 'runtime_files': runner.runtime_inventory(),
        'source': source, 'routes': routes,
        'environment': environment, 'billing_review': billing, 'reservation_review': basis,
        'source_review': source_review, 'policies': policies}
    path = tmp_path / 'manifest.json'
    put(path, manifest)
    return path, manifest


def frozen(tmp_path):
    path, manifest = fixture(tmp_path)
    return runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest()), manifest


def reserved(tmp_path):
    plan, manifest = frozen(tmp_path)
    binding = {manifest['binding_id']: plan.verify()}
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', manifest_identity('fixture', binding),
                            allowed_bindings=binding)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    ledger.reserve_job('job', 'batch', binding_id='v4-one', actual_hashes=plan.verify())
    return plan, manifest, ledger


def storage_review(plan, ledger, job_id='job'):
    """Pinned synthetic estimate only, never a real source/quality review."""
    keys=('source','artifacts','evidence','sqlite','temporary')
    return put(ledger.path.parent / 'offline-storage-budget.json', {
        'schema':'stock.storage-budget-review.v1','decision':'reviewed',
        'manifest_sha256':plan.expected_sha,'job_id':job_id,
        'components':{key:64*1024*1024 for key in keys},'maximum_files':1000,
        'basis':{key:'Synthetic test-only byte allowance; no real approval or quality proof' for key in keys}})


def test_import_has_no_backend_or_network_side_effects():
    # The module must only import standard library and inert campaign helpers.
    assert not hasattr(runner, 'config')
    assert not hasattr(runner, 'KeyRotator')


def test_existing_reviewed_files_and_exact_source_mode_are_required(tmp_path):
    plan, manifest = frozen(tmp_path)
    assert set(plan.verify()) == {'code_sha256', 'source_sha256', 'route_sha256'}
    assert plan.source_job()['pipeline_id'] == 'v4'
    assert plan.source_job()['data_snapshot']['ticker'] == '2330.TW'
    assert plan.manifest == manifest


@pytest.mark.parametrize('cutoff', [None, '2026-09-12', 'not-a-cutoff'])
def test_missing_original_aware_cutoff_rejected_in_parent_preflight(tmp_path, cutoff):
    path, manifest = fixture(tmp_path)
    source_path = Path(manifest['source']['path'])
    data = json.loads(source_path.read_text())
    data['data_snapshot']['analysis_input_cutoff'] = cutoff
    manifest['source'] = put(source_path, data)
    review_path = Path(manifest['source_review']['path'])
    review = json.loads(review_path.read_text())
    review['source_sha256'] = manifest['source']['sha256']
    manifest['source_review'] = put(review_path, review)
    put(path, manifest)
    with pytest.raises(ReplayAbort, match='original aware input cutoff'):
        runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest()).verify()


@pytest.mark.parametrize('field', ['source', 'routes', 'environment', 'billing_review',
    'reservation_review', 'source_review', 'policies'])
def test_every_frozen_external_file_is_rechecked_before_admission(tmp_path, field):
    plan, manifest = frozen(tmp_path)
    Path(manifest[field]['path']).write_text('{}')
    with pytest.raises(ReplayAbort):
        plan.verify()


@pytest.mark.parametrize('change', ['modify', 'add', 'remove', 'symlink'])
def test_full_code_inventory_detects_changes_and_new_files(tmp_path, change):
    plan, manifest = frozen(tmp_path)
    path = Path(manifest['dev']) / 'backend' / 'unit.py'
    if change == 'modify': path.write_text('ANSWER = 0\n')
    if change == 'add': (path.parent / 'extra.py').write_text('X = 1\n')
    if change == 'remove': path.unlink()
    if change == 'symlink':
        path.unlink()
        path.symlink_to(tmp_path / 'outside.py')
    with pytest.raises(ReplayAbort): plan.verify()


def test_review_labels_do_not_make_candidate_addenda_executable(tmp_path):
    path, manifest = fixture(tmp_path)
    manifest['source'] = put(tmp_path / 'addendum.json', {'purpose': 'independent_candidate_input_addendum_not_executable_job',
        'qualified_for_live': False, 'pipeline_id': 'v4', 'data_snapshot': {'ticker': '2330.TW'}})
    put(path, manifest)
    with pytest.raises(ReplayAbort): runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest()).verify()


@pytest.mark.parametrize('field,value', [('mode', 'v1'), ('stage', 'S3'), ('role', 'baseline'),
                                      ('purpose', 'qualification')])
def test_manifest_cannot_relabel_this_s1_diagnostic_source(tmp_path, field, value):
    path, manifest = fixture(tmp_path)
    manifest[field] = value
    put(path, manifest)
    with pytest.raises(ReplayAbort): runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest()).verify()


def test_unknown_or_expired_billing_never_admits_even_with_valid_hashes(tmp_path):
    path, manifest = fixture(tmp_path)
    bill_path = Path(manifest['billing_review']['path'])
    bill = json.loads(bill_path.read_text())
    bill['expires_at_ms'] = 1
    manifest['billing_review'] = put(bill_path, bill)
    policy_path = Path(manifest['policies']['path'])
    policy = json.loads(policy_path.read_text())
    policy['gemini-fixture']['billing_identity_sha256'] = manifest['billing_review']['sha256']
    manifest['policies'] = put(policy_path, policy)
    put(path, manifest)
    with pytest.raises(ReplayAbort): runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest()).verify()


@pytest.mark.parametrize('mutation', ['missing', 'replaced', 'empty', 'public'])
def test_ledger_pin_refuses_reset_or_replacement_before_reopen(tmp_path, mutation):
    plan, manifest, ledger = reserved(tmp_path)
    pin = runner.ledger_pin(ledger)
    if mutation == 'missing': ledger.path.unlink()
    elif mutation == 'replaced':
        ledger.path.rename(tmp_path / 'old.sqlite3')
        ledger.path.write_bytes((tmp_path / 'old.sqlite3').read_bytes())
        ledger.path.chmod(0o600)
    elif mutation == 'empty': ledger.path.write_bytes(b'')
    else: ledger.path.chmod(0o644)
    with pytest.raises(ReplayAbort): runner.reopen_ledger(pin)
    if mutation == 'missing': assert not ledger.path.exists()
    if mutation == 'empty': assert ledger.path.stat().st_size == 0


def test_frozen_environment_drops_ambient_keys_and_isolates_all_writes(tmp_path, monkeypatch):
    plan, manifest = frozen(tmp_path)
    output = tmp_path / 'private'
    output.mkdir(mode=0o700)
    monkeypatch.setenv('ANOTHER_SECRET', 'ambient-only')
    env = runner.child_environment(plan, output)
    assert 'ANOTHER_SECRET' not in env
    assert env['GEMINI_API_KEYS'] == 'dummy-test-key'
    assert env['CACHE_BACKEND'] == 'memory'
    assert env['RAG_ENABLED'] == 'false'
    assert env['GEMMA_EVIDENCE_BATCHING_ENABLED'] == 'false'
    assert env['OUTPUT_DIR'] == str(output / 'reports')
    assert env['OPERATIONAL_DB_PATH'] == str(output / 'operational.sqlite3')
    assert 'PYTHONPATH' not in env


def test_runner_never_finishes_without_owned_cleanup(tmp_path, monkeypatch):
    plan, manifest, ledger = reserved(tmp_path)
    def failed(*args, **kwargs): raise runner.CleanupUnconfirmed('fixture cleanup unknown')
    monkeypatch.setattr(runner, 'run_reserved_process', failed)
    with pytest.raises(runner.CleanupUnconfirmed): runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'
    assert not (tmp_path / 'job' / 'parent-receipt.json').exists()


def test_parent_readback_cannot_convert_failed_or_missing_outcome_to_success(tmp_path, monkeypatch):
    plan, manifest, ledger = reserved(tmp_path)
    def fake_process(*args, **kwargs):
        return {'cleanup_verified': True, 'cleanup_evidence_sha256': 'a' * 64,
            'cleanup_path': str(tmp_path / 'nonexistent'), 'returncode': 0, 'status': 'exited'}
    monkeypatch.setattr(runner, 'run_reserved_process', fake_process)
    with pytest.raises(ReplayAbort): runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'


def test_existing_output_or_wrong_binding_never_spawns(tmp_path, monkeypatch):
    plan, manifest, ledger = reserved(tmp_path)
    (tmp_path / 'job').mkdir(mode=0o700)
    monkeypatch.setattr(runner, 'run_reserved_process', lambda *a, **k: pytest.fail('must not spawn'))
    with pytest.raises(ReplayAbort): runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))


def test_same_candidate_code_identity_is_shared_across_source_reviews(tmp_path):
    path, manifest = fixture(tmp_path)
    first = runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest()).verify()
    source = json.loads(Path(manifest['source']['path']).read_text())
    source['data_snapshot']['ticker'] = '2412.TW'
    manifest['source'] = put(Path(manifest['source']['path']), source)
    review_path = Path(manifest['source_review']['path'])
    review = json.loads(review_path.read_text())
    review['source_sha256'] = manifest['source']['sha256']
    manifest['source_review'] = put(review_path, review)
    put(path, manifest)
    second = runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest()).verify()
    assert first['code_sha256'] == second['code_sha256']
    assert first['source_sha256'] != second['source_sha256']


def test_frozen_runtime_rejects_sdk_or_interpreter_change(tmp_path, monkeypatch):
    path, manifest = fixture(tmp_path)
    initial = {'python': 'fixture-python', 'google-genai': 'fixture-sdk-v1'}
    manifest['runtime_files'] = initial
    put(path, manifest)
    monkeypatch.setattr(runner, 'runtime_inventory', lambda: initial, raising=False)
    plan = runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest())
    plan.verify()
    monkeypatch.setattr(runner, 'runtime_inventory', lambda: {**initial, 'google-genai': 'fixture-sdk-v2'})
    with pytest.raises(ReplayAbort): plan.verify()


def test_isolated_cli_does_not_expose_harness_directory_as_sdk_import_path(tmp_path):
    helper = tmp_path / 'helper'
    helper.mkdir()
    backend = tmp_path / 'backend'
    backend.mkdir()
    (backend / 'canary_release_policy.py').write_bytes(
        (Path(runner.__file__).resolve().parents[1] / 'backend/canary_release_policy.py').read_bytes())
    for name in ('quality_campaign_runner.py', 'quality_campaign_budget.py',
                 'quality_campaign_watchdog.py', 'quality_campaign_wire.py'):
        (helper / name).write_bytes(Path(runner.__file__).with_name(name).read_bytes())
    marker = tmp_path / 'shadow-sdk-imported'
    (helper / 'httpx.py').write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
    script = 'import runpy, sys\nsys.argv = ["runner", "--help"]\ntry:\n runpy.run_path(' + repr(str(helper / 'quality_campaign_runner.py')) + ', run_name="__main__")\nexcept SystemExit as error:\n assert error.code == 0\nimport httpx\n'
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script], env={},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), 'Unfrozen sibling module shadowed the SDK despite Python -I'


def completed_process_fixture(ledger, output, *, damage=None):
    """Offline receipt fixture only, never a quality acceptance fixture."""
    job = ledger.snapshot()['jobs']['job']
    runner.exclusive_json(ledger.path.parent / 'campaign.sqlite3.job.watchdog-started.json', {
        'job_id': 'job', 'ledger_binding_sha256': ledger.binding,
        'deadline_ms': job['deadline_ms'], 'actual_hashes': job['actual_hashes']})
    cleanup = {'version': 1, 'job_id': 'job', 'ledger_binding_sha256': ledger.binding,
        'deadline_ms': job['deadline_ms'], 'command_returncode': 0, 'pgid': 123456,
        'guardian_reaped': True, 'process_group_absent': True, 'stop_reason': 'exited'}
    cleanup_path = output / 'watchdog-job.cleanup.json'
    cleanup_sha = runner.exclusive_json(cleanup_path, cleanup)
    reports = output / 'reports'
    reports.mkdir(mode=0o700)
    artifacts = {}
    for field, key, raw in [('html_key', 'fixture.html', b'<html>Offline fixture</html>'),
                            ('md_key', 'fixture.md', b'Offline fixture'), ('data_key', 'fixture.data.json', b'{}')]:
        (reports / key).write_bytes(raw)
        artifacts[field] = {'key': key, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    outcome = {'status': 'published', 'job_id': 'job', 'mode': 'v4',
        'formal_publication': False, 'qualified_for_campaign': False, 'frozen_verified': True,
        'publication': {'basis': 'offline receipt fixture'}, 'artifacts': artifacts}
    if damage == 'missing': (reports / 'fixture.md').unlink()
    if damage == 'changed': (reports / 'fixture.md').write_text('CHANGED')
    if damage == 'escape': artifacts['md_key']['key'] = '../outside.md'
    if damage == 'no_inventory': outcome['artifacts'] = None
    if damage == 'not_verified': outcome['frozen_verified'] = False
    runner.exclusive_json(output / 'outcome.json', outcome)
    return {'cleanup_verified': True, 'cleanup_path': str(cleanup_path),
        'cleanup_evidence_sha256': cleanup_sha, 'cleanup': cleanup, 'returncode': 0, 'status': 'exited'}


@pytest.mark.parametrize('damage', [None, 'missing', 'changed', 'escape', 'no_inventory', 'not_verified'])
def test_parent_requires_private_artifact_bytes_not_only_published_scalar(tmp_path, monkeypatch, damage):
    plan, manifest, ledger = reserved(tmp_path)
    monkeypatch.setattr(runner, 'run_reserved_process', lambda *a, **k:
        completed_process_fixture(ledger, tmp_path / 'job', damage=damage))
    receipt = runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))
    assert receipt['status'] == ('private_pipeline_completed' if damage is None else 'failed')
    assert receipt['qualified_for_campaign'] is False


def test_real_owned_child_shares_http_accounting_and_cleanup_without_quality_promotion(tmp_path, monkeypatch):
    """Only graph service and DNS are fixture seams; SDK/wire/ledger/guards/child are real."""
    from quality_campaign_watchdog import run_reserved_process
    path, manifest = fixture(tmp_path)
    dev = Path(manifest['dev'])
    (dev / 'backend' / 'config.py').write_text("LLM_API_KEYS_BY_PROVIDER = {'google': ['dummy-test-key']}\n")
    for name in ('security_sanitizer.py', 'canary_release_policy.py'):
        (dev / 'backend' / name).write_bytes((Path(runner.__file__).parents[1] / 'backend' / name).read_bytes())
    manifest['code_files'] = runner.code_inventory(dev)
    put(path, manifest)
    plan = runner.FrozenJob(path, hashlib.sha256(path.read_bytes()).hexdigest())
    bindings = {'v4-one': plan.verify()}
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', manifest_identity('fixture', bindings),
                            allowed_bindings=bindings)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    ledger.reserve_job('job', 'batch', binding_id='v4-one', actual_hashes=plan.verify())
    helper_root = str(Path(runner.__file__).parent)
    def real_process_with_offline_graph(ledger, job_id, argv, **kwargs):
        ticket_path = argv[argv.index('--owned-job') + 1]
        script = """
import asyncio, json, socket, sys, traceback
from pathlib import Path
sys.path.insert(0, HELPER_ROOT)
# No real DNS or external network is used by this fresh subprocess fixture.
socket.getaddrinfo = lambda host, port, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', port))]
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError('external network forbidden'))
sys.path.insert(0, str(Path(HELPER_ROOT).parent / 'backend'))
import canary_release_policy
# Explicit Python test mock only, after the real external-socket denial.
canary_release_policy.require_canary_enabled = lambda: None
import quality_campaign_runner as runner
import quality_campaign_graph as graph
async def offline_graph(**kw):
    import httpx
    from google import genai
    from google.genai import types
    from quality_campaign_safety import Evidence
    def reply(request):
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {
            'role': 'model', 'parts': [{'text': 'offline public text'}]}}],
            'usageMetadata': {'promptTokenCount': 3, 'candidatesTokenCount': 2, 'totalTokenCount': 5}})
    client = genai.Client(api_key='dummy-test-key', http_options=types.HttpOptions(
        client_args={'transport': httpx.MockTransport(reply), 'trust_env': False}))
    try:
        with kw['transport']:
            call = kw['transport'].wrap_sync(lambda client, model_id, prompt, config: client.models.generate_content(
                model=model_id, contents=prompt, config=config))
            response = call(client, 'gemini-fixture', 'offline fixture prompt', types.GenerateContentConfig(max_output_tokens=100))
            assert response.text == 'offline public text'
    finally:
        client.close()
    outcome = {'job_id': kw['job_id'], 'mode': kw['mode'], 'status': 'blocked',
               'formal_publication': False, 'qualified_for_campaign': False}
    Evidence(kw['output'], kw['secrets']).save('outcome.json', outcome)
    return outcome
graph.run_normal_job = offline_graph
try:
    code = asyncio.run(runner.owned_job(Path(TICKET_PATH), storage_capacity_fd=CAPACITY_FD))
except BaseException as error:
    # Only offline fixture data; this file helps attribute an integration failure.
    diagnostic = traceback.format_exc()
    if 'SDK/runtime dependency changed' in str(error):
        ticket = json.loads(Path(TICKET_PATH).read_text())
        expected = json.loads(Path(ticket['manifest_path']).read_text())['runtime_files']
        actual = runner.runtime_inventory()
        def differences(left, right, key='runtime'):
            if isinstance(left, dict) and isinstance(right, dict):
                return [row for name in sorted(set(left) | set(right))
                    for row in differences(left.get(name), right.get(name), key + '/' + name)]
            return [] if left == right else [{'key': key, 'expected': left, 'actual': right}]
        diagnostic += json.dumps(differences(expected, actual)[:10])
    Path(TICKET_PATH).with_name('fixture-error.txt').write_text(diagnostic)
    code = 2
raise SystemExit(code)
""".replace('HELPER_ROOT', repr(helper_root)).replace('TICKET_PATH', repr(ticket_path)).replace('CAPACITY_FD', repr(kwargs['capacity_read_fd']))
        return run_reserved_process(ledger, job_id, [sys.executable, '-I', '-B', '-c', script], **kwargs)
    monkeypatch.setattr(runner, 'run_reserved_process', real_process_with_offline_graph)
    receipt = runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))
    error_path = tmp_path / 'job' / 'fixture-error.txt'
    assert not error_path.exists(), error_path.read_text() if error_path.exists() else ''
    assert receipt['status'] == 'failed'
    assert receipt['qualified_for_campaign'] is False
    state = ledger.snapshot()
    assert state['spent'] == {'jobs': 1, 'http': 1, 'transport': 1, 'tokens': 5, 'cost_microusd': 10}, json.dumps({
        'receipt': receipt, 'files': {str(p.relative_to(tmp_path / 'job')): p.read_text(errors='replace')[:8000]
            for p in (tmp_path / 'job').rglob('*') if p.is_file() and p.suffix in ('.log', '.txt')}}, ensure_ascii=False)
    assert state['jobs']['job']['status'] == 'failed'
    assert state['batches']['batch']['ended_ms'] is None
    assert state['stages']['S1'] == 'open'
    assert (tmp_path / 'job' / 'child-started.json').is_file()
    assert json.loads((tmp_path / 'job' / 'watchdog-job.cleanup.json').read_text())['process_group_absent'] is True
