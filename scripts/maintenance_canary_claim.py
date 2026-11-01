"""Bounded raw/allowlisted RQ claims; never restore, deserialize or execute jobs.

Caller owns trusted immutable enrollment, exact Redis endpoint/timeouts, exclusive
maintenance authority, and source/billing/code qualification. The raw claim alone
does not certify execution semantics; claim_analysis_next additionally checks the
registered normal analysis shape without loading arbitrary serialized objects.
No protected phase, runtime readiness, replay recovery or controller is provided.
The caller must provide an unshared-during-call redis-py connection with Retry(0).
Actual leased Retry is checked, never mutated. An uncertain outcome MUST stop:
never retry, refund, requeue or infer that LMOVE did not commit.
Every non-claimed result requires stop. Cancellation before EXEC is explicit;
after EXEC it remains uncertain with cancellation_requested=True. Even a claimed
result does not authorize job execution or establish production readiness.
"""
from datetime import datetime
import hashlib
import json
import pickle
import re
import zlib

from redis.exceptions import WatchError
from redis.retry import Retry
import canary_release_policy


def _freeze(queue_name, registered_hashes, remaining):
    safe = lambda value: type(value) is str and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value)
    if not safe(queue_name) or ':' in queue_name:
        raise ValueError('invalid_manifest')
    if type(registered_hashes) is not dict or not 1 <= len(registered_hashes) <= 4:
        raise ValueError('invalid_manifest')
    pins = {}
    for job_id, raw in registered_hashes.items():
        if (not safe(job_id) or type(raw) is not dict or not raw
                or any(type(key) is not bytes or not key or type(value) is not bytes for key, value in raw.items())):
            raise ValueError('invalid_manifest')
        pins[job_id] = dict(raw)
    if (type(remaining) not in (list, tuple) or not remaining
            or any(not safe(item) or item not in pins for item in remaining)
            or len(set(remaining)) != len(remaining)):
        raise ValueError('invalid_manifest')
    return pins, tuple(remaining)


def _no_retry(pipe):
    retry = getattr(getattr(pipe, 'connection', None), 'retry', None)
    if type(retry) is not Retry or type(retry._retries) is not int or retry._retries != 0:
        raise ValueError('zero_retry_connection_required')


def claim_next(connection, *, queue_name, registered_hashes, remaining):
    canary_release_policy.require_canary_enabled()
    result = {'outcome': 'rejected', 'production_ready': False, 'execution_authorized': False,
        'stop_required': True, 'cancellation_requested': False}
    executing = False
    replies = []
    try:
        pins, remaining = _freeze(queue_name, registered_hashes, remaining)
        queue = 'rq:queue:' + queue_name
        intermediate = queue + ':intermediate'
        hashes = ['rq:job:' + job_id for job_id in remaining]
        relations = [key + suffix for key in hashes for suffix in (':dependencies', ':dependents')]
        with connection.pipeline(transaction=True) as pipe:
            pipe.watch(queue, intermediate, *hashes, *relations)
            _no_retry(pipe)
            if (pipe.llen(queue) != len(remaining) or pipe.llen(intermediate) != 0
                    or pipe.lrange(queue, 0, len(remaining)) != [item.encode() for item in remaining]):
                result['reason'] = 'queue_roster_or_intermediate_mismatch'
                return result
            for job_id, key in zip(remaining, hashes):
                if pipe.hgetall(key) != pins[job_id]:
                    result['reason'] = 'raw_payload_mismatch'
                    return result
            if any(pipe.scard(key) != 0 for key in relations):
                result['reason'] = 'nonempty_job_relations'
                return result
            _no_retry(pipe)
            # Observe only this owned pipeline. One command means exactly three
            # RESP replies: MULTI, queued LMOVE, EXEC. Lost I/O WatchError is NOT
            # evidence of an aborted CAS; only an observed nil EXEC is.
            parse = pipe.parse_response
            def observed(*args, **kwargs):
                value = parse(*args, **kwargs)
                replies.append(value)
                return value
            pipe.parse_response = observed
            try:
                pipe.multi()
                pipe.lmove(queue, intermediate, src='LEFT', dest='RIGHT')
                executing = True
                response = pipe.execute()
            finally:
                pipe.parse_response = parse
            if response != [remaining[0].encode()]:
                result.update(outcome='uncertain', reason='unexpected_exec_reply')
                return result
        result.update(outcome='claimed', job_id=remaining[0], raw_snapshot=dict(pins[remaining[0]]),
            stop_required=False)
    except WatchError:
        if executing and replies == [b'OK', b'QUEUED', None]:
            result.update(outcome='conflict', reason='observed_nil_exec')
        else:
            result.update(outcome='uncertain' if executing else 'rejected', reason='watch_or_connection_failure')
    except BaseException as error:
        # Never expose Redis endpoint, credentials, supplied payload or exception text.
        cancelled = not isinstance(error, Exception)
        result.update(outcome='uncertain' if executing else ('cancelled' if cancelled else 'rejected'),
            cancellation_requested=cancelled,
            reason='execution_unconfirmed' if executing else ('cancellation_requested' if cancelled else 'prerequisite_unavailable'))
    # The final claimed dict.update may itself be interrupted after mutation.
    # A non-claimed receipt must never retain its earlier executable snapshot.
    if result['outcome'] != 'claimed':
        result['stop_required'] = True
        result.pop('raw_snapshot', None)
        result.pop('job_id', None)
    return result


