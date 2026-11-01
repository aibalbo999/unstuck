"""Private Redis only; enrollment never restores or performs application jobs."""
import json
import copy
import os
from pathlib import Path
import pickle
import sys


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_maintenance_rq_private_integration_child import install_boundary
    install_boundary()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    import canary_release_policy
    canary_release_policy.require_canary_enabled = lambda: None  # Private socket-denied fixture only.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    import maintenance_canary_claim as claim
    from redis import Redis
    from redis.retry import Retry
    from redis.backoff import NoBackoff
    from redis.exceptions import ConnectionError
    from rq import Queue
    from rq.job import Job
    from rq.serializers import DefaultSerializer
    root, case = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']), sys.argv[2]
    connection = Redis(unix_socket_path=str(root / 'redis.sock'), socket_timeout=2,
        socket_connect_timeout=2, retry=Retry(NoBackoff(), int(case == 'retry_nonzero')), retry_on_error=[])
    def forbidden(*args, **kwargs):
        raise AssertionError('No deserialization or job execution allowed')
    pickle.loads = pickle.Unpickler = DefaultSerializer.loads = Job.restore = Job.perform = forbidden
    try:
        assert connection.info('server')['tcp_port'] == 0
        connection.rpush('rq:queue:ordinary', b'ordinary-job')
        connection.sadd('rq:queues', 'rq:queue:ordinary')
        connection.hset('rq:job:ordinary-job', mapping={b'data': b'ordinary-preserved'})
        connection.zadd('rq:failed:ordinary', {b'untouched-expired': 1})
        ordinary = {key: connection.dump(key) for key in
            ('rq:queue:ordinary', 'rq:job:ordinary-job', 'rq:failed:ordinary')}
        queue_name = 'create-only-' + case
        values = {'queue_name': queue_name, 'remaining': [], 'registered_hashes': {}, 'analysis_bindings': {}}
        jobs = []
        for mode in ('v1', 'v2', 'v3', 'v4'):
            bound = {'campaign_id': 'offline-campaign', 'job_id': case + '-' + mode, 'ticker': '2330.TW',
                     'pipeline_id': mode, 'manifest_sha256': mode[1] * 64, 'timeout_seconds': 60}
            job = claim.prepare_analysis_job(connection, queue_name=queue_name, binding=bound)
            job.enqueued_at, job._status = job.created_at, 'queued'
            jobs.append(job)
            values['remaining'].append(job.id)
            values['analysis_bindings'][job.id] = bound
            values['registered_hashes'][job.id] = {
                key.encode(): value if type(value) is bytes else value.encode() if isinstance(value, str) else str(value).encode()
                for key, value in job.to_dict().items()}
        try:
            from maintenance_canary_enrollment import enroll_analysis_jobs
        except ModuleNotFoundError as error:
            if error.name != 'maintenance_canary_enrollment': raise
            # Faithful pre-fix path: normal RQ enqueue overwrites/re-appends jobs.
            def enroll_analysis_jobs(conn, **arguments):
                queue = Queue(arguments['queue_name'], connection=conn)
                for job in jobs: queue.enqueue_job(job)
                return {'outcome': 'enrolled'}
        if case == 'existing_job':
            connection.hset('rq:job:' + jobs[-1].id, mapping={b'data': b'previous-work', b'old': b'preserve'})
        queue_key = 'rq:queue:' + queue_name
        marker = 'stock-agent:maintenance:canary-enrollment:' + queue_name
        last_key = 'rq:job:' + jobs[-1].id
        existing_keys = {'queue': queue_key, 'intermediate': queue_key + ':intermediate',
            'dependency': last_key + ':dependencies', 'dependent': last_key + ':dependents',
            'result': 'rq:results:' + jobs[-1].id,
            'first_seen': queue_key + ':intermediate:first_seen:' + jobs[-1].id,
            'failed_registry': 'rq:failed:' + queue_name, 'worker_registry': 'rq:workers:' + queue_name,
            'scheduler': 'rq:scheduler-lock:' + queue_name, 'cleaner': 'rq:clean_registries:' + queue_name,
            'marker_only': marker, 'wrong_registry_type': 'rq:queues'}
        if case in existing_keys:
            connection.set(existing_keys[case], b'previous-state-do-not-repair')
        if case == 'registered_empty': connection.sadd('rq:queues', queue_key)
        if case == 'replay':
            assert enroll_analysis_jobs(connection, **values)['outcome'] == 'enrolled'
        before = {key: connection.dump(key) for key in connection.scan_iter()}
        pristine = copy.deepcopy(values)
        exec_calls = []
        original_pipeline = connection.pipeline
        def pipeline(*args, **kwargs):
            pipe = original_pipeline(*args, **kwargs)
            original_execute, original_parse = pipe.execute, pipe.parse_response
            if case == 'cancel_after_readback':
                original_exit = pipe.__exit__
                class InterruptingExit(type(pipe)):
                    def __exit__(self, *args):
                        original_exit(*args)
                        raise KeyboardInterrupt('private cancellation after confirmed readback')
                pipe.__class__ = InterruptingExit
            if case == 'caller_mutation':
                original_watch = pipe.watch
                def watch(*keys):
                    value = original_watch(*keys)
                    values['analysis_bindings'][jobs[-1].id]['ticker'] = '2412.TW'
                    values['registered_hashes'][jobs[-1].id][b'data'] = b'caller-drift'
                    return value
                pipe.watch = watch
            if case == 'cancel_before_exec':
                def multi(): raise KeyboardInterrupt('private pre-EXEC cancellation')
                pipe.multi = multi
            if case == 'runtime_error':
                original_hset = pipe.hset
                def hset(key, *args, **kwargs):
                    value = original_hset(key, *args, **kwargs)
                    if key == 'rq:job:' + jobs[0].id:
                        pipe.lpush(key, b'force-real-EXEC-WRONGTYPE-with-other-writes-retained')
                    return value
                pipe.hset = hset
            def execute(*args, **kwargs):
                exec_calls.append(True)
                if case == 'race':
                    # A separate connection changes a watched identity before EXEC.
                    connection.hset(last_key, mapping={b'data': b'concurrent-work'})
                return original_execute(*args, **kwargs)
            def parse(conn, command, **kwargs):
                value = original_parse(conn, command, **kwargs)
                if command == '_' and isinstance(value, list):
                    if case == 'lost_reply': raise ConnectionError('private lost EXEC receipt')
                    if case == 'cancel_after_exec': raise KeyboardInterrupt('private post-EXEC cancellation')
                    if case == 'readback_mismatch': value[-2] = [b'not-the-enrolled-roster']
                return value
            pipe.execute, pipe.parse_response = execute, parse
            return pipe
        connection.pipeline = pipeline
        try:
            result = enroll_analysis_jobs(connection, **values)
        finally:
            connection.pipeline = original_pipeline
        expected = {'valid': 'enrolled', 'caller_mutation': 'enrolled', 'race': 'conflict',
            'lost_reply': 'uncertain', 'cancel_after_exec': 'uncertain', 'cancel_before_exec': 'cancelled',
            'cancel_after_readback': 'uncertain', 'runtime_error': 'uncertain',
            'readback_mismatch': 'uncertain'}.get(case, 'rejected')
        assert result['outcome'] == expected, result
        assert len(exec_calls) == int(expected in ('enrolled', 'conflict', 'uncertain'))
        assert ('enrollment' in result) is (expected == 'enrolled')
        assert result['cancellation_requested'] is case.startswith('cancel_')
        if expected in ('enrolled', 'uncertain'):
            assert connection.lrange(queue_key, 0, -1) == [job.id.encode() for job in jobs]
            assert all(connection.hgetall('rq:job:' + job.id) == pristine['registered_hashes'][job.id] for job in jobs)
            receipt = json.loads(connection.get(marker))
            assert receipt['task_ids'] == pristine['remaining']
            assert connection.pttl(marker) == -1
            if expected == 'enrolled':
                assert result['enrollment'] == {**pristine, 'remaining': tuple(pristine['remaining'])}
                claimed = claim.claim_analysis_next(connection, **result['enrollment'])
                assert claimed['outcome'] == 'claimed' and claimed['analysis_invocation']['pipeline_id'] == 'v1'
                assert claimed['enrollment_sha256'] == receipt['enrollment_sha256'] == result['enrollment_sha256']
                assert claimed['execution_authorized'] is False
                assert connection.lrange(queue_key, 0, -1) == [job.id.encode() for job in jobs[1:]]
                assert connection.lrange(queue_key + ':intermediate', 0, -1) == [jobs[0].id.encode()]
        else:
            if case == 'race': before[last_key.encode()] = connection.dump(last_key)
            assert {key: connection.dump(key) for key in connection.scan_iter()} == before
        assert all(connection.dump(key) == value for key, value in ordinary.items())
        if case != 'wrong_registry_type': assert connection.sismember('rq:queues', 'rq:queue:ordinary')
        assert result['stop_required'] is (expected != 'enrolled')
        assert result['execution_authorized'] is result['production_ready'] is False
        with open(sys.argv[1], 'x') as stream:
            json.dump({'case': case, 'outcome': result['outcome'], 'ordinary_unchanged': True,
                       'exec_attempts': len(exec_calls), 'executed': False}, stream)
    finally:
        connection.close()


if __name__ == '__main__': main()
