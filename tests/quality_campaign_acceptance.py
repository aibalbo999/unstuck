"""Pure acceptance of externally verified evidence, never model self-grading.

The controller verifies immutable manifest/receipt/artifact bytes, review authors
and evidence locations before calling. A result is a cleanup-complete terminal
job, including failed/cancelled jobs; running jobs remain absent. Missing reviews
are pending, not zero scores. This module does no I/O and cannot pass a ledger
stage, publish a report, certify a reviewer, or authorize S4.
"""
import json
import math
import re


MODES = ('v1', 'v2', 'v3', 'v4')
DIMENSIONS = ('source_faithfulness', 'mode_relevance', 'conclusion_reasoning', 'counterevidence_limits', 'readability')
QUALIFIED = {'verified_research', 'verified_no_action'}
CLASSIFICATIONS = QUALIFIED | {'research_with_limitations', 'diagnostic_no_action', 'rejected', 'failed', 'cancelled', 'unknown'}
BOOLEAN_FIELDS = ('completed', 'published', 'artifact_verified', 'required_roles_valid', 'generation_passed',
    'audit_passed', 'source_decision_reviewed', 'important_claims_verified', 'major_error', 'unsafe',
    'contradiction', 'secret_risk', 'source_changed')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _refs(value):
    return isinstance(value, list) and bool(value) and all(_text(item) for item in value)


def _review(value, *, fulltext):
    if not isinstance(value, dict) or type(value.get('complete')) is not bool:
        return False
    if not fulltext:
        refs = value.get('evidence_refs')
        return _refs(refs) if value['complete'] else isinstance(refs, list) and all(_text(item) for item in refs)
    dimensions, refs = value.get('dimensions'), value.get('evidence_refs')
    if not isinstance(dimensions, dict) or not isinstance(refs, dict):
        return False
    if (not set(dimensions).issubset(DIMENSIONS) or not set(refs).issubset(DIMENSIONS)
            or any(type(score) is not int or score not in (0, 1, 2) for score in dimensions.values())
            or any(not _refs(items) for items in refs.values())):
        return False
    return not value['complete'] or set(dimensions) == set(refs) == set(DIMENSIONS)


def _inputs(samples, results):
    errors, index = [], {}
    if not isinstance(samples, list) or not samples:
        return {}, {}, ['invalid_samples']
    for row in samples:
        if (not isinstance(row, dict) or not all(_text(row.get(key)) for key in
                ('job_id', 'sample_id', 'ticker', 'cutoff', 'industry'))
                or row.get('stage') not in ('S1', 'S2', 'S3', 'S4') or row.get('mode') not in MODES
                or row.get('role') not in ('candidate', 'baseline')
                or row.get('expected') not in ('qualified', 'limited', 'diagnostic', 'reject')
                or type(row.get('financial')) is not bool or type(row.get('fulltext_review')) is not bool
                or not _sha(row.get('source_sha256')) or not _sha(row.get('route_sha256'))):
            errors.append('invalid_sample')
            continue
        if row['job_id'] in index: errors.append('duplicate_sample_job_id')
        index[row['job_id']] = row
    if isinstance(results, list):
        pairs = [(item.get('job_id') if isinstance(item, dict) else None, item) for item in results]
    elif isinstance(results, dict):
        pairs = list(results.items())
    else:
        return index, {}, errors + ['invalid_results']
    accepted = {}
    for job_id, row in pairs:
        if not isinstance(job_id, str) or job_id not in index:
            errors.append('unknown_result_job_id')
            continue
        if job_id in accepted: errors.append('duplicate_result_job_id')
        valid = (isinstance(row, dict) and row.get('job_id') == job_id and _sha(row.get('code_sha256'))
            and all(type(row.get(key)) is bool for key in BOOLEAN_FIELDS)
            and isinstance(row.get('classification'), str) and row['classification'] in CLASSIFICATIONS
            and isinstance(row.get('warnings'), list) and all(_text(item) for item in row['warnings'])
            and type(row.get('duration_ms')) is int and row['duration_ms'] >= 0
            and 'tokens' in row and (row['tokens'] is None or type(row['tokens']) is int and row['tokens'] >= 0)
            and 'root_cause' in row and (row['root_cause'] is None or _text(row['root_cause']))
            and _review(row.get('independent_review'), fulltext=True) and _review(row.get('failure_review'), fulltext=False)
            and isinstance(row.get('actual_models'), list))
        if valid:
            for model in row['actual_models']:
                if (not isinstance(model, dict) or set(model) != {'role', 'requested', 'returned', 'knobs'}
                        or not _text(model['role']) or not _text(model['requested'])
                        or model['returned'] is not None and not _text(model['returned'])
                        or not isinstance(model['knobs'], dict)):
                    valid = False
                    break
            try:
                json.dumps(row, allow_nan=False)
            except (TypeError, ValueError):
                valid = False
        if not valid:
            errors.append('invalid_result:' + job_id)
            continue
        accepted[job_id] = row
    return index, accepted, sorted(set(errors))


