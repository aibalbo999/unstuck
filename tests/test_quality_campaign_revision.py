"""Real durable revision/coordinator tests; frozen executor is explicitly fake."""
import copy
from pathlib import Path

import pytest

import quality_campaign_protocol as protocol
from quality_campaign_budget import BudgetDenied
from quality_campaign_wire import ReplayAbort
from test_quality_campaign_protocol import executable_campaign, content_review, put, _run_next


def reviewed_failure(session):
    job_id = _run_next(session)['job_id']
    ref = content_review(session, job_id)
    review = protocol.referenced(ref)
    review['assessment'].update(audit_passed=False, root_cause='fixture_audit_failure')
    ref = put(Path(ref['path']), review)
    session.record_review(job_id, ref)
    return job_id


def proposed_revision(session, failed_job_id):
    state = session.ledger.snapshot()
    evidence = put(session.root / 'repair-check-fixture.json', {'warning': 'OFFLINE REPAIR FIXTURE ONLY'})
    repair = {'schema': 'campaign.repair_review.v1', 'decision': 'approved',
        'failed_job_id': failed_job_id, 'failure_review_sha256': state['reviews'][failed_job_id],
        'old_candidate_code_sha256': 'a' * 64, 'new_candidate_code_sha256': 'f' * 64,
        'rubric_sha256': session.protocol['rubric_sha256'],
        'root_cause': 'fixture_audit_failure', 'reviewer': 'OFFLINE REVIEW FIXTURE',
        'checks': {name: {'status': 'passed', 'evidence': [evidence]} for name in
            ('repair_reproduction', 'full_non_live_regression', 'required_integration_lanes', 'independent_review')}}
    plans = {}
    for row in session.protocol['samples']:
        if row['role'] != 'candidate' or row['job_id'] in state['jobs']: continue
        frozen = copy.deepcopy(protocol.referenced(row['manifest']))
        frozen.update(binding_id='revision2:' + protocol.sha(row['job_id'].encode())[:40],
                      code_files={'fixture.py': 'f' * 64})
        plans[row['job_id']] = put(session.root / ('revision-' + row['job_id'] + '.json'), frozen)
    revision = {'schema': 'campaign.candidate_revision.v1', 'campaign_id': session.protocol['campaign_id'],
        'failed_job_id': failed_job_id, 'original_protocol_sha256': protocol.sha(protocol.encoded(session.protocol)),
        'new_candidate_code_sha256': 'f' * 64, 'plans': plans,
        'review': put(session.root / 'repair-review-fixture.json', repair)}
    return put(session.root / 'revision-proposal.json', revision)


