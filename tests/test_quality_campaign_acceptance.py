"""Preregistered denominators and independent evidence, never model self-grading."""
import copy

import pytest

from quality_campaign_acceptance import evaluate_stage, early_stop


DIMENSIONS = ('source_faithfulness', 'mode_relevance', 'conclusion_reasoning', 'counterevidence_limits', 'readability')
CODE = 'a' * 64
BASE = 'b' * 64


def sample(stage, mode, index, *, role='candidate', expected='qualified', fulltext=False):
    return {'job_id': f'{stage}-{mode}-{index}-{role}', 'stage': stage, 'mode': mode, 'role': role,
            'sample_id': f'{stage}-{mode}-{index}', 'ticker': f'{stage}-T{index}', 'cutoff': f'2026-0{index % 3 + 1}-01',
            'industry': f'industry-{index % 5}', 'financial': index % 5 == 0,
            'source_sha256': f'{index + 1:064x}', 'route_sha256': 'c' * 64,
            'expected': expected, 'fulltext_review': fulltext}


def manifest():
    rows = [sample('S1', 'v4', i) for i in range(4)]
    rows += [sample('S2', mode, i, role=role) for i in range(3)
             for mode in ('v1', 'v2', 'v3', 'v4') for role in ('baseline', 'candidate')]
    rows += [sample('S3', mode, i, fulltext=i < 5) for i in range(30) for mode in ('v1', 'v2', 'v3', 'v4')]
    rows += [sample('S4', mode, 0) for mode in ('v1', 'v2', 'v3', 'v4')]
    return rows


def result(row, **changes):
    value = {'job_id': row['job_id'], 'code_sha256': CODE if row['role'] == 'candidate' else BASE,
        'completed': True, 'published': True, 'artifact_verified': True, 'classification': 'verified_research',
        'required_roles_valid': True, 'generation_passed': True, 'audit_passed': True,
        'source_decision_reviewed': True, 'important_claims_verified': True, 'major_error': False,
        'warnings': [], 'unsafe': False, 'contradiction': False, 'secret_risk': False, 'source_changed': False,
        'independent_review': {'complete': True, 'dimensions': dict.fromkeys(DIMENSIONS, 2),
                               'evidence_refs': {dim: [f'private-artifact#{dim}'] for dim in DIMENSIONS}},
        'failure_review': {'complete': True, 'evidence_refs': ['private-evidence#failure-review']},
        'actual_models': [{'role': '22', 'requested': 'route', 'returned': 'observed-model',
                           'knobs': {'max_output_tokens': 64, 'temperature': 0}}],
        'duration_ms': 1000, 'tokens': 100, 'root_cause': None}
    value.update(changes)
    return value


def stage_results(rows, stage):
    return {row['job_id']: result(row) for row in rows if row['stage'] == stage}


def test_s1_passes_only_two_consecutive_same_candidate_full_reports():
    rows = manifest()
    results = {row['job_id']: result(row) for row in rows[:2]}
    decision = evaluate_stage('S1', rows, results)
    assert decision['decision'] == 'passed'
    assert decision['metrics']['denominator'] == 4
    assert decision['metrics']['qualified'] == 2


def test_missing_and_diagnostic_jobs_remain_in_original_denominator():
    rows = manifest()
    results = {rows[0]['job_id']: result(rows[0], classification='diagnostic_no_action')}
    decision = evaluate_stage('S1', rows, results)
    assert decision['decision'] == 'pending'
    assert decision['metrics']['qualified'] == 0
    assert decision['metrics']['missing'] == 3


@pytest.mark.parametrize('mutation', ['gap', 'code', 'gate', 'review'])
def test_s1_does_not_construct_a_false_consecutive_success(mutation):
    rows = manifest()
    chosen = (rows[0], rows[2]) if mutation == 'gap' else rows[:2]
    results = {row['job_id']: result(row) for row in chosen}
    last = results[chosen[-1]['job_id']]
    if mutation == 'code': last['code_sha256'] = 'd' * 64
    if mutation == 'gate': last['required_roles_valid'] = False
    if mutation == 'review': last['source_decision_reviewed'] = False
    assert evaluate_stage('S1', rows, results)['decision'] != 'passed'


