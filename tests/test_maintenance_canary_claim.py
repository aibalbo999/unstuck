"""Private raw claim contract; no worker, deserializer or application startup."""
import importlib.util
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('raw_canary_claim_tested', ROOT / 'scripts/maintenance_canary_claim.py')
CLAIM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLAIM)


def manifest():
    return {'queue_name': 'private-canary', 'remaining': ('one', 'two'),
        'registered_hashes': {'one': {b'data': b'never-unpickle-this', b'origin': b'private-canary'},
                              'two': {b'data': b'also-raw', b'origin': b'private-canary'}}}


class Pipe:
    def __init__(self, values):
        from redis.retry import Retry
        from redis.backoff import NoBackoff
        self.connection = SimpleNamespace(retry=Retry(NoBackoff(), 0))
        self.values = values
        self.calls = []
        self.roster = [x.encode() for x in values['remaining']]
        self.raw = {key: dict(value) for key, value in values['registered_hashes'].items()}
        self.intermediate = 0
        self.dependencies = 0
        self.replies = iter([b'OK', b'QUEUED', [self.roster[0]]])
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def watch(self, *keys): self.calls.append(('WATCH', keys))
    def llen(self, key): return self.intermediate if key.endswith(':intermediate') else len(self.roster)
    def lrange(self, *args): return list(self.roster)
    def hgetall(self, key): return self.raw.get(key.removeprefix('rq:job:'), {})
    def scard(self, key): return self.dependencies
    def multi(self): self.calls.append(('MULTI',))
    def lmove(self, *args, **kwargs): self.calls.append(('LMOVE', args, kwargs))
    def parse_response(self, *args, **kwargs): return next(self.replies)
    def execute(self):
        self.calls.append(('EXEC',))
        self.parse_response(None, '_')
        self.parse_response(None, '_')
        return self.parse_response(None, '_')


class Client:
    def __init__(self, pipe): self.pipe = pipe
    def pipeline(self, transaction=True): return self.pipe


def test_verified_raw_bytes_are_returned_only_after_one_exact_claim():
    values = manifest()
    pipe = Pipe(values)
    result = CLAIM.claim_next(Client(pipe), **values)
    assert result['outcome'] == 'claimed'
    assert result['stop_required'] is False and result['cancellation_requested'] is False
    assert result['job_id'] == 'one' and result['raw_snapshot'] == values['registered_hashes']['one']
    assert [row[0] for row in pipe.calls].count('EXEC') == 1
    assert [row for row in pipe.calls if row[0] == 'LMOVE'] == [
        ('LMOVE', ('rq:queue:private-canary', 'rq:queue:private-canary:intermediate'),
         {'src': 'LEFT', 'dest': 'RIGHT'})]


@pytest.mark.parametrize('kind', ['extra', 'duplicate', 'missing', 'reordered', 'payload', 'intermediate', 'dependencies'])
def test_raw_mismatch_never_enters_multi_or_consumes(kind):
    values = manifest()
    pipe = Pipe(values)
    if kind == 'extra': pipe.roster.append(b'foreign')
    if kind == 'duplicate': pipe.roster = [b'one', b'one']
    if kind == 'missing': pipe.raw['two'] = {}
    if kind == 'reordered': pipe.roster.reverse()
    if kind == 'payload': pipe.raw['two'][b'meta'] = b'untrusted extra field'
    if kind == 'intermediate': pipe.intermediate = 1
    if kind == 'dependencies': pipe.dependencies = 1
    result = CLAIM.claim_next(Client(pipe), **values)
    assert result['outcome'] == 'rejected' and 'raw_snapshot' not in result
    assert result['stop_required'] is True and result['cancellation_requested'] is False
    assert all(row[0] == 'WATCH' for row in pipe.calls)


def test_lost_exec_reply_is_uncertain_not_a_retryable_conflict():
    from redis.exceptions import WatchError
    values = manifest()
    pipe = Pipe(values)
    def lost():
        pipe.calls.append(('EXEC',))
        raise WatchError('A ConnectionError occurred on while watching one or more keys')
    pipe.execute = lost
    result = CLAIM.claim_next(Client(pipe), **values)
    assert result['outcome'] == 'uncertain' and 'raw_snapshot' not in result
    assert result['stop_required'] is True and result['cancellation_requested'] is False
    assert [row[0] for row in pipe.calls].count('EXEC') == 1


