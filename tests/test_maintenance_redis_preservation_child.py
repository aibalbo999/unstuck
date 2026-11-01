"""Private Redis preservation probe: no application, provider or config imports."""
import base64
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket
import sys
import time


def boundary():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_maintenance_rq_private_integration_child import install_boundary
    install_boundary()
    root = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    assert root.stat().st_mode & 0o777 == 0o700
    def audit(event, args):
        if event == 'sqlite3.connect':
            raise PermissionError('This preservation lane has no SQLite access')
        if event == 'subprocess.Popen':
            raise PermissionError('The private client cannot launch a child')
    sys.addaudithook(audit)
    denied = []
    for label, family, address in [('TCP', socket.AF_INET, ('127.0.0.1', 6379)),
            ('other_UNIX', socket.AF_UNIX, str(root / 'other.sock'))]:
        with socket.socket(family) as probe:
            try: probe.connect(address)
            except OSError: denied.append(label)
    try: socket.getaddrinfo('provider.invalid', 443)
    except OSError: denied.append('DNS')
    for label, path, mode in [('.env', root / '.env', 'rb'),
            ('external_write', root.parent / (root.name + '-denied'), 'wb')]:
        try:
            with open(path, mode): pass
        except RuntimeError: denied.append(label)
    assert denied == ['TCP', 'other_UNIX', 'DNS', '.env', 'external_write']
    return root, denied


def clock_ms(connection):
    sec, micros = connection.time()
    return sec * 1000 + micros // 1000


def encode(value):
    if isinstance(value, bytes): return {'base64': base64.b64encode(value).decode('ascii')}
    if isinstance(value, dict): return [[encode(key), encode(item)] for key, item in sorted(value.items())]
    if isinstance(value, (tuple, list)): return [encode(item) for item in value]
    if isinstance(value, set): return [encode(item) for item in sorted(value)]
    if isinstance(value, float) and not math.isfinite(value): return {'float': str(value)}
    return value


def snapshot(connection):
    """Raw key/value evidence, not DUMP encoding equality across reload layouts."""
    rows = {}
    for key in sorted(connection.scan_iter()):
        kind = connection.type(key).decode()
        reader = {'string': connection.get, 'hash': connection.hgetall,
            'list': lambda key: connection.lrange(key, 0, -1), 'set': connection.smembers,
            'zset': lambda key: connection.zrange(key, 0, -1, withscores=True)}[kind]
        rows[key.decode()] = {'type': kind, 'value': encode(reader(key)),
            'absolute_expiry_ms': connection.execute_command('PEXPIRETIME', key)}
    return rows


def semantic(connection, queue_name):
    from rq import Queue
    from rq.job import Job
    from rq.registry import DeferredJobRegistry, ScheduledJobRegistry
    queue = Queue(queue_name, connection=connection)
    jobs = {}
    for label in ('first', 'second', 'scheduled', 'deferred', 'late-last', 'late-front',
            'late-scheduled', 'late-deferred'):
        job_id = queue_name + '-' + label
        if not connection.exists(Job.key_for(job_id)): continue
        job = Job.fetch(job_id, connection=connection)
        jobs[label] = {'id': job.id, 'status': job.get_status(), 'function': job.func_name,
            'args': encode(job.args), 'kwargs': encode(job.kwargs), 'meta': encode(job.meta),
            'dependency_ids': encode(job.dependency_ids), 'timeout': job.timeout,
            'result_ttl': job.result_ttl, 'failure_ttl': job.failure_ttl, 'origin': job.origin}
    return {'queue_ids': queue.get_job_ids(), 'jobs': jobs,
        'scheduled': encode(connection.zrange(ScheduledJobRegistry(queue=queue).key, 0, -1, withscores=True)),
        'deferred': encode(connection.zrange(DeferredJobRegistry(queue=queue).key, 0, -1, withscores=True))}


