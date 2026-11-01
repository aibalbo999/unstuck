"""Offline exact-denominator/cutoff reporting, not provider quality evidence."""
import copy
import json

import pytest

from quality_campaign_statistics import campaign_statistics
from test_quality_campaign_acceptance import manifest, result


START = 1_000_000
CUTOFF = START + 4_000_000


def timed(row, *, started=START, duration=1000, **changes):
    return result(row, duration_ms=duration, started_at_ms=started, finished_at_ms=started + duration, **changes)


def test_original_152_and_stage_mode_denominators_keep_missing_jobs():
    samples = manifest()
    values = {samples[0]['job_id']: timed(samples[0])}
    report = campaign_statistics(samples, values, cutoff_ms=CUTOFF)
    overall = report['overall']
    assert overall['registered'] == 152 and overall['supplied_terminal'] == 1
    assert overall['terminal_by_cutoff'] == 1 and overall['missing'] == 151
    assert overall['quality']['qualified'] == 1 and overall['quality']['unobserved'] == 151
    assert report['stages']['S1']['registered'] == 4 and report['stages']['S3']['registered'] == 120
    assert report['stages']['S3']['modes']['v1']['registered'] == 30
    assert report['modes']['v4']['registered'] == 41 and report['modes']['v1']['registered'] == 37
    assert report['formal_publication'] is False and report['qualified_for_campaign'] is False


def test_raw_classes_do_not_override_shared_qualification_and_pressure_preregistration():
    samples = manifest()
    selected = [row for row in samples if row['stage'] == 'S3'][:6]
    values = {row['job_id']: timed(row) for row in selected}
    changes = ({'classification': 'verified_no_action'}, {'classification': 'diagnostic_no_action'},
               {'classification': 'research_with_limitations'}, {'classification': 'cancelled', 'completed': False, 'published': False},
               {'classification': 'failed', 'completed': False, 'published': False}, {'audit_passed': False})
    for row, change in zip(selected, changes): values[row['job_id']].update(change)
    overall = campaign_statistics(samples, values, cutoff_ms=CUTOFF)['overall']
    assert overall['quality']['qualified'] == 1 and overall['quality']['known_unqualified'] == 5
    assert overall['classifications']['verified_research'] == 1
    assert overall['classifications']['verified_no_action'] == 1
    assert overall['classifications']['diagnostic_no_action'] == 1
    assert overall['classifications']['research_with_limitations'] == 1
    assert overall['classifications']['cancelled'] == 1 and overall['classifications']['failed'] == 1
    pressure = next(row for row in samples if row['stage'] == 'S2')
    pressure['expected'] = 'diagnostic'
    values = {pressure['job_id']: timed(pressure, classification='diagnostic_no_action')}
    group = campaign_statistics(samples, values, cutoff_ms=CUTOFF)['overall']
    assert group['quality']['qualified'] == 0 and group['quality']['registered'] == 151
    assert group['pressure']['registered'] == 1 and group['pressure']['correct'] == 1


def test_zero_observations_never_become_zero_over_zero_success_or_confidence():
    report = campaign_statistics(manifest(), {}, cutoff_ms=CUTOFF)
    quality = report['overall']['quality']
    assert quality['observed_rate']['value'] is None and quality['observed_rate']['wilson_95'] is None
    assert quality['pilot_rate']['value'] == 0 and quality['pilot_rate']['wilson_95'] is None
    assert quality['pilot_rate']['interpretation'] == 'attainment_to_date_not_final_failure_rate'
    assert report['overall']['tokens']['observed_final_tokens'] is None


def test_evidence_validation_is_shared_and_rejects_truthy_booleans():
    samples = manifest()
    values = {samples[0]['job_id']: timed(samples[0], artifact_verified=1)}
    with pytest.raises(ValueError, match='invalid_result'):
        campaign_statistics(samples, values, cutoff_ms=CUTOFF)


def test_post_cutoff_and_untimed_results_are_not_counted_as_cutoff_confirmed():
    samples = manifest()
    values = {samples[0]['job_id']: timed(samples[0], started=CUTOFF, duration=1),
              samples[1]['job_id']: result(samples[1]), samples[2]['job_id']: timed(samples[2])}
    overall = campaign_statistics(samples, values, cutoff_ms=CUTOFF)['overall']
    assert overall['supplied_terminal'] == 3 and overall['terminal_by_cutoff'] == 1
    assert overall['after_cutoff'] == 1 and overall['chronology_unverified'] == 1
    assert overall['quality']['qualified'] == 1 and overall['quality']['unobserved'] == 151
    assert overall['duration_ms']['count'] == 1


