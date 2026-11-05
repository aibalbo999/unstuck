"""Independent runner receipt-binding cases; private fixtures, no child/network."""
import asyncio
import copy
import json
from pathlib import Path

import pytest
import quality_campaign_runner as runner
from test_quality_campaign_runner import storage_review
from quality_campaign_wire import ReplayAbort
from test_quality_campaign_runner import frozen, reserved


def claim_for(ledger):
    job = ledger.snapshot()['jobs']['job']
    return {'job_id': 'job', 'ledger_binding_sha256': ledger.binding,
            'deadline_ms': job['deadline_ms'], 'actual_hashes': job['actual_hashes']}


def parent_process_result(tmp_path, ledger, *, mutate=None, skip_claim=False):
    output = tmp_path / 'job'
    claim = claim_for(ledger)
    cleanup = {'version': 1, 'job_id': 'job', 'ledger_binding_sha256': ledger.binding,
        'deadline_ms': claim['deadline_ms'], 'command_returncode': 0,
        'pgid': 123456, 'guardian_reaped': True, 'process_group_absent': True,
        'stop_reason': 'exited', 'signal_permission_denials': []}
    if mutate:
        mutate(claim, cleanup)
    if not skip_claim:
        runner.exclusive_json(tmp_path / 'campaign.sqlite3.job.watchdog-started.json', claim)
    cleanup_path = output / 'watchdog-job.cleanup.json'
    digest = runner.exclusive_json(cleanup_path, cleanup)
    reports = output / 'reports'
    reports.mkdir(mode=0o700)
    artifacts = {}
    for field, key, raw in (
        ('html_key', 'fixture.html', b'<html><body>Offline diagnostic fixture</body></html>'),
        ('md_key', 'fixture.md', b'# Offline diagnostic fixture\n'),
        ('data_key', 'fixture.data.json', b'{"fixture":true,"qualified_for_campaign":false}'),
    ):
        (reports / key).write_bytes(raw)
        artifacts[field] = {'key': key, 'bytes': len(raw), 'sha256': runner.sha(raw)}
    runner.exclusive_json(output / 'outcome.json', {'status': 'published', 'job_id': 'job',
        'mode': 'v4', 'formal_publication': False, 'qualified_for_campaign': False,
        'frozen_verified': True, 'publication': {'classification': 'diagnostic_no_action'},
        'artifacts': artifacts})
    return {'cleanup_verified': True, 'cleanup_path': str(cleanup_path),
        'cleanup_evidence_sha256': digest, 'cleanup': cleanup,
        'returncode': 0, 'status': 'exited'}


def test_real_watchdog_field_shape_can_complete_private_pipeline(tmp_path, monkeypatch):
    plan, _, ledger = reserved(tmp_path)
    monkeypatch.setattr(runner, 'run_reserved_process', lambda *a, **k:
        parent_process_result(tmp_path, ledger))
    result = runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))
    assert result['status'] == 'private_pipeline_completed'
    assert result['qualified_for_campaign'] is False


def test_parent_completion_receipt_binds_captured_generation_configuration(tmp_path, monkeypatch):
    plan, _, ledger = reserved(tmp_path)
    raw = b'{"attempt_id":"fixture","config":{"temperature":0}}\n'
    def process(*args, **kwargs):
        result = parent_process_result(tmp_path, ledger)
        (tmp_path / 'job' / 'prompts.jsonl').write_bytes(raw)
        return result
    monkeypatch.setattr(runner, 'run_reserved_process', process)
    result = runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))
    assert result.get('prompts_sha256') == runner.sha(raw)


@pytest.mark.parametrize('case', ['missing_claim', 'claim_deadline', 'claim_hashes',
                                'cleanup_deadline', 'cleanup_returncode', 'cleanup_stop_reason'])
def test_parent_rejects_cleanup_not_bound_to_original_admission(tmp_path, monkeypatch, case):
    plan, _, ledger = reserved(tmp_path)
    def mutate(claim, cleanup):
        if case == 'claim_deadline': claim['deadline_ms'] += 1
        if case == 'claim_hashes': claim['actual_hashes']['source_sha256'] = '0' * 64
        if case == 'cleanup_deadline': cleanup['deadline_ms'] += 1
        if case == 'cleanup_returncode': cleanup['command_returncode'] = -9
        if case == 'cleanup_stop_reason': cleanup['stop_reason'] = 'monotonic_deadline'
    monkeypatch.setattr(runner, 'run_reserved_process', lambda *a, **k:
        parent_process_result(tmp_path, ledger, mutate=mutate, skip_claim=case == 'missing_claim'))
    with pytest.raises(ReplayAbort):
        runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'


@pytest.mark.parametrize('case', ['deadline', 'hashes'])
def test_child_rejects_wrong_admission_claim_before_environment(tmp_path, monkeypatch, case):
    plan, _, ledger = reserved(tmp_path)
    output = tmp_path / 'job'
    output.mkdir(mode=0o700)
    claim = claim_for(ledger)
    if case == 'deadline': claim['deadline_ms'] += 1
    if case == 'hashes': claim['actual_hashes']['code_sha256'] = '0' * 64
    runner.exclusive_json(tmp_path / 'campaign.sqlite3.job.watchdog-started.json', claim)
    ticket = output / 'child-ticket.json'
    runner.exclusive_json(ticket, {'manifest_path': str(plan.path), 'manifest_sha256': plan.expected_sha,
        'ledger_pin': runner.ledger_pin(ledger), 'job_id': 'job', 'output': str(output)})
    monkeypatch.setattr(runner, 'child_environment', lambda *a, **k:
        pytest.fail('Wrong admission claim reached credential/environment setup'))
    with pytest.raises(ReplayAbort):
        asyncio.run(runner.owned_job(ticket))


