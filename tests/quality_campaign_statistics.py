"""Pure evidence-bound pilot summaries; no I/O or acceptance authority.

The caller authenticates the frozen roster, terminal receipts, external reviews
and optional ledger snapshot. Hashes here bind supplied JSON, not physical files.
Untimed results remain supplied evidence but cannot establish historical cutoff
membership. Source cutoff (sample.cutoff) is NOT the job's execution timestamp.
"""
from collections import Counter
import hashlib
import json
import math

from quality_campaign_acceptance import (CLASSIFICATIONS, MODES, _expected, _known_failure, _qualified, validate_evidence)


def _integer(value):
    return type(value) is int and value >= 0


def _digest(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise ValueError('Evidence must be finite JSON') from error
    return hashlib.sha256(raw).hexdigest()


def _wilson(successes, count):
    if not count: return None
    z = 1.959963984540054
    p, adjusted = successes / count, 1 + z * z / count
    center = (p + z * z / (2 * count)) / adjusted
    margin = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / adjusted
    return [0.0 if successes == 0 else max(0.0, center - margin),
            1.0 if successes == count else min(1.0, center + margin)]


def _rate(numerator, denominator, *, interval=False):
    return {'numerator': numerator, 'denominator': denominator,
            'value': numerator / denominator if denominator else None,
            'wilson_95': _wilson(numerator, denominator) if interval else None}


def _chronology(row):
    present = ('started_at_ms' in row, 'finished_at_ms' in row)
    if present == (False, False): return None
    start, end = row.get('started_at_ms'), row.get('finished_at_ms')
    if not all(present) or not _integer(start) or not _integer(end) or end < start or end - start != row['duration_ms']:
        raise ValueError('Invalid job chronology:' + row['job_id'])
    return start, end


def _quality(samples, observed):
    selected = [s for s in samples if s['expected'] == 'qualified']
    pairs = [(s, observed[s['job_id']]) for s in selected if s['job_id'] in observed]
    qualified = sum(_qualified(row) for _, row in pairs)
    failed = sum(_known_failure(sample, row) for sample, row in pairs)
    pending = len(pairs) - qualified - failed
    unobserved = len(selected) - len(pairs)
    complete = not pending and not unobserved
    pilot = _rate(qualified, len(selected), interval=complete)
    pilot['interpretation'] = 'complete_fixed_pilot' if complete else 'attainment_to_date_not_final_failure_rate'
    if not selected: pilot['interpretation'] = 'no_preregistered_qualified_inputs'
    return {'registered': len(selected), 'qualified': qualified, 'known_unqualified': failed,
        'review_pending': pending, 'unobserved': unobserved,
        'observed_rate': _rate(qualified, qualified + failed, interval=True), 'pilot_rate': pilot}


def _pressure(samples, observed):
    selected = [s for s in samples if s['expected'] != 'qualified']
    pairs = [(s, observed[s['job_id']]) for s in selected if s['job_id'] in observed]
    correct = sum(_expected(sample, row) for sample, row in pairs)
    incorrect = sum(_known_failure(sample, row) for sample, row in pairs)
    return {'registered': len(selected), 'correct': correct, 'known_incorrect': incorrect,
        'review_pending': len(pairs) - correct - incorrect, 'unobserved': len(selected) - len(pairs),
        'observed_correctness': _rate(correct, correct + incorrect)}


def _quantile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1] if values else None