def test_statistical_summary_is_finite_and_does_not_mutate_evidence():
    samples = manifest()
    values = {samples[0]['job_id']: timed(samples[0])}
    before = copy.deepcopy((samples, values))
    report = campaign_statistics(samples, values, cutoff_ms=CUTOFF)
    assert (samples, values) == before
    assert json.loads(json.dumps(report, allow_nan=False)) == report
    assert report['provenance']['samples_sha256'] and report['provenance']['results_sha256']


def test_window_completion_separates_terminal_failure_censoring_and_unknown_age():
    samples = manifest()
    chosen = [row for row in samples if row['stage'] == 'S3'][:6]
    cutoff = 2_000_000
    values = {
        chosen[0]['job_id']: timed(chosen[0], started=0, duration=900_000),
        chosen[1]['job_id']: timed(chosen[1], started=0, duration=900_001),
        chosen[2]['job_id']: timed(chosen[2], started=0, duration=600_000, completed=False, published=False, classification='cancelled'),
        chosen[3]['job_id']: timed(chosen[3], started=cutoff - 100_000, duration=500_000),
        chosen[4]['job_id']: timed(chosen[4], started=cutoff - 1_000_000, duration=2_000_000),
        chosen[5]['job_id']: timed(chosen[5], started=cutoff + 1, duration=1000),
    }
    windows = campaign_statistics(samples, values, cutoff_ms=cutoff)['overall']['completion_minutes']
    assert windows['15']['observed_window'] == 4 and windows['15']['completed'] == 1
    assert windows['15']['right_censored'] == 1 and windows['15']['not_started_by_cutoff'] == 1
    assert windows['15']['age_unknown'] == 146
    assert windows['15']['observed_completion_rate']['value'] == .25
    assert windows['15']['registered_attainment']['denominator'] == 152
    assert windows['30']['observed_window'] == 3 and windows['30']['completed'] == 2
    assert windows['30']['right_censored'] == 2
    assert windows['60']['completed'] == 2


def test_latency_nearest_rank_keeps_slow_failed_and_cancelled_jobs():
    samples = manifest()
    values = {row['job_id']: timed(row, duration=duration, classification='cancelled' if i == 3 else 'verified_research',
                                   completed=i != 3, published=i != 3)
              for i, (row, duration) in enumerate(zip(samples[:4], (1000, 2000, 3000, 60000)))}
    latency = campaign_statistics(samples, values, cutoff_ms=CUTOFF)['overall']['duration_ms']
    assert latency == {'count': 4, 'p50': 2000, 'p95': 60000, 'method': 'nearest_rank'}


def test_wilson_29_of_30_is_nominal_and_incomplete_pilot_interval_is_not_fabricated():
    samples = manifest()
    chosen = [row for row in samples if row['stage'] == 'S3' and row['mode'] == 'v1']
    values = {row['job_id']: timed(row) for row in chosen}
    values[chosen[0]['job_id']].update(classification='failed', completed=False, published=False)
    report = campaign_statistics(samples, values, cutoff_ms=CUTOFF)
    quality = report['stages']['S3']['modes']['v1']['quality']
    assert quality['observed_rate']['wilson_95'] == pytest.approx([.833296090085, .994091409619], abs=1e-10)
    assert quality['pilot_rate']['wilson_95'] == quality['observed_rate']['wilson_95']
    assert report['overall']['quality']['pilot_rate']['wilson_95'] is None
    assert report['correlation']['cluster_adjusted_intervals'] is False
    assert report['correlation']['long_term_success_lower_bound'] is False
    values[chosen[0]['job_id']] = timed(chosen[0], source_decision_reviewed=False, important_claims_verified=False)
    quality = campaign_statistics(samples, values, cutoff_ms=CUTOFF)['stages']['S3']['modes']['v1']['quality']
    assert quality['review_pending'] == 1 and quality['known_unqualified'] == 0
    assert quality['observed_rate']['denominator'] == 29 and quality['pilot_rate']['wilson_95'] is None


@pytest.mark.parametrize('change', [{'started_at_ms': True}, {'finished_at_ms': -1}, {'finished_at_ms': START + 2},
                                   {'finished_at_ms': None}, {'started_at_ms': START + 1001}])
def test_malformed_chronology_fails_closed(change):
    samples = manifest()
    row = timed(samples[0]) | change
    with pytest.raises(ValueError, match='chronology'):
        campaign_statistics(samples, {samples[0]['job_id']: row}, cutoff_ms=CUTOFF)


