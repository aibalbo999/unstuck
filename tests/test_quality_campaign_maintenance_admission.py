"""An owned maintenance launch cannot borrow a legacy watchdog claim."""
from test_quality_campaign_runner import reserved
from test_quality_campaign_safety import fresh_guarded_child
import quality_campaign_runner as runner


def test_maintenance_ticket_without_pipe_cannot_fall_back_to_watchdog(tmp_path):
    plan, _, ledger = reserved(tmp_path)
    output = tmp_path / 'job'
    output.mkdir(mode=0o700)
    job = ledger.snapshot()['jobs']['job']
    runner.exclusive_json(output / 'child-ticket.json', {
        'manifest_path': str(plan.path), 'manifest_sha256': plan.expected_sha,
        'ledger_pin': runner.ledger_pin(ledger), 'job_id': 'job', 'output': str(output),
        'maintenance_admission': {'schema': 'maintenance.owned-admission.v1'}})
    # A valid old claim must not authorize this new, explicitly different lane.
    runner.exclusive_json(tmp_path / (ledger.path.name + '.job.watchdog-started.json'), {
        'job_id': 'job', 'ledger_binding_sha256': ledger.binding,
        'deadline_ms': job['deadline_ms'], 'actual_hashes': job['actual_hashes']})
    fresh_guarded_child(ledger, output, '''
import asyncio
import quality_campaign_runner as runner
import canary_release_policy
canary_release_policy.require_canary_enabled = lambda: None
reached = []
def environment(*args):
    reached.append(True)
    raise runner.ReplayAbort('Offline environment sentinel')
runner.child_environment = environment
try:
    asyncio.run(runner.owned_job(output / 'child-ticket.json'))
except runner.ReplayAbort:
    pass
assert not reached, 'Maintenance launch fell back to an unrelated legacy watchdog claim'
''', identity=ledger.identity)