@pytest.mark.parametrize('retries', [1, -1, True])
def test_retrying_connection_rejected_without_changing_shared_retry(retries):
    values = manifest()
    pipe = Pipe(values)
    pipe.connection.retry._retries = retries
    result = CLAIM.claim_next(Client(pipe), **values)
    assert result['outcome'] == 'rejected'
    assert pipe.connection.retry._retries == retries
    assert all(row[0] == 'WATCH' for row in pipe.calls)


def test_caller_pin_mutation_after_watch_cannot_change_acceptance():
    values = manifest()
    pipe = Pipe(values)
    original = pipe.watch
    def changed(*args):
        original(*args)
        values['registered_hashes']['two'][b'data'] = b'mutated-during-WATCH'
        pipe.raw['two'][b'data'] = b'mutated-during-WATCH'
    pipe.watch = changed
    result = CLAIM.claim_next(Client(pipe), **values)
    assert result['outcome'] == 'rejected'
    assert all(row[0] == 'WATCH' for row in pipe.calls)


@pytest.mark.parametrize('error_type', [KeyboardInterrupt, SystemExit, asyncio.CancelledError])
@pytest.mark.parametrize('point', ['before_exec', 'after_exec'])
def test_cancellation_intent_is_preserved_without_turning_unknown_commit_into_rejection(error_type, point):
    values = manifest()
    pipe = Pipe(values)
    if point == 'before_exec':
        def interrupt(*args): raise error_type('must-not-expose-stop-detail-or-key')
        pipe.watch = interrupt
    else:
        execute = pipe.execute
        def interrupt():
            execute()
            raise error_type('must-not-expose-stop-detail-or-key')
        pipe.execute = interrupt
    result = CLAIM.claim_next(Client(pipe), **values)
    assert result['outcome'] == ('cancelled' if point == 'before_exec' else 'uncertain')
    assert result['cancellation_requested'] is True and result['stop_required'] is True
    assert result['execution_authorized'] is False and result['production_ready'] is False
    assert 'raw_snapshot' not in result
    assert 'must-not-expose' not in json.dumps(result)
    assert [row[0] for row in pipe.calls].count('EXEC') == (point == 'after_exec')


@pytest.mark.parametrize('interruption', [KeyboardInterrupt, SystemExit])
def test_interrupt_after_claimed_receipt_mutation_keeps_stop_and_no_execution_payload(interruption):
    values = manifest()
    pipe = Pipe(values)
    reached = []
    previous = sys.getprofile()
    def profile(frame, event, arg):
        if (frame.f_code is CLAIM.claim_next.__code__ and event == 'c_return'
                and getattr(arg, '__name__', None) == 'update'
                and isinstance(getattr(arg, '__self__', None), dict)
                and arg.__self__.get('outcome') == 'claimed'):
            reached.append(True)
            sys.setprofile(None)
            raise interruption('private receipt boundary')
    try:
        sys.setprofile(profile)
        result = CLAIM.claim_next(Client(pipe), **values)
    finally:
        sys.setprofile(previous)
    assert reached == [True]
    assert result['outcome'] == 'uncertain' and result['cancellation_requested'] is True
    assert result['stop_required'] is True
    assert 'raw_snapshot' not in result and 'job_id' not in result
    assert [row[0] for row in pipe.calls].count('EXEC') == 1


