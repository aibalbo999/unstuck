"""Shared unknown-429 protection without changing provider quota state."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import pytest

from llm_congestion_store import CongestionStore


def rig():
    now = [1000.0]
    return CongestionStore(clock=lambda: now[0], jitter=lambda: 0), now


def fail(store, key, **kwargs):
    return store.operate('model', 'failure', key_hash=key, **kwargs)


def open_guard(store):
    fail(store, 'a')
    return fail(store, 'b')


def test_distinct_keys_and_window_and_normal_success():
    store, now = rig()
    fail(store, 'a')
    fail(store, 'a')
    assert store.operate('model', 'peek')['wait'] == 0
    store.operate('model', 'success')
    assert fail(store, 'b')['wait'] == 60
    assert store.operate('other-model', 'admit')['admitted']
    store, now = rig()
    fail(store, 'a')
    now[0] += 61
    assert fail(store, 'b')['wait'] == 0


def test_cooldown_one_probe_stale_completion_and_recovery():
    store, now = rig()
    opened = open_guard(store)
    assert not store.operate('model', 'admit', owner='before')['admitted']
    now[0] += 61
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: (str(i), store.operate('model', 'admit', owner=str(i))), range(8)))
    winners = [(owner, r) for owner, r in results if r['admitted']]
    assert len(winners) == 1
    owner, receipt = winners[0]
    assert receipt['probe']
    fail(store, 'c', owner=owner, generation=receipt['generation'])
    assert store.operate('model', 'peek')['wait'] == 120
    store.operate('model', 'success', owner=owner, generation=receipt['generation'])
    assert store.operate('model', 'peek')['wait'] == 120
    now[0] += 121
    receipt = store.operate('model', 'admit', owner='new')
    store.operate('model', 'success', owner='new', generation=receipt['generation'])
    assert store.operate('model', 'admit')['admitted']
    assert not store.operate('model', 'peek')['probe']
    fail(store, 'old', generation=opened['generation'])
    assert store.operate('model', 'peek')['wait'] == 0


def test_cancel_release_and_expired_lease_reject_old_owner():
    store, now = rig()
    open_guard(store)
    now[0] += 61
    first = store.operate('model', 'admit', owner='first', lease=5)
    now[0] += 6
    second = store.operate('model', 'admit', owner='second')
    assert second['admitted']
    store.operate('model', 'success', owner='first', generation=first['generation'])
    assert store.operate('model', 'peek')['wait'] == 400
    store.operate('model', 'release', owner='second', generation=second['generation'])
    assert store.operate('model', 'peek')['wait'] == 30


def test_backoff_cap_jitter_and_provider_hint():
    store, now = rig()
    assert open_guard(store)['wait'] == 60
    for delay in (120, 240, 300, 300):
        now[0] += 1000
        r = store.operate('model', 'admit', owner='probe')
        assert fail(store, 'a', owner='probe', generation=r['generation'])['wait'] == delay
    now[0] += 1000
    r = store.operate('model', 'admit', owner='probe')
    assert fail(store, 'a', owner='probe', generation=r['generation'], delay=600)['wait'] == 600
    jittered = CongestionStore(clock=lambda: 1000, jitter=lambda: 7)
    assert open_guard(jittered)['wait'] == 67


def test_redis_failure_preserves_known_wait_and_fails_closed_once():
    class Broken:
        def eval(self, *args):
            raise OSError('unavailable')
    now = [1000.0]
    store = CongestionStore(redis_client=Broken(), clock=lambda: now[0], jitter=lambda: 0)
    assert store.operate('model', 'admit', owner='x')['wait'] == 60
    now[0] += 10
    assert store.operate('model', 'peek')['wait'] == 50
    assert store.operate('healthy', 'admit')['wait'] == 60
    now[0] += 51
    assert store.operate('model', 'admit', owner='recovery')['probe']


@pytest.mark.parametrize('action', ['admit', 'peek', 'failure', 'success', 'release'])
def test_result_has_safe_fixed_schema(action):
    store, _ = rig()
    assert set(store.operate('model', action, key_hash='hash')) == {'generation', 'wait', 'probe', 'admitted'}


def test_required_shared_unavailable_initially_quarantines_only_once():
    now = [1000.0]
    store = CongestionStore(clock=lambda: now[0], jitter=lambda: 0, shared_required=True)
    assert store.operate('model', 'peek')['wait'] == 60
    now[0] += 61
    receipt = store.operate('model', 'admit', owner='recovery')
    assert receipt['admitted'] and receipt['probe']
    store.operate('model', 'success', owner='recovery', generation=receipt['generation'])
    assert store.operate('model', 'admit')['admitted']


def test_first_redis_outage_recording_failure_preserves_provider_hint():
    class Broken:
        def eval(self, *args):
            raise OSError('unavailable')
    store = CongestionStore(Broken(), clock=lambda: 1000, jitter=lambda: 0)
    assert fail(store, 'a', delay=600)['wait'] == 600


def test_stale_failure_hint_does_not_extend_outage_quarantine():
    class Broken:
        def eval(self, *args):
            raise OSError('unavailable')
    store = CongestionStore(Broken(), clock=lambda: 1000, jitter=lambda: 0)
    assert fail(store, 'a', generation=999, delay=600)['wait'] == 60


@pytest.fixture
def redis_socket(tmp_path):
    server, cli = shutil.which('redis-server'), shutil.which('redis-cli')
    if not server or not cli:
        pytest.skip('Disposable Redis binaries unavailable')
    directory = tempfile.TemporaryDirectory(prefix='sa-congestion-', dir='/tmp')
    socket = Path(directory.name) / 'redis.sock'
    process = subprocess.Popen([server, '--port', '0', '--unixsocket', str(socket),
        '--unixsocketperm', '700', '--save', '', '--appendonly', 'no', '--dir', str(tmp_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    class Client:
        def command(self, *args):
            return subprocess.check_output([cli, '-s', str(socket), '--raw', *map(str, args)], text=True).strip()

        def eval(self, *args):
            return self.command('EVAL', *args)

    client = Client()
    try:
        for _ in range(100):
            if socket.exists() and client.command('PING') == 'PONG':
                break
            if process.poll() is not None:
                pytest.fail('Disposable Redis startup failed')
            time.sleep(.01)
        else:
            pytest.fail('Disposable Redis startup timeout')
        yield client
    finally:
        process.terminate()
        process.communicate(timeout=5)
        directory.cleanup()


def expire_cooldown(client):
    """Advance only this isolated fixture's saved deadline without sleeping."""
    key = client.command('KEYS', 'stock-agent:llm:congestion:*')
    state = json.loads(client.command('GET', key))
    state.update(until_at=time.time()-1, probe_until=0, owner='')
    client.command('SET', key, json.dumps(state), 'PX', 86400000)


