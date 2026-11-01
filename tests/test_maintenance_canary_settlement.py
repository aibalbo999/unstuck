"""Private enrollment → claim → real owned normal job → guarded RQ settlement."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('case', ['published_v1', 'published_v2', 'published_v3', 'published_v4',
    'blocked', 'stopped', 'cleanup_error', 'missing_cleanup', 'wrong_pid', 'wrong_manifest',
    'changed_outcome', 'changed_artifact', 'live_process', 'race', 'lost_reply', 'cancel_before_exec',
    'cancel_after_exec', 'cancel_after_readback', 'readback_mismatch', 'runtime_error', 'file_drift_after_exec',
    'replay', 'wrong_intermediate', 'changed_payload', 'retry_nonzero', 'mutated_process_binding',
    'pending_generator', 'missing_generator_observation'])
def test_canary_settlement_requires_owned_execution_evidence(case, request):
    from test_maintenance_rq_private_integration import private_redis
    def record(label, value):
        request.node.user_properties.append((label, json.dumps(value, sort_keys=True)))
    with private_redis(record) as (root, sock):
        output = root / 'settlement-evidence.json'
        process = subprocess.Popen([sys.executable, '-I', '-B',
            str(Path(__file__).with_name('test_maintenance_canary_settlement_child.py')), str(output), case],
            env={'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
                 'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(sock)},
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=55)
            assert process.returncode == 0, (stdout + stderr).decode(errors='replace')[-6000:]
            record('private_owned_canary_settlement', json.loads(output.read_text()))
        finally:
            # The finite offline child request expires on its own. Never use a
            # test cleanup SIGKILL to claim formal warm-stop compatibility.
            if process.poll() is None:
                process.communicate(timeout=30)


@pytest.mark.parametrize('case', ['four_modes', 'stop_after_second'])
def test_one_enrollment_advances_in_order_without_replaying_prior_jobs(case, request):
    from test_maintenance_rq_private_integration import private_redis
    def record(label, value):
        request.node.user_properties.append((label, json.dumps(value, sort_keys=True)))
    with private_redis(record) as (root, sock):
        output = root / 'roster-evidence.json'
        process = subprocess.Popen([sys.executable, '-I', '-B',
            str(Path(__file__).with_name('test_maintenance_canary_roster_child.py')), str(output), case],
            env={'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
                 'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(sock)},
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=90)
            assert process.returncode == 0, (stdout + stderr).decode(errors='replace')[-6000:]
            record('private_ordered_roster', json.loads(output.read_text()))
        finally:
            if process.poll() is None:
                process.communicate(timeout=30)
