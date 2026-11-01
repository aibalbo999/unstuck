"""Bounded pipe protocol fixtures; real parent provenance is tested separately."""
import asyncio
import os
import threading

import pytest
import quality_campaign_runner as runner


def protocol(tmp_path):
    reader, writer = os.pipe()
    info = os.fstat(reader)
    identity = {'device': info.st_dev, 'inode': info.st_ino}
    binding = {'operation_id': 'protocol-only', 'control_sha256': 'c' * 64, 'backend_revision': 'b' * 40}
    ticket = {'output': str(tmp_path), 'job_id': 'job', 'manifest_sha256': 'f' * 64, 'ledger_pin': {}}
    intent = {'schema': 'maintenance.canary-launch.v1', 'parent_pid': os.getppid(),
        'process_binding': binding, 'job_id': 'job', 'output': str(tmp_path), 'manifest_sha256': 'f' * 64,
        'ledger_pin_sha256': runner.sha(runner.encoded({}))}
    digest = runner.exclusive_json(tmp_path / 'dispatch-intent.json', intent)
    ticket['maintenance_admission'] = {'schema': 'maintenance.owned-admission.v1', 'intent_sha256': digest,
        'parent_pid': os.getppid(), 'pipe_identity': identity, 'process_binding': binding}
    ticket_sha = runner.exclusive_json(tmp_path / 'child-ticket.json', ticket)
    authorization = {'schema': 'maintenance.owned-admission.v1', 'parent_pid': os.getppid(),
        'child_pid': os.getpid(), 'pipe_identity': identity, 'ticket_sha256': ticket_sha,
        'intent_sha256': digest, 'started_journal_sha256': 'd' * 64}
    return reader, writer, ticket, authorization


@pytest.mark.parametrize('case', ['accepted', 'wrong_child', 'wrong_parent', 'wrong_ticket',
    'wrong_intent', 'wrong_journal_hash', 'intent_drift', 'metadata_drift', 'empty', 'no_eof', 'oversized'])
def test_pipe_rejects_incomplete_or_mismatched_admission_before_receipt(tmp_path, case):
    reader, writer, ticket, authorization = protocol(tmp_path)
    if case == 'wrong_child': authorization['child_pid'] += 1
    if case == 'wrong_parent': authorization['parent_pid'] += 1
    if case == 'wrong_ticket': authorization['ticket_sha256'] = '0' * 64
    if case == 'wrong_intent': authorization['intent_sha256'] = '0' * 64
    if case == 'wrong_journal_hash': authorization['started_journal_sha256'] = 'not-a-digest'
    if case == 'metadata_drift': ticket['maintenance_admission']['parent_pid'] += 1
    if case == 'intent_drift': (tmp_path / 'dispatch-intent.json').write_bytes(b'{}')
    raw = b'' if case == 'empty' else b'x' * 8193 if case == 'oversized' else runner.encoded(authorization)
    errors = []
    def deliver():
        try:
            pending = memoryview(raw)
            while pending: pending = pending[os.write(writer, pending):]
        except BrokenPipeError:
            pass  # Child fail-closed may close before this test writer finishes.
        except BaseException as error:
            errors.append(type(error).__name__)
        finally:
            if case != 'no_eof': os.close(writer)
    sender = threading.Thread(target=deliver)
    sender.start()
    try:
        if case == 'accepted':
            intent, digest = runner.consume_maintenance_admission(tmp_path / 'child-ticket.json', ticket, reader)
            assert intent['schema'] == 'maintenance.canary-launch.v1'
            assert digest == runner.sha(runner.encoded(authorization))
            assert (tmp_path / 'maintenance-admission.json').read_bytes() == runner.encoded(authorization)
        else:
            with pytest.raises(runner.ReplayAbort):
                runner.consume_maintenance_admission(tmp_path / 'child-ticket.json', ticket, reader)
            assert not (tmp_path / 'maintenance-admission.json').exists()
        with pytest.raises(OSError): os.fstat(reader)
    finally:
        if case == 'no_eof': os.close(writer)
        sender.join(timeout=2)
    assert not sender.is_alive() and not errors


def test_owned_stop_before_admission_cannot_read_frozen_inputs(tmp_path):
    from test_quality_campaign_runner import reserved
    from test_quality_campaign_safety import fresh_guarded_child
    plan, _, ledger = reserved(tmp_path)
    output = tmp_path / 'job'
    output.mkdir(mode=0o700)
    runner.exclusive_json(output / 'child-ticket.json', {
        'manifest_path': str(plan.path), 'manifest_sha256': plan.expected_sha,
        'ledger_pin': runner.ledger_pin(ledger), 'job_id': 'job', 'output': str(output)})
    fresh_guarded_child(ledger, output, '''
import asyncio
import quality_campaign_runner as runner
import canary_release_policy
canary_release_policy.require_canary_enabled = lambda: None
def forbidden(*args, **kwargs):
    raise AssertionError('A stopped child read frozen inputs or credentials')
runner.FrozenJob = runner.child_environment = forbidden
try:
    asyncio.run(runner.owned_job(output / 'child-ticket.json', stop_requested=lambda: True))
except asyncio.CancelledError:
    pass
else:
    raise AssertionError('Stopped child was admitted')
assert not (output / 'child-started.json').exists()
''', identity=ledger.identity)