def test_schema_does_not_accept_truthy_booleans_or_unknown_jobs():
    rows = manifest()
    values = {row['job_id']: result(row) for row in rows[:2]}
    values[rows[0]['job_id']]['artifact_verified'] = 1
    assert evaluate_stage('S1', rows, values)['decision'] == 'failed'
    assert early_stop(rows, values)
    values = {'unknown': result(rows[0])}
    assert evaluate_stage('S1', rows, values)['decision'] == 'failed'


def test_s1_cannot_promote_inputs_preregistered_as_diagnostic():
    rows = manifest()
    for row in rows[:2]: row['expected'] = 'diagnostic'
    assert evaluate_stage('S1', rows, {row['job_id']: result(row) for row in rows[:2]})['decision'] != 'passed'


def test_s2_accepts_exact_pairs_and_retains_all_24_jobs():
    rows = manifest()
    values = stage_results(rows, 'S2')
    decision = evaluate_stage('S2', rows, values)
    assert decision['decision'] == 'passed'
    assert decision['metrics']['denominator'] == 24
    assert decision['metrics']['comparable_pairs'] == 12
    assert decision['metrics']['candidate_qualified'] == 12
    assert decision['metrics']['cost']['token_per_qualified_ratio'] == 1
    values.pop(next(iter(values)))
    assert evaluate_stage('S2', rows, values)['decision'] == 'pending'


@pytest.mark.parametrize('mutation', ['models', 'per_mode', 'source', 'cutoff', 'route'])
def test_s2_refuses_insufficient_or_invalid_pairs(mutation):
    rows = manifest()
    values = stage_results(rows, 'S2')
    candidates = [row for row in rows if row['stage'] == 'S2' and row['role'] == 'candidate']
    if mutation in ('models', 'per_mode'):
        chosen = candidates[:5] if mutation == 'models' else [row for row in candidates if row['mode'] == 'v1'][:2]
        for row in chosen: values[row['job_id']]['actual_models'][0]['returned'] = 'fallback-other-model'
    else:
        key = {'source': 'source_sha256', 'cutoff': 'cutoff', 'route': 'route_sha256'}[mutation]
        candidates[0][key] = 'd' * 64 if key.endswith('sha256') else 'different cutoff'
    assert evaluate_stage('S2', rows, values)['decision'] != 'passed'


@pytest.mark.parametrize('metric,value,expected', [('duration_ms', 1250, 'passed'), ('duration_ms', 1251, 'failed'),
                                                   ('tokens', 125, 'passed'), ('tokens', 126, 'failed'), ('tokens', None, 'pending')])
def test_s2_cost_regression_is_strictly_more_than_25_percent(metric, value, expected):
    rows = manifest()
    values = stage_results(rows, 'S2')
    for row in rows:
        if row['stage'] == 'S2' and row['role'] == 'candidate': values[row['job_id']][metric] = value
    assert evaluate_stage('S2', rows, values)['decision'] == expected


def test_s2_ninety_percent_ceil_and_non_regression_are_both_required():
    rows = manifest()
    values = stage_results(rows, 'S2')
    pair = [row for row in rows if row['stage'] == 'S2' and row['mode'] == 'v1' and row['sample_id'].endswith('-0')]
    candidate = next(row for row in pair if row['role'] == 'candidate')
    values[candidate['job_id']]['classification'] = 'diagnostic_no_action'
    assert evaluate_stage('S2', rows, values)['decision'] == 'failed', '11/12 cannot conceal lower within-mode completion than baseline'
    for row in pair: values[row['job_id']]['classification'] = 'diagnostic_no_action'
    assert evaluate_stage('S2', rows, values)['decision'] == 'passed'
    another = next(row for row in rows if row['stage'] == 'S2' and row['mode'] == 'v2' and row['role'] == 'candidate')
    values[another['job_id']]['classification'] = 'diagnostic_no_action'
    assert evaluate_stage('S2', rows, values)['decision'] == 'failed'