def _group(samples, results, times, cutoff_ms):
    present = [(s, results[s['job_id']]) for s in samples if s['job_id'] in results]
    observed = {s['job_id']: row for s, row in present
                if times[s['job_id']] is not None and times[s['job_id']][1] <= cutoff_ms}
    rows = list(observed.values())
    classes = Counter(row['classification'] for row in rows)
    total, known = len(samples), len(rows)
    final_tokens = [row['tokens'] for row in rows if row['tokens'] is not None]
    windows = {}
    for minutes in (15, 30, 60):
        threshold = minutes * 60_000
        window_observed = qualified_window_observed = completed = qualified = right_censored = not_started = 0
        quality_review_pending = 0
        for sample in samples:
            row, timing = results.get(sample['job_id']), times.get(sample['job_id'])
            if row is None or timing is None: continue
            start, end = timing
            if start > cutoff_ms:
                not_started += 1
            elif end <= cutoff_ms or cutoff_ms - start >= threshold:
                window_observed += 1
                if sample['expected'] == 'qualified':
                    if end > cutoff_ms or row['duration_ms'] > threshold or _qualified(row) or _known_failure(sample, row):
                        qualified_window_observed += 1
                    else:
                        quality_review_pending += 1
                if end <= cutoff_ms and row['duration_ms'] <= threshold:
                    completed += row['completed']
                    qualified += sample['expected'] == 'qualified' and _qualified(row)
            else:
                right_censored += 1
        windows[str(minutes)] = {'registered': total, 'observed_window': window_observed,
            'age_unknown': total - sum(times.get(s['job_id']) is not None for s in samples),
            'right_censored': right_censored, 'not_started_by_cutoff': not_started,
            'completed': completed, 'qualified': qualified, 'quality_review_pending': quality_review_pending,
            'observed_completion_rate': _rate(completed, window_observed),
            'observed_qualified_rate': _rate(qualified, qualified_window_observed),
            'registered_attainment': _rate(completed, total),
            'registered_qualified_attainment': _rate(qualified, sum(s['expected'] == 'qualified' for s in samples))}
    signals = {name: _rate(sum(row[name] for row in rows), known) for name in
        ('completed', 'required_roles_valid', 'generation_passed', 'audit_passed', 'source_decision_reviewed', 'important_claims_verified')}
    signals['without_reported_contradiction'] = _rate(sum(not row['contradiction'] for row in rows), known)
    return {'registered': total, 'supplied_terminal': len(present), 'terminal_by_cutoff': known,
        'missing': total - len(present), 'chronology_unverified': sum(times[s['job_id']] is None for s, _ in present),
        'after_cutoff': sum(times[s['job_id']] is not None and times[s['job_id']][1] > cutoff_ms for s, _ in present),
        'classifications': {name: classes[name] for name in sorted(CLASSIFICATIONS)},
        'quality': _quality(samples, observed), 'pressure': _pressure(samples, observed),
        'quality_by_role': {role: _quality([s for s in samples if s['role'] == role], observed) for role in ('candidate', 'baseline')},
        'signals': signals, 'completion_minutes': windows,
        'duration_ms': {'count': known, 'p50': _quantile([r['duration_ms'] for r in rows], .5),
                        'p95': _quantile([r['duration_ms'] for r in rows], .95), 'method': 'nearest_rank'},
        'tokens': {'final_covered_jobs': len(final_tokens), 'final_missing_jobs': known - len(final_tokens),
                   'unobserved_jobs': total - known, 'observed_final_tokens': sum(final_tokens) if final_tokens else None}}


