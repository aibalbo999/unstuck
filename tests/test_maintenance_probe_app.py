"""A legacy readiness surface must not expose arbitrary old API operations."""
import asyncio
import _socket
from functools import lru_cache
import importlib.util
import os
from pathlib import Path
import socket
import stat
import tempfile

import pytest


SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'maintenance_probe_app.py'


@lru_cache(maxsize=1)
def module():
    spec = importlib.util.spec_from_file_location('maintenance_probe_under_test', SOURCE)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def request(path='/healthz', **changes):
    value = {'type': 'http', 'method': 'GET', 'path': path,
             'raw_path': path.encode(), 'query_string': b'', 'root_path': '', 'headers': []}
    value.update(changes)
    return value


def exercise(scope, *, body=b'', readiness=True):
    seen, sent = [], []

    async def original(scope, receive, send):
        seen.append(('original', scope['path'], await receive()))
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'original'})

    async def readonly(scope, receive, send):
        seen.append(('readonly', scope['path'], await receive()))
        await send({'type': 'http.response.start', 'status': 503, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'not-ready'})

    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': False}

    async def send(value):
        sent.append(value)

    wrapper = module().ProbeOnlyASGI(original, readiness_app=readonly if readiness else None)
    asyncio.run(wrapper(scope, receive, send))
    return seen, sent


@pytest.mark.parametrize('path', ['/healthz', '/api/runtime-identity'])
def test_only_original_liveness_and_identity_reach_baseline_app(path):
    seen, sent = exercise(request(path))
    assert seen == [('original', path, {'type': 'http.request', 'body': b'', 'more_body': False})]
    assert sent[0]['status'] == 200


def test_readyz_must_use_separate_readonly_handler_and_preserve_failure_status():
    seen, sent = exercise(request('/readyz'))
    assert seen[0][:2] == ('readonly', '/readyz')
    assert sent[0]['status'] == 503
    assert sent[-1]['body'] == b'not-ready'


def test_missing_readonly_handler_does_not_call_mutating_baseline_readyz():
    seen, sent = exercise(request('/readyz'), readiness=False)
    assert seen == [] and sent[0]['status'] == 503


@pytest.mark.parametrize('scope', [
    request('/api/analyze/2330.TW'), request('/api/watchlist'), request('/docs'),
    request(method='POST'), request(method='HEAD'), request(method='OPTIONS'),
    request(query_string=b'refresh=true'), request(raw_path=b'/%68ealthz'),
    request(root_path='/mounted'), request('/healthz/'),
    request(headers=[(b'content-length', b'1')]),
    request(headers=[(b'transfer-encoding', b'chunked')]),
    request(headers=[(b'content-length', b'0'), (b'content-length', b'0')]),
])
def test_noncanonical_or_nonprobe_requests_never_reach_old_app(scope):
    seen, sent = exercise(scope)
    assert seen == [] and sent[0]['status'] == 503


def test_get_with_undeclared_body_is_rejected_before_old_app():
    seen, sent = exercise(request(), body=b'run=true')
    assert seen == [] and sent[0]['status'] == 503


def test_websocket_denied_without_calling_old_app():
    seen, sent = exercise({'type': 'websocket', 'path': '/healthz'})
    assert seen == [] and sent == [{'type': 'websocket.close', 'code': 1008}]


def test_original_lifespan_is_not_silently_skipped():
    seen = []

    async def original(scope, receive, send):
        seen.append(scope['type'])
        assert await receive() == {'type': 'lifespan.startup'}
        await send({'type': 'lifespan.startup.complete'})

    async def receive():
        return {'type': 'lifespan.startup'}

    async def send(value):
        seen.append(value['type'])

    asyncio.run(module().ProbeOnlyASGI(original)({'type': 'lifespan'}, receive, send))
    assert seen == ['lifespan', 'lifespan.startup.complete']


def test_listener_is_only_private_unix_and_close_preserves_socket_marker(tmp_path):
    from test_maintenance_rq_private_integration import private_test_base
    with tempfile.TemporaryDirectory(prefix='p-', dir=private_test_base()) as directory:
        _check_listener_private_namespace(Path(directory))


def _check_listener_private_namespace(tmp_path):
    root = tmp_path / 'probe'; root.mkdir(mode=0o700)
    with module().private_listener(root) as listener:
        assert listener.family == socket.AF_UNIX
        assert listener.getsockname() == str(root / 'api.sock')
        # macOS AF_UNIX has no SO_ACCEPTCONN. Prove listen with a real exchange;
        # the runner's general network ban stays in place. Only this exact
        # owned fixture socket uses the base-class connect operation.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            _socket.socket.connect(client, str(root / 'api.sock'))
            accepted, _ = listener.accept()
            with accepted:
                client.sendall(b'private-probe')
                assert accepted.recv(64) == b'private-probe'
        info = (root / 'api.sock').lstat()
        assert stat.S_ISSOCK(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
        assert info.st_uid == os.getuid()
    assert listener.fileno() == -1
    assert (root / 'api.sock').lstat().st_ino == info.st_ino
    with pytest.raises(module().ProbeError):
        with module().private_listener(root):
            pytest.fail('Never overwrite a previous listener marker')


@pytest.mark.parametrize('kind', ['public', 'missing', 'symlink', 'occupied'])
def test_unsafe_listener_namespace_or_existing_path_fails_closed(tmp_path, kind):
    root = tmp_path / 'probe'
    if kind != 'missing': root.mkdir(mode=0o700)
    if kind == 'public': root.chmod(0o755)
    if kind == 'occupied': (root / 'api.sock').write_bytes(b'preserve')
    if kind == 'symlink':
        alias = tmp_path / 'alias'; alias.symlink_to(root, target_is_directory=True); root = alias
    with pytest.raises((module().ProbeError, OSError)):
        with module().private_listener(root):
            pytest.fail('Unsafe listener was admitted')
    if kind == 'occupied': assert (root / 'api.sock').read_bytes() == b'preserve'