def _safe(row):
    return not any(row[key] for key in ('major_error', 'unsafe', 'contradiction', 'secret_risk', 'source_changed'))


def _artifact(row):
    return (all(row[key] for key in ('completed', 'published', 'artifact_verified', 'required_roles_valid',
            'generation_passed', 'audit_passed', 'source_decision_reviewed', 'important_claims_verified')) and _safe(row))


def _qualified(row):
    return row is not None and row['classification'] in QUALIFIED and _artifact(row)


def _expected(sample, row):
    if row is None: return False
    if sample['expected'] == 'qualified': return _qualified(row)
    if sample['expected'] == 'reject':
        return (row['classification'] == 'rejected' and not row['published'] and not row['artifact_verified']
                and row['source_decision_reviewed'] and row['failure_review']['complete'] and _safe(row))
    expected = {'limited': 'research_with_limitations', 'diagnostic': 'diagnostic_no_action'}[sample['expected']]
    return row['classification'] == expected and _artifact(row)


def _known_failure(sample, row):
    if _expected(sample, row): return False
    if not _safe(row): return True
    if sample['expected'] == 'reject':
        return row['published'] or row['classification'] != 'rejected'
    target = QUALIFIED if sample['expected'] == 'qualified' else {
        'limited': {'research_with_limitations'}, 'diagnostic': {'diagnostic_no_action'}}[sample['expected']]
    return (row['classification'] not in target or not all(row[key] for key in
        ('completed', 'published', 'artifact_verified', 'required_roles_valid', 'generation_passed', 'audit_passed'))
        or row['source_decision_reviewed'] and not row['important_claims_verified'])


def _stops(samples, results):
    reasons, previous, streak = [], None, 0
    s3_failures = dict.fromkeys(MODES, 0)
    for sample in samples:
        row = results.get(sample['job_id'])
        if row is None:
            previous, streak = None, 0
            continue
        if row['secret_risk']: reasons.append('secret_risk:' + sample['job_id'])
        if row['source_changed']: reasons.append('source_changed:' + sample['job_id'])
        if row['published'] and any(row[key] for key in ('major_error', 'unsafe', 'contradiction')):
            reasons.append('unsafe_published_content:' + sample['job_id'])
        failed = _known_failure(sample, row)
        if sample['stage'] == 'S3' and failed:
            s3_failures[sample['mode']] += 1
        # The S3 independent-review rubric veto is distinct from the global
        # published-error stop: a reviewed retained draft cannot be excused by
        # 29/30 completion. An unfinished review is not asserted as a finding.
        if (sample['stage'] == 'S3' and row['major_error'] and (row['independent_review']['complete']
                or (failed or row['warnings']) and row['failure_review']['complete'])):
            reasons.append('S3_reviewed_major_falsehood:' + sample['job_id'])
        cause = row['root_cause'] if failed else None
        streak = streak + 1 if cause is not None and cause == previous else 1 if cause else 0
        previous = cause
        if streak >= 3: reasons.append('three_consecutive_same_cause:' + cause)
    reasons += ['S3_two_failures:' + mode for mode, count in s3_failures.items() if count >= 2]
    s1 = [(sample, results[sample['job_id']]) for sample in samples
          if sample['stage'] == 'S1' and sample['job_id'] in results]
    failed_codes = {row['code_sha256'] for sample, row in s1 if _known_failure(sample, row)}
    if len(failed_codes) >= 2 and not any(sample['expected'] == 'qualified' and _qualified(row) for sample, row in s1):
        reasons.append('S1_two_failed_candidates_without_qualified_report')
    return sorted(set(reasons))


def early_stop(samples, results):
    """Reasons to stop further dispatch; absence does not authorize dispatch."""
    _, accepted, errors = _inputs(samples, results)
    return errors or _stops(samples, accepted)


def validate_evidence(samples, results):
    """Return schema errors only, without I/O or mutation.

    Controllers use this before persisting review pointers. A structurally valid
    reviewed safety failure returns no schema error; early_stop owns that
    separate decision. This does not authenticate external evidence or authors.
    """
    return _inputs(samples, results)[2]