_ANALYSIS_FUNCTION = 'analysis_jobs.run_stock_analysis_job'
_BINDING_FIELDS = {'campaign_id', 'job_id', 'ticker', 'pipeline_id', 'manifest_sha256', 'timeout_seconds'}
_EMPTY_JOB_FIELDS = {b'success_callback_name', b'failure_callback_name', b'stopped_callback_name',
                     b'started_at', b'ended_at', b'last_heartbeat', b'worker_name'}
_REQUIRED_JOB_FIELDS = _EMPTY_JOB_FIELDS | {b'created_at', b'enqueued_at', b'data', b'meta',
    b'origin', b'status', b'timeout', b'result_ttl', b'failure_ttl', b'retries_left', b'retry_intervals'}


def _bounded_inflate(raw):
    # Never deserialize input objects. One small zlib member is enough for the
    # registered primitive RQ invocation; trailing frames/bytes are rejected.
    if not 0 < len(raw) <= 16384:
        raise ValueError('invalid_analysis_payload')
    decoder = zlib.decompressobj()
    plain = decoder.decompress(raw, 8193)
    if (len(plain) > 8192 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail):
        raise ValueError('invalid_analysis_payload')
    return plain


def _checked_binding(source):
    if type(source) is not dict or set(source) != _BINDING_FIELDS:
        raise ValueError('invalid_analysis_binding')
    binding = dict(source)
    safe = lambda value: type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value)
    if (not all(safe(binding[key]) for key in ('campaign_id', 'job_id', 'ticker'))
            or len(binding['job_id']) > 119 or binding['ticker'] != binding['ticker'].upper()
            or type(binding['pipeline_id']) is not str or binding['pipeline_id'] not in ('v1', 'v2', 'v3', 'v4')
            or type(binding['manifest_sha256']) is not str
            or re.fullmatch(r'[a-f0-9]{64}', binding['manifest_sha256']) is None
            or type(binding['timeout_seconds']) is not int or not 1 <= binding['timeout_seconds'] <= 3600):
        raise ValueError('invalid_analysis_binding')
    return binding


def _analysis_components(binding):
    return ((_ANALYSIS_FUNCTION, None,
        (binding['job_id'], binding['ticker'], binding['pipeline_id']), {'force_refresh': False}),
        {'canary_campaign_id': binding['campaign_id'], 'canary_manifest_sha256': binding['manifest_sha256']})


def prepare_analysis_job(connection, *, queue_name, binding):
    """Construct a normal RQ Job only; no save/enqueue, claim or authority grant.

    RQ Retry(max=0) is invalid, so set the job's explicit zero budget directly.
    A future controller must create-only enroll it under exclusive ownership,
    freeze the resulting Redis bytes, then use claim_analysis_next. A caller can
    mutate a prepared Job; semantic claim rejects any subsequent policy drift.
    """
    canary_release_policy.require_canary_enabled()
    if type(queue_name) is not str or re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', queue_name) is None:
        raise ValueError('invalid_analysis_queue')
    bound = _checked_binding(binding)
    call, meta = _analysis_components(bound)
    from rq.job import Job
    job = Job.create(call[0], connection=connection, args=call[2], kwargs=call[3],
        id='analysis:' + bound['job_id'], origin=queue_name, timeout=bound['timeout_seconds'],
        result_ttl=604800, failure_ttl=604800, meta=meta)
    job.retries_left, job.retry_intervals = 0, []
    return job


