"""Private SQLite campaign budget behavior; no provider or runtime access."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from quality_campaign_budget import BudgetDenied, CampaignBudget, manifest_identity

IDENTITY = {'campaign_id': 'campaign-review', 'code_sha256': 'a' * 64,
            'source_sha256': 'b' * 64, 'route_sha256': 'c' * 64}
RESERVATION = {'tokens': 6, 'cost_microusd': 3, 'billing_status': 'verified_paid',
               'billing_identity_sha256': 'd' * 64, 'reservation_basis_sha256': 'e' * 64}


def test_reopening_cannot_refund_a_consumed_reservation(tmp_path):
    path = tmp_path / 'campaign.sqlite3'
    limits = {'S1': {'tokens': 10}}
    ledger = CampaignBudget(path, IDENTITY, limits=limits)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    ledger.reserve_job('job', 'batch')
    ledger.reserve_attempt('first', 'job', **RESERVATION)
    resumed = CampaignBudget(path, IDENTITY, limits=limits)
    with pytest.raises(BudgetDenied, match='tokens'):
        resumed.reserve_attempt('second', 'job', **RESERVATION)


def active(tmp_path, *, limits=None, clock=None):
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', IDENTITY, limits=limits, clock=clock)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    ledger.reserve_job('job', 'batch')
    return ledger


def test_defaults_match_the_approved_caps():
    from quality_campaign_budget import DEFAULT_LIMITS
    assert [DEFAULT_LIMITS[stage]['jobs'] for stage in ('S1', 'S2', 'S3', 'S4')] == [4, 24, 120, 4]
    assert [DEFAULT_LIMITS[stage]['http'] for stage in ('S1', 'S2', 'S3', 'S4')] == [48, 360, 1920, 72]
    assert [DEFAULT_LIMITS[stage]['transport'] for stage in ('S1', 'S2', 'S3', 'S4')] == [48, 360, 1920, 72]
    assert [DEFAULT_LIMITS[stage]['tokens'] for stage in ('S1', 'S2', 'S3', 'S4')] == [4_000_000, 25_000_000, 126_000_000, 5_000_000]
    assert DEFAULT_LIMITS['campaign']['cost_microusd'] == 50_000_000
    assert DEFAULT_LIMITS['campaign']['tokens'] == 160_000_000
    assert DEFAULT_LIMITS['campaign']['live_seconds'] == 7 * 86400


@pytest.mark.parametrize('field', ['transport', 'http', 'tokens', 'cost_microusd'])
def test_each_stage_and_total_admission_limit_is_enforced(tmp_path, field):
    scope = 'campaign' if field == 'cost_microusd' else 'S1'
    amount = RESERVATION.get(field, 1)
    ledger = active(tmp_path, limits={scope: {field: amount}})
    ledger.reserve_attempt('first', 'job', **RESERVATION)
    with pytest.raises(BudgetDenied, match=field):
        ledger.reserve_attempt('second', 'job', **RESERVATION)
    assert len(ledger.snapshot()['attempts']) == 1


@pytest.mark.parametrize('mutation', [
    {'billing_status': 'unknown'}, {'billing_identity_sha256': ''},
    {'reservation_basis_sha256': None}, {'billing_status': 'verified_paid', 'cost_microusd': 0},
    {'billing_status': 'verified_free'}, {'tokens': 0}, {'tokens': True},
    {'cost_microusd': 0.1}, {'transport': 0, 'http': 0},
])
def test_unknown_billing_or_non_conservative_reservation_never_admits(tmp_path, mutation):
    ledger = active(tmp_path)
    with pytest.raises(BudgetDenied): ledger.reserve_attempt('attempt', 'job', **(RESERVATION | mutation))
    assert not ledger.snapshot()['attempts']


def test_unknown_usage_keeps_reservation_and_cached_input_is_not_double_counted(tmp_path):
    ledger = active(tmp_path)
    ledger.reserve_attempt('attempt', 'job', **RESERVATION)
    ledger.settle_attempt('attempt')
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'tokens': 6, 'cost_microusd': 3, 'transport': 1, 'http': 1}
    ledger.settle_attempt('attempt', actual_tokens=4, cached_input_tokens=3, usage_final=True, usage_evidence_sha256='f' * 64)
    assert ledger.snapshot()['spent']['tokens'] == 4
    assert ledger.snapshot()['spent']['cost_microusd'] == 3
    with pytest.raises(BudgetDenied, match='immutable'):
        ledger.settle_attempt('attempt', actual_tokens=0, usage_evidence_sha256='f' * 64)


def test_partial_stream_usage_never_refunds_cancelled_reservation(tmp_path):
    ledger = active(tmp_path, limits={'S1': {'tokens': 10}})
    ledger.reserve_attempt('attempt', 'job', **RESERVATION)
    ledger.settle_attempt('attempt', actual_tokens=1, actual_cost_microusd=1, usage_evidence_sha256='f' * 64)
    assert ledger.snapshot()['spent']['tokens'] == 6, 'A partial usage receipt is not provider final billing'
    assert ledger.snapshot()['spent']['cost_microusd'] == 3
    ledger.finish_job('job', status='cancelled')
    resumed = CampaignBudget(ledger.path, IDENTITY, limits={'S1': {'tokens': 10}})
    resumed.reserve_job('next-job', 'batch')
    with pytest.raises(BudgetDenied, match='tokens'):
        resumed.reserve_attempt('next-attempt', 'next-job', **RESERVATION)


def test_final_cost_does_not_promote_partial_or_missing_token_usage_to_final(tmp_path):
    ledger = active(tmp_path)
    ledger.reserve_attempt('attempt', 'job', **RESERVATION)
    ledger.settle_attempt('attempt', actual_tokens=1, usage_evidence_sha256='f' * 64)
    ledger.settle_attempt('attempt', actual_cost_microusd=2, usage_final=True, usage_evidence_sha256='f' * 64)
    assert ledger.snapshot()['spent']['tokens'] == 6
    assert ledger.snapshot()['spent']['cost_microusd'] == 2
    ledger.settle_attempt('attempt', usage_final=True, usage_evidence_sha256='f' * 64)
    assert ledger.snapshot()['spent']['tokens'] == 6
    ledger.settle_attempt('attempt', actual_tokens=3, usage_final=True, usage_evidence_sha256='f' * 64)
    assert ledger.snapshot()['spent']['tokens'] == 3


def test_token_only_or_cached_only_final_does_not_finalize_partial_cost(tmp_path):
    ledger = active(tmp_path)
    ledger.reserve_attempt('attempt', 'job', **RESERVATION)
    ledger.settle_attempt('attempt', actual_cost_microusd=1, usage_evidence_sha256='f' * 64)
    ledger.settle_attempt('attempt', actual_tokens=4, usage_final=True, usage_evidence_sha256='f' * 64)
    assert ledger.snapshot()['spent']['cost_microusd'] == 3
    ledger.settle_attempt('attempt', cached_input_tokens=3, usage_final=True, usage_evidence_sha256='f' * 64)
    assert ledger.snapshot()['spent']['tokens'] == 4
    assert ledger.snapshot()['spent']['cost_microusd'] == 3
    ledger.settle_attempt('attempt', actual_cost_microusd=2, usage_final=True, usage_evidence_sha256='f' * 64)
    assert ledger.snapshot()['spent']['cost_microusd'] == 2


@pytest.mark.parametrize('stage', ['S1', 'S2', 'S3', 'S4'])
def test_no_stage_can_borrow_http_units_from_another_stage(tmp_path, stage):
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', IDENTITY, limits={stage: {'http': 1}})
    for previous in ('S1', 'S2', 'S3', 'S4'):
        ledger.start_stage(previous)
        ledger.start_batch(previous, previous)
        ledger.reserve_job(previous, previous)
        if previous == stage: break
        ledger.finish_job(previous, status='completed')
        ledger.finish_batch(previous, cleanup_evidence_sha256='f' * 64)
        ledger.pass_stage(previous, acceptance_evidence_sha256='f' * 64)
    ledger.reserve_attempt('first', stage, **RESERVATION)
    with pytest.raises(BudgetDenied, match=stage + ' http'):
        ledger.reserve_attempt('retry', stage, **RESERVATION)


def test_campaign_http_limit_applies_across_distinct_passed_stages(tmp_path):
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', IDENTITY, limits={'campaign': {'http': 1}})
    ledger.start_stage('S1')
    ledger.start_batch('one', 'S1')
    ledger.reserve_job('one', 'one')
    ledger.reserve_attempt('one', 'one', **RESERVATION)
    ledger.finish_job('one', status='completed')
    ledger.finish_batch('one', cleanup_evidence_sha256='f' * 64)
    ledger.pass_stage('S1', acceptance_evidence_sha256='f' * 64)
    ledger.start_stage('S2')
    ledger.start_batch('two', 'S2')
    ledger.reserve_job('two', 'two')
    with pytest.raises(BudgetDenied, match='campaign http'):
        ledger.reserve_attempt('two', 'two', **RESERVATION)


@pytest.mark.parametrize('actual', [{'actual_tokens': 7}, {'actual_cost_microusd': 4}])
def test_actual_overrun_records_truth_then_blocks_even_after_reopen(tmp_path, actual):
    ledger = active(tmp_path)
    ledger.reserve_attempt('attempt', 'job', **RESERVATION)
    ledger.settle_attempt('attempt', **actual, usage_evidence_sha256='f' * 64)
    fresh = CampaignBudget(ledger.path, IDENTITY)
    assert all(fresh.snapshot()['attempts']['attempt'][key] == value for key, value in actual.items())
    with pytest.raises(BudgetDenied, match='exceeded'):
        fresh.reserve_attempt('next', 'job', **RESERVATION)
    fresh.finish_job('job', status='cancelled')
    fresh.finish_batch('batch', cleanup_evidence_sha256='f' * 64)
    assert fresh.snapshot()['spent']['http'] == 1


def test_cancel_and_abandon_never_refund_jobs_or_calls(tmp_path):
    ledger = active(tmp_path, limits={'S1': {'jobs': 2}})
    ledger.reserve_attempt('a', 'job', **RESERVATION)
    ledger.reserve_job('b', 'batch')
    with pytest.raises(BudgetDenied, match='active'): ledger.reserve_job('c', 'batch')
    ledger.finish_job('job', status='abandoned')
    ledger.finish_job('b', status='cancelled')
    with pytest.raises(BudgetDenied, match='jobs'): ledger.reserve_job('c', 'batch')
    assert ledger.snapshot()['spent']['jobs'] == 2 and ledger.snapshot()['spent']['http'] == 1


def test_stage_serialization_requires_completed_cleanup_and_explicit_pass(tmp_path):
    ledger = active(tmp_path)
    with pytest.raises(BudgetDenied, match='previous'): ledger.start_stage('S2')
    with pytest.raises(BudgetDenied, match='cleanup'): ledger.pass_stage('S1', acceptance_evidence_sha256='f' * 64)
    ledger.finish_job('job', status='completed')
    with pytest.raises(BudgetDenied, match='cleanup'): ledger.start_batch('next', 'S1')
    ledger.finish_batch('batch', cleanup_evidence_sha256='f' * 64)
    ledger.pass_stage('S1', acceptance_evidence_sha256='f' * 64)
    ledger.start_stage('S2')
    with pytest.raises(BudgetDenied): ledger.start_stage('S1')
    with pytest.raises(BudgetDenied): ledger.start_batch('bad', 'S1')


def test_first_live_not_initialization_starts_unresettable_seven_day_deadline(tmp_path):
    clock = [10.0]
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', IDENTITY, clock=lambda: clock[0])
    assert ledger.snapshot()['live_deadline_ms'] is None
    clock[0] += 30 * 86400
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    expected = int((clock[0] + 7 * 86400) * 1000)
    assert ledger.snapshot()['live_deadline_ms'] == expected
    ledger.finish_batch('batch', cleanup_evidence_sha256='f' * 64)
    clock[0] += 86400
    fresh = CampaignBudget(ledger.path, IDENTITY, clock=lambda: clock[0])
    fresh.start_batch('next', 'S1')
    assert fresh.snapshot()['live_deadline_ms'] == expected


def test_stage_wallclock_includes_cleanup_and_does_not_reset_per_batch(tmp_path):
    clock = [10.0]
    ledger = active(tmp_path, limits={'S1': {'seconds': 10}}, clock=lambda: clock[0])
    clock[0] = 13
    ledger.finish_job('job', status='completed')
    clock[0] = 16
    ledger.finish_batch('batch', cleanup_evidence_sha256='f' * 64)
    clock[0] = 100
    ledger.start_batch('next', 'S1')
    assert ledger.snapshot()['batches']['next']['deadline_ms'] == 104000
    clock[0] = 105
    with pytest.raises(BudgetDenied, match='deadline'): ledger.check()
    ledger.finish_batch('next', cleanup_evidence_sha256='f' * 64)
    assert ledger.events()[-1]['payload']['elapsed_ms'] == 5000


def test_per_job_deadline_and_clock_rollback_remain_fail_closed(tmp_path):
    clock = [10.0]
    ledger = active(tmp_path, limits={'campaign': {'job_seconds': 2}}, clock=lambda: clock[0])
    clock[0] = 13
    with pytest.raises(BudgetDenied, match='deadline'): ledger.reserve_attempt('a', 'job', **RESERVATION)
    assert ledger.snapshot()['blocked']
    clock[0] = 11
    with pytest.raises(BudgetDenied): ledger.check()
    ledger.finish_job('job', status='abandoned')
    assert ledger.snapshot()['jobs']['job']['status'] == 'abandoned'


def test_clock_rollback_is_durable_even_if_clock_later_recovers(tmp_path):
    clock = [10.0]
    ledger = active(tmp_path, clock=lambda: clock[0])
    clock[0] = 9
    with pytest.raises(BudgetDenied, match='clock rollback'): ledger.check()
    clock[0] = 11
    fresh = CampaignBudget(ledger.path, IDENTITY, clock=lambda: clock[0])
    with pytest.raises(BudgetDenied, match='clock rollback'): fresh.reserve_attempt('a', 'job', **RESERVATION)


def test_rejected_capacity_check_persists_clock_without_consuming_the_attempt(tmp_path):
    clock = [10.0]
    limits = {'S1': {'tokens': 10}}
    ledger = active(tmp_path, limits=limits, clock=lambda: clock[0])
    ledger.reserve_attempt('first', 'job', **RESERVATION)
    before = ledger.snapshot()['spent']
    clock[0] = 30
    with pytest.raises(BudgetDenied, match='tokens'):
        ledger.reserve_attempt('too-large', 'job', **RESERVATION)
    assert ledger.snapshot()['spent'] == before
    clock[0] = 20
    resumed = CampaignBudget(ledger.path, IDENTITY, limits=limits, clock=lambda: clock[0])
    with pytest.raises(BudgetDenied, match='clock rollback'):
        resumed.reserve_attempt('after-rollback', 'job', **(RESERVATION | {'tokens': 4}))
    assert resumed.snapshot()['spent'] == before


def test_identity_limits_and_events_are_immutable(tmp_path):
    ledger = active(tmp_path)
    for field in ('code_sha256', 'source_sha256', 'route_sha256'):
        with pytest.raises(BudgetDenied, match='drift'):
            CampaignBudget(ledger.path, IDENTITY | {field: 'f' * 64})
    with pytest.raises(BudgetDenied, match='drift'):
        CampaignBudget(ledger.path, IDENTITY, limits={'S1': {'jobs': 3}})
    with pytest.raises(BudgetDenied, match='reduced'):
        CampaignBudget(tmp_path / 'bad.sqlite3', IDENTITY, limits={'campaign': {'active_jobs': 3}})
    with sqlite3.connect(ledger.path) as connection:
        for sql in ('DELETE FROM campaign_events', "UPDATE campaign_events SET kind='forged'"):
            with pytest.raises(sqlite3.IntegrityError, match='append-only'): connection.execute(sql)
    assert os.stat(ledger.path).st_mode & 0o777 == 0o600


def _compete(path, count, operation, *, limits=None, crash=False, identity=None, allowed_bindings=None, extra=None):
    module = str(Path(__file__).resolve().parent)
    script = ('import json,sys,os; sys.path.insert(0,sys.argv[1]); '
              'from quality_campaign_budget import CampaignBudget,BudgetDenied; '
              'args=json.loads(sys.argv[2]); ledger=CampaignBudget(args["path"],args["identity"],limits=args["limits"],allowed_bindings=args["allowed_bindings"]); '
              '\ntry:\n ' + operation + '\nexcept BudgetDenied:\n sys.exit(3)\n'
              + ('os._exit(7)\n' if crash else 'sys.exit(0)\n'))
    processes = [subprocess.Popen([sys.executable, '-B', '-c', script, module,
        json.dumps({'path': str(path), 'identity': identity or IDENTITY, 'limits': limits, 'index': index,
                    'reservation': RESERVATION, 'allowed_bindings': allowed_bindings, **(extra or {})})],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for index in range(count)]
    results = []
    for process in processes:
        out, err = process.communicate(timeout=20)
        assert process.returncode in (0, 3, 7), (out, err)
        results.append(process.returncode)
    return results


def test_real_processes_compete_for_two_job_slots_atomically(tmp_path):
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', IDENTITY)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    results = _compete(ledger.path, 8, 'ledger.reserve_job("job-"+str(args["index"]),"batch")')
    assert results.count(0) == 2 and results.count(3) == 6
    assert len(ledger.snapshot()['jobs']) == 2


def test_real_processes_cannot_oversubscribe_attempt_tokens(tmp_path):
    limits = {'S1': {'tokens': 10}}
    ledger = active(tmp_path, limits=limits)
    results = _compete(ledger.path, 8,
        'ledger.reserve_attempt("a-"+str(args["index"]),"job",**args["reservation"])', limits=limits)
    assert results.count(0) == 1 and results.count(3) == 7
    assert ledger.snapshot()['spent']['tokens'] == 6


def test_process_crash_leaves_active_job_and_reservation_consumed(tmp_path):
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', IDENTITY)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    assert _compete(ledger.path, 1,
        'ledger.reserve_job("crashed","batch"); ledger.reserve_attempt("a","crashed",**args["reservation"])', crash=True) == [7]
    fresh = CampaignBudget(ledger.path, IDENTITY)
    assert fresh.snapshot()['jobs']['crashed']['status'] == 'active'
    assert fresh.snapshot()['spent']['tokens'] == 6
    fresh.finish_job('crashed', status='abandoned')
    assert fresh.snapshot()['spent']['http'] == 1


def test_approved_manifest_binds_each_job_and_attempt_to_its_actual_hashes(tmp_path):
    bindings = {'baseline': {key: IDENTITY[key] for key in ('code_sha256', 'source_sha256', 'route_sha256')},
                'candidate': {'code_sha256': 'f' * 64, 'source_sha256': 'b' * 64, 'route_sha256': 'c' * 64}}
    identity = {'campaign_id': 'paired-campaign'}
    for field in bindings['baseline']:
        raw = json.dumps({name: row[field] for name, row in bindings.items()}, sort_keys=True, separators=(',', ':'))
        identity[field] = hashlib.sha256(raw.encode()).hexdigest()
    ledger = CampaignBudget(tmp_path / 'manifest.sqlite3', identity, allowed_bindings=bindings)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    for name, actual in bindings.items():
        ledger.reserve_job(name, 'batch', binding_id=name, actual_hashes=actual)
        ledger.reserve_attempt(name, name, actual_hashes=actual, **RESERVATION)
    snapshot = ledger.snapshot()
    for name, actual in bindings.items():
        assert snapshot['jobs'][name]['actual_hashes'] == actual
        assert snapshot['attempts'][name]['actual_hashes'] == actual
    with pytest.raises(BudgetDenied, match='actual'):
        ledger.reserve_attempt('wrong', 'baseline', actual_hashes=bindings['candidate'], **RESERVATION)
    with pytest.raises(BudgetDenied):
        ledger.reserve_attempt('missing', 'baseline', **RESERVATION)
    changed = copy.deepcopy(bindings)
    changed['candidate']['code_sha256'] = 'a' * 64
    with pytest.raises(BudgetDenied, match='manifest'):
        CampaignBudget(ledger.path, identity, allowed_bindings=changed)


def failed_candidate(tmp_path, *, clock=None, limits=None, status='failed', cleanup=True):
    bindings = {
        'baseline': {key: IDENTITY[key] for key in ('code_sha256', 'source_sha256', 'route_sha256')},
        'candidate1': {'code_sha256': 'f' * 64, 'source_sha256': 'b' * 64, 'route_sha256': 'c' * 64},
        'candidate1-other-source': {'code_sha256': 'f' * 64, 'source_sha256': '0' * 64, 'route_sha256': 'c' * 64},
    }
    identity = manifest_identity('revision-campaign', bindings)
    ledger = CampaignBudget(tmp_path / 'revision.sqlite3', identity, allowed_bindings=bindings, clock=clock, limits=limits)
    ledger.start_stage('S1')
    ledger.start_batch('first-batch', 'S1')
    ledger.reserve_job('failed-job', 'first-batch', binding_id='candidate1', actual_hashes=bindings['candidate1'])
    ledger.reserve_attempt('first-attempt', 'failed-job', actual_hashes=bindings['candidate1'], **RESERVATION)
    if status is not None: ledger.finish_job('failed-job', status=status)
    if cleanup: ledger.finish_batch('first-batch', cleanup_evidence_sha256='d' * 64)
    return ledger, identity, bindings


def candidate_revision():
    return {'candidate2': {'parent_binding_id': 'candidate1', 'code_sha256': 'e' * 64,
                           'source_sha256': 'b' * 64, 'route_sha256': 'c' * 64}}


def register_revision(ledger, **overrides):
    return ledger.register_s1_candidate_revision(**{
        'revisions': candidate_revision(), 'failed_job_id': 'failed-job',
        'repair_evidence_sha256': 'd' * 64, **overrides})


def test_candidate_revision_reopens_original_manifest_without_refunding_or_rewriting(tmp_path):
    clock = [10.0]
    limits = {'S1': {'tokens': 12, 'seconds': 10}}
    ledger, identity, bindings = failed_candidate(tmp_path, clock=lambda: clock[0], limits=limits, cleanup=False)
    clock[0] = 14
    ledger.finish_batch('first-batch', cleanup_evidence_sha256='d' * 64)
    original_events = ledger.events()
    original = ledger.snapshot()
    clock[0] = 16
    register_revision(ledger)
    reopened = CampaignBudget(ledger.path, identity, allowed_bindings=bindings, clock=lambda: clock[0], limits=limits)
    snapshot = reopened.snapshot()
    assert reopened.events()[:len(original_events)] == original_events
    assert snapshot['spent'] == original['spent']
    assert snapshot['live_deadline_ms'] == original['live_deadline_ms']
    assert snapshot['jobs'] == original['jobs'] and snapshot['attempts'] == original['attempts']
    assert reopened.bindings == bindings, 'The initial manifest must remain immutable'
    expected = {key: value for key, value in candidate_revision()['candidate2'].items() if key != 'parent_binding_id'}
    reopened.start_batch('repaired-batch', 'S1')
    assert reopened.snapshot()['batches']['repaired-batch']['deadline_ms'] == 22000
    reopened.reserve_job('repaired-job', 'repaired-batch', binding_id='candidate2', actual_hashes=expected)
    reopened.reserve_attempt('repaired-attempt', 'repaired-job', actual_hashes=expected, **RESERVATION)
    assert reopened.snapshot()['spent'] == {'jobs': 2, 'tokens': 12, 'cost_microusd': 6, 'transport': 2, 'http': 2}
    with pytest.raises(BudgetDenied, match='tokens'):
        reopened.reserve_attempt('over-budget', 'repaired-job', actual_hashes=expected, **RESERVATION)


def test_transport_only_reservation_charges_no_provider_usage_and_http_retries_charge_once(tmp_path):
    ledger = active(tmp_path)
    ledger.reserve_attempt('transport', 'job', **(RESERVATION | {'tokens': 0, 'cost_microusd': 0, 'http': 0}))
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'tokens': 0, 'cost_microusd': 0, 'transport': 1, 'http': 0}
    assert ledger.snapshot()['attempts']['transport']['billing_status'] == 'verified_paid'
    for name in ('http-first', 'http-retry'):
        ledger.reserve_attempt(name, 'job', **(RESERVATION | {'transport': 0}))
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'tokens': 12, 'cost_microusd': 6, 'transport': 1, 'http': 2}


def test_transport_only_cannot_mix_provider_usage_into_logical_counter(tmp_path):
    ledger = active(tmp_path)
    with pytest.raises(BudgetDenied):
        ledger.reserve_attempt('mixed', 'job', **(RESERVATION | {'http': 0}))
    assert ledger.snapshot()['spent']['transport'] == 0


@pytest.mark.parametrize('mutation', [
    {'tokens': 1}, {'cost_microusd': 1}, {'transport': 0},
    {'billing_status': 'unknown'}, {'billing_identity_sha256': ''}, {'reservation_basis_sha256': None},
    {'http': 1}, {'tokens': 1, 'http': 1},
])
def test_transport_only_cannot_bypass_identity_or_physical_http_reservation(tmp_path, mutation):
    ledger = active(tmp_path)
    reservation = RESERVATION | {'tokens': 0, 'cost_microusd': 0, 'http': 0} | mutation
    with pytest.raises(BudgetDenied): ledger.reserve_attempt('invalid', 'job', **reservation)
    assert not ledger.snapshot()['attempts']


@pytest.mark.parametrize('state_case', ['active', 'cleanup', 'completed', 'cancelled', 'abandoned', 'unknown-job', 'passed', 'S2'])
def test_candidate_revision_requires_failed_s1_and_complete_cleanup(tmp_path, state_case):
    status = None if state_case == 'active' else state_case if state_case in ('completed', 'cancelled', 'abandoned') else 'failed'
    cleanup = state_case not in ('active', 'cleanup')
    ledger, _, _ = failed_candidate(tmp_path, status=status, cleanup=cleanup)
    if state_case in ('passed', 'S2'):
        ledger.pass_stage('S1', acceptance_evidence_sha256='d' * 64)
    if state_case == 'S2': ledger.start_stage('S2')
    before = ledger.snapshot()
    with pytest.raises(BudgetDenied):
        register_revision(ledger, failed_job_id='missing' if state_case == 'unknown-job' else 'failed-job')
    after = ledger.snapshot()
    assert after['spent'] == before['spent']
    assert after['effective_bindings'] == before['effective_bindings']
    assert after['candidate_revision'] is None


@pytest.mark.parametrize('case', [
    'empty', 'overwrite', 'unknown-parent', 'wrong-parent-code', 'new-source', 'new-route',
    'old-baseline-code', 'old-candidate-code', 'mixed-code', 'bad-code', 'bad-proof', 'missing-hash',
])
def test_candidate_revision_rejects_binding_drift_atomically(tmp_path, case):
    ledger, _, bindings = failed_candidate(tmp_path)
    revisions = candidate_revision()
    row = revisions['candidate2']
    if case == 'empty': revisions = {}
    elif case == 'overwrite': revisions = {'candidate1': row}
    elif case == 'unknown-parent': row['parent_binding_id'] = 'missing'
    elif case == 'wrong-parent-code': row['parent_binding_id'] = 'baseline'
    elif case == 'new-source': row['source_sha256'] = '1' * 64
    elif case == 'new-route': row['route_sha256'] = '1' * 64
    elif case == 'old-baseline-code': row['code_sha256'] = bindings['baseline']['code_sha256']
    elif case == 'old-candidate-code': row['code_sha256'] = bindings['candidate1']['code_sha256']
    elif case == 'mixed-code': revisions['candidate2-extra'] = row | {'code_sha256': '2' * 64}
    elif case == 'bad-code': row['code_sha256'] = 'unverified'
    elif case == 'missing-hash': del row['route_sha256']
    before = ledger.snapshot()
    with pytest.raises(BudgetDenied):
        register_revision(ledger, revisions=revisions, repair_evidence_sha256='' if case == 'bad-proof' else 'd' * 64)
    after = ledger.snapshot()
    assert after['spent'] == before['spent']
    assert after['effective_bindings'] == bindings
    assert after['candidate_revision'] is None
    assert not any(event['kind'] == 's1_candidate_revision' for event in ledger.events())


def test_one_revision_can_copy_multiple_existing_parents_but_not_add_new_sources(tmp_path):
    ledger, identity, bindings = failed_candidate(tmp_path)
    revisions = candidate_revision()
    revisions['candidate2-other-source'] = revisions['candidate2'] | {
        'parent_binding_id': 'candidate1-other-source', 'source_sha256': '0' * 64}
    register_revision(ledger, revisions=revisions)
    reopened = CampaignBudget(ledger.path, identity, allowed_bindings=bindings)
    effective = reopened.snapshot()['effective_bindings']
    for name, actual in bindings.items(): assert effective[name] == actual
    for name, row in revisions.items():
        assert effective[name] == {key: row[key] for key in ('code_sha256', 'source_sha256', 'route_sha256')}
    revision = reopened.snapshot()['candidate_revision']
    assert revision['revisions'] == revisions
    assert revision['failed_job_id'] == 'failed-job' and revision['repair_evidence_sha256'] == 'd' * 64
    before = reopened.snapshot()['spent']
    with pytest.raises(BudgetDenied, match='already'):
        register_revision(reopened, revisions={'candidate3': revisions['candidate2'] | {'code_sha256': '2' * 64}})
    assert reopened.snapshot()['spent'] == before
    assert len([event for event in reopened.events() if event['kind'] == 's1_candidate_revision']) == 1


def test_revision_binding_rejects_actual_hash_drift_and_can_continue_into_s2(tmp_path):
    ledger, _, bindings = failed_candidate(tmp_path)
    register_revision(ledger)
    actual = ledger.snapshot()['effective_bindings']['candidate2']
    ledger.start_batch('second-batch', 'S1')
    for wrong in (None, bindings['candidate1'], actual | {'route_sha256': '1' * 64}):
        with pytest.raises(BudgetDenied, match='actual'):
            ledger.reserve_job('wrong', 'second-batch', binding_id='candidate2', actual_hashes=wrong)
    ledger.reserve_job('repaired', 'second-batch', binding_id='candidate2', actual_hashes=actual)
    with pytest.raises(BudgetDenied, match='actual'):
        ledger.reserve_attempt('wrong-attempt', 'repaired', actual_hashes=bindings['candidate1'], **RESERVATION)
    ledger.finish_job('repaired', status='completed')
    ledger.finish_batch('second-batch', cleanup_evidence_sha256='d' * 64)
    ledger.pass_stage('S1', acceptance_evidence_sha256='d' * 64)
    ledger.start_stage('S2')
    ledger.start_batch('s2-batch', 'S2')
    ledger.reserve_job('s2-job', 's2-batch', binding_id='candidate2', actual_hashes=actual)
    assert ledger.snapshot()['stage_spent']['S1']['jobs'] == 2
    assert ledger.snapshot()['stage_spent']['S2']['jobs'] == 1


def test_original_manifest_cannot_be_replaced_by_the_effective_revision_manifest(tmp_path):
    ledger, identity, bindings = failed_candidate(tmp_path)
    register_revision(ledger)
    effective = ledger.snapshot()['effective_bindings']
    for replacement in (identity, manifest_identity(identity['campaign_id'], effective)):
        with pytest.raises(BudgetDenied, match='drift'):
            CampaignBudget(ledger.path, replacement, allowed_bindings=effective)
    assert CampaignBudget(ledger.path, identity, allowed_bindings=bindings).snapshot()['candidate_revision']


@pytest.mark.parametrize('reason', ['deadline', 'rollback', 'actual-overrun'])
def test_candidate_revision_never_clears_a_blocked_ledger(tmp_path, reason):
    clock = [10.0]
    limits = {'campaign': {'live_seconds': 20}}
    ledger, identity, bindings = failed_candidate(tmp_path, clock=lambda: clock[0], limits=limits)
    if reason == 'deadline': clock[0] = 31
    elif reason == 'rollback': clock[0] = 9
    else: ledger.settle_attempt('first-attempt', actual_tokens=7, usage_evidence_sha256='d' * 64)
    with pytest.raises(BudgetDenied): register_revision(ledger)
    before = ledger.snapshot()
    assert before['blocked'] and before['candidate_revision'] is None
    clock[0] = 32
    reopened = CampaignBudget(ledger.path, identity, allowed_bindings=bindings, clock=lambda: clock[0], limits=limits)
    with pytest.raises(BudgetDenied): register_revision(reopened)
    assert reopened.snapshot()['spent'] == before['spent']
    assert reopened.snapshot()['blocked'] == before['blocked']


def test_real_processes_can_register_at_most_one_candidate_revision(tmp_path):
    ledger, identity, bindings = failed_candidate(tmp_path)
    before = ledger.snapshot()
    results = _compete(ledger.path, 6,
        'ledger.register_s1_candidate_revision(revisions={"candidate2-"+str(args["index"]):args["revision"]},failed_job_id="failed-job",repair_evidence_sha256="d"*64)',
        identity=identity, allowed_bindings=bindings, extra={'revision': candidate_revision()['candidate2']})
    assert results.count(0) == 1 and results.count(3) == 5
    after = CampaignBudget(ledger.path, identity, allowed_bindings=bindings).snapshot()
    assert len(after['effective_bindings']) == len(bindings) + 1
    assert after['spent'] == before['spent'] and after['live_deadline_ms'] == before['live_deadline_ms']


def test_check_and_snapshot_do_not_decode_an_unchanged_verified_history(tmp_path, monkeypatch):
    import quality_campaign_budget as budget_module
    ledger = active(tmp_path)
    for _ in range(250): ledger.check()
    ledger.snapshot()
    decoded = []
    original_loads = budget_module.json.loads
    def observed_loads(value, *args, **kwargs):
        decoded.append(value)
        return original_loads(value, *args, **kwargs)
    monkeypatch.setattr(budget_module.json, 'loads', observed_loads)
    ledger.check()
    assert len(decoded) <= 4, 'Each check must validate init and replay only the committed tail, not the whole history'
    decoded.clear()
    ledger.snapshot()
    assert len(decoded) <= 4


def test_warm_instance_observes_other_instance_consumption_and_revision(tmp_path):
    ledger, identity, bindings = failed_candidate(tmp_path, limits={'S1': {'tokens': 10}})
    warm = CampaignBudget(ledger.path, identity, allowed_bindings=bindings, limits={'S1': {'tokens': 10}})
    warm.snapshot()
    register_revision(ledger)
    actual = candidate_revision()['candidate2'].copy()
    del actual['parent_binding_id']
    warm.start_batch('second-batch', 'S1')
    warm.reserve_job('second-job', 'second-batch', binding_id='candidate2', actual_hashes=actual)
    ledger.reserve_attempt('second-attempt', 'second-job', actual_hashes=actual, **(RESERVATION | {'tokens': 4}))
    with pytest.raises(BudgetDenied, match='tokens'):
        warm.reserve_attempt('over-budget', 'second-job', actual_hashes=actual, **(RESERVATION | {'tokens': 1}))
    assert warm.snapshot()['spent']['tokens'] == 10
    assert warm.snapshot() == CampaignBudget(ledger.path, identity, allowed_bindings=bindings, limits={'S1': {'tokens': 10}}).snapshot()


def test_warm_instance_observes_external_clock_watermark_and_durable_block(tmp_path):
    clock = [10.0]
    ledger = active(tmp_path, clock=lambda: clock[0])
    ledger.snapshot()
    other = CampaignBudget(ledger.path, IDENTITY, clock=lambda: clock[0])
    clock[0] = 30
    other.check()
    clock[0] = 20
    with pytest.raises(BudgetDenied, match='clock rollback'): ledger.check()
    clock[0] = 40
    with pytest.raises(BudgetDenied, match='clock rollback'): other.check()
    assert ledger.snapshot()['blocked'] == other.snapshot()['blocked'] == 'clock rollback'


def test_rollback_after_insert_leaves_no_phantom_state_or_clock(tmp_path, monkeypatch):
    clock = [10.0]
    ledger = active(tmp_path, limits={'S1': {'tokens': 10}}, clock=lambda: clock[0])
    ledger.reserve_attempt('first', 'job', **RESERVATION)
    before = ledger.snapshot()
    append = ledger._append
    def fail_after_insert(connection, state, now, kind, payload):
        append(connection, state, now, kind, payload)
        if kind == 'attempt_reserve': raise RuntimeError('simulated action failure after SQL insert')
    clock[0] = 30
    with monkeypatch.context() as patch:
        patch.setattr(ledger, '_append', fail_after_insert)
        with pytest.raises(RuntimeError, match='simulated'):
            ledger.reserve_attempt('second', 'job', **(RESERVATION | {'tokens': 4}))
    assert ledger.snapshot() == before
    clock[0] = 20
    ledger.reserve_attempt('second', 'job', **(RESERVATION | {'tokens': 4}))
    assert ledger.snapshot()['spent']['tokens'] == 10


@pytest.mark.parametrize('capacity_denial', [False, True])
def test_failed_commit_cannot_publish_admission_or_denial_watermark(tmp_path, monkeypatch, capacity_denial):
    clock = [10.0]
    ledger = active(tmp_path, limits={'S1': {'tokens': 10}}, clock=lambda: clock[0])
    ledger.reserve_attempt('first', 'job', **RESERVATION)
    before = ledger.snapshot()
    connect = ledger._connect
    class FailedCommit:
        def __init__(self): self.connection = connect()
        def __getattr__(self, name): return getattr(self.connection, name)
        def commit(self): raise sqlite3.OperationalError('simulated commit failure')
    clock[0] = 30
    with monkeypatch.context() as patch:
        patch.setattr(ledger, '_connect', FailedCommit)
        with pytest.raises(sqlite3.OperationalError, match='simulated'):
            ledger.reserve_attempt('second', 'job', **(RESERVATION | {'tokens': 6 if capacity_denial else 4}))
    assert ledger.snapshot() == before
    clock[0] = 20
    ledger.reserve_attempt('second', 'job', **(RESERVATION | {'tokens': 4}))
    assert ledger.snapshot()['spent']['tokens'] == 10


def test_caller_cannot_mutate_warm_state_through_nested_readback(tmp_path):
    ledger, identity, bindings = failed_candidate(tmp_path)
    register_revision(ledger)
    baseline = ledger.snapshot()
    changed = ledger.snapshot()
    changed['jobs']['failed-job']['status'] = 'active'
    changed['attempts']['first-attempt']['tokens'] = 0
    changed['effective_bindings']['candidate2']['code_sha256'] = '0' * 64
    changed['candidate_revision']['revisions']['candidate2']['source_sha256'] = '0' * 64
    changed['stages']['S1'] = 'passed'
    for event in ledger.events():
        if event['kind'] == 's1_candidate_revision':
            event['payload']['revisions']['candidate2']['code_sha256'] = '0' * 64
    assert ledger.snapshot() == baseline
    assert CampaignBudget(ledger.path, identity, allowed_bindings=bindings).snapshot() == baseline


@pytest.mark.parametrize('field', ['identity', 'limits', 'allowed_bindings'])
def test_warm_cache_does_not_hide_initial_configuration_drift(tmp_path, field):
    ledger = active(tmp_path)
    ledger.snapshot()
    if field == 'identity': ledger.config['identity']['source_sha256'] = '0' * 64
    elif field == 'limits': ledger.config['limits']['S1']['jobs'] = 3
    else: ledger.config['allowed_bindings']['default']['source_sha256'] = '0' * 64
    with pytest.raises(BudgetDenied, match='drift'): ledger.check()


def test_warm_cache_rejects_an_unknown_external_event(tmp_path):
    ledger = active(tmp_path, clock=lambda: 10)
    ledger.snapshot()
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('INSERT INTO campaign_events(at_ms,kind,payload) VALUES (?,?,?)',
            (10000, 'unknown-external-event', json.dumps({'binding_sha256': ledger.binding, 'stage': 'S1'})))
    for read in (ledger.check, ledger.snapshot, ledger.events):
        with pytest.raises(BudgetDenied, match='unknown ledger event'): read()