def _decision(decision, reasons, metrics):
    return {'decision': decision, 'reasons': sorted(set(reasons)), 'metrics': metrics}


def _rate(numerator, denominator):
    return numerator / denominator if denominator else None


def _models(row):
    models = row['actual_models']
    if not models or any(not _text(item['returned']) or not item['knobs'] for item in models):
        return None
    # Parallel role completion order is irrelevant; repeated attempts are not
    # deduplicated, so fallback/retry identity differences remain confounded.
    return sorted(json.dumps(item, sort_keys=True, allow_nan=False, separators=(',', ':')) for item in models)


def _p95(values):
    return sorted(values)[math.ceil(len(values) * .95) - 1] if values else None


def _hard_published(rows):
    failed, pending = [], []
    for row in rows:
        if row['published']:
            if not row['artifact_verified'] or not _safe(row):
                failed.append('published_content_not_verified:' + row['job_id'])
            if not row['source_decision_reviewed']:
                pending.append('published_source_decision_review_pending:' + row['job_id'])
            elif not row['important_claims_verified']:
                failed.append('published_important_claims_not_verified:' + row['job_id'])
    return failed, pending


def _cost(pairs):
    arms = {role: [pair[role] for pair in pairs] for role in ('baseline', 'candidate')}
    metrics = {}
    for role, rows in arms.items():
        qualified = sum(_qualified(row) for row in rows)
        covered = all(row['tokens'] is not None for row in rows)
        total = sum(row['tokens'] for row in rows) if covered and rows else None
        metrics[role] = {'jobs': len(rows), 'qualified': qualified, 'p95_duration_ms': _p95([r['duration_ms'] for r in rows]),
            'token_coverage': sum(r['tokens'] is not None for r in rows), 'tokens': total,
            'token_per_qualified': total / qualified if total is not None and qualified else None}
    for metric, name in (('p95_duration_ms', 'p95_ratio'), ('token_per_qualified', 'token_per_qualified_ratio')):
        baseline, candidate = metrics['baseline'][metric], metrics['candidate'][metric]
        metrics[name] = candidate / baseline if baseline is not None and baseline > 0 and candidate is not None else None
    return metrics