def _analysis_enrollment(queue_name, registered_hashes, remaining, analysis_bindings):
    pins, remaining = _freeze(queue_name, registered_hashes, remaining)
    if type(analysis_bindings) is not dict or set(analysis_bindings) != set(pins):
        raise ValueError('invalid_analysis_binding')
    bindings = {}
    for task_id, raw in pins.items():
        binding = _checked_binding(analysis_bindings[task_id])
        if task_id != 'analysis:' + binding['job_id']:
            raise ValueError('invalid_analysis_binding')
        # Default RQ 1.16 serialization of this explicit canary shape only.
        # Comparing a locally generated primitive tuple does not execute a
        # pickle GLOBAL/REDUCE from Redis, nor restore metadata/result objects.
        expected_call, expected_meta = _analysis_components(binding)
        expected_fields = {b'origin': queue_name.encode(), b'status': b'queued',
            b'timeout': str(binding['timeout_seconds']).encode(), b'result_ttl': b'604800',
            b'failure_ttl': b'604800', b'retries_left': b'0', b'retry_intervals': b'[]',
            **{key: b'' for key in _EMPTY_JOB_FIELDS}}
        if (set(raw) not in (_REQUIRED_JOB_FIELDS, _REQUIRED_JOB_FIELDS | {b'description'})
                or any(len(key) > 64 or len(value) > 16384 for key, value in raw.items())
                or any(raw[key] != value for key, value in expected_fields.items())
                or _bounded_inflate(raw[b'data']) != pickle.dumps(expected_call, protocol=5)
                or raw[b'meta'] != pickle.dumps(expected_meta, protocol=5)):
            raise ValueError('invalid_analysis_semantics')
        for field in (b'created_at', b'enqueued_at'):
            text = raw[field].decode('ascii')
            # Same UTC representation as RQ utcformat. No inference of source
            # freshness or expiry authority is made from these timestamps.
            parsed = datetime.strptime(text, '%Y-%m-%dT%H:%M:%S.%fZ')
            if parsed.strftime('%Y-%m-%dT%H:%M:%S.%fZ') != text:
                raise ValueError('invalid_analysis_timestamp')
        bindings[task_id] = binding
    if len({row['campaign_id'] for row in bindings.values()}) != 1:
        raise ValueError('mixed_analysis_campaigns')
    digest = hashlib.sha256(json.dumps({'queue_name': queue_name, 'remaining': remaining,
        'bindings': bindings, 'raw': {task_id: {key.hex(): hashlib.sha256(value).hexdigest()
            for key, value in raw.items()} for task_id, raw in pins.items()}},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return pins, remaining, bindings, digest


def checked_analysis_claim(*, queue_name, registered_hashes, remaining, analysis_bindings, claimed):
    """Freeze and recheck a claim's exact normal invocation; not launch authority."""
    pins, order, bindings, digest = _analysis_enrollment(queue_name, registered_hashes, remaining, analysis_bindings)
    task_id, binding = order[0], bindings[order[0]]
    expected = {'function': _ANALYSIS_FUNCTION,
        'args': [binding['job_id'], binding['ticker'], binding['pipeline_id']],
        'kwargs': {'force_refresh': False}, **binding}
    if (type(claimed) is not dict or claimed.get('outcome') != 'claimed'
            or claimed.get('analysis_semantics_verified') is not True or claimed.get('job_id') != task_id
            or claimed.get('raw_snapshot') != pins[task_id] or claimed.get('enrollment_sha256') != digest
            or claimed.get('analysis_invocation') != expected):
        raise ValueError('exact_claim_required')
    return pins, order, bindings, digest


def claim_analysis_next(connection, *, queue_name, registered_hashes, remaining, analysis_bindings):
    """Claim a registered normal analysis payload, without executing/restoring it.

    RQ's normal queue defaults intentionally do not qualify: enrollment must use
    explicit zero retries, empty callbacks/relations, seven-day result/failure
    retention, canonical pickle5 args and the exact manifest metadata. The
    controller must still verify source/code/billing, acquire exclusive authority,
    install shared budgets and dispatch through the frozen normal-job adapter.
    No payload, metadata flag or successful claim grants those capabilities.
    """
    canary_release_policy.require_canary_enabled()
    entered_claim = False
    try:
        pins, remaining, bindings, digest = _analysis_enrollment(
            queue_name, registered_hashes, remaining, analysis_bindings)
        entered_claim = True
        result = claim_next(connection, queue_name=queue_name, registered_hashes=pins, remaining=remaining)
        if result['outcome'] != 'claimed':
            return {**result, 'analysis_semantics_verified': False}
        task_id = result['job_id']
        if task_id != remaining[0] or result['raw_snapshot'] != pins[task_id]:
            raise ValueError('claimed_analysis_identity_mismatch')
        binding = bindings[task_id]
        return {**result, 'analysis_semantics_verified': True, 'enrollment_sha256': digest,
            'analysis_invocation': {'function': _ANALYSIS_FUNCTION,
                'args': [binding['job_id'], binding['ticker'], binding['pipeline_id']],
                'kwargs': {'force_refresh': False}, **binding}}
    except BaseException as error:
        cancelled = not isinstance(error, Exception)
        return {'outcome': 'uncertain' if entered_claim else ('cancelled' if cancelled else 'rejected'),
            'reason': 'analysis_claim_unconfirmed' if entered_claim else 'analysis_semantics_rejected',
            'production_ready': False, 'execution_authorized': False, 'analysis_semantics_verified': False,
            'stop_required': True, 'cancellation_requested': cancelled}