def _ledger_tokens(samples, snapshot, cutoff_ms):
    if snapshot is None:
        return {'status': 'not_provided', 'charged': None, 'observed_actual': None}
    def require(condition):
        if not condition: raise ValueError('Invalid or contradictory ledger snapshot')
    require(isinstance(snapshot, dict) and _integer(snapshot.get('last_ms')))
    require('blocked' in snapshot and (snapshot['blocked'] is None
            or isinstance(snapshot['blocked'], str) and bool(snapshot['blocked'].strip())))
    jobs, attempts, spent = snapshot.get('jobs'), snapshot.get('attempts'), snapshot.get('spent')
    require(isinstance(jobs, dict) and isinstance(attempts, dict) and isinstance(spent, dict))
    index = {s['job_id']: s for s in samples}
    for job_id, job in jobs.items():
        require(isinstance(job_id, str) and job_id in index and isinstance(job, dict)
                and job.get('stage') == index[job_id]['stage'])
    physical, charged, reserved, transport, http = [], 0, 0, 0, 0
    for attempt_id, row in attempts.items():
        require(isinstance(attempt_id, str) and bool(attempt_id) and isinstance(row, dict))
        job_id = row.get('job_id')
        require(isinstance(job_id, str) and job_id in jobs and row.get('stage') == index[job_id]['stage'])
        require(all(_integer(row.get(key)) for key in ('tokens', 'transport', 'http'))
                and row['transport'] + row['http'] > 0 and 'actual_tokens' in row
                and (row['actual_tokens'] is None or _integer(row['actual_tokens']))
                and type(row.get('final_tokens')) is bool
                and (not row['final_tokens'] or row['actual_tokens'] is not None))
        require('cached_input_tokens' not in row or _integer(row['cached_input_tokens']))
        if row['http']:
            physical.append(row)
        else:
            require(row['tokens'] == 0 and row['actual_tokens'] in (None, 0))
        observed = row['actual_tokens']
        charged += observed if row['final_tokens'] else max(row['tokens'], observed if observed is not None else 0)
        reserved += row['tokens']
        transport += row['transport']
        http += row['http']
    expected = {'tokens': charged, 'transport': transport, 'http': http, 'jobs': len(jobs)}
    require(all(_integer(spent.get(key)) and spent[key] == value for key, value in expected.items()))
    if snapshot['last_ms'] > cutoff_ms:
        return {'status': 'after_cutoff_unverified', 'snapshot_last_event_ms': snapshot['last_ms'],
                'charged': None, 'observed_actual': None}
    actual = [row['actual_tokens'] for row in physical if row['actual_tokens'] is not None]
    final = [row['actual_tokens'] for row in physical if row['final_tokens']]
    observed = sum(actual) if actual else 0 if not physical else None
    return {'status': 'observed_snapshot', 'snapshot_last_event_ms': snapshot['last_ms'],
        'job_reservations': len(jobs), 'transport_reserved_units': transport, 'http_reserved_units': http,
        'http_events': len(physical), 'observed_attempts': len(actual), 'usage_unknown_attempts': len(physical) - len(actual),
        'final_attempts': len(final), 'initial_reserved': reserved, 'observed_actual': observed,
        'final_actual': sum(final) if final else 0 if not physical else None,
        'charged': charged, 'held_above_observed': charged - sum(actual),
        'over_reserved_attempts': sum(row['actual_tokens'] is not None and row['actual_tokens'] > row['tokens'] for row in physical),
        'campaign_blocked': snapshot['blocked'] is not None,
        'basis': 'Latest actual per physical reservation; nonfinal=max(reserved,observed), final=actual. Not a provider invoice.',
        'cached_input_added': False, 'added_to_result_token_totals': False}


def _models(samples, results, times, cutoff_ms):
    counts, role_routes = Counter(), {}
    identity_rows = returned_missing = unknown_roles = missing_jobs = 0
    observed_jobs = 0
    for sample in samples:
        job_id = sample['job_id']
        timing = times.get(job_id)
        if timing is None or timing[1] > cutoff_ms: continue
        observed_jobs += 1
        models = results[job_id]['actual_models']
        missing_jobs += not models
        for row in models:
            identity_rows += 1
            returned_missing += row['returned'] is None
            counts[(row['role'], row['requested'], row['returned'])] += 1
            if row['role'].lower() in ('unobserved', 'unknown'):
                unknown_roles += 1
            else:
                role_routes.setdefault((job_id, row['role']), set()).add(row['requested'])
    return {'terminal_job_denominator': observed_jobs, 'jobs_without_model_identities': missing_jobs,
        'observed_identity_rows': identity_rows, 'returned_identity_missing': returned_missing,
        'role_identity_unknown': unknown_roles,
        'requested_returned': [{'role': key[0], 'requested': key[1], 'returned': key[2], 'identity_rows': value}
                              for key, value in sorted(counts.items(), key=lambda item: tuple(v or '' for v in item[0]))],
        'role_job_denominator': len(role_routes),
        'role_jobs_with_multiple_requested_routes': sum(len(routes) > 1 for routes in role_routes.values()),
        'basis': 'Cutoff-confirmed result.actual_models only; a returned label is not proof of complete delivery or quality.',
        'first_choice': {'status': 'unverified', 'delivery_rate': None, 'qualified_rate': None, 'denominator': None,
            'missing_evidence': 'Preregistered required roles/intended primary routes and complete matching request/delivery outcomes.'},
        'fallback': {'status': 'unverified', 'count': None, 'rate': None, 'denominator': None,
            'missing_evidence': 'Causal route-transition/retry evidence. Alias/version label differences and route diversity are not fallback proof.'}}