def _s2(selected, accepted, metrics):
    pairs = {}
    for sample in selected:
        key = (sample['mode'], sample['sample_id'])
        pair = pairs.setdefault(key, {})
        if sample['role'] in pair: return _decision('failed', ['duplicate_S2_pair_role'], metrics)
        pair[sample['role']] = sample
    if len(selected) != 24 or len(pairs) != 12 or any(sum(key[0] == mode for key in pairs) != 3 for mode in MODES):
        return _decision('failed', ['invalid_S2_preregistration'], metrics)
    match_fields = ('ticker', 'cutoff', 'industry', 'financial', 'source_sha256', 'route_sha256', 'expected')
    if any(set(pair) != {'baseline', 'candidate'} or any(pair['baseline'][key] != pair['candidate'][key]
            for key in match_fields) for pair in pairs.values()):
        return _decision('failed', ['S2_pair_input_or_route_mismatch'], metrics)
    rows = [accepted[s['job_id']] for s in selected if s['job_id'] in accepted]
    failed, pending = _hard_published(rows)
    candidates = [pair['candidate'] for pair in pairs.values()]
    if len({accepted[s['job_id']]['code_sha256'] for s in candidates if s['job_id'] in accepted}) > 1:
        failed.append('S2_candidate_code_drift')
    baseline_samples = [pair['baseline'] for pair in pairs.values()]
    if len({accepted[s['job_id']]['code_sha256'] for s in baseline_samples if s['job_id'] in accepted}) > 1:
        failed.append('S2_baseline_code_drift')
    eligible = [s for s in candidates if s['expected'] == 'qualified']
    count = sum(_qualified(accepted.get(s['job_id'])) for s in eligible)
    pressure = [s for s in candidates if s['expected'] != 'qualified']
    correct_pressure = sum(_expected(s, accepted.get(s['job_id'])) for s in pressure)
    metrics.update(candidate_denominator=12, candidate_qualified=count, qualified_denominator=len(eligible),
        qualified_rate=_rate(count, len(eligible)), pressure_denominator=len(pressure), pressure_correct=correct_pressure)
    for sample in pressure:
        row = accepted.get(sample['job_id'])
        if row is None: continue
        if _known_failure(sample, row): failed.append('S2_pressure_not_correct:' + sample['job_id'])
        elif not _expected(sample, row): pending.append('S2_pressure_review_pending:' + sample['job_id'])
    comparable, confounded = {}, []
    for key, pair in pairs.items():
        observed = {role: accepted.get(sample['job_id']) for role, sample in pair.items()}
        if any(row is None for row in observed.values()): continue
        baseline, candidate = observed['baseline'], observed['candidate']
        identity = _models(baseline)
        if identity is not None and identity == _models(candidate): comparable[key] = observed
        else: confounded.append({'mode': key[0], 'sample_id': key[1]})
        for row in observed.values():
            review = row['independent_review'] if row['published'] else row['failure_review']
            if not review['complete']: pending.append('S2_external_review_pending:' + row['job_id'])
    metrics.update(comparable_pairs=len(comparable), model_confounded=confounded, modes={})
    all_received = not metrics['missing']
    if all_received and len(comparable) < 8: failed.append('S2_requires_8_comparable_pairs')
    for mode in MODES:
        group = [value for key, value in comparable.items() if key[0] == mode]
        qgroup = [value for key, value in comparable.items() if key[0] == mode and pairs[key]['candidate']['expected'] == 'qualified']
        baseline_count = sum(_qualified(pair['baseline']) for pair in qgroup)
        candidate_count = sum(_qualified(pair['candidate']) for pair in qgroup)
        metrics['modes'][mode] = {'pair_denominator': 3, 'comparable_pairs': len(group), 'qualified_denominator': len(qgroup),
            'baseline_qualified': baseline_count, 'candidate_qualified': candidate_count,
            'baseline_qualified_rate': _rate(baseline_count, len(qgroup)), 'candidate_qualified_rate': _rate(candidate_count, len(qgroup))}
        if all_received and len(group) < 2: failed.append('S2_requires_2_comparable_pairs:' + mode)
        if all_received and not pending and candidate_count < baseline_count: failed.append('S2_qualified_completion_regressed:' + mode)
    if all_received and count < math.ceil(len(eligible) * .9):
        if any(s['job_id'] in accepted and not _known_failure(s, accepted[s['job_id']]) and not _qualified(accepted[s['job_id']]) for s in eligible):
            pending.append('S2_qualified_review_pending')
        else: failed.append('S2_qualified_rate_below_ceil_90_percent')
    metrics['cost'] = cost = _cost(list(comparable.values()))
    for ratio in ('p95_ratio', 'token_per_qualified_ratio'):
        if all_received and not pending and cost[ratio] is not None and cost[ratio] > 1.25:
            failed.append('S2_' + ratio + '_regressed_over_25_percent')
    if comparable and cost['baseline']['p95_duration_ms'] == 0:
        pending.append('S2_baseline_duration_ratio_unavailable')
    if cost['baseline']['qualified'] and (cost['baseline']['token_coverage'] < len(comparable)
            or cost['candidate']['token_coverage'] < len(comparable)):
        pending.append('S2_token_cost_evidence_missing')
    if cost['baseline']['qualified'] and cost['baseline']['token_per_qualified'] == 0:
        pending.append('S2_baseline_token_cost_ratio_unavailable')
    metrics['limitations'] = ['No qualified baseline means token cost ratio is unavailable, not zero or infinite improvement.',
        'Model-confounded and failed jobs remain in the original 12-pair/24-job denominator; sample-internal comparison only.']
    if failed: return _decision('failed', failed + pending, metrics)
    if metrics['missing'] or pending: return _decision('pending', pending + (['S2_results_missing'] if metrics['missing'] else []), metrics)
    return _decision('passed', [], metrics)


