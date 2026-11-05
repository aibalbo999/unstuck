"""Campaign preregistration tests: invented samples are NEVER source approval."""
import copy
import json
from pathlib import Path

import pytest

import quality_campaign_protocol as protocol
from quality_campaign_budget import BudgetDenied
from quality_campaign_wire import ReplayAbort

ROLES = {'v1': [11, 1, 2, 3, 20, 4, 5, 6, 21, 7], 'v2': [11, 12, 13, 20, 14, 15, 21, 16],
         'v3': [17, 18, 20, 21, 19], 'v4': [22, 23, 24]}


def manifest():
    rows = []
    def row(stage, mode, index, role='candidate', expected='qualified'):
        sample = f'{stage}-{mode}-{index}'
        return {'job_id': sample + '-' + role, 'sample_id': sample, 'stage': stage,
            'mode': mode, 'role': role, 'ticker': f'{1000 + index}.TW',
            'cutoff': f'2026-09-{1 + index % 3:02}', 'industry': f'fixture-sector-{index % 5}',
            'financial': index % 5 == 0, 'expected': expected,
            'required_roles': ROLES[mode].copy(),
            'source_sha256': protocol.sha(sample.encode()), 'route_sha256': 'b' * 64,
            'fulltext_review': stage == 'S3' and index < 5,
            'manifest': {'path': f'/private/tmp/fixture-only/{sample}-{role}.json', 'sha256': 'd' * 64}}
    for i in range(4): rows.append(row('S1', 'v4', 50 + i))
    for m in ('v1', 'v2', 'v3', 'v4'):
        for i in range(3):
            roles = ('baseline', 'candidate') if i % 2 == 0 else ('candidate', 'baseline')
            rows.extend(row('S2', m, 60 + i, role) for role in roles)
    for batch in range(10):
        for m in ('v1', 'v2', 'v3', 'v4'):
            rows.extend(row('S3', m, i) for i in range(batch * 3, batch * 3 + 3))
    for m in ('v1', 'v2', 'v3', 'v4'): rows.append(row('S4', m, 90))
    return {'schema': 'campaign.protocol.v1', 'campaign_id': 'offline-fixture',
        'baseline_revision': protocol.BASELINE_REVISION,
        'rubric_sha256': protocol.rubric_digest(), 'samples': rows,
        'limitations': 'Invented unit-test samples, not approved source or live authority'}


def test_fixed_denominators_and_industry_review_selection():
    value = manifest()
    validated = protocol.validate_protocol(value)
    assert len(validated['samples']) == 152
    value['samples'][0]['ticker'] = 'CHANGED'
    assert validated['samples'][0]['ticker'] != 'CHANGED'


@pytest.mark.parametrize('case', ['missing', 'duplicate', 'same_cutoff', 's1_reuse',
    'one_industry', 'no_finance', 'review_after_results', 'unpaired', 'route_confounded',
    'not_interleaved', 'future_baseline', 'changed_rubric', 'relative_manifest'])
def test_invalid_preregistration_cannot_become_an_allowlist(case):
    value = manifest()
    rows = value['samples']
    s3 = [r for r in rows if r['stage'] == 'S3']
    s2 = [r for r in rows if r['stage'] == 'S2']
    if case == 'missing': rows.pop()
    if case == 'duplicate': rows[-1]['job_id'] = rows[0]['job_id']
    if case == 'same_cutoff':
        s3[1].update(ticker=s3[0]['ticker'], cutoff=s3[0]['cutoff'])
    if case == 's1_reuse':
        s3[0].update(ticker=rows[0]['ticker'], cutoff=rows[0]['cutoff'])
    if case == 'one_industry':
        for r in s3: r['industry'] = 'one'
    if case == 'no_finance':
        for r in s3: r['financial'] = False
    if case == 'review_after_results': s3[0]['fulltext_review'] = False
    if case == 'unpaired': s2[0]['source_sha256'] = 'e' * 64
    if case == 'route_confounded': s2[0]['route_sha256'] = 'e' * 64
    if case == 'not_interleaved': rows[4], rows[6] = rows[6], rows[4]
    if case == 'future_baseline': value['baseline_revision'] = 'f' * 40
    if case == 'changed_rubric': value['rubric_sha256'] = 'f' * 64
    if case == 'relative_manifest': rows[0]['manifest']['path'] = '../unregistered.json'
    with pytest.raises(ReplayAbort): protocol.validate_protocol(value)