def test_s2_pressure_correctness_and_zero_qualified_denominators_are_explicit():
    rows = manifest()
    for row in rows:
        if row['stage'] == 'S2': row['expected'] = 'diagnostic'
    values = stage_results(rows, 'S2')
    for row in values.values(): row['classification'] = 'diagnostic_no_action'
    decision = evaluate_stage('S2', rows, values)
    assert decision['decision'] == 'passed'
    assert decision['metrics']['qualified_rate'] is None
    assert decision['metrics']['cost']['token_per_qualified_ratio'] is None
    assert all(value['candidate_qualified_rate'] is None for value in decision['metrics']['modes'].values())
    candidate = next(row for row in rows if row['stage'] == 'S2' and row['role'] == 'candidate')
    values[candidate['job_id']]['classification'] = 'verified_research'
    assert evaluate_stage('S2', rows, values)['decision'] != 'passed'


def test_s2_reject_requires_positive_nonpublication_review_not_merely_no_artifact():
    rows = manifest()
    pair = [row for row in rows if row['stage'] == 'S2' and row['mode'] == 'v1' and row['sample_id'].endswith('-0')]
    for row in pair: row['expected'] = 'reject'
    values = stage_results(rows, 'S2')
    for row in pair:
        values[row['job_id']].update(classification='rejected', published=False, completed=False, artifact_verified=False)
    assert evaluate_stage('S2', rows, values)['decision'] == 'passed'
    candidate = next(row for row in pair if row['role'] == 'candidate')
    values[candidate['job_id']]['published'] = True
    assert evaluate_stage('S2', rows, values)['decision'] == 'failed'


def test_s3_accepts_29_of_30_per_mode_but_missing_slots_never_disappear():
    rows = manifest()
    values = stage_results(rows, 'S3')
    for mode in ('v1', 'v2', 'v3', 'v4'):
        row = next(row for row in rows if row['stage'] == 'S3' and row['mode'] == mode)
        values[row['job_id']]['classification'] = 'diagnostic_no_action'
    decision = evaluate_stage('S3', rows, values)
    assert decision['decision'] == 'passed'
    assert decision['metrics']['qualified'] == 116 and decision['metrics']['denominator'] == 120
    assert all(value['qualified'] == 29 and value['denominator'] == 30 for value in decision['metrics']['modes'].values())
    values.pop(next(iter(values)))
    assert evaluate_stage('S3', rows, values)['decision'] == 'pending'


@pytest.mark.parametrize('failure', ['required_roles_valid', 'generation_passed', 'audit_passed',
                                    'artifact_verified', 'important_claims_verified'])
def test_s3_two_failures_of_any_essential_gate_stop_campaign(failure):
    rows = manifest()
    values = stage_results(rows, 'S3')
    chosen = [row for row in rows if row['stage'] == 'S3' and row['mode'] == 'v2'][:2]
    for row in chosen: values[row['job_id']][failure] = False
    assert 'S3_two_failures:v2' in early_stop(rows, values)
    assert evaluate_stage('S3', rows, values)['decision'] == 'failed'


@pytest.mark.parametrize('mutation', ['missing', '18_of_20', 'mode_average', 'warning', 'dimension_ref', 'code'])
def test_s3_fulltext_rubric_and_warning_review_cannot_be_skipped(mutation):
    rows = manifest()
    values = stage_results(rows, 'S3')
    selected = [row for row in rows if row['stage'] == 'S3' and row['fulltext_review']]
    first = values[selected[0]['job_id']]
    if mutation == 'missing': first['independent_review']['complete'] = False
    elif mutation == 'dimension_ref': first['independent_review']['evidence_refs'].pop('source_faithfulness')
    elif mutation == 'warning':
        first['warnings'] = ['source limitation']
        first['failure_review']['complete'] = False
    elif mutation == 'code': first['code_sha256'] = 'e' * 64
    else:
        chosen = selected[:3] if mutation == '18_of_20' else [row for row in selected if row['mode'] == 'v1']
        for row in chosen:
            values[row['job_id']]['independent_review']['dimensions'] = dict(zip(DIMENSIONS, (2, 1, 1, 1, 1)))
    assert evaluate_stage('S3', rows, values)['decision'] != 'passed'


def test_same_cause_requires_three_consecutive_failed_jobs_and_preserves_gaps():
    rows = manifest()
    chosen = [row for row in rows if row['stage'] == 'S2'][:3]
    values = {row['job_id']: result(row, classification='failed', completed=False, published=False,
                                  artifact_verified=False, root_cause='provider_500') for row in chosen}
    assert 'three_consecutive_same_cause:provider_500' in early_stop(rows, values)
    values.pop(chosen[1]['job_id'])
    assert not early_stop(rows, values)


