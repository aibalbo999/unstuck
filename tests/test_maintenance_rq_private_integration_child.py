"""Test-only fresh process; imports no application config, API or report jobs."""
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time


def install_boundary():
    root = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    target = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_SOCKET'])
    if root.resolve() != root or target != root / 'redis.sock':
        raise RuntimeError('Exact private socket namespace required')
    original, original_ex = socket.socket.connect, socket.socket.connect_ex
    def permitted(sock, address):
        return sock.family == socket.AF_UNIX and isinstance(address, str) and address == str(target)
    def connect(sock, address):
        if not permitted(sock, address): raise OSError('Private RQ denies every other socket')
        return original(sock, address)
    def connect_ex(sock, address):
        if not permitted(sock, address): raise OSError('Private RQ denies every other socket')
        return original_ex(sock, address)
    def deny(*args, **kwargs): raise OSError('Private RQ denies TCP and DNS')
    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    socket.create_connection = socket.getaddrinfo = socket.gethostbyname = deny
    def audit(event, args):
        if event == 'import' and args[0] in ('config', 'api', 'analysis_jobs', 'dotenv'):
            raise RuntimeError('Private adapter lane cannot import application startup or secrets')
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0]))
            if path.name == '.env': raise RuntimeError('Private adapter lane cannot read .env')
            flags = args[2]
            if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                if path != Path('/dev/null') and not path.resolve().is_relative_to(root):
                    raise RuntimeError('Private adapter lane cannot write outside its own directory')
    sys.addaudithook(audit)


# macOS multiprocessing spawn re-executes this file as __mp_main__; install the
# same socket boundary before RQ scheduler code imports and opens its connection.
if __name__ in ('__main__', '__mp_main__'):
    install_boundary()
    sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'backend')]


def plan():
    return {'campaign_id': 'private-real-rq', 'old_revision': 'a' * 40, 'new_revision': 'b' * 40,
        'control_sha256': 'c' * 64, 'queue_name': 'private-fixture-not-canary',
        'canaries': [{'mode': mode, 'job_id': mode, 'manifest_sha256': 'd' * 64}
                     for mode in ('v1', 'v2', 'v3', 'v4')]}


def held_job(directory):
    """No application job, provider, API or DB import: only a private handshake."""
    root = Path(directory)
    if root != Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']):
        raise RuntimeError('Unexpected private job output directory')
    (root / 'job-started').touch()
    deadline = time.monotonic() + 4
    while not (root / 'job-release').exists() and time.monotonic() < deadline:
        time.sleep(.01)
    if not (root / 'job-release').exists(): raise RuntimeError('Private controller did not release its job')
    return 'accepted-before-arm'