def test_parent_rechecks_original_ledger_inode_after_child(tmp_path, monkeypatch):
    plan, _, ledger = reserved(tmp_path)
    def finish(*args, **kwargs):
        result = parent_process_result(tmp_path, ledger)
        old = tmp_path / 'old-private-campaign.sqlite3'
        ledger.path.rename(old)
        ledger.path.write_bytes(old.read_bytes())
        ledger.path.chmod(0o600)
        return result
    monkeypatch.setattr(runner, 'run_reserved_process', finish)
    with pytest.raises(ReplayAbort):
        runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))


def test_real_report_template_extension_cannot_change_without_frozen_rejection(tmp_path):
    plan, manifest = frozen(tmp_path)
    template = Path(manifest['dev']) / 'backend' / 'templates' / 'report.html.j2'
    template.parent.mkdir()
    template.write_text('<h1>Frozen report changed after registration</h1>')
    with pytest.raises(ReplayAbort):
        plan.verify()


@pytest.mark.parametrize('case', ['failed_returncode', 'cancelled', 'wrong_mode', 'missing_outcome'])
def test_failed_or_unbound_outcome_is_never_completed(tmp_path, monkeypatch, case):
    plan, _, ledger = reserved(tmp_path)
    def finish(*args, **kwargs):
        def mutate(claim, cleanup):
            if case == 'failed_returncode': cleanup['command_returncode'] = 2
            if case == 'cancelled':
                cleanup['command_returncode'] = -9
                cleanup['stop_reason'] = 'cancelled'
        result = parent_process_result(tmp_path, ledger, mutate=mutate)
        if case == 'failed_returncode': result['returncode'] = 2
        if case == 'cancelled': result.update(status='stopped', returncode=-9)
        outcome = tmp_path / 'job' / 'outcome.json'
        if case == 'wrong_mode':
            row = json.loads(outcome.read_text())
            row['mode'] = 'v1'
            outcome.write_text(json.dumps(row))
        if case == 'missing_outcome': outcome.unlink()
        return result
    monkeypatch.setattr(runner, 'run_reserved_process', finish)
    result = runner.execute_reserved_job(plan, ledger, 'job', storage_budget=storage_review(plan, ledger))
    assert result['status'] == 'failed'
    assert ledger.snapshot()['jobs']['job']['status'] == 'failed'
"""Narrow runtime-file inventory checks with fake distributions, no real secrets."""
from importlib import metadata
from pathlib import Path

import pytest
import quality_campaign_runner as runner
from test_quality_campaign_runner import storage_review
from quality_campaign_wire import ReplayAbort


def fixture_distribution(tmp_path, monkeypatch, *, code=True, extras=()):
    root = tmp_path / 'site-packages'
    package = root / 'fixture_runtime'
    package.mkdir(parents=True)
    dist_info = root / 'fixture_runtime-1.0.dist-info'
    dist_info.mkdir()
    (dist_info / 'METADATA').write_text('Metadata-Version: 2.1\nName: fixture-runtime\nVersion: 1.0\n')
    paths = ['fixture_runtime-1.0.dist-info/METADATA', 'fixture_runtime-1.0.dist-info/RECORD']
    if code:
        (package / '__init__.py').write_text('VERSION = 1\n')
        paths.insert(0, 'fixture_runtime/__init__.py')
    paths.extend(extras)
    (dist_info / 'RECORD').write_text(''.join(path + ',,\n' for path in paths))
    distribution = metadata.Distribution.at(dist_info)
    monkeypatch.setattr(runner, 'RUNTIME_PACKAGES', ('fixture-runtime',))
    monkeypatch.setattr(runner.metadata, 'distribution', lambda name: distribution)
    return package, dist_info


def test_recorded_python_bytes_drift_is_detected(tmp_path, monkeypatch):
    package, _ = fixture_distribution(tmp_path, monkeypatch)
    before = runner.runtime_inventory()
    (package / '__init__.py').write_text('VERSION = 2\n')
    assert runner.runtime_inventory() != before


def test_metadata_only_distribution_cannot_claim_runtime_code_is_frozen(tmp_path, monkeypatch):
    fixture_distribution(tmp_path, monkeypatch, code=False)
    with pytest.raises(ReplayAbort):
        runner.runtime_inventory()


@pytest.mark.parametrize('kind', ['relative', 'absolute'])
def test_record_path_escape_is_rejected_before_reading_external_file(tmp_path, monkeypatch, kind):
    outside = tmp_path / 'outside.py'
    outside.write_text('# Harmless sentinel, not a credential\n')
    fixture_distribution(tmp_path, monkeypatch,
        extras=('../outside.py' if kind == 'relative' else str(outside),))
    original = runner.os.open
    def no_outside_read(path, *args, **kwargs):
        if Path(path).resolve() == outside:
            pytest.fail('Distribution inventory attempted to read outside its install root')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(runner.os, 'open', no_outside_read)
    with pytest.raises(ReplayAbort):
        runner.runtime_inventory()


def test_new_python_file_in_owned_package_changes_runtime_identity(tmp_path, monkeypatch):
    package, _ = fixture_distribution(tmp_path, monkeypatch)
    before = runner.runtime_inventory()
    (package / 'unrecorded_extra.py').write_text('VERSION = 2\n')
    assert runner.runtime_inventory() != before