def test_redis_two_clients_share_distinct_keys_and_one_atomic_probe(redis_socket):
    first = CongestionStore(redis_socket, jitter=lambda: 0)
    second = CongestionStore(redis_socket, jitter=lambda: 0)
    assert fail(first, 'a')['wait'] == 0
    assert 59 <= fail(second, 'b')['wait'] <= 60
    assert 59 <= first.operate('model', 'peek')['wait'] <= 60
    expire_cooldown(redis_socket)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: (str(i), CongestionStore(redis_socket, jitter=lambda: 0).operate(
            'model', 'admit', owner=str(i))), range(8)))
    winners = [(owner, r) for owner, r in results if r['admitted']]
    assert len(winners) == 1
    owner, receipt = winners[0]
    assert receipt['probe']
    assert 119 <= fail(first, 'c', owner=owner, generation=receipt['generation'])['wait'] <= 120
    second.operate('model', 'success', owner=owner, generation=receipt['generation'])
    assert 119 <= second.operate('model', 'peek')['wait'] <= 120
    expire_cooldown(redis_socket)
    receipt = second.operate('model', 'admit', owner='recovered')
    first.operate('model', 'success', owner='recovered', generation=receipt['generation'])
    assert second.operate('model', 'admit')['admitted']
    assert 'model' not in redis_socket.command('KEYS', '*')


