"""Exercise the real cooldown Lua against a disposable Unix-socket Redis."""
from concurrent.futures import ThreadPoolExecutor
import shutil
import subprocess
import time
import tempfile
from pathlib import Path

import pytest

from shared_runtime_guards import RedisFixedWindowRateLimiter


@pytest.fixture
def redis_socket(tmp_path):
    server, cli = shutil.which('redis-server'), shutil.which('redis-cli')
    if not server or not cli:
        pytest.skip('Disposable Redis binaries unavailable')
    socket_directory = tempfile.TemporaryDirectory(prefix='sa-redis-', dir='/tmp')
    socket = Path(socket_directory.name) / 'redis.sock'
    process = subprocess.Popen([server, '--port', '0', '--unixsocket', str(socket),
                                '--unixsocketperm', '700', '--save', '', '--appendonly', 'no',
                                '--dir', str(tmp_path)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    class Client:
        def command(self, *args):
            return subprocess.check_output([cli, '-s', str(socket), '--raw', *map(str, args)], text=True).strip()

        def eval(self, *args):
            return int(self.command('EVAL', *args))

        def pttl(self, key):
            return int(self.command('PTTL', key))

        def set(self, key, value, *, px):
            return self.command('SET', key, value, 'PX', px)

    client = Client()
    try:
        for _ in range(100):
            if socket.exists() and client.command('PING') == 'PONG':
                break
            if process.poll() is not None:
                pytest.fail('Disposable Redis failed to start')
            time.sleep(0.01)
        else:
            pytest.fail('Disposable Redis startup timeout')
        yield client
    finally:
        process.terminate()
        process.communicate(timeout=5)
        socket_directory.cleanup()


def test_shorter_later_penalty_never_overwrites_longer_retry_after(redis_socket):
    first = RedisFixedWindowRateLimiter(redis_socket, namespace='isolated-cooldown')
    second = RedisFixedWindowRateLimiter(redis_socket, namespace='isolated-cooldown')
    first.penalize('key-a', 'model', 120)
    second.penalize('key-a', 'model', 1)
    assert 119 <= second.reserve('key-a', 'model', rpm_limit=100) <= 120
    assert second.reserve('key-b', 'model', rpm_limit=100) == 0
    assert second.reserve('key-a', 'other-model', rpm_limit=100) == 0
    assert second.rpd_disabled_wait('key-a', 'model') == 0
    keys = redis_socket.command('KEYS', '*').splitlines()
    assert all('key-a' not in key and 'model' not in key for key in keys)


def test_concurrent_penalties_keep_longest_deadline(redis_socket):
    delays = [1, 10, 120, 2, 60, 3, 90, 4]
    def penalize(delay):
        RedisFixedWindowRateLimiter(redis_socket, namespace='isolated-cooldown').penalize('key-a', 'model', delay)
    with ThreadPoolExecutor(max_workers=len(delays)) as pool:
        list(pool.map(penalize, delays))
    reader = RedisFixedWindowRateLimiter(redis_socket, namespace='isolated-cooldown')
    assert 119 <= reader.reserve('key-a', 'model', rpm_limit=100) <= 120


def test_successful_penalty_survives_subsequent_redis_failure(redis_socket):
    limiter = RedisFixedWindowRateLimiter(redis_socket, namespace='isolated-cooldown')
    limiter.penalize('key-a', 'model', 120)
    def unavailable(*args):
        raise RuntimeError('Redis unavailable')
    redis_socket.eval = unavailable
    assert 119 <= limiter.reserve('key-a', 'model', rpm_limit=100) <= 120