@pytest.mark.parametrize('cutoff', [None, True, -1, 1.5, float('nan')])
def test_invalid_cutoff_never_leaks_nonfinite_statistics(cutoff):
    with pytest.raises(ValueError, match='cutoff'):
        campaign_statistics(manifest(), {}, cutoff_ms=cutoff)


def ledger_for(tmp_path, row):
    from quality_campaign_budget import CampaignBudget
    identity = {'campaign_id': 'stats-private-fixture', 'code_sha256': 'a' * 64,
                'source_sha256': row['source_sha256'], 'route_sha256': row['route_sha256']}
    ledger = CampaignBudget(tmp_path / 'ledger.sqlite3', identity, clock=lambda: START / 1000)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    ledger.reserve_job(row['job_id'], 'batch')
    return ledger


def reserve(ledger, job_id, attempt, *, transport=1, http=1):
    ledger.reserve_attempt(attempt, job_id, tokens=100 if http else 0, cost_microusd=100 if http else 0,
        billing_status='verified_paid', billing_identity_sha256='d' * 64, reservation_basis_sha256='e' * 64,
        transport=transport, http=http)


def test_real_ledger_snapshot_separates_final_observed_partial_reserved_and_cached_input(tmp_path):
    samples = manifest()
    row = samples[0]
    ledger = ledger_for(tmp_path, row)
    reserve(ledger, row['job_id'], 'logical', transport=1, http=0)
    reserve(ledger, row['job_id'], 'first', transport=0, http=1)
    ledger.settle_attempt('first', actual_tokens=60, cached_input_tokens=40, usage_final=True, usage_evidence_sha256='f' * 64)
    reserve(ledger, row['job_id'], 'second', transport=0, http=1)
    ledger.settle_attempt('second', actual_tokens=20, cached_input_tokens=10, usage_evidence_sha256='f' * 64)
    snapshot = ledger.snapshot()
    before = copy.deepcopy(snapshot)
    values = {row['job_id']: timed(row, tokens=None)}
    report = campaign_statistics(samples, values, cutoff_ms=CUTOFF, ledger_snapshot=snapshot)
    tokens = report['ledger_tokens']
    assert tokens['status'] == 'observed_snapshot'
    assert tokens['initial_reserved'] == 200 and tokens['observed_actual'] == 80
    assert tokens['charged'] == 160 and tokens['held_above_observed'] == 80
    assert tokens['final_actual'] == 60 and tokens['http_events'] == 2 and tokens['final_attempts'] == 1
    assert report['overall']['tokens']['observed_final_tokens'] is None
    assert snapshot == before


def test_missing_ledger_usage_is_unknown_while_reservation_remains_charged(tmp_path):
    samples = manifest()
    ledger = ledger_for(tmp_path, samples[0])
    reserve(ledger, samples[0]['job_id'], 'unknown')
    tokens = campaign_statistics(samples, {}, cutoff_ms=CUTOFF, ledger_snapshot=ledger.snapshot())['ledger_tokens']
    assert tokens['observed_actual'] is None and tokens['usage_unknown_attempts'] == 1
    assert tokens['charged'] == 100 and tokens['held_above_observed'] == 100


def test_ledger_after_cutoff_and_no_ledger_do_not_become_zero_cost(tmp_path):
    samples = manifest()
    assert campaign_statistics(samples, {}, cutoff_ms=CUTOFF)['ledger_tokens']['status'] == 'not_provided'
    ledger = ledger_for(tmp_path, samples[0])
    reserve(ledger, samples[0]['job_id'], 'after')
    report = campaign_statistics(samples, {}, cutoff_ms=START - 1, ledger_snapshot=ledger.snapshot())
    assert report['ledger_tokens']['status'] == 'after_cutoff_unverified'
    assert report['ledger_tokens']['charged'] is None


def test_contradictory_ledger_totals_or_foreign_jobs_are_not_used(tmp_path):
    samples = manifest()
    ledger = ledger_for(tmp_path, samples[0])
    reserve(ledger, samples[0]['job_id'], 'attempt')
    snapshot = ledger.snapshot()
    snapshot['spent']['tokens'] = 0
    with pytest.raises(ValueError, match='ledger'):
        campaign_statistics(samples, {}, cutoff_ms=CUTOFF, ledger_snapshot=snapshot)
    snapshot = ledger.snapshot()
    snapshot['attempts']['attempt']['job_id'] = 'another-campaign-job'
    with pytest.raises(ValueError, match='ledger'):
        campaign_statistics(samples, {}, cutoff_ms=CUTOFF, ledger_snapshot=snapshot)


