"""Explicit baseline archive required; never start a formal or current checkout."""
import _socket
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import signal
import subprocess
import sys
import time

import pytest

from test_maintenance_rq_private_integration import private_redis, cli_environment, record_evidence, private_test_base


ROOT = Path(__file__).resolve().parents[1]
REVISION = '758242290e795146520f58f68ffa113cac35e52c'
CHILD = Path(__file__).with_name('test_maintenance_legacy_probe_child.py')


def owned_process_adapter():
    path = ROOT / 'scripts/maintenance_owned_process.py'
    spec = importlib.util.spec_from_file_location('legacy_probe_owned_process', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    sources = {str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest() for file in
               (path, ROOT / 'backend/maintenance_state.py')}
    return value, hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()


def verified_archive():
    value = os.environ.get('STOCK_AGENT_LEGACY_PROBE_BASELINE')
    if not value:
        pytest.skip('Exact private 75824229 git archive not supplied')
    root = Path(value)
    assert root.is_absolute() and root.resolve() == root
    assert root.is_relative_to(private_test_base())
    assert not (root / 'backend/.env').exists() and not (root / '.git').exists()
    result = subprocess.run(['git', 'ls-tree', '-rz', REVISION, '--', 'backend'],
                            cwd=ROOT, capture_output=True, check=True)
    rows = []
    expected = set()
    for item in result.stdout.split(b'\0'):
        if not item: continue
        info, name = item.split(b'\t', 1)
        mode, kind, object_id = info.split()
        assert kind == b'blob' and mode in (b'100644', b'100755')
        relative = name.decode()
        path = root / relative
        assert path.resolve() == path and path.is_file()
        raw = path.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        assert actual == object_id.decode(), relative
        rows.append((relative, actual)); expected.add(relative)
    assert {str(path.relative_to(root)) for path in (root / 'backend').rglob('*') if path.is_file()} == expected
    return root, hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest(), len(rows)


def request(sock_path, path, method='GET', body=b''):
    # Exact private AF_UNIX only; leave the runner's general socket ban intact.
    assert sock_path.name == 'api.sock' and sock_path.parent.name == 'probe'
    assert sock_path.resolve().is_relative_to(private_test_base())
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        _socket.socket.connect(client, str(sock_path))
        message = (f'{method} {path} HTTP/1.1\r\nHost: private-probe.invalid\r\n'
                   f'Connection: close\r\nContent-Length: {len(body)}\r\n\r\n').encode() + body
        client.sendall(message)
        chunks = []
        while True:
            chunk = client.recv(65536)
            if not chunk: break
            chunks.append(chunk)
        head, content = b''.join(chunks).split(b'\r\n\r\n', 1)
        return int(head.split(b' ', 2)[1]), content


@pytest.mark.parametrize('readonly_probe', [False, True])
def test_original_7582_app_lifespan_runs_only_over_private_uds_and_preserves_general_job(record_evidence, readonly_probe):
    baseline, digest, count = verified_archive()
    with private_redis(record_evidence) as (root, sock):
        env = cli_environment(root, sock)
        env.pop('PYTHONPATH', None)
        env.update(STOCK_AGENT_LEGACY_PROBE_BASELINE=str(baseline), GIT_COMMIT=REVISION,
                   GIT_DIRTY='false', PYTHONPYCACHEPREFIX=str(root / 'bytecode'),
                   REPORT_STORAGE_BACKEND='local', CACHE_BACKEND='sqlite',
                   STOCK_AGENT_PRIVATE_READONLY_PROBE='1' if readonly_probe else '0',
                   YFINANCE_CACHE_DIR=str(root / 'yfinance'))
        adapter, control_digest = owned_process_adapter()
        owner_namespace = root / 'probe-owner'
        owner_namespace.mkdir(mode=0o700)
        owner = adapter.OwnedProcess(owner_namespace, {'operation_id': 'legacy-private-probe',
            'backend_revision': REVISION, 'control_sha256': control_digest})
        process = None
        try:
            owner.start([sys.executable, '-I', '-B', str(CHILD)], cwd=root, env=env)
            process = owner.process
            deadline = time.monotonic() + 30
            ready = root / 'probe-ready.json'
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            assert ready.exists(), 'Original private API did not complete lifespan/startup'
            receipt = json.loads(ready.read_text())
            endpoint = root / 'probe/api.sock'
            results = {}
            for path in ('/healthz', '/api/runtime-identity', '/readyz', '/api/analyze/2330.TW', '/api/watchlist'):
                results[path] = request(endpoint, path)
            assert results['/healthz'] == (200, b'{"status":"ok"}')
            identity = json.loads(results['/api/runtime-identity'][1])
            assert identity['commit'] == REVISION and identity['dirty'] is False
            assert [results[path][0] for path in ('/api/analyze/2330.TW', '/api/watchlist')] == [503] * 2
            if readonly_probe:
                payload = json.loads(results['/readyz'][1])
                record_evidence('readonly_probe_http_payload', payload)
                assert results['/readyz'][0] == 200, payload['probe_details'].get('storage')
                assert payload['schema_version'] == 'stock-agent.maintenance-readonly-probe.v1'
                assert payload['status'] == 'probe_pass' and payload['production_ready'] is False
                probe_receipt = json.loads((root / 'readonly-probe.json').read_text())
                assert all(probe_receipt[key] is True for key in (
                    'db_wal_unchanged', 'sqlite_file_set_unchanged',
                    'expired_registry_member_preserved', 'ordinary_queue_unchanged'))
                record_evidence('actual_legacy_readonly_probe', probe_receipt)
            else:
                assert results['/readyz'][0] == 503
            assert request(endpoint, '/healthz', 'POST')[0] == 503
            assert request(endpoint, '/healthz', body=b'run=true')[0] == 503
            assert receipt['lifespan_runtime_created'] is True
            assert receipt['binds'] == [str(endpoint)]
            owner.request_stop()
            process_receipt = owner.wait_for_exit(10)
            assert process_receipt['process_exited'] is True
            assert process.returncode in (0, -signal.SIGTERM), process_receipt
            final = json.loads((root / 'probe-finished.json').read_text())
            assert final['before'] == final['after'] and final['runtime_closed'] is True
            assert final['listener_fileno'] == -1
            assert final['protected_or_handover_verified'] is False
            journal = adapter.read_process_record(owner_namespace)
            assert journal['stop_requested'] is True and journal['signal_call_returned'] is True
            assert journal['process_exited'] is True and journal['cleanup_verified'] is False
            assert journal['handover_verified'] is False and journal['resume_authorized'] is False
            record_evidence('legacy_probe', {'baseline': REVISION, 'archive_files': count,
                'archive_digest': digest, 'original_lifespan': receipt, 'final': final,
                'statuses': {path: result[0] for path, result in results.items()},
                'returncode': process.returncode, 'owned_process': journal,
                'owner_control_digest': control_digest})
        finally:
            try:
                if owner.process is not None:
                    owner.request_stop()  # Existing intent prevents a second TERM.
                    assert owner.wait_for_exit(10)['process_exited'] is True
            finally:
                owner.close()
        after, after_digest, after_count = verified_archive()
        assert (after, after_digest, after_count) == (baseline, digest, count)