def test_real_private_redis_claim_drift_cas_and_lost_reply_preserve_ordinary_queue(request):
    from test_maintenance_rq_private_integration import private_redis
    def record(label, value): request.node.user_properties.append((label, json.dumps(value, sort_keys=True)))
    with private_redis(record) as (root, sock):
        output = root / 'claim-evidence.json'
        process = subprocess.Popen([sys.executable, '-I', '-B',
            str(Path(__file__).with_name('test_maintenance_canary_claim_child.py')), str(output)],
            env={'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
                'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(sock)},
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, (stdout + stderr).decode(errors='replace')[-6000:]
            value = json.loads(output.read_text())
            record('real_private_raw_claim', value)
            assert [row['outcome'] for row in value] == ['claimed', 'rejected', 'conflict', 'uncertain', 'uncertain']
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)


def analysis_enrollment():
    from datetime import datetime, timezone
    from rq.job import Job, JobStatus
    values = {'queue_name': 'private-analysis-canary', 'remaining': ('analysis:one',),
              'registered_hashes': {}, 'analysis_bindings': {}}
    binding = {'campaign_id': 'offline-campaign', 'job_id': 'one', 'ticker': '2330.TW',
               'pipeline_id': 'v4', 'manifest_sha256': 'a' * 64, 'timeout_seconds': 60}
    job = Job.create('analysis_jobs.run_stock_analysis_job', connection=object(),
        args=('one', '2330.TW', 'v4'), kwargs={'force_refresh': False},
        id='analysis:one', origin=values['queue_name'], status=JobStatus.QUEUED,
        timeout=60, result_ttl=604800, failure_ttl=604800,
        meta={'canary_campaign_id': binding['campaign_id'],
              'canary_manifest_sha256': binding['manifest_sha256']})
    job.created_at = job.enqueued_at = datetime(2026, 9, 16, tzinfo=timezone.utc)
    job.retries_left, job.retry_intervals = 0, []
    values['registered_hashes']['analysis:one'] = {
        key.encode(): value if type(value) is bytes else value.encode() if isinstance(value, str) else str(value).encode()
        for key, value in job.to_dict().items()}
    values['analysis_bindings']['analysis:one'] = binding
    return values


def semantic_claim(connection, values):
    # Before implementation exercise the old raw-only acceptance path for RED.
    function = getattr(CLAIM, 'claim_analysis_next', CLAIM.claim_next)
    arguments = dict(values)
    if not hasattr(CLAIM, 'claim_analysis_next'):
        arguments.pop('analysis_bindings')
    return function(connection, **arguments)


@pytest.mark.parametrize('field,value', [
    (b'success_callback_name', b'os.system'), (b'failure_callback_name', b'os.system'),
    (b'stopped_callback_name', b'os.system'), (b'retries_left', b'1'),
    (b'retry_intervals', b'[60]'), (b'dependency_id', b'other-job'),
    (b'allow_dependency_failures', b'1'), (b'unknown_future_hook', b'enabled'),
])
def test_analysis_semantics_rejected_before_watch_or_claim(field, value):
    values = analysis_enrollment()
    values['registered_hashes']['analysis:one'][field] = value
    pipe = Pipe(values)
    result = semantic_claim(Client(pipe), values)
    assert result['outcome'] == 'rejected' and result['stop_required'] is True
    assert pipe.calls == []
    assert 'analysis_invocation' not in result and 'raw_snapshot' not in result


def test_exact_default_rq_analysis_payload_has_verified_semantics_but_no_execution_authority():
    values = analysis_enrollment()
    pipe = Pipe(values)
    result = semantic_claim(Client(pipe), values)
    assert result['outcome'] == 'claimed'
    assert result.get('analysis_semantics_verified') is True
    assert result['execution_authorized'] is result['production_ready'] is False
    assert result['analysis_invocation'] == {
        'function': 'analysis_jobs.run_stock_analysis_job', 'args': ['one', '2330.TW', 'v4'],
        'kwargs': {'force_refresh': False}, **values['analysis_bindings']['analysis:one']}


@pytest.mark.parametrize('change', ['function', 'instance', 'job', 'ticker', 'mode', 'force', 'kwargs',
    'pickle_global', 'meta_global', 'manifest', 'trailing', 'two_members', 'oversized', 'truncated',
    'missing_zero', 'negative_retry', 'noncanonical_zero', 'callback_timeout', 'result', 'heartbeat',
    'origin', 'timeout', 'retention', 'timestamp', 'binding_timeout', 'binding_task', 'binding_mode'])
def test_unsafe_analysis_payloads_are_rejected_without_deserializing(change, monkeypatch):
    import pickle, zlib
    from rq.job import Job
    from rq.serializers import DefaultSerializer
    values = analysis_enrollment()
    raw = values['registered_hashes']['analysis:one']
    binding = values['analysis_bindings']['analysis:one']
    call = ['analysis_jobs.run_stock_analysis_job', None, ('one', '2330.TW', 'v4'), {'force_refresh': False}]
    if change == 'function': call[0] = 'os.system'
    elif change == 'instance': call[1] = {'unapproved': 'instance'}
    elif change in ('job', 'ticker', 'mode'):
        args = list(call[2]); args[{'job': 0, 'ticker': 1, 'mode': 2}[change]] = 'other'; call[2] = tuple(args)
    elif change == 'force': call[3]['force_refresh'] = True
    elif change == 'kwargs': call[3]['unapproved_argument'] = True
    if change in ('function', 'instance', 'job', 'ticker', 'mode', 'force', 'kwargs'):
        raw[b'data'] = zlib.compress(pickle.dumps(tuple(call), protocol=5))
    elif change == 'pickle_global': raw[b'data'] = zlib.compress(b"cos\nsystem\n(S'DO-NOT-RUN'\ntR.")
    elif change == 'meta_global': raw[b'meta'] = b"cos\nsystem\n(S'DO-NOT-RUN'\ntR."
    elif change == 'manifest': binding['manifest_sha256'] = 'b' * 64
    elif change == 'trailing': raw[b'data'] += b'ignored-by-unbounded-zlib'
    elif change == 'two_members': raw[b'data'] += raw[b'data']
    elif change == 'oversized': raw[b'data'] = zlib.compress(b'x' * 1000000)
    elif change == 'truncated': raw[b'data'] = raw[b'data'][:-2]
    elif change == 'missing_zero': raw.pop(b'retries_left')
    elif change == 'negative_retry': raw[b'retries_left'] = b'-1'
    elif change == 'noncanonical_zero': raw[b'retries_left'] = b'00'
    elif change == 'callback_timeout': raw[b'success_callback_timeout'] = b'60'
    elif change == 'result': raw[b'result'] = b'old result not adopted'
    elif change == 'heartbeat': raw[b'last_heartbeat'] = raw[b'created_at']
    elif change == 'origin': raw[b'origin'] = b'ordinary'
    elif change == 'timeout': raw[b'timeout'] = b'3601'
    elif change == 'retention': raw[b'failure_ttl'] = b'0'
    elif change == 'timestamp': raw[b'enqueued_at'] = b'2026-09-16'
    elif change == 'binding_timeout': binding['timeout_seconds'] = True
    elif change == 'binding_task': binding['job_id'] = 'other'
    elif change == 'binding_mode': binding['pipeline_id'] = 'both'
    seen = []
    def forbidden(*args, **kwargs):
        seen.append(True)
        raise AssertionError('raw jobs must never be restored or unpickled')
    monkeypatch.setattr(pickle, 'loads', forbidden)
    monkeypatch.setattr(pickle, 'Unpickler', forbidden)
    monkeypatch.setattr(DefaultSerializer, 'loads', forbidden)
    monkeypatch.setattr(Job, 'restore', forbidden)
    pipe = Pipe(values)
    result = semantic_claim(Client(pipe), values)
    assert result['outcome'] == 'rejected' and result['stop_required'] is True
    assert not pipe.calls and not seen
    assert 'DO-NOT-RUN' not in json.dumps(result)


@pytest.mark.parametrize('point', ['binding_mutation', 'raw_drift', 'lost_reply', 'cancelled_after_exec'])
def test_analysis_claim_preserves_raw_cas_and_post_exec_uncertainty(point):
    from redis.exceptions import WatchError
    values = analysis_enrollment()
    pipe = Pipe(values)
    watch, execute = pipe.watch, pipe.execute
    if point in ('binding_mutation', 'raw_drift'):
        def mutated(*args):
            watch(*args)
            values['analysis_bindings']['analysis:one']['ticker'] = '2412.TW'
            if point == 'raw_drift':
                pipe.raw['analysis:one'][b'retries_left'] = b'1'
        pipe.watch = mutated
    else:
        def interrupted():
            execute()
            raise WatchError() if point == 'lost_reply' else KeyboardInterrupt()
        pipe.execute = interrupted
    result = semantic_claim(Client(pipe), values)
    assert result['outcome'] == {'binding_mutation': 'claimed', 'raw_drift': 'rejected',
        'lost_reply': 'uncertain', 'cancelled_after_exec': 'uncertain'}[point]
    assert result['execution_authorized'] is False
    if point == 'binding_mutation':
        assert result['analysis_invocation']['ticker'] == '2330.TW'
    else:
        assert result['stop_required'] is True and 'analysis_invocation' not in result
    assert result['cancellation_requested'] is (point == 'cancelled_after_exec')


def test_real_private_rq_analysis_payload_semantics_and_claim(request):
    from test_maintenance_rq_private_integration import private_redis
    def record(label, value): request.node.user_properties.append((label, json.dumps(value, sort_keys=True)))
    with private_redis(record) as (root, sock):
        output = root / 'analysis-claim-evidence.json'
        process = subprocess.Popen([sys.executable, '-I', '-B',
            str(Path(__file__).with_name('test_maintenance_canary_analysis_child.py')), str(output)],
            env={'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
                'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(sock)},
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, (stdout + stderr).decode(errors='replace')[-5000:]
            value = json.loads(output.read_text())
            record('real_private_analysis_claim', value)
            assert [row['outcome'] for row in value] == ['claimed', 'rejected', 'rejected', 'rejected', 'uncertain']
            assert all(row['ordinary_unchanged'] and not row['executed'] for row in value)
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)


def test_prepare_normal_analysis_job_sets_explicit_zero_retry_without_redis_writes(monkeypatch):
    from rq.job import Job
    values = analysis_enrollment()
    binding = values['analysis_bindings']['analysis:one']
    seen = []
    def forbidden(*args, **kwargs):
        seen.append(True)
        raise AssertionError('preparation must not save or restore a job')
    monkeypatch.setattr(Job, 'save', forbidden)
    monkeypatch.setattr(Job, 'restore', forbidden)
    prepare = getattr(CLAIM, 'prepare_analysis_job', None)
    job = (prepare(object(), queue_name=values['queue_name'], binding=binding) if prepare else
           Job.create('analysis_jobs.run_stock_analysis_job', connection=object(),
               args=('one', '2330.TW', 'v4'), kwargs={'force_refresh': False}, id='analysis:one'))
    assert job.retries_left == 0 and job.retry_intervals == []
    assert job.func_name == 'analysis_jobs.run_stock_analysis_job'
    assert job.id == 'analysis:one' and job.args == ('one', '2330.TW', 'v4')
    assert job.kwargs == {'force_refresh': False} and job.timeout == 60
    assert job.result_ttl == job.failure_ttl == 604800
    assert job._success_callback_name is job._failure_callback_name is job._stopped_callback_name is None
    assert job._dependency_ids == [] and not seen
    assert job.meta == {'canary_campaign_id': binding['campaign_id'], 'canary_manifest_sha256': binding['manifest_sha256']}


@pytest.mark.parametrize('invalid_last', [False, True])
def test_all_four_enrolled_modes_are_semantically_checked_before_claim(invalid_last):
    values = {'queue_name': 'four-mode-canary', 'remaining': [], 'registered_hashes': {}, 'analysis_bindings': {}}
    for mode in ('v1', 'v2', 'v3', 'v4'):
        binding = {'campaign_id': 'offline-campaign', 'job_id': 'canary-' + mode,
            'ticker': '2330.TW', 'pipeline_id': mode, 'manifest_sha256': mode[1] * 64, 'timeout_seconds': 60}
        job = CLAIM.prepare_analysis_job(object(), queue_name=values['queue_name'], binding=binding)
        job.enqueued_at, job._status = job.created_at, 'queued'
        values['remaining'].append(job.id)
        values['analysis_bindings'][job.id] = binding
        values['registered_hashes'][job.id] = {
            key.encode(): value if type(value) is bytes else value.encode() if isinstance(value, str) else str(value).encode()
            for key, value in job.to_dict().items()}
    if invalid_last:
        values['registered_hashes']['analysis:canary-v4'][b'success_callback_name'] = b'os.system'
    pipe = Pipe(values)
    result = semantic_claim(Client(pipe), values)
    assert result['outcome'] == ('rejected' if invalid_last else 'claimed')
    assert len([call for call in pipe.calls if call[0] == 'EXEC']) == int(not invalid_last)
    if invalid_last:
        assert not pipe.calls
    else:
        assert result['analysis_invocation']['pipeline_id'] == 'v1'
        assert len(result['enrollment_sha256']) == 64


@pytest.mark.parametrize('field,value', [('pipeline_id', 'both'), ('ticker', '2330.tw'),
    ('timeout_seconds', 0), ('timeout_seconds', True), ('timeout_seconds', 3601),
    ('job_id', 'analysis:colon'), ('manifest_sha256', 'bad')])
def test_invalid_preparation_binding_cannot_even_construct_rq_job(monkeypatch, field, value):
    from rq.job import Job
    binding = dict(analysis_enrollment()['analysis_bindings']['analysis:one'])
    binding[field] = value
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError('invalid binding reached RQ constructor')
    monkeypatch.setattr(Job, 'create', forbidden)
    with pytest.raises(ValueError):
        CLAIM.prepare_analysis_job(object(), queue_name='private-canary', binding=binding)
    assert not calls
