"""Fresh private UNIX Redis evidence; deliberately no Job or worker import."""
import importlib.util
import json
import os
from pathlib import Path
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
    root = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    spec = importlib.util.spec_from_file_location('private_raw_claim', Path(__file__).resolve().parents[1] / 'scripts/maintenance_canary_claim.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    options = dict(unix_socket_path=str(root / 'redis.sock'), socket_timeout=2,
        socket_connect_timeout=2, retry=Retry(NoBackoff(), 0), retry_on_error=[])
    connection, other = Redis(**options), Redis(**options)
    evidence = []
    try:
        assert connection.info('server')['tcp_port'] == 0
        connection.rpush('rq:queue:ordinary', b'ordinary-job')
        connection.hset('rq:job:ordinary-job', mapping={b'data': b'ordinary-payload'})
        connection.zadd('rq:failed:ordinary', {b'expired-but-untouched': 1})
        ordinary = {key: connection.dump(key) for key in
            ('rq:queue:ordinary', 'rq:job:ordinary-job', 'rq:failed:ordinary')}
        for mode in ('success', 'payload', 'race', 'lost-exec-reply', 'cancelled-after-exec'):
            name = 'claim-' + mode
            key, intermediate = 'rq:queue:' + name, 'rq:queue:' + name + ':intermediate'
            ids = (name + '-one', name + '-two')
            pins = {job_id: {b'data': b'controller-frozen-bytes', b'origin': name.encode(),
                b'status': b'queued', b'meta': b'raw-not-deserialized'} for job_id in ids}
            for job_id, raw in pins.items(): connection.hset('rq:job:' + job_id, mapping=raw)
            connection.rpush(key, *[item.encode() for item in ids])
            if mode == 'payload': other.hset('rq:job:' + ids[1], b'data', b'changed')
            original_pipeline = connection.pipeline
            sends = []
            def pipeline(*args, **kwargs):
                pipe = original_pipeline(*args, **kwargs)
                execute = pipe.execute
                def observed_execute(*args, **kwargs):
                    sends.append('EXEC')
                    if mode == 'race': other.rpush(key, b'foreign-added-after-WATCH')
                    return execute(*args, **kwargs)
                pipe.execute = observed_execute
                if mode in ('lost-exec-reply', 'cancelled-after-exec'):
                    parse = pipe.parse_response
                    def lost_reply(conn, command, **kwargs):
                        value = parse(conn, command, **kwargs)
                        # Real EXEC already committed and its array was read;
                        # simulate loss before caller receives it, not before send.
                        if command == '_' and isinstance(value, list):
                            if mode == 'cancelled-after-exec':
                                raise KeyboardInterrupt('private cancellation after actual commit')
                            raise ConnectionError('private fixture lost EXEC receipt')
                        return value
                    pipe.parse_response = lost_reply
                return pipe
            connection.pipeline = pipeline
            try:
                result = helper.claim_next(connection, queue_name=name, registered_hashes=pins, remaining=ids)
            finally:
                connection.pipeline = original_pipeline
            assert result['outcome'] == {'success': 'claimed', 'payload': 'rejected',
                'race': 'conflict', 'lost-exec-reply': 'uncertain', 'cancelled-after-exec': 'uncertain'}[mode], result
            assert result['stop_required'] is (mode != 'success')
            assert result['cancellation_requested'] is (mode == 'cancelled-after-exec')
            committed = mode in ('success', 'lost-exec-reply', 'cancelled-after-exec')
            expected = [ids[1].encode()] if committed else [item.encode() for item in ids]
            if mode == 'race': expected.append(b'foreign-added-after-WATCH')
            assert connection.lrange(key, 0, -1) == expected
            assert connection.lrange(intermediate, 0, -1) == (
                [ids[0].encode()] if committed else [])
            assert sends == ([] if mode == 'payload' else ['EXEC'])
            assert all(connection.dump(key) == value for key, value in ordinary.items())
            assert ('raw_snapshot' in result) is (mode == 'success')
            evidence.append({'case': mode, 'outcome': result['outcome'], 'exec_calls': len(sends),
                'queue_ids': [item.decode() for item in expected], 'ordinary_unchanged': True,
                'stop_required': result['stop_required'], 'cancellation_requested': result['cancellation_requested']})
        with open(sys.argv[1], 'x') as stream: json.dump(evidence, stream)
    finally:
        connection.close()
        other.close()


if __name__ == '__main__': main()