def test_redis_clock_translation_and_outage_preserve_longer_deadline(redis_socket):
    now = [1000.0]
    store = CongestionStore(redis_socket, clock=lambda: now[0], jitter=lambda: 0)
    fail(store, 'a', delay=600)
    assert 599 <= fail(store, 'b')['wait'] <= 600
    def broken(*args):
        raise OSError('unavailable')
    redis_socket.eval = broken
    assert 599 <= store.operate('model', 'admit', owner='blocked')['wait'] <= 600
    now[0] += 100
    assert 499 <= store.operate('model', 'peek')['wait'] <= 500


def test_redis_release_parity_and_no_normal_success_reset(redis_socket):
    store = CongestionStore(redis_socket, jitter=lambda: 0)
    fail(store, 'a')
    store.operate('model', 'success')
    assert 59 <= fail(store, 'b')['wait'] <= 60
    expire_cooldown(redis_socket)
    r = store.operate('model', 'admit', owner='cancelled')
    result = store.operate('model', 'release', owner='cancelled', generation=r['generation'])
    assert 29 <= result['wait'] <= 30


def test_redis_503_cross_worker_skip_single_probe_and_success(redis_socket, monkeypatch):
    import config
    import llm_congestion as guard
    from llm_model_circuits import ModelCircuitOpenError

    class Unavailable(RuntimeError):
        status_code = 503

    first = CongestionStore(redis_socket, jitter=lambda: 0)
    second = CongestionStore(redis_socket, jitter=lambda: 0)
    monkeypatch.setattr(config, 'LLM_CONGESTION_GUARD_ENABLED', True)
    monkeypatch.setattr(guard, '_store', first)
    with pytest.raises(Unavailable):
        with guard.provider_attempt_scope('gemini-test', 'synthetic-a'):
            raise Unavailable('busy')
    monkeypatch.setattr(guard, '_store', second)
    assert 59 <= guard.congestion_wait('gemini-test') <= 60
    with pytest.raises(ModelCircuitOpenError):
        with guard.provider_attempt_scope('gemini-test', 'synthetic-b'):
            pytest.fail('second worker bypassed shared 503 cooldown')
    expire_cooldown(redis_socket)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: (str(i), CongestionStore(redis_socket, jitter=lambda: 0).operate(
            'google:gemini-test', 'admit', owner=str(i))), range(8)))
    winners = [(owner, result) for owner, result in results if result['admitted']]
    assert len(winners) == 1 and winners[0][1]['probe']
    owner, result = winners[0]
    first.operate('google:gemini-test', 'success', owner=owner, generation=result['generation'])
    assert second.operate('google:gemini-test', 'admit', owner='next')['admitted']
    # Late completions from before the cooldown may not reopen recovered state.
    assert first.operate('google:gemini-test', 'server_failure', owner='old', generation=0)['wait'] == 0


def test_mixed_429_503_keep_provider_hint_and_recovery_backoff_separate_from_rpd():
    store, now = rig()
    assert fail(store, 'a')['wait'] == 0
    assert store.operate('model', 'server_failure', delay=600)['wait'] == 600
    now[0] += 601
    receipt = store.operate('model', 'admit', owner='recovery')
    assert fail(store, 'b', owner='recovery', generation=receipt['generation'])['wait'] == 120
    assert store.operate('healthy', 'admit')['admitted']


def test_first_redis_outage_recording_503_preserves_provider_hint():
    class Broken:
        def eval(self, *args):
            raise OSError('unavailable')
    store = CongestionStore(Broken(), clock=lambda: 1000, jitter=lambda: 0)
    assert store.operate('model', 'server_failure', delay=600)['wait'] == 600
