"""One private roster and shared ledger; no formal launcher or stage acceptance.

The test drives each real normal child and explicitly performs fixture ledger
bookkeeping between jobs. This is NOT the missing production dispatch/controller
or descendant proof. Source, billing, prerequisite and upstream are fixtures.
"""
import json
import os
from pathlib import Path
import pickle
import sys


def main():
    root, case = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']), sys.argv[2]
    sys.path[:0] = [str(Path(__file__).resolve().parent),
                   str(Path(__file__).resolve().parents[1] / 'scripts'),
                   str(Path(__file__).resolve().parents[1] / 'backend')]
    from test_maintenance_rq_private_integration_child import install_boundary
    install_boundary()
    import canary_release_policy
    canary_release_policy.require_canary_enabled = lambda: None  # Private socket-denied fixture only.
    import quality_campaign_runner as runner
    from quality_campaign_budget import CampaignBudget, manifest_identity
    from test_quality_campaign_owned_normal import frozen_normal_fixture
    from test_quality_campaign_runner import put
    from maintenance_canary_claim import prepare_analysis_job, claim_analysis_next
    from maintenance_canary_enrollment import enroll_analysis_jobs
    from maintenance_canary_settlement import settle_claimed_analysis
    from maintenance_owned_process import OwnedProcess
    from redis import Redis
    from redis.retry import Retry
    from redis.backoff import NoBackoff
    from rq.job import Job
    from rq.serializers import DefaultSerializer
    def forbidden(*args, **kwargs):
        raise AssertionError('Controller may not deserialize or perform RQ payloads')
    pickle.loads = pickle.Unpickler = Job.restore = Job.perform = DefaultSerializer.loads = forbidden
    connection = Redis(unix_socket_path=str(root / 'redis.sock'), socket_timeout=2,
        socket_connect_timeout=2, retry=Retry(NoBackoff(), 0), retry_on_error=[])
    plans, hashes = {}, {}
    for mode in ('v1', 'v2', 'v3', 'v4'):
        source_root = root / ('source-' + mode)
        source_root.mkdir(mode=0o700)
        plan = frozen_normal_fixture(source_root, mode)
        manifest = plan.manifest
        manifest['binding_id'] = mode
        put(plan.path, manifest)
        plan = runner.FrozenJob(plan.path, runner.sha(plan.path.read_bytes()))
        plans[mode], hashes[mode] = plan, plan.verify()
    ledger = CampaignBudget(root / 'campaign.sqlite3', manifest_identity('fixture', hashes),
        allowed_bindings=hashes, limits={'campaign': {'job_seconds': 45}})
    # Explicit test prerequisite only, exactly as in the existing normal fixture.
    ledger.start_stage('S1')
    ledger.start_batch('fixture-prerequisite', 'S1')
    ledger.reserve_job('fixture-prerequisite', 'fixture-prerequisite', binding_id='v4', actual_hashes=hashes['v4'])
    ledger.finish_job('fixture-prerequisite', status='completed')
    ledger.finish_batch('fixture-prerequisite', cleanup_evidence_sha256='c' * 64)
    ledger.pass_stage('S1', acceptance_evidence_sha256='f' * 64)
    ledger.start_stage('S2')
    ledger.start_batch('batch', 'S2')
    values = {'queue_name': 'whole-roster', 'remaining': [], 'registered_hashes': {}, 'analysis_bindings': {}}
    for mode, plan in plans.items():
        binding = {'campaign_id': 'fixture', 'job_id': 'job-' + mode, 'ticker': '2330.TW',
                   'pipeline_id': mode, 'manifest_sha256': plan.expected_sha, 'timeout_seconds': 45}
        job = prepare_analysis_job(connection, queue_name=values['queue_name'], binding=binding)
        job.enqueued_at, job._status = job.created_at, 'queued'
        values['remaining'].append(job.id)
        values['analysis_bindings'][job.id] = binding
        values['registered_hashes'][job.id] = {
            key.encode(): value if type(value) is bytes else value.encode() if isinstance(value, str) else str(value).encode()
            for key, value in job.to_dict().items()}
    try:
        assert connection.info('server')['tcp_port'] == 0
        connection.rpush('rq:queue:ordinary', b'original-ordinary')
        ordinary = connection.dump('rq:queue:ordinary')
        enrolled = enroll_analysis_jobs(connection, **values)
        assert enrolled['outcome'] == 'enrolled', enrolled
        marker_key = 'stock-agent:maintenance:canary-enrollment:' + values['queue_name']
        enrollment_before = connection.dump(marker_key)
        previous, settled = {}, []
        current = dict(values)
        while current['remaining']:
            claimed = claim_analysis_next(connection, **current)
            assert claimed['outcome'] == 'claimed', claimed
            bound = current['analysis_bindings'][claimed['job_id']]
            job_id, mode = bound['job_id'], bound['pipeline_id']
            plan = plans[mode]
            ledger.reserve_job(job_id, 'batch', binding_id=mode, actual_hashes=hashes[mode])
            original_job = ledger.snapshot()['jobs'][job_id]
            output = root / job_id
            output.mkdir(mode=0o700)
            ticket = output / 'child-ticket.json'
            runner.exclusive_json(ticket, {'manifest_path': str(plan.path), 'manifest_sha256': plan.expected_sha,
                'ledger_pin': runner.ledger_pin(ledger), 'job_id': job_id, 'output': str(output)})
            runner.exclusive_json(root / (ledger.path.name + '.' + job_id + '.watchdog-started.json'), {
                'job_id': job_id, 'ledger_binding_sha256': ledger.binding,
                'deadline_ms': original_job['deadline_ms'], 'actual_hashes': original_job['actual_hashes']})
            namespace = root / ('owner-' + mode)
            namespace.mkdir(mode=0o700)
            process_binding = {'operation_id': 'canary-' + mode, 'control_sha256': 'a' * 64, 'backend_revision': 'b' * 40}
            controller = OwnedProcess(namespace, process_binding)
            child_case = 'blocked' if case == 'stop_after_second' and mode == 'v2' else 'published'
            try:
                child = Path(__file__).with_name('test_quality_campaign_owned_normal_child.py')
                controller.start([sys.executable, '-I', '-B', str(child), str(ticket), child_case],
                                 env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}, cwd=root)
                assert controller.wait_for_exit(30)['process_exited']
                assert not (output / 'offline-fixture-error.txt').exists()
                result = settle_claimed_analysis(connection, **current, claimed=claimed,
                    process=controller, process_binding=process_binding, output_dir=output)
                assert result['outcome'] == 'settled', result
                assert ledger.snapshot()['jobs'][job_id] == original_job
                assert all(connection.dump(key) == data for key, data in previous.items())
                previous['rq:job:' + claimed['job_id']] = connection.dump('rq:job:' + claimed['job_id'])
                settled.append((mode, result['terminal_status']))
                # Derive the expected tail from the original enrollment, never
                # from the helper's response (which could share a queue bug).
                expected_remaining = tuple(values['remaining'][len(settled):])
                assert tuple(result['remaining']) == expected_remaining
                assert connection.lrange('rq:queue:whole-roster', 0, -1) == [
                    item.encode() for item in expected_remaining]
                # Explicit fixture driver bookkeeping, NOT performed by the RQ
                # settlement helper or claimed as production ledger settlement.
                ledger.finish_job(job_id, status='failed' if result['stop_required'] else 'completed')
                current['remaining'] = result['remaining']
                if result['stop_required']: break
            finally:
                if controller.process is not None: controller.process.wait(timeout=30)
                controller.close()
        assert settled == ([('v1', 'finished'), ('v2', 'failed')] if case == 'stop_after_second'
                           else [(mode, 'finished') for mode in ('v1', 'v2', 'v3', 'v4')])
        expected_remaining = tuple(values['remaining'][len(settled):])
        assert tuple(current['remaining']) == expected_remaining
        assert connection.lrange('rq:queue:whole-roster', 0, -1) == [item.encode() for item in expected_remaining]
        assert connection.llen('rq:queue:whole-roster:intermediate') == 0
        for item in expected_remaining:
            assert connection.hgetall('rq:job:' + item) == values['registered_hashes'][item]
            assert item.removeprefix('analysis:') not in ledger.snapshot()['jobs']
        assert connection.dump(marker_key) == enrollment_before
        assert connection.dump('rq:queue:ordinary') == ordinary
        assert ledger.snapshot()['stages']['S2'] == 'open' and ledger.snapshot()['batches']['batch']['ended_ms'] is None
        with open(sys.argv[1], 'x') as stream:
            json.dump({'case': case, 'settled': settled, 'remaining': list(current['remaining']),
                'one_shared_ledger': True, 'ordinary_unchanged': True,
                'driver_fixture_bookkeeping': True, 'production_ready': False}, stream)
    finally:
        connection.close()


if __name__ == '__main__': main()
