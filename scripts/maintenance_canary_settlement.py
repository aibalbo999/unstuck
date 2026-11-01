"""Settle one claimed canary only after original owned-process and file readback.

Caller retains the original OwnedProcess, qualified code/command/environment,
exclusive queue ownership, durable operation attempt and frozen enrollment. No
source/billing approval, process launch/adoption, budget settlement, RQ restore,
callback, retry, ordinary-queue cleanup or formal handover is performed here.
The non-expiring settlement marker records one attempt's acknowledged bytes; it
is not Redis disk durability or a distributed filesystem/Redis transaction.
An uncertain EXEC is never retried, compensated or adopted as successful.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat

from redis.exceptions import WatchError

from maintenance_canary_claim import _analysis_enrollment, _no_retry, checked_analysis_claim
from maintenance_owned_process import OwnedProcess, _binding
from maintenance_state import _directory, _pairs, _private


def _raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _read(path, *, limit=64 * 1024 * 1024):
    """Read bounded private bytes, rejecting linked ancestors/files and drift."""
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('private_evidence_path_required')
    directory = _directory(str(path.parent))
    fd = None
    try:
        _private(os.fstat(directory), directory=True)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size > limit):
            raise ValueError('private_evidence_file_required')
        chunks, size = [], 0
        while part := os.read(fd, min(65536, limit + 1 - size)):
            chunks.append(part)
            size += len(part)
            if size > limit: raise ValueError('evidence_read_limit')
        current = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        if (current != os.fstat(fd) or (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino)
                or current.st_size != size or current.st_nlink != 1
                or current.st_mode != info.st_mode or current.st_uid != info.st_uid):
            raise ValueError('evidence_changed_during_read')
        return b''.join(chunks)
    finally:
        if fd is not None: os.close(fd)
        os.close(directory)


def _json(raw):
    value = json.loads(raw, object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_evidence')))
    if type(value) is not dict: raise ValueError('evidence_object_required')
    return value


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _completion(process, process_binding, output, binding):
    if type(process) is not OwnedProcess:
        raise ValueError('original_process_owner_required')
    lifecycle = process.wait_for_exit(0)
    if (lifecycle['binding'] != process_binding or not lifecycle['process_exited']
            or lifecycle['returncode'] not in (0, 2)):
        raise ValueError('owned_exit_unconfirmed')
    output = Path(output)
    files = {name: _read(output / name, limit=2 * 1024 * 1024 if name != 'outcome.json' else 64 * 1024 * 1024)
             for name in ('child-ticket.json', 'child-started.json', 'child-cleanup.json', 'outcome.json')}
    ticket, started, cleanup, outcome = (_json(files[name]) for name in
        ('child-ticket.json', 'child-started.json', 'child-cleanup.json', 'outcome.json'))
    expected_started = {'job_id': binding['job_id'], 'process_pid': lifecycle['pid'],
                        'ticket_sha256': _sha(files['child-ticket.json'])}
    if (lifecycle['admission_pipe_identity'] is not None) != ('maintenance_admission' in ticket):
        raise ValueError('original_parent_admission_unconfirmed')
    if 'maintenance_admission' in ticket:
        metadata = ticket['maintenance_admission']
        files['maintenance-admission.json'] = _read(output / 'maintenance-admission.json', limit=8192)
        files['dispatch-intent.json'] = _read(output / 'dispatch-intent.json', limit=8192)
        admission, intent = _json(files['maintenance-admission.json']), _json(files['dispatch-intent.json'])
        if (lifecycle['owned_session'] is not intent.get('owned_session', False)
                or lifecycle['owned_session'] and not lifecycle['process_group_absence_verified']):
            raise ValueError('original_owned_group_unconfirmed')
        if lifecycle['owned_session']:
            scope = cleanup.get('owned_process_scope')
            if (type(scope) is not dict or scope != {'policy': 'deny-python-process-creation-v1', 'denied': 0,
                    'pid': lifecycle['pid'], 'pgid': lifecycle['pid'], 'sid': lifecycle['pid']}
                    or any(type(scope[key]) is not int for key in ('denied', 'pid', 'pgid', 'sid'))):
                raise ValueError('original_owned_process_scope_unconfirmed')
            identity = cleanup.get('runtime_code_identity')
            if (type(identity) is not dict or set(identity) != {'commit', 'dirty', 'code_sha256'}
                    or type(identity['dirty']) is not bool or identity['commit'] != process_binding['backend_revision']
                    or identity != intent.get('runtime_code_identity')
                    or identity['code_sha256'] != intent.get('reservation', {}).get('actual_hashes', {}).get('code_sha256')):
                raise ValueError('original_runtime_code_identity_unconfirmed')
        expected_admission = {'schema': 'maintenance.owned-admission.v1', 'parent_pid': lifecycle['owner_pid'],
            'child_pid': lifecycle['pid'], 'pipe_identity': lifecycle['admission_pipe_identity'],
            'ticket_sha256': _sha(files['child-ticket.json']), 'intent_sha256': _sha(files['dispatch-intent.json']),
            'started_journal_sha256': lifecycle['started_journal_sha256']}
        if (type(metadata) is not dict or metadata != {'schema': 'maintenance.owned-admission.v1',
                'intent_sha256': expected_admission['intent_sha256'], 'parent_pid': lifecycle['owner_pid'],
                'pipe_identity': lifecycle['admission_pipe_identity'], 'process_binding': process_binding}
                or lifecycle['admission_pipe_identity'] is None or admission != expected_admission
                or intent.get('process_binding') != process_binding or intent.get('job_id') != binding['job_id']
                or intent.get('manifest_sha256') != binding['manifest_sha256']
                or type(intent.get('timeout_seconds')) is not int
                or intent['timeout_seconds'] != binding['timeout_seconds']
                or cleanup.get('maintenance_admission_sha256') != _sha(files['maintenance-admission.json'])):
            raise ValueError('original_parent_admission_unconfirmed')
        expected_started['maintenance_admission_sha256'] = _sha(files['maintenance-admission.json'])
    if (ticket.get('output') != str(output) or ticket.get('job_id') != binding['job_id']
            or ticket.get('manifest_sha256') != binding['manifest_sha256']
            or ticket.get('ledger_pin', {}).get('config', {}).get('identity', {}).get('campaign_id') != binding['campaign_id']
            or started != expected_started
            or cleanup.get('schema') != 'campaign.child_cleanup.v1'
            or cleanup.get('job_id') != binding['job_id'] or type(cleanup.get('process_pid')) is not int
            or cleanup['process_pid'] != lifecycle['pid']
            or cleanup.get('ticket_sha256') != _sha(files['child-ticket.json'])
            or cleanup.get('manifest_sha256') != binding['manifest_sha256']
            or cleanup.get('outcome_sha256') != _sha(files['outcome.json'])
            or cleanup.get('stop_requested') is not lifecycle['stop_requested']):
        raise ValueError('owned_evidence_identity_mismatch')
    if (any(cleanup.get(key) is not True for key in ('application_cleanup_verified', 'event_loop_closed',
                'sdk_cleanup_verified', 'sdk_cache_empty_after_shutdown', 'transport_restored'))
            or any(type(cleanup.get(key)) is not int or cleanup[key] != 0 for key in
                   ('pending_async_tasks', 'pending_async_generators', 'background_threads',
                    'shutdown_http_denials', 'shutdown_async_error_count'))
            or cleanup.get('shutdown_async_error_types') != []):
        raise ValueError('application_cleanup_unconfirmed')
    if (outcome.get('job_id') != binding['job_id'] or outcome.get('mode') != binding['pipeline_id']
            or outcome.get('frozen_verified') is not True or outcome.get('sdk_cleanup_verified') is not True
            or outcome.get('formal_publication') is not False or outcome.get('qualified_for_campaign') is not False
            or type(outcome.get('job')) is not dict or outcome['job'].get('job_id') != binding['job_id']
            or outcome['job'].get('ticker') != binding['ticker']
            or outcome['job'].get('pipeline_id') != binding['pipeline_id']):
        raise ValueError('normal_job_readback_mismatch')
    status = outcome.get('status')
    if status not in ('published', 'blocked', 'partial', 'error'):
        raise ValueError('normal_job_outcome_unknown')
    artifacts = {}
    if status == 'published':
        rows = outcome.get('artifacts')
        if (type(rows) is not dict or set(rows) != {'html_key', 'md_key', 'data_key'}
                or outcome['job'].get('status') != 'done' or type(outcome.get('publication')) is not dict):
            raise ValueError('publication_readback_missing')
        for field, extension in (('html_key', '.html'), ('md_key', '.md'), ('data_key', '.json')):
            row = rows[field]
            if (type(row) is not dict or set(row) != {'key', 'bytes', 'sha256'} or type(row['key']) is not str
                    or type(row['bytes']) is not int or not 0 < row['bytes'] <= 64 * 1024 * 1024):
                raise ValueError('invalid_private_artifact')
            relative = Path(row['key'])
            if relative.is_absolute() or '..' in relative.parts or not row['key'].endswith(extension):
                raise ValueError('artifact_escape')
            if field == 'html_key' and relative.name != outcome['job'].get('filename'):
                raise ValueError('publication_filename_mismatch')
            content = _read(output / 'reports' / relative)
            if len(content) != row['bytes'] or _sha(content) != row['sha256']:
                raise ValueError('private_artifact_changed')
            artifacts[field] = dict(row)
    elif lifecycle['returncode'] == 0:
        raise ValueError('exit_outcome_mismatch')
    terminal = 'finished' if status == 'published' and lifecycle['returncode'] == 0 and not lifecycle['stop_requested'] else 'failed'
    return {'task_id': 'analysis:' + binding['job_id'], 'manifest_sha256': binding['manifest_sha256'],
        'terminal_status': terminal, 'normal_outcome': status, 'process_pid': lifecycle['pid'],
        'process_journal_sha256': lifecycle['journal_sha256'],
        'evidence_sha256': {name: _sha(raw) for name, raw in files.items()}, 'artifacts': artifacts}


def settle_claimed_analysis(connection, *, queue_name, registered_hashes, remaining,
                            analysis_bindings, claimed, process, process_binding, output_dir):
    """CAS one exact intermediate ID to terminal RQ state after owned readback.

    Acknowledge only this terminal projection. Never infer qualification, finish
    the campaign ledger, execute callbacks, refresh TTL on replay, or resume a
    lost controller. Frozen inputs and all other queued jobs stay unchanged.
    """
    base = {'production_ready': False, 'execution_authorized': False, 'handover_verified': False,
            'campaign_settled': False, 'stop_required': True, 'cancellation_requested': False}
    executing, replies, commands = False, [], 0
    try:
        process_binding = _binding(process_binding)
        pins, order, bindings, digest = checked_analysis_claim(queue_name=queue_name,
            registered_hashes=registered_hashes, remaining=remaining, analysis_bindings=analysis_bindings, claimed=claimed)
        task_id, binding = order[0], bindings[order[0]]
        proof = _completion(process, process_binding, output_dir, binding)
        queue, job_key = 'rq:queue:' + queue_name, 'rq:job:' + task_id
        intermediate = queue + ':intermediate'
        enrollment_marker = 'stock-agent:maintenance:canary-enrollment:' + queue_name
        marker = 'stock-agent:maintenance:canary-settlement:' + queue_name + ':' + task_id
        hashes = ['rq:job:' + item for item in order]
        forbidden = [key + suffix for key in hashes for suffix in (':dependencies', ':dependents')]
        forbidden += ['rq:results:' + item for item in order]
        forbidden += [queue + ':intermediate:first_seen:' + item for item in order]
        forbidden += ['rq:' + prefix + ':' + queue_name for prefix in ('wip', 'scheduled', 'deferred', 'canceled')]
        registries = ['rq:finished:' + queue_name, 'rq:failed:' + queue_name]
        with connection.pipeline(transaction=True) as pipe:
            pipe.watch(queue, intermediate, enrollment_marker, marker, *hashes, *forbidden, *registries, 'rq:queues')
            _no_retry(pipe)
            if (pipe.exists(marker, *forbidden) or pipe.llen(queue) != len(order) - 1
                    or pipe.lrange(queue, 0, len(order)) != [item.encode() for item in order[1:]]
                    or pipe.llen(intermediate) != 1 or pipe.lrange(intermediate, 0, 1) != [task_id.encode()]
                    or not pipe.sismember('rq:queues', queue)):
                return {**base, 'outcome': 'rejected', 'reason': 'claimed_queue_state_mismatch'}
            for item, key in zip(order, hashes):
                if pipe.hgetall(key) != pins[item]:
                    return {**base, 'outcome': 'rejected', 'reason': 'claimed_payload_changed'}
            enrolled = _json(pipe.get(enrollment_marker))
            original = enrolled.get('task_ids')
            _, full_order, _, full_digest = _analysis_enrollment(queue_name, pins, original, bindings)
            expected_enrollment = {'schema': 'canary-enrollment.v1', 'queue_name': queue_name,
                                  'task_ids': list(full_order), 'enrollment_sha256': full_digest}
            if (enrolled != expected_enrollment or set(full_order) != set(pins)
                    or tuple(full_order[-len(order):]) != order):
                raise ValueError('original_enrollment_changed')
            prior = {item.encode() for item in full_order[:-len(order)]}
            for registry in registries:
                if pipe.type(registry) not in (b'none', b'zset') or pipe.zcard(registry) > len(prior):
                    raise ValueError('canary_registry_changed')
                if not set(pipe.zrange(registry, 0, len(pins))).issubset(prior):
                    raise ValueError('canary_registry_changed')
            seconds, micros = pipe.time()
            ended = datetime.fromtimestamp(seconds + micros / 1000000, timezone.utc)
            created = datetime.strptime(pins[task_id][b'created_at'].decode(), '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
            if ended < created: raise ValueError('invalid_settlement_clock')
            receipt = _raw({'schema': 'canary-settlement.v1', 'queue_name': queue_name,
                'enrollment_sha256': digest, 'ended_at': ended.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), **proof})
            updates = {b'status': proof['terminal_status'].encode(), b'ended_at': ended.strftime('%Y-%m-%dT%H:%M:%S.%fZ').encode(),
                       b'canary_settlement_sha256': _sha(receipt).encode()}
            terminal = {**pins[task_id], **updates}
            registry = 'rq:' + proof['terminal_status'] + ':' + queue_name
            score = seconds + 604800
            # The original owner/bytes must still match after all Redis reads.
            if _completion(process, process_binding, output_dir, binding) != proof:
                raise ValueError('completion_changed_before_exec')
            _no_retry(pipe)
            parse = pipe.parse_response
            def observed(*args, **kwargs):
                value = parse(*args, **kwargs)
                replies.append(value)
                return value
            pipe.parse_response = observed
            try:
                pipe.multi()
                pipe.set(marker, receipt, nx=True)
                pipe.hset(job_key, mapping=updates)
                pipe.zadd(registry, {task_id: score}, nx=True)
                pipe.expire(job_key, 604800)
                pipe.lpop(intermediate)
                pipe.get(marker)
                pipe.hgetall(job_key)
                pipe.lrange(queue, 0, len(order))
                pipe.llen(intermediate)
                pipe.zscore(registry, task_id)
                pipe.ttl(job_key)
                expected = [True, 1, 1, True, task_id.encode(), receipt, terminal,
                            [item.encode() for item in order[1:]], 0, float(score), 604800]
                commands = len(expected)
                executing = True
                response = pipe.execute()
            finally:
                pipe.parse_response = parse
            if response != expected or _completion(process, process_binding, output_dir, binding) != proof:
                return {**base, 'outcome': 'uncertain', 'reason': 'settlement_readback_mismatch'}
        return {**base, 'outcome': 'settled', 'stop_required': proof['terminal_status'] != 'finished',
            'task_id': task_id, 'terminal_status': proof['terminal_status'], 'remaining': order[1:],
            'settlement_sha256': _sha(receipt)}
    except WatchError:
        if executing and replies == [b'OK', *([b'QUEUED'] * commands), None]:
            return {**base, 'outcome': 'conflict', 'reason': 'observed_nil_exec'}
        return {**base, 'outcome': 'uncertain' if executing else 'rejected', 'reason': 'watch_or_connection_failure'}
    except BaseException as error:
        cancelled = not isinstance(error, Exception)
        return {**base, 'outcome': 'uncertain' if executing else ('cancelled' if cancelled else 'rejected'),
            'cancellation_requested': cancelled,
            'reason': 'settlement_unconfirmed' if executing else 'owned_completion_or_queue_unconfirmed'}
