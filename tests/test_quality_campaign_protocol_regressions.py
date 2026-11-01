"""Independent offline controller review; synthetic reports are not live evidence."""
import json
from pathlib import Path

import pytest

import quality_campaign_protocol as protocol
from quality_campaign_budget import BudgetDenied
from quality_campaign_wire import ReplayAbort
from test_quality_campaign_protocol import executable_campaign, content_review, put


def test_actual_knobs_are_bound_at_completion_before_external_review(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    prompt_path = session.root / job_id / 'prompts.jsonl'
    prompts = [json.loads(line) for line in prompt_path.read_bytes().splitlines()]
    prompts[0]['config']['temperature'] = 1.5
    prompt_path.write_bytes(b'\n'.join(protocol.encoded(row) for row in prompts) + b'\n')
    review = content_review(session, job_id)
    with pytest.raises((ReplayAbort, BudgetDenied)):
        session.record_review(job_id, review)


@pytest.mark.parametrize('missing', ['warnings', 'root_cause', 'source_decision_reviewed'])
def test_schema_incomplete_review_is_rejected_without_permanent_campaign_stop(tmp_path, monkeypatch, missing):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    original = content_review(session, job_id)
    review = json.loads(Path(original['path']).read_bytes())
    del review['assessment'][missing]
    incomplete = put(session.root / 'incomplete-review.json', review)
    error = None
    try:
        session.record_review(job_id, incomplete)
    except ReplayAbort as caught:
        error = caught
    state = session.ledger.snapshot()
    assert state['blocked'] is None, 'Malformed review must not become an irreversible content safety stop'
    assert not (session.root / ('review-' + job_id + '.json')).exists()
    assert error is not None, 'Malformed review must be rejected before durable acceptance'
    session.record_review(job_id, original)
    assert session.run_next()['job_id'] != job_id


def test_actual_generation_knobs_cannot_change_after_review_without_detection(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    session.record_review(job_id, content_review(session, job_id))
    before = session.results()[job_id]['actual_models']
    prompt_path = session.root / job_id / 'prompts.jsonl'
    prompts = [json.loads(line) for line in prompt_path.read_bytes().splitlines()]
    prompts[0]['config']['temperature'] = 1.5
    prompt_path.write_bytes(b'\n'.join(protocol.encoded(row) for row in prompts) + b'\n')
    try:
        after = session.results()[job_id]['actual_models']
    except (ReplayAbort, BudgetDenied):
        return
    assert after == before, 'Unbound prompts.jsonl changes the accepted actual-model fingerprint'


def test_detected_source_change_persists_stop_even_after_original_restored(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    review = content_review(session, job_id)
    session.record_review(job_id, review)
    manifest = json.loads(Path(session._sample(job_id)['manifest']['path']).read_bytes())
    source = Path(manifest['source']['path'])
    original = source.read_bytes()
    source.write_bytes(b'{"data_snapshot":{"changed":true}}')
    with pytest.raises((ReplayAbort, BudgetDenied)):
        session.run_next()
    source.write_bytes(original)
    assert session.ledger.snapshot()['blocked'] is not None, 'Observed source rewrite must stop campaign durably'
    with pytest.raises((ReplayAbort, BudgetDenied)):
        session.run_next()


def test_completed_content_review_cannot_be_rebound_after_stage_pass(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_ids = []
    for _ in range(2):
        job_id = session.run_next()['job_id']
        job_ids.append(job_id)
        session.record_review(job_id, content_review(session, job_id))
    session.pass_stage('S1')
    job_id = job_ids[0]
    pointer = session.root / ('review-' + job_id + '.json')
    review_ref = json.loads(pointer.read_bytes())
    review = json.loads(Path(review_ref['path']).read_bytes())
    review['reviewer'] = 'ANOTHER OFFLINE REVIEWER'
    alternate = put(session.root / 'alternate-review.json', review)
    put(pointer, alternate)
    with pytest.raises((ReplayAbort, BudgetDenied)):
        session.run_next()
    assert session.ledger.snapshot()['spent']['jobs'] == 2


def test_valid_pending_source_review_is_not_pinned_as_finished_review(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    original = content_review(session, job_id)
    value = json.loads(Path(original['path']).read_bytes())
    value['assessment']['source_decision_reviewed'] = False
    pending = put(session.root / 'pending-review.json', value)
    with pytest.raises(ReplayAbort):
        session.record_review(job_id, pending)
    assert not (session.root / ('review-' + job_id + '.json')).exists()
    assert session.ledger.snapshot()['blocked'] is None
    session.record_review(job_id, original)
    assert session.run_next()['job_id'] != job_id


def test_real_stop_reason_remains_first_and_spent_counters_are_retained(tmp_path, monkeypatch):
    session = executable_campaign(tmp_path, monkeypatch)
    job_id = session.run_next()['job_id']
    before = session.ledger.snapshot()['spent']
    session.ledger.stop('first_real_stop', evidence_sha256='a' * 64)
    session.ledger.stop('second_stop', evidence_sha256='b' * 64)
    reopened = protocol.Campaign.resume(session.anchor)
    assert reopened.ledger.snapshot()['blocked'] == 'first_real_stop'
    assert reopened.ledger.snapshot()['spent'] == before
    with pytest.raises(BudgetDenied):
        reopened.ledger.check()
    events = [e for e in reopened.ledger.events() if e['kind'] == 'blocked']
    assert len(events) == 1 and events[0]['payload']['evidence_sha256'] == 'a' * 64