def seed(connection, root):
    from rq import Queue
    from rq.registry import DeferredJobRegistry, ScheduledJobRegistry
    queue = Queue('preserve-' + root.name, connection=connection)
    seed_started_ms = clock_ms(connection)
    job_ids = {}
    def queued(label, *, parent=None, front=False):
        job = queue.enqueue_call('math.sqrt', args=(81,), kwargs={},
            job_id=queue.name + '-' + label, depends_on=parent, at_front=front,
            meta={'fixture': label, 'text': '凍結 payload', 'binary': b'\x00\xff'},
            description=label, timeout=17, result_ttl=120, failure_ttl=240)
        job_ids[label] = job.id
        return job
    queued('first')
    queued('second')
    scheduled_at = datetime.fromtimestamp(clock_ms(connection) / 1000 + 3600, timezone.utc).replace(microsecond=0)
    job = queue.enqueue_at(scheduled_at, 'math.sqrt', 144, job_id=queue.name + '-scheduled',
        meta={'source': 'original-schedule', 'do_not_reschedule': True})
    job_ids['scheduled'] = job.id
    queued('deferred', parent=job)
    now = clock_ms(connection)
    guards = {queue.name + ':quota:rpm': (b'3', now + 60_000),
        queue.name + ':quota:rpd-disabled': (b'1', now + 120_000),
        queue.name + ':model-circuit': (b'1', now + 90_000),
        queue.name + ':provider-circuit:open': (b'HTTP 503 fixture', now + 90_000),
        queue.name + ':expired-during-downtime': (b'1', now + 1500)}
    for key, (value, expiry) in guards.items(): connection.set(key, value, pxat=expiry)
    fail_key = queue.name + ':provider-circuit:fail'
    connection.hset(fail_key, mapping={'failures': 4, 'last_error': 'fixture'})
    connection.pexpireat(fail_key, now + 86_400_000)
    assert connection.save() is True
    initial = snapshot(connection)
    saved_at = clock_ms(connection)
    while clock_ms(connection) <= saved_at: time.sleep(.001)
    late_at = clock_ms(connection)
    queued('late-last')
    queued('late-front', front=True)
    late_scheduled_at = scheduled_at.timestamp() - 30
    late_scheduled = queue.enqueue_at(datetime.fromtimestamp(late_scheduled_at, timezone.utc),
        'math.sqrt', 169, job_id=queue.name + '-late-scheduled', meta={'original': 'late schedule'})
    job_ids['late-scheduled'] = late_scheduled.id
    queued('late-deferred', parent=late_scheduled)
    connection.set(queue.name + ':quota:rpm', b'4', keepttl=True)
    late_key = queue.name + ':quota:late-reservation'
    connection.set(late_key, b'unknown-attempt-not-refunded', pxat=now + 180_000)
    final = snapshot(connection)
    return {'initial': initial, 'final': final, 'queue_key': queue.key,
        'job_ids': job_ids, 'queue_ids': queue.get_job_ids(),
        'scheduled_key': ScheduledJobRegistry(queue=queue).key,
        'deferred_key': DeferredJobRegistry(queue=queue).key,
        'scheduled_at': scheduled_at.isoformat(), 'scheduled_epoch': int(scheduled_at.timestamp()),
        'initial_save_completed_ms': saved_at, 'late_enqueue_started_ms': late_at,
        'expired_key': queue.name + ':expired-during-downtime',
        'expire_during_downtime_ms': now + 1500, 'late_guard_key': late_key,
        'semantic': semantic(connection, queue.name), 'seed_started_ms': seed_started_ms,
        'seed_completed_ms': clock_ms(connection)}


def main():
    root, denied = boundary()
    from redis import Redis, ConnectionPool, UnixDomainSocketConnection
    from redis.backoff import NoBackoff
    from redis.retry import Retry
    import rq
    shutdown_commands = []
    class ObservedUnix(UnixDomainSocketConnection):
        def send_command(self, *args, **kwargs):
            if args[0] == 'SHUTDOWN':
                assert shutdown_commands == [], 'Never send a second shutdown'
                shutdown_commands.append(list(args))
            assert args[0] not in ('FLUSHDB', 'FLUSHALL')
            return super().send_command(*args, **kwargs)
    pool = ConnectionPool(connection_class=ObservedUnix, path=str(root / 'redis.sock'),
        socket_timeout=3, socket_connect_timeout=2, retry=Retry(NoBackoff(), 0), retry_on_error=[])
    connection = Redis(connection_pool=pool)
    assert connection.ping() is True
    server = connection.info('server')
    assert server['tcp_port'] == 0
    assert connection.config_get('save') == {'save': ''}
    assert connection.config_get('appendonly') == {'appendonly': 'no'}
    mode, output = sys.argv[1:]
    result = {'boundary_denied': denied, 'server_pid': server['process_id'],
        'redis_version': server['redis_version'], 'redis_build_id': server['redis_build_id'],
        'redis_run_id': server['run_id'], 'rq_version': rq.__version__, 'tcp_port': 0}
    try:
        if mode == 'seed': result.update(seed(connection, root))
        elif mode == 'snapshot':
            result['snapshot'] = snapshot(connection)
            result['semantic'] = semantic(connection, 'preserve-' + root.name)
            result['readback_ms'] = clock_ms(connection)
        elif mode in ('shutdown-save', 'shutdown-nosave'):
            result['command_ms'] = clock_ms(connection)
            attempt = root / ('shutdown-attempt-' + Path(output).name.split('-', 1)[0])
            attempt.touch(exist_ok=False)
            connection.shutdown(save=mode == 'shutdown-save', nosave=mode == 'shutdown-nosave')
            result['shutdown_command'] = mode
        else: raise AssertionError('Unknown private preservation operation')
    finally:
        connection.close()
        pool.disconnect()
    result['shutdown_commands'] = shutdown_commands
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream: json.dump(result, stream, sort_keys=True)


if __name__ == '__main__': main()
