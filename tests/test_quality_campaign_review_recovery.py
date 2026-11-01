"""Review binding interruptions and incomplete failure review; offline only."""
import json
from pathlib import Path
import pytest
import quality_campaign_protocol as protocol
from quality_campaign_budget import BudgetDenied
from quality_campaign_wire import ReplayAbort
from test_quality_campaign_protocol import executable_campaign, content_review, put

@pytest.mark.parametrize('after_bind', [False, True])
def test_review_bind_interruption_cannot_reset_or_dispatch_past_known_stop(tmp_path, monkeypatch, after_bind):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    ref = content_review(session, job_id)
    value = json.loads(Path(ref['path']).read_bytes())
    value['assessment']['major_error'] = True
    ref = put(Path(ref['path']), value)
    budget_type = type(session.ledger)
    original = budget_type.bind_review
    def interrupted(ledger, *args, **kwargs):
        if after_bind:
            original(ledger, *args, **kwargs)
        raise RuntimeError('offline interruption at review binding')
    before = session.ledger.snapshot()['spent']
    with monkeypatch.context() as patch:
        patch.setattr(budget_type, 'bind_review', interrupted)
        with pytest.raises(RuntimeError, match='offline interruption'):
            session.record_review(job_id, ref)
    assert (session.root / ('review-' + job_id + '.json')).is_file()
    resumed = protocol.Campaign.resume(session.anchor)
    assert (job_id in resumed.ledger.snapshot()['reviews']) is after_bind
    with pytest.raises((ReplayAbort, BudgetDenied)):
        resumed.run_next()
    assert resumed.ledger.snapshot()['spent'] == before
    if after_bind:
        assert resumed.ledger.snapshot()['blocked'] == 'acceptance_safety_stop'
    else:
        assert resumed.ledger.snapshot()['blocked'] is None
        assert job_id not in resumed.ledger.snapshot()['reviews']
    assert (session.root / ('review-' + job_id + '.json')).is_file()