def test_bootstrap_is_exclusive_and_resume_never_initializes_missing_ledger(tmp_path, monkeypatch):
    # Binding verification is a separate boundary; this slice exercises real
    # durable SQLite, fixed anchor, protocol bytes and filesystem identities.
    monkeypatch.setattr(protocol, 'verify_plans', lambda value: {
        r['job_id']: {'code_sha256': ('a' if r['role'] == 'candidate' else 'c') * 64,
                     'source_sha256': r['source_sha256'], 'route_sha256': r['route_sha256']}
        for r in value['samples']})
    value = manifest()
    root, anchor = tmp_path / 'campaign', tmp_path / 'approved-campaign-anchor.json'
    session = protocol.Campaign.create(anchor, root, value)
    assert session.ledger.snapshot()['spent']['jobs'] == 0
    assert session.ledger.snapshot()['live_deadline_ms'] is None
    with pytest.raises(ReplayAbort): protocol.Campaign.create(anchor, root, value)
    with pytest.raises(ReplayAbort): protocol.Campaign.create(anchor, tmp_path / 'new-root', value)
    reopened = protocol.Campaign.resume(anchor)
    assert reopened.ledger.config == session.ledger.config
    session.ledger.path.unlink()
    with pytest.raises(ReplayAbort): protocol.Campaign.resume(anchor)
    assert not session.ledger.path.exists()


@pytest.mark.parametrize('case', ['protocol', 'root_replaced', 'ledger_replaced', 'anchor_public'])
def test_resume_detects_evidence_drift(tmp_path, monkeypatch, case):
    monkeypatch.setattr(protocol, 'verify_plans', lambda value: {
        r['job_id']: {'code_sha256': 'a' * 64, 'source_sha256': r['source_sha256'],
                     'route_sha256': r['route_sha256']} for r in value['samples']})
    anchor, root = tmp_path / 'anchor.json', tmp_path / 'campaign'
    session = protocol.Campaign.create(anchor, root, manifest())
    if case == 'protocol': (root / 'protocol.json').write_text('{}')
    if case == 'root_replaced':
        root.rename(tmp_path / 'old')
        root.mkdir(mode=0o700)
    if case == 'ledger_replaced':
        data = session.ledger.path.read_bytes()
        session.ledger.path.rename(root / 'old.sqlite3')
        session.ledger.path.write_bytes(data)
        session.ledger.path.chmod(0o600)
    if case == 'anchor_public': anchor.chmod(0o644)
    with pytest.raises(ReplayAbort): protocol.Campaign.resume(anchor)


def test_missing_authoritative_reviews_never_start_live_clock(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, 'verify_plans', lambda value: {
        r['job_id']: {'code_sha256': 'a' * 64, 'source_sha256': r['source_sha256'],
                     'route_sha256': r['route_sha256']} for r in value['samples']})
    session = protocol.Campaign.create(tmp_path / 'anchor.json', tmp_path / 'campaign', manifest())
    with pytest.raises(ReplayAbort): _run_next(session)
    state = session.ledger.snapshot()
    assert state['live_deadline_ms'] is None
    assert state['jobs'] == {}


def test_campaign_stop_is_durable_and_does_not_refund(tmp_path):
    from quality_campaign_budget import CampaignBudget, BudgetDenied
    ledger = CampaignBudget(tmp_path / 'budget.sqlite3', {'campaign_id': 'fixture',
        'code_sha256': 'a' * 64, 'source_sha256': 'b' * 64, 'route_sha256': 'c' * 64})
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    ledger.reserve_job('job', 'batch')
    ledger.stop('source_integrity_risk', evidence_sha256='d' * 64)
    with pytest.raises(BudgetDenied): ledger.check()
    ledger.finish_job('job', status='cancelled')
    ledger.finish_batch('batch', cleanup_evidence_sha256='e' * 64)
    assert ledger.snapshot()['spent']['jobs'] == 1
    other = CampaignBudget(ledger.path, ledger.identity)
    with pytest.raises(BudgetDenied): other.start_batch('new', 'S1')
    assert other.snapshot()['blocked'] == 'source_integrity_risk'


