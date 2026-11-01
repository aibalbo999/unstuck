"""Real RQ serialization and private Redis claims, never job execution."""
import importlib.util
import json
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
    from redis import Redis
    from redis.retry import Retry
    from redis.backoff import NoBackoff
    from redis.exceptions import ConnectionError
    from rq import Queue
    from rq.job import Job
    root = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    spec = importlib.util.spec_from_file_location('private_analysis_claim',
        Path(__file__).resolve().parents[1] / 'scripts/maintenance_canary_claim.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    connection = Redis(unix_socket_path=str(root / 'redis.sock'), socket_timeout=2,
        socket_connect_timeout=2, retry=Retry(NoBackoff(), 0), retry_on_error=[])
    events = []
    def forbidden(*args, **kwargs):
        raise AssertionError('No restore, pickle load or job execution allowed')
    pickle.loads, Job.restore, Job.perform = forbidden, forbidden, forbidden
    try:
        assert connection.info('server')['tcp_port'] == 0
        connection.rpush('rq:queue:ordinary', b'ordinary-job')
        connection.hset('rq:job:ordinary-job', mapping={b'data': b'ordinary-preserved'})
        connection.zadd('rq:failed:ordinary', {b'untouched-expired': 1})
        ordinary = {key: connection.dump(key) for key in
            ('rq:queue:ordinary', 'rq:job:ordinary-job', 'rq:failed:ordinary')}
        for case in ('valid', 'callback', 'retry', 'dependency', 'lost_reply'):
            queue_name, job_id = 'analysis-canary-' + case, 'business-' + case
            task_id = 'analysis:' + job_id
            binding = {'campaign_id': 'offline-campaign', 'job_id': job_id, 'ticker': '2330.TW',
                'pipeline_id': 'v4', 'manifest_sha256': 'a' * 64, 'timeout_seconds': 60}
            queue = Queue(queue_name, connection=connection)
            job = helper.prepare_analysis_job(connection, queue_name=queue_name, binding=binding)
            if case == 'callback': job._failure_callback_name = 'os.system'
            if case == 'retry': job.retries_left, job.retry_intervals = 1, [60]
            queue.enqueue_job(job)
            if case == 'dependency': connection.sadd('rq:job:' + task_id + ':dependencies', 'unapproved')
            raw = connection.hgetall('rq:job:' + task_id)
            original_pipeline = connection.pipeline
            def pipeline(*args, **kwargs):
                pipe = original_pipeline(*args, **kwargs)
                original_parse = pipe.parse_response
                def lose_after_commit(conn, command, **options):
                    value = original_parse(conn, command, **options)
                    if command == '_' and isinstance(value, list):
                        raise ConnectionError('private lost EXEC receipt')
                    return value
                pipe.parse_response = lose_after_commit
                return pipe
            if case == 'lost_reply': connection.pipeline = pipeline
            try:
                result = helper.claim_analysis_next(connection, queue_name=queue_name,
                    registered_hashes={task_id: raw}, remaining=(task_id,), analysis_bindings={task_id: binding})
            finally:
                connection.pipeline = original_pipeline
            expected = 'claimed' if case == 'valid' else 'uncertain' if case == 'lost_reply' else 'rejected'
            assert result['outcome'] == expected, (case, result)
            moved = case in ('valid', 'lost_reply')
            assert connection.lrange(queue.key, 0, -1) == ([] if moved else [task_id.encode()])
            assert connection.lrange(queue.key + ':intermediate', 0, -1) == ([task_id.encode()] if moved else [])
            assert all(connection.dump(key) == value for key, value in ordinary.items())
            assert result['execution_authorized'] is result['production_ready'] is False
            assert ('analysis_invocation' in result) is (case == 'valid')
            events.append({'case': case, 'outcome': result['outcome'], 'ordinary_unchanged': True,
                           'executed': False, 'analysis_semantics_verified': result['analysis_semantics_verified']})
        with open(sys.argv[1], 'x') as stream: json.dump(events, stream)
    finally:
        connection.close()


if __name__ == '__main__': main()