@pytest.mark.parametrize('flag', ['secret_risk', 'source_changed', 'major_error', 'unsafe', 'contradiction'])
def test_global_safety_stops_are_not_hidden_by_good_scores(flag):
    rows = manifest()
    values = {rows[0]['job_id']: result(rows[0], **{flag: True})}
    assert early_stop(rows, values)
    assert evaluate_stage('S1', rows, values)['decision'] == 'failed'


def test_s4_is_not_authorized_by_private_report_success_and_inputs_are_not_mutated():
    rows = manifest()
    values = stage_results(rows, 'S4')
    before = copy.deepcopy((rows, values))
    assert evaluate_stage('S4', rows, values)['decision'] == 'failed'
    assert (rows, values) == before


def test_s1_does_not_pass_while_an_earlier_registered_job_is_missing():
    rows = manifest()
    values = {row['job_id']: result(row) for row in rows[1:3]}
    assert evaluate_stage('S1', rows, values)['decision'] == 'pending'


def test_s1_exhausted_slots_and_two_failed_candidates_are_terminal_not_forever_pending():
    rows = manifest()
    for row in rows[2:4]: row['expected'] = 'diagnostic'
    values = {row['job_id']: result(row, classification='diagnostic_no_action') for row in rows[:4]}
    assert evaluate_stage('S1', rows, values)['decision'] == 'failed'
    rows = manifest()
    values = {rows[0]['job_id']: result(rows[0], classification='failed', root_cause='source_contract'),
              rows[1]['job_id']: result(rows[1], code_sha256='d' * 64, classification='failed', root_cause='another_contract')}
    assert 'S1_two_failed_candidates_without_qualified_report' in early_stop(rows, values)


def test_s2_incomplete_or_unreviewed_comparison_is_pending_not_proven_regression():
    rows = manifest()
    first_pair = [row for row in rows if row['stage'] == 'S2'][:2]
    values = {row['job_id']: result(row, duration_ms=2000 if row['role'] == 'candidate' else 1000) for row in first_pair}
    assert evaluate_stage('S2', rows, values)['decision'] == 'pending'
    values = stage_results(rows, 'S2')
    candidate = next(row for row in rows if row['stage'] == 'S2' and row['role'] == 'candidate')
    values[candidate['job_id']]['source_decision_reviewed'] = False
    assert evaluate_stage('S2', rows, values)['decision'] == 'pending'


def test_s2_zero_baseline_token_cost_is_undefined_not_a_passed_ratio():
    rows = manifest()
    values = stage_results(rows, 'S2')
    for row in rows:
        if row['stage'] == 'S2' and row['role'] == 'baseline': values[row['job_id']]['tokens'] = 0
    decision = evaluate_stage('S2', rows, values)
    assert decision['metrics']['cost']['token_per_qualified_ratio'] is None
    assert decision['decision'] == 'pending'


def test_s2_failed_job_tokens_are_not_excluded_from_cost_per_qualified_report():
    rows = manifest()
    values = stage_results(rows, 'S2')
    pair = [row for row in rows if row['stage'] == 'S2' and row['mode'] == 'v1' and row['sample_id'].endswith('-0')]
    for row in pair:
        values[row['job_id']].update(classification='diagnostic_no_action', tokens=10000 if row['role'] == 'candidate' else 100)
    assert evaluate_stage('S2', rows, values)['decision'] == 'failed'


@pytest.mark.parametrize('field,value', [('root_cause', True), ('tokens', True), ('duration_ms', False),
                                         ('classification', []), ('warnings', 'warning'), ('published', None)])
def test_malformed_external_results_fail_closed_without_type_errors(field, value):
    rows = manifest()
    values = {rows[0]['job_id']: result(rows[0], **{field: value})}
    assert evaluate_stage('S1', rows, values)['decision'] == 'failed'
    assert early_stop(rows, values)


def test_missing_required_fields_and_duplicate_results_fail_closed():
    rows = manifest()
    value = result(rows[0])
    for field in value:
        broken = copy.deepcopy(value)
        broken.pop(field)
        assert evaluate_stage('S1', rows, {rows[0]['job_id']: broken})['decision'] == 'failed', field
    assert evaluate_stage('S1', rows, [value, copy.deepcopy(value)])['decision'] == 'failed'


