"""No formal service/network/secret access; normal job runs in an owned child.

The normal child uses explicit offline source/billing/limiter/model fixtures.
The preexisting watchdog claim is a fixture, not a completed formal dispatcher.
"""
import json
import os
from pathlib import Path
import sys
import time


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
    from test_quality_campaign_owned_normal import reserved_normal_fixture
    from maintenance_owned_process import OwnedProcess
    from maintenance_canary_claim import prepare_analysis_job, claim_analysis_next
    from maintenance_canary_enrollment import enroll_analysis_jobs
    from redis import Redis
    from redis.retry import Retry
    from redis.backoff import NoBackoff
    from redis.exceptions import ConnectionError
    try:
        from maintenance_canary_settlement import settle_claimed_analysis
    except ModuleNotFoundError as error:
        if error.name != 'maintenance_canary_settlement': raise
        # The current chain really stops after the normal job: its RQ item
        # remains in intermediate. Do not invent an unsafe pre-fix mutator.
        def settle_claimed_analysis(*args, **kwargs): return {'outcome': 'not_implemented'}
    mode = case.rsplit('_', 1)[-1] if case.startswith('published_') else 'v4'
    fixture_root = root / 'campaign'
    fixture_root.mkdir(mode=0o700)
    plan, ledger = reserved_normal_fixture(fixture_root, mode)
    binding = {'campaign_id': 'fixture', 'job_id': 'job', 'ticker': '2330.TW',
               'pipeline_id': mode, 'manifest_sha256': plan.expected_sha, 'timeout_seconds': 45}
    connection = Redis(unix_socket_path=str(root / 'redis.sock'), socket_timeout=2,
        socket_connect_timeout=2, retry=Retry(NoBackoff(), 0), retry_on_error=[])
    namespace = root / 'owner'
    namespace.mkdir(mode=0o700)
    process_binding = {'operation_id': 'canary-fixture', 'control_sha256': 'a' * 64, 'backend_revision': 'b' * 40}
    controller = OwnedProcess(namespace, process_binding)
    try:
        assert connection.info('server')['tcp_port'] == 0
        connection.rpush('rq:queue:ordinary', b'ordinary-job')
        connection.hset('rq:job:ordinary-job', mapping={b'data': b'original-unrelated-job'})
        connection.zadd('rq:failed:ordinary', {b'expired-preserved': 1})
        connection.sadd('rq:queues', 'rq:queue:ordinary')
        ordinary = {key: connection.dump(key) for key in
                    ('rq:queue:ordinary', 'rq:job:ordinary-job', 'rq:failed:ordinary')}
        values = {'queue_name': 'owned-canary', 'remaining': [], 'registered_hashes': {}, 'analysis_bindings': {}}
        for index, selected in enumerate([mode, *[value for value in ('v1', 'v2', 'v3', 'v4') if value != mode]]):
            bound = binding if index == 0 else {**binding, 'job_id': 'pending-' + selected, 'pipeline_id': selected}
            job = prepare_analysis_job(connection, queue_name=values['queue_name'], binding=bound)
            job.enqueued_at, job._status = job.created_at, 'queued'
            values['remaining'].append(job.id)
            values['analysis_bindings'][job.id] = bound
            values['registered_hashes'][job.id] = {
                key.encode(): value if type(value) is bytes else value.encode() if isinstance(value, str) else str(value).encode()
                for key, value in job.to_dict().items()}
        enrollment = enroll_analysis_jobs(connection, **values)
        assert enrollment['outcome'] == 'enrolled', enrollment
        claimed = claim_analysis_next(connection, **values)
        assert claimed['outcome'] == 'claimed', claimed
        original_job = ledger.snapshot()['jobs']['job']
        output = fixture_root / 'job'
        output.mkdir(mode=0o700)
        ticket = output / 'child-ticket.json'
        runner.exclusive_json(ticket, {'manifest_path': str(plan.path), 'manifest_sha256': plan.expected_sha,
            'ledger_pin': runner.ledger_pin(ledger), 'job_id': 'job', 'output': str(output)})
        runner.exclusive_json(fixture_root / (ledger.path.name + '.job.watchdog-started.json'), {
            'job_id': 'job', 'ledger_binding_sha256': ledger.binding,
            'deadline_ms': original_job['deadline_ms'], 'actual_hashes': original_job['actual_hashes']})
        child_case = {'blocked': 'blocked', 'stopped': 'warm_stop', 'cleanup_error': 'warm_stop_close_error',
                      'live_process': 'warm_stop'}.get(case, 'published')
        child = Path(__file__).with_name('test_quality_campaign_owned_normal_child.py')
        controller.start([sys.executable, '-I', '-B', str(child), str(ticket), child_case],
                         env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}, cwd=root)
        if child_case.startswith('warm_stop'):
            deadline = time.monotonic() + 15
            while not (output / 'stop-ready.json').exists() and controller.process.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            assert (output / 'stop-ready.json').is_file()
            if case != 'live_process': controller.request_stop()
        if case != 'live_process':
            assert controller.wait_for_exit(30)['process_exited']
            assert not (output / 'offline-fixture-error.txt').exists()
        cleanup_path = output / 'child-cleanup.json'
        if case == 'missing_cleanup': cleanup_path.rename(output / 'held-cleanup.json')
        if case in ('wrong_pid', 'wrong_manifest'):
            row = json.loads(cleanup_path.read_text())
            row['process_pid' if case == 'wrong_pid' else 'manifest_sha256'] = 1 if case == 'wrong_pid' else '0' * 64
            cleanup_path.write_text(json.dumps(row))
        if case in ('pending_generator', 'missing_generator_observation'):
            row = json.loads(cleanup_path.read_text())
            assert row['application_cleanup_verified'] is True
            if case == 'pending_generator': row['pending_async_generators'] = 1
            else: del row['pending_async_generators']
            cleanup_path.write_text(json.dumps(row))
        if case == 'changed_outcome': (output / 'outcome.json').write_text('{}')
        if case == 'changed_artifact':
            row = json.loads((output / 'outcome.json').read_text())
            (output / 'reports' / row['artifacts']['html_key']['key']).write_text('changed-after-render')
        queue = 'rq:queue:' + values['queue_name']
        if case == 'wrong_intermediate': connection.rpush(queue + ':intermediate', b'other-work')
        if case == 'changed_payload': connection.hset('rq:job:analysis:job', b'data', b'changed-after-claim')
        arguments = dict(**values, claimed=claimed, process=controller, process_binding=process_binding, output_dir=output)
        if case == 'mutated_process_binding':
            controller.binding['backend_revision'] = 'c' * 40
            arguments['process_binding'] = dict(controller.binding)
        if case == 'replay': assert settle_claimed_analysis(connection, **arguments)['outcome'] == 'settled'
        before = {key: connection.dump(key) for key in connection.scan_iter()}
        execs = []
        original_pipeline = connection.pipeline
        def pipeline(*args, **kwargs):
            pipe = original_pipeline(*args, **kwargs)
            execute, parse = pipe.execute, pipe.parse_response
            watch = pipe.watch
            if case == 'cancel_after_readback':
                original_exit = pipe.__exit__
                class InterruptingExit(type(pipe)):
                    def __exit__(self, *args):
                        original_exit(*args)
                        raise KeyboardInterrupt('offline cancellation after settlement readback')
                pipe.__class__ = InterruptingExit
            def watched(*keys):
                result = watch(*keys)
                if case == 'retry_nonzero': pipe.connection.retry = Retry(NoBackoff(), 1)
                return result
            pipe.watch = watched
            if case == 'cancel_before_exec':
                def multi(): raise KeyboardInterrupt('offline pre-EXEC cancellation')
                pipe.multi = multi
            if case == 'runtime_error':
                hset = pipe.hset
                def hset_with_wrongtype(key, *args, **kwargs):
                    result = hset(key, *args, **kwargs)
                    pipe.lpush(key, b'force-real-EXEC-WRONGTYPE')
                    return result
                pipe.hset = hset_with_wrongtype
            def observed_execute(*args, **kwargs):
                execs.append(True)
                if case == 'race': connection.hset('rq:job:analysis:job', b'data', b'concurrent-change')
                return execute(*args, **kwargs)
            def observed_parse(conn, command, **kwargs):
                result = parse(conn, command, **kwargs)
                if command == '_' and isinstance(result, list):
                    if case == 'lost_reply': raise ConnectionError('offline lost settlement ACK')
                    if case == 'cancel_after_exec': raise KeyboardInterrupt('offline post-EXEC cancellation')
                    if case == 'readback_mismatch': result[-1] = 0
                    if case == 'file_drift_after_exec': (output / 'outcome.json').write_text('{}')
                return result
            pipe.execute, pipe.parse_response = observed_execute, observed_parse
            return pipe
        connection.pipeline = pipeline
        try:
            result = settle_claimed_analysis(connection, **arguments)
        finally:
            connection.pipeline = original_pipeline
        expected = 'settled' if case.startswith('published_') or case in ('blocked', 'stopped') else {
            'race': 'conflict', 'lost_reply': 'uncertain', 'cancel_before_exec': 'cancelled',
            'cancel_after_exec': 'uncertain', 'cancel_after_readback': 'uncertain', 'readback_mismatch': 'uncertain',
            'runtime_error': 'uncertain', 'file_drift_after_exec': 'uncertain'}.get(case, 'rejected')
        assert result['outcome'] == expected, result
        assert result['production_ready'] is result['handover_verified'] is result['campaign_settled'] is False
        if expected in ('settled', 'uncertain'):
            status = b'failed' if case in ('blocked', 'stopped') else b'finished'
            assert connection.hget('rq:job:analysis:job', 'status') == status
            assert connection.lrange(queue + ':intermediate', 0, -1) == []
            assert connection.lrange(queue, 0, -1) == [value.encode() for value in values['remaining'][1:]]
            assert connection.zscore('rq:' + status.decode() + ':' + values['queue_name'], 'analysis:job') is not None
            assert 604790 <= connection.ttl('rq:job:analysis:job') <= 604800
            assert all(connection.hgetall('rq:job:' + task_id) == values['registered_hashes'][task_id]
                       for task_id in values['remaining'][1:])
        else:
            if case == 'race': before[b'rq:job:analysis:job'] = connection.dump('rq:job:analysis:job')
            assert {key: connection.dump(key) for key in connection.scan_iter()} == before
        assert len(execs) == int(expected in ('settled', 'uncertain', 'conflict'))
        assert all(connection.dump(key) == value for key, value in ordinary.items())
        assert ledger.snapshot()['jobs']['job'] == original_job
        with open(sys.argv[1], 'x') as stream:
            json.dump({'case': case, 'outcome': result['outcome'], 'exec_attempts': len(execs),
                'ordinary_unchanged': True, 'campaign_not_settled': True, 'live_qualified': False}, stream)
    finally:
        if controller.process is not None:
            if case == 'live_process' and controller.process.poll() is None: controller.request_stop()
            controller.process.wait(timeout=30)
        controller.close()
        connection.close()


if __name__ == '__main__': main()