def put(path, value):
    raw = protocol.encoded(value)
    path.write_bytes(raw)
    path.chmod(0o600)
    return {'path': str(path), 'sha256': protocol.sha(raw)}


def executable_campaign(tmp_path, monkeypatch):
    """Only the executor/provider boundary and freeze/source approval are fake.

    Uses real anchor, roster, ledger, reservations, settlement, private artifact
    files, immutable receipts and external-review binding. NEVER live evidence.
    """
    value = manifest()
    for row in value['samples']:
        folder = tmp_path / row['job_id']
        folder.mkdir(mode=0o700)
        source = put(folder / 'database-job.json', {'pipeline_id': row['mode'],
            'data_snapshot': {'ticker': row['ticker'], 'fetch_date': row['cutoff']}})
        row['source_sha256'] = source['sha256']
        # Freeze verification is mocked, but revision tests need the complete
        # immutable profile to prove it cannot be substituted between versions.
        frozen = {'schema': 'campaign.frozen_job.v1', 'campaign_id': value['campaign_id'],
            'binding_id': row['job_id'], 'stage': row['stage'], 'mode': row['mode'],
            'role': row['role'], 'purpose': 'qualification', 'dev': str(tmp_path / 'fixture-dev'),
            'code_files': {'fixture.py': ('a' if row['role'] == 'candidate' else 'c') * 64},
            'harness_files': {'fixture-harness.py': 'd' * 64}, 'runtime_files': {'fixture': 'e' * 64},
            'fixture_job_id': row['job_id'], 'source': source}
        for name in ('routes', 'environment', 'billing_review', 'reservation_review', 'source_review', 'policies'):
            frozen[name] = put(folder / (name + '.json'), {'fixture': name})
        row['manifest'] = put(folder / 'manifest.json', frozen)
    bindings = {r['job_id']: {'code_sha256': ('a' if r['role'] == 'candidate' else 'c') * 64,
        'source_sha256': r['source_sha256'], 'route_sha256': r['route_sha256']} for r in value['samples']}
    monkeypatch.setattr(protocol, 'verify_plans', lambda _: bindings)
    evidence = put(tmp_path / 'offline-test-only.json', {'warning': 'NOT REAL S0 APPROVAL'})
    review = {'schema': 'campaign.s0_review.v1', 'decision': 'approved',
        'roster_sha256': protocol.sha(protocol.encoded(value['samples'])),
        'rubric_sha256': value['rubric_sha256'], 'candidate_code_sha256': 'a' * 64,
        'checks': {name: {'status': 'passed', 'evidence': [evidence]} for name in
            ('full_non_live_regression', 'required_integration_lanes', 'skips_classified', 'independent_review', 'maintenance_isolation')},
        'original_regression': [{'mode': r['mode'], 'source_sha256': r['source_sha256']} for r in value['samples'] if r['stage'] == 'S2' and r['role'] == 'baseline']}
    value['s0_review'] = put(tmp_path / 's0-review-fixture.json', review)
    session = protocol.Campaign.create(tmp_path / 'anchor.json', tmp_path / 'campaign', value)
    class Plan:
        def __init__(self, path, digest):
            self.expected_sha = digest
            self.manifest = protocol.referenced({'path': str(path), 'sha256': digest})
            self.row = copy.deepcopy(next(r for r in value['samples'] if r['job_id'] == self.manifest['fixture_job_id']))
            self.row['manifest'] = {'path': str(path), 'sha256': digest}
        def source_job(self):
            return protocol.referenced(self.manifest['source'])
        def verify(self):
            return bindings[self.row['job_id']] | {'code_sha256': self.manifest['code_files']['fixture.py']}
    monkeypatch.setattr(protocol, 'FrozenJob', Plan)
    monkeypatch.setattr(protocol, 'frozen_mode_roles', lambda frozen: ROLES[frozen['mode']].copy())
    def executor(plan, ledger, job_id, *, storage_budget, _storage):
        assert _storage.lease.receipt()['state']=='active'
        assert _storage.reference==storage_budget
        output = ledger.path.parent / job_id
        output.mkdir(mode=0o700)
        (output / 'reports').mkdir(mode=0o700)
        actual = plan.verify()
        calls, http_rows, prompts = [], [], []
        for agent in plan.row['required_roles']:
            logical, physical = f'{job_id}-{agent}-transport', f'{job_id}-{agent}-http'
            billing = {'billing_status': 'verified_free', 'billing_identity_sha256': 'd' * 64,
                'reservation_basis_sha256': 'e' * 64, 'cost_microusd': 0, 'actual_hashes': actual}
            ledger.reserve_attempt(logical, job_id, tokens=0, http=0, transport=1, **billing)
            ledger.reserve_attempt(physical, job_id, tokens=100, http=1, transport=0, **billing)
            ledger.settle_attempt(physical, actual_tokens=75, actual_cost_microusd=0,
                usage_evidence_sha256='f' * 64, usage_final=True)
            calls.append({'attempt_id': logical, 'agent_num': agent, 'completed_response': True, 'status': 'completed'})
            http_rows.append({'attempt_id': logical, 'http_id': physical, 'response_complete': True,
                'model': 'gemini-fixture', 'provider_model_version': 'observed-fixture'})
            prompts.append({'attempt_id': logical, 'config': {'temperature': 0, 'max_output_tokens': 10}, 'prompt': 'offline fixture'})
        artifacts = {}
        for field, suffix in (('html_key', 'html'), ('md_key', 'md'), ('data_key', 'json')):
            path = output / 'reports' / ('report.' + suffix)
            ref = put(path, {'synthetic': 'EXECUTOR FIXTURE NOT REAL REPORT'})
            artifacts[field] = {'key': path.name, 'bytes': len(path.read_bytes()), 'sha256': ref['sha256']}
        outcome = {'job_id': job_id, 'mode': plan.row['mode'], 'status': 'published',
            'frozen_verified': True, 'publication': {'publication_class': 'verified_research'},
            'artifacts': artifacts,
            'provider_transport_calls': calls, 'http_attempts': http_rows}
        outcome_ref = put(output / 'outcome.json', outcome)
        (output / 'prompts.jsonl').write_bytes(b'\n'.join(protocol.encoded(p) for p in prompts) + b'\n')
        (output / 'prompts.jsonl').chmod(0o600)
        cleanup_ref = put(output / ('watchdog-' + job_id + '.cleanup.json'), {
            'job_id': job_id, 'ledger_binding_sha256': ledger.binding,
            'deadline_ms': ledger.snapshot()['jobs'][job_id]['deadline_ms'], 'guardian_reaped': True, 'process_group_absent': True})
        ledger.finish_job(job_id, status='completed')
        receipt = {'job_id': job_id, 'status': 'private_pipeline_completed', 'formal_publication': False,
            'qualified_for_campaign': False, 'manifest_sha256': plan.row['manifest']['sha256'],
            'prompts_sha256': protocol.sha((output / 'prompts.jsonl').read_bytes()),
            'cleanup_sha256': cleanup_ref['sha256'], 'outcome_sha256': outcome_ref['sha256']}
        put(output / 'parent-receipt.json', receipt)
        return receipt
    monkeypatch.setattr(protocol, 'execute_reserved_job', executor)
    return session