def test_terminal_times_are_ledger_facts_not_reviewer_claims(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = _run_next(session)['job_id']
    ref = content_review(session, job_id)
    review = protocol.referenced(ref)
    review['assessment'].update(started_at_ms=0, finished_at_ms=0)
    observed = session.record_review(job_id, put(Path(ref['path']), review))
    events = session.ledger.events()
    assert observed['started_at_ms'] == next(e['at_ms'] for e in events if e['kind'] == 'job_reserve')
    assert observed['finished_at_ms'] == next(e['at_ms'] for e in events if e['kind'] == 'job_finish')
    assert observed['finished_at_ms'] - observed['started_at_ms'] == observed['duration_ms']


def test_second_candidate_maps_whole_remaining_roster_without_budget_reset(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    failed = reviewed_failure(session)
    before = session.ledger.snapshot()
    protocol_bytes = (session.root / 'protocol.json').read_bytes()
    ref = proposed_revision(session, failed)
    session.register_candidate_revision(ref)
    resumed = protocol.Campaign.resume(session.anchor)
    after = resumed.ledger.snapshot()
    assert after['spent'] == before['spent']
    assert after['live_deadline_ms'] == before['live_deadline_ms']
    assert (session.root / 'protocol.json').read_bytes() == protocol_bytes
    assert resumed._sample(failed)['manifest'] == session.protocol['samples'][0]['manifest']
    for row in session.protocol['samples']:
        effective = resumed._sample(row['job_id'])
        if row['role'] == 'candidate' and row['job_id'] != failed:
            assert protocol.referenced(effective['manifest'])['code_files'] == {'fixture.py': 'f' * 64}
        else:
            assert effective['manifest'] == row['manifest']
    for _ in range(2):
        job_id = _run_next(resumed)['job_id']
        assert resumed.record_review(job_id, content_review(resumed, job_id))['code_sha256'] == 'f' * 64
    assert resumed.pass_stage('S1')['metrics']['accepted_code_sha256'] == 'f' * 64
    first = _run_next(resumed)['job_id']  # Fixed baseline then new candidate.
    assert resumed.record_review(first, content_review(resumed, first))['code_sha256'] == 'c' * 64
    second = _run_next(resumed)['job_id']
    assert resumed.record_review(second, content_review(resumed, second))['code_sha256'] == 'f' * 64
    assert resumed.ledger.snapshot()['spent']['jobs'] == 5


@pytest.mark.parametrize('case', ['missing_slot', 'used_slot', 'baseline_slot', 'source', 'route',
    'billing', 'harness', 'runtime', 'roles', 'mixed_code', 'same_code', 'failure_proof',
    'unreviewed_check', 'rubric', 'cause', 'not_failed'])
def test_revision_cannot_change_inputs_profiles_or_repair_authority(tmp_path, monkeypatch, case):
    session = executable_campaign(tmp_path, monkeypatch)
    failed = reviewed_failure(session) if case != 'not_failed' else _run_next(session)['job_id']
    if case == 'not_failed': session.record_review(failed, content_review(session, failed))
    ref = proposed_revision(session, failed)
    revision = protocol.referenced(ref)
    first = next(iter(revision['plans']))
    if case == 'missing_slot': revision['plans'].pop(first)
    elif case == 'used_slot': revision['plans'][failed] = revision['plans'][first]
    elif case == 'baseline_slot': revision['plans'][session.protocol['samples'][4]['job_id']] = revision['plans'][first]
    elif case in ('failure_proof', 'unreviewed_check', 'rubric', 'cause'):
        review = protocol.referenced(revision['review'])
        if case == 'failure_proof': review['failure_review_sha256'] = '0' * 64
        if case == 'unreviewed_check': review['checks'].pop('independent_review')
        if case == 'rubric': review['rubric_sha256'] = '0' * 64
        if case == 'cause': review['root_cause'] = 'unrelated_failure'
        revision['review'] = put(Path(revision['review']['path']), review)
    else:
        frozen = protocol.referenced(revision['plans'][first])
        field = {'source': 'source', 'route': 'routes', 'billing': 'billing_review',
            'harness': 'harness_files', 'runtime': 'runtime_files', 'roles': 'mode',
            'mixed_code': 'code_files', 'same_code': 'code_files'}.get(case)
        if field:
            frozen[field] = {'fixture.py': ('a' if case == 'same_code' else '0') * 64} if field == 'code_files' else {'changed': True}
            revision['plans'][first] = put(Path(revision['plans'][first]['path']), frozen)
    ref = put(Path(ref['path']), revision)
    before = session.ledger.snapshot()
    with pytest.raises((ReplayAbort, BudgetDenied)):
        session.register_candidate_revision(ref)
    assert session.ledger.snapshot()['candidate_revision'] is None
    assert session.ledger.snapshot()['spent'] == before['spent']
    assert not (session.root / 'candidate-revision.json').exists()


def test_unbound_revision_pointer_is_a_blocker_not_automatic_reset(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    failed = reviewed_failure(session)
    ref = proposed_revision(session, failed)
    put(session.root / 'candidate-revision.json', ref)
    with pytest.raises(ReplayAbort): protocol.Campaign.resume(session.anchor)
    assert session.ledger.snapshot()['spent']['jobs'] == 1


@pytest.mark.parametrize('case', ['revision', 'pointer', 'manifest', 'review', 'second_revision'])
def test_registered_revision_is_bound_across_resume(tmp_path, monkeypatch, case):
    session = executable_campaign(tmp_path, monkeypatch)
    ref = proposed_revision(session, reviewed_failure(session))
    revision = protocol.referenced(ref)
    session.register_candidate_revision(ref)
    if case == 'second_revision':
        with pytest.raises((ReplayAbort, BudgetDenied)): session.register_candidate_revision(ref)
    else:
        path = {'revision': ref['path'], 'pointer': str(session.root / 'candidate-revision.json'),
            'manifest': next(iter(revision['plans'].values()))['path'], 'review': revision['review']['path']}[case]
        Path(path).write_bytes(b'{}')
        with pytest.raises(ReplayAbort): protocol.Campaign.resume(session.anchor)
    assert session.ledger.snapshot()['spent']['jobs'] == 1


def test_raw_ledger_revision_cannot_turn_reviewed_success_into_repair_authority(tmp_path, monkeypatch):
    from quality_campaign_revision import binding_id
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = _run_next(session)['job_id']
    session.record_review(job_id, content_review(session, job_id))
    ref = proposed_revision(session, job_id)
    revision = protocol.referenced(ref)
    state = session.ledger.snapshot()
    additions = {binding_id(key): {'parent_binding_id': key,
        **(state['effective_bindings'][key] | {'code_sha256': 'f' * 64})} for key in revision['plans']}
    put(session.root / 'candidate-revision.json', ref)
    session.ledger.register_s1_candidate_revision(revisions=additions, failed_job_id=job_id,
        repair_evidence_sha256=ref['sha256'], reviewed_quality_failure_sha256=state['reviews'][job_id])
    with pytest.raises(ReplayAbort, match='failure'):
        protocol.Campaign.resume(session.anchor)
    assert session.ledger.snapshot()['spent']['jobs'] == 1


def test_controller_statistics_uses_real_timestamps_fixed_roster_and_separate_token_views(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = _run_next(session)['job_id']
    observed = session.record_review(job_id, content_review(session, job_id))
    before = session.ledger.snapshot()
    output = session.statistics()
    assert output['overall']['registered'] == 152
    assert output['stages']['S1']['registered'] == 4
    assert output['stages']['S1']['terminal_by_cutoff'] == 1
    assert output['stages']['S3']['registered'] == 120
    assert output['overall']['quality']['pilot_rate']['wilson_95'] is None
    assert output['overall']['tokens']['observed_final_tokens'] == 225
    assert output['ledger_tokens']['charged'] == 225
    assert output['ledger_tokens']['added_to_result_token_totals'] is False
    earlier = session.statistics(cutoff_ms=observed['started_at_ms'] - 1)
    assert earlier['overall']['terminal_by_cutoff'] == 0
    assert earlier['ledger_tokens']['status'] == 'after_cutoff_unverified'
    assert session.ledger.snapshot() == before
    Path(session.root / ('external-review-' + job_id + '.json')).write_bytes(b'{}')
    with pytest.raises(ReplayAbort): session.statistics()