def test_requested_and_returned_labels_do_not_invent_fallback_or_primary_delivery():
    samples = manifest()
    row = timed(samples[0])
    row['actual_models'] = [
        {'role': '22', 'requested': 'primary-alias', 'returned': 'different-provider-version-label', 'knobs': {'max_output_tokens': 64}},
        {'role': '22', 'requested': 'other-route', 'returned': None, 'knobs': {'max_output_tokens': 64}},
        {'role': '23', 'requested': 'primary-alias', 'returned': 'different-provider-version-label', 'knobs': {'max_output_tokens': 64}},
    ]
    report = campaign_statistics(samples, {samples[0]['job_id']: row}, cutoff_ms=CUTOFF)
    models = report['models']
    assert models['observed_identity_rows'] == 3 and models['returned_identity_missing'] == 1
    assert models['role_jobs_with_multiple_requested_routes'] == 1
    assert models['first_choice']['delivery_rate'] is None and models['first_choice']['qualified_rate'] is None
    assert models['fallback']['count'] is None and models['fallback']['rate'] is None
    assert report['recovery']['status'] == 'unverified'
    assert report['recovery']['post_recovery_completion_rate'] is None


def test_quality_completion_window_does_not_count_pending_review_as_failed_quality():
    samples = manifest()
    values = {samples[0]['job_id']: timed(samples[0], source_decision_reviewed=False, important_claims_verified=False)}
    window = campaign_statistics(samples, values, cutoff_ms=CUTOFF)['overall']['completion_minutes']['15']
    assert window['observed_completion_rate']['value'] == 1
    assert window['observed_qualified_rate']['denominator'] == 0
    assert window['observed_qualified_rate']['value'] is None and window['quality_review_pending'] == 1
    values[samples[0]['job_id']] = timed(samples[0], duration=900001, source_decision_reviewed=False, important_claims_verified=False)
    window = campaign_statistics(samples, values, cutoff_ms=CUTOFF)['overall']['completion_minutes']['15']
    assert window['observed_qualified_rate']['denominator'] == 1 and window['quality_review_pending'] == 0


def test_zero_preregistered_research_is_not_labeled_a_complete_quality_pilot():
    samples = manifest()
    for row in samples:
        if row['stage'] == 'S2' and row['mode'] == 'v1': row['expected'] = 'diagnostic'
    quality = campaign_statistics(samples, {}, cutoff_ms=CUTOFF)['stages']['S2']['modes']['v1']['quality']
    assert quality['registered'] == 0 and quality['pilot_rate']['value'] is None
    assert quality['pilot_rate']['interpretation'] == 'no_preregistered_qualified_inputs'


def test_true_ledger_overrun_remains_visible_even_though_reservation_was_smaller(tmp_path):
    samples = manifest()
    ledger = ledger_for(tmp_path, samples[0])
    reserve(ledger, samples[0]['job_id'], 'overrun')
    ledger.settle_attempt('overrun', actual_tokens=150, cached_input_tokens=40, usage_evidence_sha256='f' * 64)
    tokens = campaign_statistics(samples, {}, cutoff_ms=CUTOFF, ledger_snapshot=ledger.snapshot())['ledger_tokens']
    assert tokens['initial_reserved'] == 100 and tokens['observed_actual'] == tokens['charged'] == 150
    assert tokens['over_reserved_attempts'] == 1 and tokens['campaign_blocked'] is True
    assert tokens['held_above_observed'] == 0


def test_unknown_roles_are_not_grouped_into_an_invented_fallback_role():
    samples = manifest()
    row = timed(samples[0])
    row['actual_models'] = [{'role': 'unobserved', 'requested': name, 'returned': None, 'knobs': {}} for name in ('a', 'b')]
    report = campaign_statistics(samples, {samples[0]['job_id']: row}, cutoff_ms=CUTOFF)
    assert report['models']['role_identity_unknown'] == 2
    assert report['models']['role_jobs_with_multiple_requested_routes'] == 0
    assert report['models']['fallback']['count'] is None


def test_interval_extremes_are_finite_and_never_substitute_for_missing_outcomes():
    samples = manifest()
    selected = [row for row in samples if row['stage'] == 'S3' and row['mode'] == 'v1']
    for successes in (0, 1, 15, 29, 30):
        values = {row['job_id']: timed(row, classification='verified_research' if i < successes else 'cancelled',
                                      completed=i < successes, published=i < successes)
                  for i, row in enumerate(selected)}
        rate = campaign_statistics(samples, values, cutoff_ms=CUTOFF)['stages']['S3']['modes']['v1']['quality']['pilot_rate']
        lo, hi = rate['wilson_95']
        assert 0 <= lo <= rate['value'] <= hi <= 1
        if successes == 0: assert lo == 0
        if successes == 30: assert hi == 1