def content_review(session, job_id):
    from test_quality_campaign_acceptance import result
    sample = session._sample(job_id)
    output = session.root / job_id
    parent_raw = (output / 'parent-receipt.json').read_bytes()
    parent = json.loads(parent_raw)
    outcome = json.loads((output / 'outcome.json').read_bytes())
    source = json.loads(Path(sample['manifest']['path']).read_bytes())['source']
    documents = {'source': protocol.encoded(json.loads(Path(source['path']).read_bytes())['data_snapshot']),
        'md_key': (output / 'reports' / outcome['artifacts']['md_key']['key']).read_bytes(),
        'outcome': (output / 'outcome.json').read_bytes()}
    positions = {key: {'document': key, 'start': 0, 'end': len(raw), 'sha256': protocol.sha(raw)}
                 for key, raw in documents.items()}
    review = {'schema': 'campaign.content_review.v1', 'job_id': job_id, 'reviewer': 'OFFLINE TEST ONLY',
        'evidence': {'source_sha256': sample['source_sha256'], 'parent_receipt_sha256': protocol.sha(parent_raw),
            'outcome_sha256': parent['outcome_sha256'], 'artifacts_sha256': protocol.sha(protocol.encoded(outcome['artifacts'])),
            'prompts_sha256': protocol.sha((output / 'prompts.jsonl').read_bytes()),
            'rubric_sha256': session.protocol['rubric_sha256']}, 'assessment': result(sample), 'positions': positions}
    review['assessment']['independent_review']['evidence_refs'] = {
        key: ['source', 'md_key'] for key in review['assessment']['independent_review']['dimensions']}
    review['assessment']['failure_review']['evidence_refs'] = ['outcome']
    return put(session.root / ('external-review-' + job_id + '.json'), review)