@pytest.mark.parametrize('field,value', [('returned', None), ('knobs', {})])
def test_unknown_actual_model_or_generation_knobs_never_proves_comparability(field, value):
    rows = manifest()
    values = stage_results(rows, 'S2')
    for row in values.values(): row['actual_models'][0][field] = value
    decision = evaluate_stage('S2', rows, values)
    assert decision['decision'] == 'failed' and decision['metrics']['comparable_pairs'] == 0


def test_review_pending_is_not_counted_as_a_known_s3_failure():
    rows = manifest()
    chosen = [row for row in rows if row['stage'] == 'S3' and row['mode'] == 'v1'][:2]
    values = {row['job_id']: result(row, source_decision_reviewed=False, important_claims_verified=False) for row in chosen}
    assert not early_stop(rows, values)
    assert evaluate_stage('S3', rows, values)['decision'] == 'pending'


@pytest.mark.parametrize('preregistered,review_kind', [(True, 'both'), (True, 'independent'), (False, 'independent'), (False, 'failure')])
def test_s3_reviewed_major_falsehood_veto_includes_retained_unpublished_draft(preregistered, review_kind):
    rows = manifest()
    chosen = next(row for row in rows if row['stage'] == 'S3' and row['fulltext_review'] is preregistered)
    values = stage_results(rows, 'S3')
    reviewed = values[chosen['job_id']]
    reviewed.update(completed=False, published=False, artifact_verified=False, classification='failed', major_error=True)
    if review_kind == 'failure': reviewed['independent_review']['complete'] = False
    elif review_kind == 'independent': reviewed['failure_review']['complete'] = False
    decision = evaluate_stage('S3', rows, values)
    assert decision['decision'] == 'failed', '29/30 and high scores cannot override a reviewed major falsehood'
    reason = 'S3_reviewed_major_falsehood:' + chosen['job_id']
    assert reason in decision['reasons'] and reason in early_stop(rows, values)
    assert decision['metrics']['qualified'] == 119 and decision['metrics']['denominator'] == 120


def test_s3_unreviewed_flag_is_pending_and_ordinary_unpublished_failure_still_allows_29_of_30():
    rows = manifest()
    chosen = next(row for row in rows if row['stage'] == 'S3' and not row['fulltext_review'])
    values = stage_results(rows, 'S3')
    reviewed = values[chosen['job_id']]
    reviewed.update(completed=False, published=False, artifact_verified=False, classification='failed', major_error=True)
    reviewed['independent_review']['complete'] = reviewed['failure_review']['complete'] = False
    assert not early_stop(rows, values)
    assert evaluate_stage('S3', rows, values)['decision'] == 'pending'
    reviewed['major_error'] = False
    reviewed['failure_review']['complete'] = True
    assert not early_stop(rows, values)
    assert evaluate_stage('S3', rows, values)['decision'] == 'passed'


def test_s3_rubric_veto_does_not_become_a_new_global_rule_for_all_unpublished_errors():
    rows = manifest()
    chosen = rows[0]
    values = {chosen['job_id']: result(chosen, completed=False, published=False, artifact_verified=False,
                                      classification='failed', major_error=True)}
    assert not early_stop(rows, values)
    assert evaluate_stage('S1', rows, values)['decision'] == 'pending'


def test_validate_evidence_reports_schema_errors_without_changing_input():
    from quality_campaign_acceptance import validate_evidence
    rows = manifest()
    values = {rows[0]['job_id']: result(rows[0])}
    values[rows[0]['job_id']].pop('published')
    before = copy.deepcopy((rows, values))
    assert validate_evidence(rows, values) == ['invalid_result:' + rows[0]['job_id']]
    assert (rows, values) == before


def test_validate_evidence_keeps_a_valid_major_error_distinct_from_schema_rejection():
    from quality_campaign_acceptance import validate_evidence
    rows = manifest()
    values = {rows[0]['job_id']: result(rows[0], major_error=True)}
    assert validate_evidence(rows, values) == []
    assert 'unsafe_published_content:' + rows[0]['job_id'] in early_stop(rows, values)