def test_ledger_review_binding_is_single_assignment_across_reopen(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    session.record_review(job_id, content_review(session, job_id))
    before = session.ledger.snapshot()
    resumed = protocol.Campaign.resume(session.anchor)
    with pytest.raises(BudgetDenied):
        resumed.ledger.bind_review(job_id, review_ref_sha256='f' * 64)
    with pytest.raises(BudgetDenied):
        resumed.ledger.bind_review('never-reserved-job', review_ref_sha256='f' * 64)
    assert resumed.ledger.snapshot()['reviews'] == before['reviews']
    assert resumed.ledger.snapshot()['spent'] == before['spent']


@pytest.mark.parametrize('failure', ['required_roles_valid', 'generation_passed', 'audit_passed', 'classification'])
def test_terminal_failed_review_cannot_pin_pending_failure_review(tmp_path, monkeypatch, failure):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    if failure == 'classification':
        output = session.root / job_id
        outcome = json.loads((output / 'outcome.json').read_bytes())
        outcome['publication']['publication_class'] = 'diagnostic_no_action'
        changed = put(output / 'outcome.json', outcome)
        parent = json.loads((output / 'parent-receipt.json').read_bytes())
        parent['outcome_sha256'] = changed['sha256']
        put(output / 'parent-receipt.json', parent)
    original = content_review(session, job_id)
    value = json.loads(Path(original['path']).read_bytes())
    if failure != 'classification':
        value['assessment'][failure] = False
    value['assessment']['failure_review'] = {'complete': False, 'evidence_refs': []}
    pending = put(session.root / 'pending-failure-review.json', value)
    with pytest.raises(ReplayAbort, match='pending'):
        session.record_review(job_id, pending)
    assert not (session.root / ('review-' + job_id + '.json')).exists()
    assert session.ledger.snapshot()['blocked'] is None
    assert session.ledger.snapshot()['spent']['jobs'] == 1


@pytest.mark.parametrize('major_error', [False, True])
@pytest.mark.parametrize('after_bind', [False, True])
def test_explicit_recovery_only_binds_existing_fully_reverified_review(tmp_path, monkeypatch, major_error, after_bind):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    ref = content_review(session, job_id)
    review = protocol.referenced(ref)
    review['assessment']['major_error'] = major_error
    ref = put(Path(ref['path']), review)
    original = type(session.ledger).bind_review
    def interrupted(ledger, *args, **kwargs):
        if after_bind: original(ledger, *args, **kwargs)
        raise RuntimeError('interrupt binding')
    with monkeypatch.context() as patch:
        patch.setattr(type(session.ledger), 'bind_review', interrupted)
        with pytest.raises(RuntimeError): session.record_review(job_id, ref)
    pointer = session.root / ('review-' + job_id + '.json')
    raw = pointer.read_bytes()
    before = session.ledger.snapshot()
    resumed = protocol.Campaign.resume(session.anchor)
    recovered = resumed.recover_review_binding(job_id)
    assert recovered['major_error'] is major_error
    assert pointer.read_bytes() == raw
    after = resumed.ledger.snapshot()
    assert after['reviews'][job_id] == protocol.sha(raw)
    assert after['spent'] == before['spent']
    assert after['live_deadline_ms'] == before['live_deadline_ms']
    assert len([e for e in resumed.ledger.events() if e['kind'] == 'review_bind']) == 1
    assert after['blocked'] == ('acceptance_safety_stop' if major_error else None)


@pytest.mark.parametrize('mutation', ['review', 'artifact', 'pending', 'missing_pointer'])
def test_review_recovery_cannot_adopt_changed_or_incomplete_evidence(tmp_path, monkeypatch, mutation):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    ref = content_review(session, job_id)
    if mutation == 'pending':
        review = protocol.referenced(ref)
        review['assessment']['audit_passed'] = False
        review['assessment']['failure_review']['complete'] = False
        ref = put(Path(ref['path']), review)
    if mutation != 'missing_pointer': put(session.root / ('review-' + job_id + '.json'), ref)
    if mutation == 'review': Path(ref['path']).write_bytes(b'{}')
    if mutation == 'artifact': (session.root / job_id / 'reports' / 'report.md').write_bytes(b'changed')
    with pytest.raises((ReplayAbort, OSError)):
        session.recover_review_binding(job_id)
    assert session.ledger.snapshot()['reviews'] == {}
    assert session.ledger.snapshot()['spent']['jobs'] == 1


def interrupted_batch(session, monkeypatch):
    original = protocol.execute_reserved_job
    def executor(plan, ledger, job_id):
        receipt = original(plan, ledger, job_id)
        job = ledger.snapshot()['jobs'][job_id]
        put(ledger.path.parent / (ledger.path.name + '.' + job_id + '.watchdog-started.json'),
            {'job_id': job_id, 'ledger_binding_sha256': ledger.binding,
             'deadline_ms': job['deadline_ms'], 'actual_hashes': job['actual_hashes']})
        return receipt
    def interrupted(*args, **kwargs): raise RuntimeError('interrupt batch closure')
    with monkeypatch.context() as patch:
        patch.setattr(protocol, 'execute_reserved_job', executor)
        patch.setattr(type(session.ledger), 'finish_batch', interrupted)
        with pytest.raises(RuntimeError): session.run_next()
    job_id = next(iter(session.ledger.snapshot()['jobs']))
    return job_id, session.ledger.snapshot()['jobs'][job_id]['batch_id']


def test_explicit_batch_recovery_closes_only_original_terminal_receipt_without_rerun(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id, batch_id = interrupted_batch(session, monkeypatch)
    session.record_review(job_id, content_review(session, job_id))
    before = session.ledger.snapshot()
    original_files = {p: p.read_bytes() for p in (session.root / job_id).rglob('*') if p.is_file()}
    session.recover_terminal_batch(batch_id)
    after = session.ledger.snapshot()
    assert after['batches'][batch_id]['ended_ms'] is not None
    assert after['spent'] == before['spent']
    assert after['live_deadline_ms'] == before['live_deadline_ms']
    assert all(p.read_bytes() == raw for p, raw in original_files.items())
    with pytest.raises(ReplayAbort): session.recover_terminal_batch(batch_id)
    assert session.run_next()['job_id'] != job_id


@pytest.mark.parametrize('case', ['no_review', 'missing_parent', 'missing_cleanup', 'claim_drift', 'active', 'unknown'])
def test_recovery_refuses_unknown_cleanup_or_unreviewed_terminal_work(tmp_path, monkeypatch, case):
    session = executable_campaign(tmp_path, monkeypatch)
    if case == 'active':
        session.ledger.start_stage('S1')
        session.ledger.start_batch('batch', 'S1')
        job_id = session.protocol['samples'][0]['job_id']
        session.ledger.reserve_job(job_id, 'batch', binding_id=job_id, actual_hashes=session.ledger.bindings[job_id])
        batch_id = 'batch'
    else:
        job_id, batch_id = interrupted_batch(session, monkeypatch)
        if case != 'no_review': session.record_review(job_id, content_review(session, job_id))
        if case == 'missing_parent': (session.root / job_id / 'parent-receipt.json').unlink()
        if case == 'missing_cleanup': (session.root / job_id / ('watchdog-' + job_id + '.cleanup.json')).unlink()
        if case == 'claim_drift': (session.root / (session.ledger.path.name + '.' + job_id + '.watchdog-started.json')).write_bytes(b'{}')
    before = session.ledger.snapshot()
    with pytest.raises((ReplayAbort, OSError)):
        session.recover_terminal_batch('unknown' if case == 'unknown' else batch_id)
    after = session.ledger.snapshot()
    assert after['spent'] == before['spent']
    assert after['batches'][batch_id]['ended_ms'] is None