def test_controller_requires_artifact_review_and_retains_real_ledger_counters(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    first = _run_next(session)
    first_id = first['job_id']
    with pytest.raises(ReplayAbort, match='pending external'): _run_next(session)
    assert session.ledger.snapshot()['spent']['jobs'] == 1
    actual = session.record_review(first_id, content_review(session, first_id))
    assert actual['tokens'] == 225  # 3 real ledger observations, not review's invented 100.
    assert actual['actual_models'][0]['returned'] == 'observed-fixture'
    with pytest.raises(ReplayAbort): session.pass_stage('S1')
    second = _run_next(session)
    session.record_review(second['job_id'], content_review(session, second['job_id']))
    assert session.pass_stage('S1')['decision'] == 'passed'
    resumed = protocol.Campaign.resume(session.anchor)
    third = _run_next(resumed)
    assert third['job_id'].startswith('S2-')
    state = resumed.ledger.snapshot()
    assert state['spent']['jobs'] == 3
    assert state['spent']['http'] == state['spent']['transport'] == 16
    assert state['spent']['tokens'] == 1200
    assert state['stage_spent']['S1']['jobs'] == 2
    assert all(b['ended_ms'] is not None for b in state['batches'].values())


@pytest.mark.parametrize('mutation', ['snapshot', 'outcome', 'review_source', 'receipt', 'review_replaced'])
def test_changed_report_or_review_cannot_authorize_next_dispatch(tmp_path, monkeypatch, mutation):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = _run_next(session)['job_id']
    ref = content_review(session, job_id)
    if mutation == 'snapshot': (session.root / job_id / 'reports' / 'report.json').write_text('changed')
    if mutation == 'outcome': (session.root / job_id / 'outcome.json').write_text('{}')
    if mutation == 'review_source':
        value = json.loads(Path(ref['path']).read_bytes())
        value['evidence']['source_sha256'] = 'f' * 64
        ref = put(Path(ref['path']), value)
    if mutation == 'receipt': (session.root / job_id / 'parent-receipt.json').write_text('{}')
    if mutation == 'review_replaced':
        session.record_review(job_id, ref)
        Path(ref['path']).write_text('{}')
        with pytest.raises((ReplayAbort, BudgetDenied)): _run_next(session)
    else:
        try: session.record_review(job_id, ref)
        except ReplayAbort: pass
        with pytest.raises((ReplayAbort, BudgetDenied)): _run_next(session)
    assert session.ledger.snapshot()['spent']['jobs'] == 1


def test_anchor_lock_prevents_overlapping_coordinators(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    with session.lock():
        with pytest.raises(ReplayAbort, match='holds the anchor'):
            _run_next(protocol.Campaign.resume(session.anchor))
    assert session.ledger.snapshot()['spent']['jobs'] == 0


def test_raw_ledger_hash_cannot_skip_stage_acceptance(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = _run_next(session)['job_id']
    session.record_review(job_id, content_review(session, job_id))
    session.ledger.pass_stage('S1', acceptance_evidence_sha256='a' * 64)
    with pytest.raises(ReplayAbort, match='no verified acceptance receipt'): _run_next(session)
    assert session.ledger.snapshot()['spent']['jobs'] == 1


def test_industry_whitespace_does_not_invent_five_industries():
    value = manifest()
    labels = ('Technology', ' Technology', 'Technology ', '\tTechnology', 'technology')
    for index, row in enumerate(value['samples']):
        if row['stage'] == 'S3': row['industry'] = labels[index % len(labels)]
    with pytest.raises(ReplayAbort, match='industry coverage'): protocol.validate_protocol(value)


@pytest.mark.parametrize('change', ['bad_offset', 'bad_hash', 'unknown_position', 'missing_source'])
def test_completed_review_requires_actual_source_and_artifact_positions(tmp_path, monkeypatch, change):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = _run_next(session)['job_id']
    ref = content_review(session, job_id)
    value = json.loads(Path(ref['path']).read_bytes())
    if change == 'bad_offset': value['positions']['source']['end'] = 10000000
    if change == 'bad_hash': value['positions']['source']['sha256'] = 'e' * 64
    if change == 'unknown_position': value['assessment']['failure_review']['evidence_refs'] = ['unknown']
    if change == 'missing_source': del value['positions']['source']
    ref = put(Path(ref['path']), value)
    with pytest.raises(ReplayAbort): session.record_review(job_id, ref)
    assert session.ledger.snapshot()['spent']['jobs'] == 1


def plans_fixture(tmp_path, monkeypatch):
    value = manifest()
    evidence = put(tmp_path / 'review-evidence.json', {'fixture_only': True})
    backend = tmp_path / 'isolated' / 'backend'
    backend.mkdir(parents=True)
    contract = backend / 'pipeline_modes.py'
    contract.write_text('PIPELINE_DEFINITIONS = ' + repr({m: {'agents': roles} for m, roles in ROLES.items()}) + '\n')
    plans = {}
    for row in value['samples']:
        review = put(tmp_path / (row['job_id'] + '-source-review.json'), {
            **{f: row[f] for f in ('ticker', 'cutoff', 'industry', 'financial')},
            'evidence_refs': [evidence]})
        frozen = {'campaign_id': value['campaign_id'], 'binding_id': row['job_id'],
            **{f: row[f] for f in ('stage', 'mode', 'role')},
            'purpose': 'qualification', 'dev': str(backend.parent),
            'code_files': {'backend/pipeline_modes.py': protocol.sha(contract.read_bytes())},
            'source_review': review,
            **{f: {'path': '/private/tmp/fixture-only', 'sha256': 'b' * 64} for f in
                ('routes', 'environment', 'billing_review', 'reservation_review', 'policies')}}
        plans[row['manifest']['path']] = {'manifest': frozen, 'hashes': {
            'code_sha256': ('a' if row['role'] == 'candidate' else 'c') * 64,
            **{f: row[f] for f in ('source_sha256', 'route_sha256')}}}
    class Plan:
        def __init__(self, path, digest): self.record = plans[path]
        @property
        def manifest(self): return copy.deepcopy(self.record['manifest'])
        def verify(self): return copy.deepcopy(self.record['hashes'])
    monkeypatch.setattr(protocol, 'FrozenJob', Plan)
    roots = []
    monkeypatch.setattr(protocol, 'baseline_checkout', roots.append)
    return value, plans, roots


def test_actual_plan_binding_checks_all_modes_roles_and_pair_policies(tmp_path, monkeypatch):
    value, plans, roots = plans_fixture(tmp_path, monkeypatch)
    bindings = protocol.verify_plans(value)
    assert set(bindings) == {r['job_id'] for r in value['samples']}
    assert len(roots) == 1


@pytest.mark.parametrize('change', ['role', 'binding', 'code', 'source', 'source_review', 'pair_profile'])
def test_actual_plan_drift_cannot_initialize_a_campaign(tmp_path, monkeypatch, change):
    value, plans, roots = plans_fixture(tmp_path, monkeypatch)
    row = next(r for r in value['samples'] if r['stage'] == 'S2' and r['role'] == 'candidate')
    plan = plans[row['manifest']['path']]
    if change == 'role': plan['manifest']['role'] = 'baseline'
    if change == 'binding': plan['manifest']['binding_id'] = 'different'
    if change == 'code': plan['hashes']['code_sha256'] = 'f' * 64
    if change == 'source': plan['hashes']['source_sha256'] = 'f' * 64
    if change == 'pair_profile': plan['manifest']['policies']['sha256'] = 'f' * 64
    if change == 'source_review':
        ref = plan['manifest']['source_review']
        data = json.loads(Path(ref['path']).read_bytes())
        data['financial'] = 0  # False-ish is not verified financial identity.
        plan['manifest']['source_review'] = put(Path(ref['path']), data)
    with pytest.raises(ReplayAbort): protocol.verify_plans(value)


def test_qualified_role_claim_cannot_replace_completed_provider_node_evidence(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = _run_next(session)['job_id']
    # Preserve the original red's only-Agent-22 evidence after the positive
    # executor fixture was improved to emit every node and real ledger attempt.
    outcome_path = session.root / job_id / 'outcome.json'
    outcome = json.loads(outcome_path.read_bytes())
    outcome['provider_transport_calls'] = outcome['provider_transport_calls'][:1]
    changed = put(outcome_path, outcome)
    parent_path = session.root / job_id / 'parent-receipt.json'
    parent = json.loads(parent_path.read_bytes())
    parent['outcome_sha256'] = changed['sha256']
    put(parent_path, parent)
    observed = session.record_review(job_id, content_review(session, job_id))
    assert observed['required_roles_valid'] is False




def next_storage_review(session):
    state=session.ledger.snapshot()
    stage=next(s for s in protocol.STAGES if state['stages'].get(s)!='passed')
    raw=next(r for r in session.protocol['samples'] if r['stage']==stage and r['job_id'] not in state['jobs'])
    row=session._sample(raw['job_id'])
    return put(session.root.parent/(row['job_id']+'-storage-review.json'), {
        'schema':'stock.storage-budget-review.v1','decision':'reviewed',
        'manifest_sha256':row['manifest']['sha256'],'job_id':row['job_id'],
        'components':{k:16*1024**2 for k in ('source','artifacts','evidence','sqlite','temporary')},
        'maximum_files':1000,
        'basis':{k:'Synthetic offline test-only allowance' for k in ('source','artifacts','evidence','sqlite','temporary')}})


def _run_next(session):
    return session.run_next(storage_budget=next_storage_review(session))


def test_missing_storage_estimate_does_not_consume_live_clock_slot_or_ledger(tmp_path, monkeypatch):
    from storage.capacity import StorageCapacityUnavailable
    session=executable_campaign(tmp_path,monkeypatch)
    before=session.ledger.path.read_bytes();state=session.ledger.snapshot()
    with pytest.raises(StorageCapacityUnavailable):session.run_next()
    assert session.ledger.path.read_bytes()==before
    assert session.ledger.snapshot()==state
    assert not any((session.root/r['job_id']).exists() for r in session.protocol['samples'])


def test_denied_storage_claim_does_not_consume_live_clock_slot_or_ledger(tmp_path, monkeypatch):
    from storage.capacity import StorageCapacityUnavailable, _shared
    session=executable_campaign(tmp_path,monkeypatch)
    reference=next_storage_review(session)
    before=session.ledger.path.read_bytes();state=session.ledger.snapshot()
    monkeypatch.setattr(_shared(),'available_bytes',lambda:0)
    with pytest.raises(StorageCapacityUnavailable):session.run_next(storage_budget=reference)
    assert session.ledger.path.read_bytes()==before
    assert session.ledger.snapshot()==state
    assert not any((session.root/r['job_id']).exists() for r in session.protocol['samples'])


def test_protocol_reuses_one_bound_claim_through_original_runner(tmp_path, monkeypatch):
    import quality_campaign_runner as runner
    from storage.capacity import _shared
    session=executable_campaign(tmp_path,monkeypatch)
    executor=protocol.execute_reserved_job;calls=[]
    original=_shared().Reservation
    def counted(*args,**kwargs):
        value=original(*args,**kwargs);calls.append(value);return value
    monkeypatch.setattr(_shared(),'Reservation',counted)
    monkeypatch.setattr(protocol,'execute_reserved_job',runner.execute_reserved_job)
    def leaf(plan,ledger,job_id,reference,lease,fd,capability):
        assert len(calls)==1 and lease is calls[0]
        from types import SimpleNamespace
        return executor(plan,ledger,job_id,storage_budget=reference,
            _storage=SimpleNamespace(lease=lease,reference=reference))
    monkeypatch.setattr(runner,'_execute_reserved_job',leaf)
    result=_run_next(session)
    assert result['status']=='private_pipeline_completed'
    assert len(calls)==1 and calls[0].receipt()['state']=='completed'
    assert session.ledger.snapshot()['spent']['jobs']==1
