"""One real parent→watchdog→owned child→normal job→cleanup→ledger path.

Leaf model/limiter/research fixtures remain explicit. This is not provider
success, S4 formal handover, or qualification evidence.
"""
import json
from pathlib import Path
import sys

import pytest
import quality_campaign_runner as runner
from quality_campaign_budget import CampaignBudget, manifest_identity
from quality_campaign_watchdog import run_reserved_process
from test_quality_campaign_runner import fixture, put


def frozen_normal_fixture(tmp_path, mode):
    path, manifest = fixture(tmp_path)
    dev = Path(__file__).resolve().parents[1]
    manifest['dev'], manifest['code_files'] = str(dev), runner.code_inventory(dev)
    manifest['mode'], manifest['stage'] = mode, 'S2'
    source_path = Path(manifest['source']['path'])
    source = json.loads(source_path.read_text())
    source['pipeline_id'] = mode
    source['data_snapshot'].update(company_name='Offline Company', current_price=100,
        price_history={}, temporal_memory={'fixture': 'original-cutoff-memory'})
    source['data_snapshot']['daily_market_data'] = {
        'source': 'explicit offline fixture, not real market proof',
        'as_of': '2026-09-11', 'bars': [{'date': '2026-09-11', 'close': 100, 'volume': 1}]}
    manifest['source'] = put(source_path, source)
    review_path = Path(manifest['source_review']['path'])
    review = json.loads(review_path.read_text())
    review['mode'] = mode
    review['source_sha256'] = manifest['source']['sha256']
    manifest['source_review'] = put(review_path, review)
    model = 'gemini-3.6-flash'
    for field, key in [('billing_review', 'reviewed_models'), ('reservation_review', 'models')]:
        target = Path(manifest[field]['path'])
        value = json.loads(target.read_text())
        value[key] = [model] if field == 'billing_review' else {model: value[key]['gemini-fixture']}
        manifest[field] = put(target, value)
    policy_path = Path(manifest['policies']['path'])
    policy = json.loads(policy_path.read_text())['gemini-fixture']
    policy.update(billing_identity_sha256=manifest['billing_review']['sha256'],
                  reservation_basis_sha256=manifest['reservation_review']['sha256'])
    manifest['policies'] = put(policy_path, {model: policy})
    routes_path = Path(manifest['routes']['path'])
    manifest['routes'] = put(routes_path, json.loads((dev / 'backend/model_routes.json').read_text()))
    environment = Path(manifest['environment']['path'])
    environment.write_text(environment.read_text() + 'GIT_COMMIT=offline-owned-normal\nGIT_DIRTY=false\n')
    manifest['environment']['sha256'] = runner.sha(environment.read_bytes())
    put(path, manifest)
    plan = runner.FrozenJob(path, runner.sha(path.read_bytes()))
    return plan


def reserved_normal_fixture(tmp_path, mode, *, job_seconds=45):
    plan = frozen_normal_fixture(tmp_path, mode)
    bindings = {'v4-one': plan.verify()}
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', manifest_identity('fixture', bindings),
        allowed_bindings=bindings, limits={'campaign': {'job_seconds': job_seconds}})
    ledger.start_stage('S1')
    # Explicit offline prerequisite fixture only, not an actual stage approval.
    ledger.start_batch('fixture-prerequisite', 'S1')
    ledger.reserve_job('fixture-prerequisite', 'fixture-prerequisite', binding_id='v4-one', actual_hashes=plan.verify())
    ledger.finish_job('fixture-prerequisite', status='completed')
    ledger.finish_batch('fixture-prerequisite', cleanup_evidence_sha256='c' * 64)
    ledger.pass_stage('S1', acceptance_evidence_sha256='f' * 64)
    ledger.start_stage('S2')
    ledger.start_batch('batch', 'S2')
    ledger.reserve_job('job', 'batch', binding_id='v4-one', actual_hashes=plan.verify())
    return plan, ledger


@pytest.mark.parametrize('case,mode', [(case, mode) for case in ('blocked', 'published')
    for mode in ('v1', 'v2', 'v3', 'v4')] + [('published_executor', 'v4')])
def test_real_owned_normal_job_settles_only_after_parent_readback(tmp_path, monkeypatch, case, mode):
    plan, ledger = reserved_normal_fixture(tmp_path, mode)
    expected_status = 'blocked' if case == 'blocked' else 'published'
    invocations = []
    def real_owned(ledger, job_id, argv, **kwargs):
        invocations.append(list(argv))
        # Replace only the outer executable with this explicit test bootstrap.
        # The watchdog, runner.owned_job and run_normal_job are real and unchanged.
        child = Path(__file__).with_name('test_quality_campaign_owned_normal_child.py')
        return run_reserved_process(ledger, job_id, [sys.executable, '-I', '-B', str(child), argv[-1], case], **kwargs)
    monkeypatch.setattr(runner, 'run_reserved_process', real_owned)
    receipt = runner.execute_reserved_job(plan, ledger, 'job')
    output = tmp_path / 'job'
    diagnostic = output / 'offline-fixture-error.txt'
    assert not diagnostic.exists(), diagnostic.read_text() if diagnostic.exists() else ''
    assert len(invocations) == 1
    outcome = json.loads((output / 'outcome.json').read_text())
    proof = json.loads((output / 'owned-normal-test-proof.json').read_text())
    assert outcome['status'] == expected_status, json.dumps(outcome, ensure_ascii=False)
    assert proof['normal_entry_called'] and proof['sdk_clients_closed'] and proof['transport_restored']
    assert proof['mock_http_calls'] == int(case == 'blocked')
    assert proof['shared_quota_fixture_pings'] == 1
    state = ledger.snapshot()
    assert state['spent']['jobs'] == 2  # Includes the explicit prerequisite fixture.
    assert state['spent']['http'] == state['spent']['transport'] == int(case == 'blocked')
    assert state['jobs']['job']['status'] == ('completed' if expected_status == 'published' else 'failed')
    assert state['batches']['batch']['ended_ms'] is None and state['stages']['S2'] == 'open'
    assert receipt['status'] == ('private_pipeline_completed' if expected_status == 'published' else 'failed')
    assert receipt['qualified_for_campaign'] is receipt['formal_publication'] is False
    assert json.loads((output / 'parent-receipt.json').read_text()) == receipt
    cleanup_path = output / 'watchdog-job.cleanup.json'
    cleanup = json.loads(cleanup_path.read_text())
    assert cleanup['guardian_reaped'] and cleanup['process_group_absent'] and cleanup['command_returncode'] == (0 if expected_status == 'published' else 2)
    assert runner.sha(cleanup_path.read_bytes()) == receipt['cleanup_sha256']
    normal = json.loads((output / 'normal-job.json').read_text())
    data = json.loads(normal['data_snapshot'])
    assert data['analysis_input_cutoff'] == '2026-09-12T07:30:00+00:00' and data['quant_metrics']
    assert (output / 'events.jsonl').is_file()
    if case == 'blocked':
        assert (output / 'checkpoint.sqlite3').is_file() and not list(output.rglob('*.html'))
    else:
        assert runner.private_artifacts_match(output, outcome)
        snapshot = json.loads((output / 'reports' / outcome['artifacts']['data_key']['key']).read_text())
        assert not snapshot.get('generation_contract')
