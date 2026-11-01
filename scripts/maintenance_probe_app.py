"""Version-neutral, private readiness surface for a future maintenance controller.

This module does not import a backend, load settings, start a server, grant a
protected state, or authorize rollback. The controller must verify legacy drain,
code/runtime identities and environment before importing its chosen ASGI app.
The original app's lifespan is NOT read-only and is deliberately not suppressed.
Legacy /readyz is also mutating: a separately verified readiness handler is
required. A private listener plus this request filter is not an OS sandbox.
"""
import asyncio
from contextlib import contextmanager
import os
from pathlib import Path
import socket
import stat


class ProbeError(RuntimeError):
    pass


class ProbeOnlyASGI:
    """Only exact empty-body probes; never delegate the legacy readyz route.

    No app/request headers or exception messages are returned on rejection.
    A missing read-only handler is unavailable, not an excuse to call the old
    storage-initializing and RQ-cleaning readiness endpoint.
    """

    def __init__(self, app, *, readiness_app=None):
        self.app = app
        self.readiness_app = readiness_app

    async def _deny(self, send):
        body = b'{"status":"maintenance_probe_only"}'
        await send({'type': 'http.response.start', 'status': 503,
                    'headers': [(b'content-type', b'application/json'),
                                (b'cache-control', b'no-store'),
                                (b'content-length', str(len(body)).encode())]})
        await send({'type': 'http.response.body', 'body': body})

    async def __call__(self, scope, receive, send):
        kind = scope.get('type')
        if kind == 'lifespan':
            return await self.app(scope, receive, send)
        if kind == 'websocket':
            return await send({'type': 'websocket.close', 'code': 1008})
        if kind != 'http':
            raise ProbeError('Unsupported probe scope')
        path = scope.get('path')
        if (scope.get('method') != 'GET'
                or path not in ('/healthz', '/readyz', '/api/runtime-identity')
                or scope.get('raw_path') != path.encode('ascii')
                or scope.get('query_string') != b'' or scope.get('root_path', '') != ''):
            return await self._deny(send)
        lengths = []
        for name, value in scope.get('headers', []):
            if name.lower() == b'transfer-encoding':
                return await self._deny(send)
            if name.lower() == b'content-length':
                lengths.append(value)
        if lengths not in ([], [b'0']):
            return await self._deny(send)
        target = self.readiness_app if path == '/readyz' else self.app
        if target is None:
            return await self._deny(send)
        try:
            first = await asyncio.wait_for(receive(), timeout=1.0)
        except TimeoutError:
            return await self._deny(send)
        if first.get('type') == 'http.disconnect':
            return
        if (first.get('type') != 'http.request' or first.get('body', b'') != b''
                or first.get('more_body', False)):
            return await self._deny(send)
        pending = True

        async def replay_receive():
            nonlocal pending
            if pending:
                pending = False
                return first
            return await receive()

        return await target(scope, replay_receive, send)


def _directory_identity(fd):
    info = os.fstat(fd)
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.getuid()):
        raise ProbeError('Private owned 0700 probe directory required')
    return info.st_dev, info.st_ino


@contextmanager
def private_listener(namespace):
    """Bind only a new AF_UNIX socket in an existing exact private namespace.

    The controller passes the returned socket explicitly to its server; this
    function never binds TCP or runs a process. Close retains the socket marker,
    so crashes/re-entry cannot silently overwrite another listener. No unlink,
    chmod of existing user objects, implicit mkdir or stale-socket cleanup.
    Directory drift is rejected; this is not protection against a malicious
    same-UID process with control of the namespace's parent.
    """
    root = Path(namespace)
    if not root.is_absolute() or root.resolve(strict=True) != root:
        raise ProbeError('Exact nonsymlink probe namespace required')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    listener = None
    try:
        identity = _directory_identity(fd)

        def verify():
            named = root.lstat()
            if (_directory_identity(fd) != identity or (named.st_dev, named.st_ino) != identity
                    or not stat.S_ISDIR(named.st_mode)):
                raise ProbeError('Probe directory identity changed')

        verify()
        try:
            os.stat('api.sock', dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProbeError('Probe listener path already exists')
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.set_inheritable(False)
        listener.bind(str(root / 'api.sock'))
        verify()
        info = os.stat('api.sock', dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise ProbeError('Probe socket identity mismatch')
        os.chmod('api.sock', 0o600, dir_fd=fd, follow_symlinks=False)
        verified = os.stat('api.sock', dir_fd=fd, follow_symlinks=False)
        if ((info.st_dev, info.st_ino) != (verified.st_dev, verified.st_ino)
                or stat.S_IMODE(verified.st_mode) != 0o600):
            raise ProbeError('Probe socket identity changed')
        listener.listen(16)
        verify()
        yield listener
    finally:
        if listener is not None:
            listener.close()
        os.close(fd)
