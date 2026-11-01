"""Fresh private process: unmodified archived legacy app, real lifespan and UDS."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def prepare_readonly_probe(api, private, redis):
    """Seed a private warm runtime with real baseline public store initializers."""
    from cache_backends import SqliteCacheBackend
    import decision_tracking_store
    import watchlist_store
    from langgraph.checkpoint.sqlite import SqliteSaver
    from runtime_health import build_readiness_payload
    paths = {'cache_db': private / 'cache.sqlite3', 'task_db': private / 'operational.sqlite3',
             'decision_tracking_db': private / 'operational.sqlite3',
             'watchlist_db': private / 'watchlist.sqlite3', 'checkpoint_db': private / 'checkpoints.sqlite3'}
    cache = SqliteCacheBackend(paths['cache_db'])
    cache.set_json('private-probe-sentinel', {'preserve': True}, ttl_seconds=3600)
    cache.close()
    decision_tracking_store.list_items()
    watchlist_store.list_watchlist()
    saver_connection = sqlite3.connect(paths['checkpoint_db'])
    SqliteSaver(saver_connection).setup()
    holders = [saver_connection]
    for path in dict.fromkeys(paths.values()):
        connection = sqlite3.connect(path)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('SELECT name FROM sqlite_schema').fetchall()
        holders.append(connection)
    expected_tables = {'cache_db': ('cache_entries',), 'task_db': ('analysis_jobs',),
        'decision_tracking_db': ('decision_tracking_items', 'decision_backtest_results'),
        'watchlist_db': ('watchlist_items', 'watchlist_meta'), 'checkpoint_db': ('checkpoints', 'writes')}
    checks = load('private_readonly_readiness', ROOT / 'scripts/maintenance_readiness.py')
    probe = checks.ReadOnlyMaintenanceProbe(directories={
        'output_dir': private / 'output', 'cache_dir': private / 'cache',
        'market_calendar_dir': private / 'market-calendars', 'yfinance_cache_dir': private / 'yfinance'},
        sqlite_paths=paths, required_tables=expected_tables, queue_names=(os.environ['TASK_QUEUE_NAME'],))
    expired_member = 'missing-expired-private-job'
    registry = 'rq:failed:' + os.environ['TASK_QUEUE_NAME']
    redis.zadd(registry, {expired_member: 1})

    def contents():
        # SHM coordination is explicitly not asserted byte-inert; DB/WAL are.
        values = {}
        for path in dict.fromkeys(paths.values()):
            for suffix in ('', '-wal'):
                source = Path(str(path) + suffix)
                values[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
        return values

    async def readiness(scope, receive, send):
        before = contents()
        files = sorted(str(path) for path in private.glob('*.sqlite3*'))
        queued = redis.lrange(api.analysis_task_queue.queue.key, 0, -1)
        payload = await asyncio.to_thread(probe.build_payload, build_readiness_payload,
            runtime_settings=api.runtime_settings_for_output_dir(api.OUTPUT_DIR), task_queue=api.analysis_task_queue)
        assert contents() == before
        assert sorted(str(path) for path in private.glob('*.sqlite3*')) == files
        assert redis.zscore(registry, expired_member) == 1
        assert redis.lrange(api.analysis_task_queue.queue.key, 0, -1) == queued
        (private / 'readonly-probe.json').write_text(json.dumps({
            'payload': payload, 'db_wal_unchanged': True, 'sqlite_file_set_unchanged': True,
            'expired_registry_member_preserved': True, 'ordinary_queue_unchanged': True}))
        body = json.dumps(payload).encode()
        await send({'type': 'http.response.start',
            'status': 200 if payload['status'] == 'probe_pass' else 503,
            'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())]})
        await send({'type': 'http.response.body', 'body': body})

    return readiness, holders


def main():
    private = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    baseline = Path(os.environ['STOCK_AGENT_LEGACY_PROBE_BASELINE'])
    if baseline.resolve() != baseline or not (baseline / 'backend/api.py').is_file():
        raise RuntimeError('Verified archived baseline required')
    boundary = load('probe_startup_boundary', ROOT / 'tests/test_maintenance_rq_private_integration_bootstrap.py')
    registered = ()
    if os.environ.get('STOCK_AGENT_PRIVATE_READONLY_PROBE') == '1':
        registered = tuple(private / name for name in (
            'cache.sqlite3', 'operational.sqlite3', 'watchlist.sqlite3', 'checkpoints.sqlite3'))
    boundary.install(readonly_sqlite_paths=registered)
    target = private / 'probe/api.sock'
    binds = []

    def restrict_bind(event, args):
        if event == 'socket.bind':
            if args[0].family != socket.AF_UNIX or args[1] != str(target):
                raise PermissionError('Only exact private probe UDS may bind')
            binds.append(args[1])
        elif event == 'subprocess.Popen':
            raise PermissionError('Private API probe does not spawn other services')

    sys.addaudithook(restrict_bind)
    sys.path.insert(0, str(baseline / 'backend'))
    from job_store import create_job, get_job
    from redis import Redis
    from rq import Queue
    import math
    redis = Redis(unix_socket_path=str(private / 'redis.sock'), socket_timeout=2)
    job_id = create_job('PRIVATE-PROBE', 'v4')
    queue = Queue(os.environ['TASK_QUEUE_NAME'], connection=redis)
    rq_job = queue.enqueue_call(math.sqrt, args=(81,), job_id='analysis:' + job_id)
    before = {'job_status': get_job(job_id)['status'], 'queue_ids': queue.job_ids}
    assert before['queue_ids'] == [rq_job.id]
    import api
    if Path(api.__file__).resolve() != baseline / 'backend/api.py':
        raise RuntimeError('Wrong backend imported')
    readiness, holders = None, []
    if os.environ.get('STOCK_AGENT_PRIVATE_READONLY_PROBE') == '1':
        readiness, holders = prepare_readonly_probe(api, private, redis)
    import uvicorn
    wrapper = load('private_probe_control', ROOT / 'scripts/maintenance_probe_app.py')
    probe_dir = private / 'probe'
    probe_dir.mkdir(mode=0o700)
    with wrapper.private_listener(probe_dir) as listener:
        # Without a verified readonly readiness dependency, readyz stays 503.
        # The real baseline lifespan remains active and must complete normally.
        async def observed_original(scope, receive, send):
            async def observe_send(message):
                if message['type'] == 'lifespan.shutdown.complete':
                    after = {'job_status': get_job(job_id)['status'], 'queue_ids': queue.job_ids}
                    assert before == after
                    assert api.app.state.runtime._closed is True
                    (private / 'probe-finished.json').write_text(json.dumps({
                        'before': before, 'after': after, 'binds': binds, 'runtime_closed': True,
                        'listener_fileno': listener.fileno(), 'production_ready': False,
                        'protected_or_handover_verified': False}))
                    for connection in holders:
                        connection.close()
                    redis.close()
                await send(message)
            await api.app(scope, receive, observe_send)

        application = wrapper.ProbeOnlyASGI(observed_original, readiness_app=readiness)
        config = uvicorn.Config(application, uds=str(target), lifespan='on', loop='asyncio',
                                log_config=None, access_log=False, timeout_graceful_shutdown=5)
        server = uvicorn.Server(config)

        async def serve():
            async def observe():
                while not server.started:
                    await asyncio.sleep(.01)
                if not hasattr(api.app.state, 'runtime'):
                    raise RuntimeError('Original app lifespan did not create its runtime')
                (private / 'probe-ready.json').write_text(json.dumps({
                    'pid': os.getpid(), 'app_file': api.__file__, 'binds': binds,
                    'lifespan_runtime_created': True, 'before': before,
                    'identity_binding': 'externally verified archive; GIT_COMMIT labels that copy'}))
            observer = asyncio.create_task(observe())
            try:
                await server.serve(sockets=[listener])
            finally:
                observer.cancel()
                await asyncio.gather(observer, return_exceptions=True)

        asyncio.run(serve())
    # Installed Uvicorn restores and re-raises captured SIGTERM after completing
    # shutdown. The receipt is therefore captured at real lifespan completion,
    # not by suppressing the signal or pretending a -15 exit is zero.


if __name__ == '__main__':
    main()