def campaign_statistics(samples, results, *, cutoff_ms, ledger_snapshot=None):
    """Summarize validated terminal evidence; malformed inputs raise ValueError.

    Optional integer started_at_ms/finished_at_ms must agree exactly with
    duration_ms. No timestamps means chronology_unverified, never inferred from
    source dates or job deadlines. The caller alone authenticates ledger/bytes.
    """
    if not _integer(cutoff_ms): raise ValueError('Nonnegative integer cutoff_ms required')
    errors = validate_evidence(samples, results)
    if errors: raise ValueError(';'.join(errors))
    accepted = results if isinstance(results, dict) else {r['job_id']: r for r in results}
    times = {job_id: _chronology(row) for job_id, row in accepted.items()}
    stages = {}
    for stage in ('S1', 'S2', 'S3', 'S4'):
        subset = [s for s in samples if s['stage'] == stage]
        stages[stage] = _group(subset, accepted, times, cutoff_ms)
        stages[stage]['modes'] = {mode: _group([s for s in subset if s['mode'] == mode], accepted, times, cutoff_ms) for mode in MODES}
    return {'schema': 'campaign.statistics.v1', 'cutoff_ms': cutoff_ms,
        'formal_publication': False, 'qualified_for_campaign': False,
        'overall': _group(samples, accepted, times, cutoff_ms), 'stages': stages,
        'modes': {mode: _group([s for s in samples if s['mode'] == mode], accepted, times, cutoff_ms) for mode in MODES},
        'ledger_tokens': _ledger_tokens(samples, ledger_snapshot, cutoff_ms),
        'models': _models(samples, accepted, times, cutoff_ms),
        'recovery': {'status': 'unverified', 'incident_chronology': 'not_observed_in_current_result_schema',
            'post_recovery_denominator': None, 'post_recovery_completion_rate': None,
            'missing_evidence': 'Linked 429/5xx incidents, explicit recovery observation times and subsequent eligible job chronology.'},
        'correlation': {'registered_jobs': len(samples), 'distinct_tickers': len({s['ticker'] for s in samples}),
            'distinct_source_cutoffs': len({s['cutoff'] for s in samples}),
            'distinct_ticker_cutoff_pairs': len({(s['ticker'], s['cutoff']) for s in samples}),
            'same_ticker_or_date_dependence_possible': True, 'cluster_adjusted_intervals': False,
            'long_term_success_lower_bound': False},
        'provenance': {'samples_sha256': _digest(samples), 'results_sha256': _digest(results),
            'ledger_snapshot_sha256': _digest(ledger_snapshot) if ledger_snapshot is not None else None,
            'classification_basis': 'cutoff-confirmed terminal result.classification, not automatic qualification',
            'qualification_basis': 'quality_campaign_acceptance shared predicates plus preregistered expected=qualified',
            'timing_basis': 'verified job_reserve to job_finish duration including cleanup; all terminal outcomes, not successful-only',
            'window_basis': 'terminal outcome or known elapsed window; missing/untimed age is unknown, not assumed failure',
            'token_basis': 'result.tokens is per-job final actual total; cache input is not added',
            'interval_basis': 'nominal Wilson95 iid reference, not cluster adjusted; observed assessable jobs only or complete fixed pilot'},
        'limitations': ['Supplied JSON hashes do not authenticate physical evidence or external reviewers.',
            'All numeric classifications and rates exclude post-cutoff or untimed results; their counts remain visible.',
            'Pooled baseline/candidate rates are not a treatment estimate; quality_by_role keeps the roles separate.',
            'Same ticker/date inputs may be correlated; nominal intervals are descriptive and not a long-term success lower bound.',
            'Unobserved or review-pending jobs do not become failures to manufacture a pilot confidence interval.',
            'Private statistics do not authorize stage passage, deployment or canary readiness.']}