def _s3(selected, accepted, metrics):
    if (len(selected) != 120 or any(s['role'] != 'candidate' or s['expected'] != 'qualified' for s in selected)
            or any(sum(s['mode'] == mode for s in selected) != 30 for mode in MODES)
            or any(sum(s['mode'] == mode and s['fulltext_review'] for s in selected) != 5 for mode in MODES)
            or any(len({(s['ticker'], s['cutoff']) for s in selected if s['mode'] == mode}) != 30 for mode in MODES)):
        return _decision('failed', ['invalid_S3_preregistration'], metrics)
    rows = [accepted[s['job_id']] for s in selected if s['job_id'] in accepted]
    failed, pending = _hard_published(rows)
    if len({row['code_sha256'] for row in rows}) > 1: failed.append('S3_candidate_code_drift')
    scores = {mode: [] for mode in MODES}
    metrics['modes'] = {}
    for sample in selected:
        row = accepted.get(sample['job_id'])
        if row is None: continue
        if (_known_failure(sample, row) or row['warnings']) and not row['failure_review']['complete']:
            pending.append('S3_failure_or_warning_review_pending:' + row['job_id'])
        if sample['fulltext_review']:
            if not row['independent_review']['complete']:
                pending.append('S3_fulltext_review_pending:' + row['job_id'])
            else:
                scores[sample['mode']].append(sum(row['independent_review']['dimensions'].values()))
    for mode in MODES:
        group = [s for s in selected if s['mode'] == mode]
        qualified = sum(_qualified(accepted.get(s['job_id'])) for s in group)
        received = sum(s['job_id'] in accepted for s in group)
        metrics['modes'][mode] = {'denominator': 30, 'received': received, 'qualified': qualified,
            'qualified_rate': qualified / 30, 'fulltext_denominator': 5, 'fulltext_reviewed': len(scores[mode]),
            'fulltext_average': sum(scores[mode]) / len(scores[mode]) if scores[mode] else None}
        if received == 30 and qualified < 29:
            if any(not _known_failure(s, accepted[s['job_id']]) and not _qualified(accepted[s['job_id']]) for s in group):
                pending.append('S3_qualified_review_pending:' + mode)
            else: failed.append('S3_below_29_of_30:' + mode)
        if len(scores[mode]) == 5 and sum(scores[mode]) < 40: failed.append('S3_fulltext_average_below_8:' + mode)
    complete_scores = [score for values in scores.values() for score in values]
    metrics['fulltext'] = {'denominator': 20, 'reviewed': len(complete_scores), 'score_at_least_8': sum(score >= 8 for score in complete_scores)}
    if len(complete_scores) == 20 and metrics['fulltext']['score_at_least_8'] < 18:
        failed.append('S3_requires_18_of_20_fulltext_scores_at_least_8')
    if failed: return _decision('failed', failed + pending, metrics)
    if metrics['missing'] or pending: return _decision('pending', pending + (['S3_results_missing'] if metrics['missing'] else []), metrics)
    return _decision('passed', [], metrics)


def evaluate_stage(stage, samples, results):
    """Return passed/pending/failed, preserving every preregistered denominator."""
    _, accepted, errors = _inputs(samples, results)
    if stage not in ('S1', 'S2', 'S3', 'S4'): errors.append('invalid_stage')
    if errors: return _decision('failed', errors, {})
    selected = [row for row in samples if row['stage'] == stage]
    current = [accepted[row['job_id']] for row in selected if row['job_id'] in accepted]
    metrics = {'denominator': len(selected), 'received': len(current), 'missing': len(selected) - len(current),
               'qualified': sum(s['expected'] == 'qualified' and _qualified(accepted.get(s['job_id'])) for s in selected)}
    if stage == 'S4': return _decision('failed', ['formal_specific_evidence_required'], metrics)
    stops = _stops(samples, accepted)
    if stops: return _decision('failed', stops, metrics)
    if stage == 'S1':
        if len(selected) != 4 or any(row['mode'] != 'v4' or row['role'] != 'candidate' for row in selected):
            return _decision('failed', ['invalid_S1_preregistration'], metrics)
        prequalified = {(row['ticker'], row['cutoff']) for row in selected if row['expected'] == 'qualified'}
        if len(prequalified) < 2: return _decision('failed', ['S1_requires_two_prequalified_inputs'], metrics)
        if len({row['code_sha256'] for row in current}) > 2:
            return _decision('failed', ['S1_candidate_limit'], metrics)
        # Gaps and nonqualified results interrupt the preregistered sequence.
        # Unused trailing slots do not demand needless additional model calls.
        last = max((i for i, row in enumerate(selected) if row['job_id'] in accepted), default=-1)
        tail_samples = selected[max(0, last - 1):last + 1]
        tail = [accepted.get(row['job_id']) for row in tail_samples]
        if (len(tail) == 2 and all(s['job_id'] in accepted for s in selected[:last + 1])
                and all(s['expected'] == 'qualified' for s in tail_samples)
                and all(_qualified(row) for row in tail) and tail[0]['code_sha256'] == tail[1]['code_sha256']):
            metrics['accepted_code_sha256'] = tail[0]['code_sha256']
            return _decision('passed', [], metrics)
        status = 'failed' if len(current) == 4 and all(_known_failure(s, accepted[s['job_id']]) or _expected(s, accepted[s['job_id']])
            for s in selected) else 'pending'
        return _decision(status, ['S1_requires_two_consecutive_same_candidate_qualified'], metrics)
    return _s2(selected, accepted, metrics) if stage == 'S2' else _s3(selected, accepted, metrics)
