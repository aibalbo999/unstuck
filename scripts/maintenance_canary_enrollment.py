"""Create-only, single-attempt enrollment for one private RQ canary roster.

Caller owns a trusted pre-registration, exclusive dedicated queue/Redis endpoint,
zero-retry connection with bounded timeouts, and an independent durable attempt
journal. This helper neither acquires maintenance authority nor certifies Redis
disk durability. It is NOT exposed by the formal maintenance entry.

Never use RQ enqueue/save here: those overwrite existing hashes and append replayed
IDs. The one watched transaction creates only absent keys and reads back its own
bytes. A lost/error reply may leave partial or complete work; stop without retry,
delete, compensation, job execution, budget refund, or inferred rollback.
"""
import json
import canary_release_policy

from redis.exceptions import WatchError

from maintenance_canary_claim import _analysis_enrollment, _no_retry


def enroll_analysis_jobs(connection, *, queue_name, registered_hashes, remaining, analysis_bindings):
    """Enroll all 1–4 semantic-checked pins, returning claim inputs only on ACK.

The receipt means the transaction's readback matched, not that a worker/source/
billing/maintenance gate passed. Subsequent claim still compares exact bytes via
WATCH. No existing queue membership, RQ state, or enrollment marker is adopted.
"""
    canary_release_policy.require_canary_enabled()
    executing, replies = False, []
    command_count = 0
    base = {'production_ready': False, 'execution_authorized': False,
            'stop_required': True, 'cancellation_requested': False}
    try:
        pins, order, bindings, digest = _analysis_enrollment(
            queue_name, registered_hashes, remaining, analysis_bindings)
        if set(order) != set(pins):
            raise ValueError('entire_enrollment_required')
        queue = 'rq:queue:' + queue_name
        marker = 'stock-agent:maintenance:canary-enrollment:' + queue_name
        hashes = ['rq:job:' + task_id for task_id in order]
        reserved = [queue, queue + ':intermediate', marker, *hashes,
            *[key + suffix for key in hashes for suffix in (':dependencies', ':dependents')],
            *['rq:results:' + task_id for task_id in order],
            *[queue + ':intermediate:first_seen:' + task_id for task_id in order],
            *['rq:' + prefix + ':' + queue_name for prefix in
              ('registry', 'wip', 'finished', 'failed', 'deferred', 'scheduled', 'canceled',
               'workers', 'scheduler', 'scheduler-lock', 'clean_registries')]]
        receipt = json.dumps({'schema': 'canary-enrollment.v1', 'queue_name': queue_name,
            'task_ids': order, 'enrollment_sha256': digest}, sort_keys=True, separators=(',', ':')).encode()
        with connection.pipeline(transaction=True) as pipe:
            pipe.watch('rq:queues', *reserved)
            _no_retry(pipe)
            if pipe.exists(*reserved) != 0:
                return {**base, 'outcome': 'rejected', 'reason': 'existing_canary_state'}
            if (pipe.type('rq:queues') not in (b'none', b'set')
                    or pipe.sismember('rq:queues', queue)):
                return {**base, 'outcome': 'rejected', 'reason': 'existing_or_invalid_queue_registry'}
            _no_retry(pipe)
            parse = pipe.parse_response
            def observed(*args, **kwargs):
                value = parse(*args, **kwargs)
                replies.append(value)
                return value
            pipe.parse_response = observed
            try:
                pipe.multi()
                # Marker is first and has no expiry. EXEC runtime errors are not
                # rollback; retain every resulting key for owned reconciliation.
                pipe.set(marker, receipt, nx=True)
                for task_id, key in zip(order, hashes):
                    pipe.hset(key, mapping=pins[task_id])
                pipe.rpush(queue, *[item.encode() for item in order])
                pipe.sadd('rq:queues', queue)
                # Read within the same transaction, without a second connection
                # lease or restoring serialized RQ jobs.
                pipe.get(marker)
                for key in hashes:
                    pipe.hgetall(key)
                pipe.lrange(queue, 0, len(order))
                pipe.sismember('rq:queues', queue)
                expected = [True, *[len(pins[item]) for item in order], len(order), 1,
                            receipt, *[pins[item] for item in order],
                            [item.encode() for item in order], True]
                command_count = len(expected)
                executing = True
                response = pipe.execute()
            finally:
                pipe.parse_response = parse
            if response != expected:
                return {**base, 'outcome': 'uncertain', 'reason': 'enrollment_readback_mismatch'}
        return {**base, 'outcome': 'enrolled', 'stop_required': False,
                'enrollment_sha256': digest, 'enrollment': {'queue_name': queue_name,
                    'registered_hashes': pins, 'remaining': order, 'analysis_bindings': bindings}}
    except WatchError:
        if executing and replies == [b'OK', *([b'QUEUED'] * command_count), None]:
            return {**base, 'outcome': 'conflict', 'reason': 'observed_nil_exec'}
        return {**base, 'outcome': 'uncertain' if executing else 'rejected',
                'reason': 'watch_or_connection_failure'}
    except BaseException as error:
        cancelled = not isinstance(error, Exception)
        return {**base, 'outcome': 'uncertain' if executing else ('cancelled' if cancelled else 'rejected'),
                'cancellation_requested': cancelled,
                'reason': 'enrollment_unconfirmed' if executing else
                    ('cancellation_requested' if cancelled else 'enrollment_prerequisite_rejected')}