def main():
    import maintenance_guard as guard
    from redis import Redis
    from rq import Queue, SimpleWorker
    from rq.job import Job
    from rq.exceptions import NoSuchJobError
    from rq.registry import FailedJobRegistry
    from maintenance_rq_worker import maintenance_worker_class
    import multiprocessing
    import signal
    root = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    control = root / 'maintenance'
    guard.initialize(control)
    connection = Redis(unix_socket_path=os.environ['STOCK_AGENT_PRIVATE_RQ_SOCKET'],
        socket_connect_timeout=2, socket_timeout=8)
    name = sys.argv[1]
    events, controller_errors, pop_calls, scheduler_signals = [], [], [], []
    entered_pop = threading.Event()
    class ObservedQueue(Queue):
        @classmethod
        def lpop(cls, queue_keys, timeout, connection=None):
            pop_calls.append({'kind': 'lpop', 'timeout': timeout})
            entered_pop.set()
            return super().lpop(queue_keys, timeout, connection=connection)
        @classmethod
        def lmove(cls, connection, queue_key, timeout):
            pop_calls.append({'kind': 'lmove', 'timeout': timeout})
            entered_pop.set()
            return super().lmove(connection, queue_key, timeout)
    class ObservedJob(Job):
        @classmethod
        def fetch(cls, *args, **kwargs):
            try:
                return super().fetch(*args, **kwargs)
            except NoSuchJobError:
                # Observe the real stale-ID error before Queue.dequeue_any's
                # own retry. No mocked fetch/pop or synthetic exception.
                guard.arm(control, plan())
                events.append({'point': 'stale', 'drained': guard.wait_drained(control, 0)})
                raise
    queue = ObservedQueue('private-' + root.name, connection=connection, job_class=ObservedJob)
    queues = [queue]
    if name.endswith('-multi'):
        queues.append(ObservedQueue(queue.name + '-spare', connection=connection, job_class=ObservedJob))
    jobs = []
    if name.startswith('accepted'):
        from test_maintenance_rq_private_integration_child import held_job as function
        jobs.append(queue.enqueue_call(function, args=(str(root),), job_id=queue.name + '-first',
            timeout=6, result_ttl=60, failure_ttl=60))
    if name != 'empty':
        jobs.append(queue.enqueue_call('math.sqrt', args=(81,), job_id=queue.name + '-second',
            result_ttl=60, failure_ttl=60))
    if name.startswith('stale'):
        connection.lpush(queue.key, queue.name + '-nonexistent')
    if name == 'armed': guard.arm(control, plan())
    before_ids = queue.get_job_ids()

    def controller_action():
        try:
            if name == 'empty':
                if not entered_pop.wait(5): raise RuntimeError('No real pop observed')
            else:
                deadline = time.monotonic() + 5
                while not (root / 'job-started').exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                if not (root / 'job-started').exists(): raise RuntimeError('No real job observed')
            guard.arm(control, plan())
            events.append({'point': 'empty-pop' if name == 'empty' else 'job',
                'drained': guard.wait_drained(control, 0)})
            (root / 'job-release').touch()
        except BaseException as error:
            controller_errors.append(type(error).__name__ + ':' + str(error))
    controller = None
    if name == 'empty' or name.startswith('accepted'):
        controller = threading.Thread(target=controller_action)
        controller.start()
    worker_class = SimpleWorker if sys.argv[3] == 'unguarded' else maintenance_worker_class(SimpleWorker)
    worker = worker_class(queues, connection=connection, queue_class=ObservedQueue, job_class=ObservedJob)
    original_kill = os.kill
    def owned_scheduler_signal(pid, signum):
        scheduler = worker.scheduler._process if worker.scheduler else None
        if scheduler is None or pid != scheduler.pid or signum != signal.SIGTERM:
            raise RuntimeError('Unexpected process target in private RQ worker')
        scheduler_signals.append({'pid': pid, 'signal': signum})
        return original_kill(pid, signum)
    os.kill = owned_scheduler_signal
    started = time.monotonic()
    try:
        worker.work(burst=name in ('armed', 'normal'), max_jobs=2, max_idle_time=7,
            with_scheduler=True, logging_level='WARNING')
    finally:
        os.kill = original_kill
        if controller:
            (root / 'job-release').touch()
            controller.join(timeout=6)
            if controller.is_alive(): raise RuntimeError('Private controller did not terminate')
    elapsed = time.monotonic() - started
    denied = 0
    for address, family, operation in [(('127.0.0.1', 6379), socket.AF_INET, 'connect'),
                                       (str(root / 'other.sock'), socket.AF_UNIX, 'connect_ex')]:
        with socket.socket(family) as probe:
            try: getattr(probe, operation)(address)
            except OSError: denied += 1
    try: socket.getaddrinfo('provider.invalid', 443)
    except OSError: denied += 1
    scheduler = worker.scheduler._process if worker.scheduler else None
    value = {'statuses': [job.get_status(refresh=True) for job in jobs],
        'results': [job.return_value() for job in jobs], 'job_ids': [job.id for job in jobs],
        'before_ids': before_ids, 'queue_ids': queue.get_job_ids(),
        'pause': getattr(worker, 'maintenance_pause_reason', None),
        'scheduler': {'pid': scheduler.pid, 'exitcode': scheduler.exitcode, 'alive': scheduler.is_alive()} if scheduler else None,
        'scheduler_signals': scheduler_signals, 'children_alive': [p.pid for p in multiprocessing.active_children()],
        'pubsub_alive': worker.pubsub_thread.is_alive() if worker.pubsub_thread else False,
        'events': events, 'controller_errors': controller_errors, 'pop_calls': pop_calls,
        'elapsed': elapsed, 'drained': guard.wait_drained(control, 0) if name != 'normal' else None,
        'failed_count': FailedJobRegistry(queue.name, connection=connection).count,
        'tcp_port': connection.info('server')['tcp_port'], 'forbidden_network_denied': denied}
    connection.close()
    with open(sys.argv[2], 'x') as stream: json.dump(value, stream)


if __name__ == '__main__':
    main()
