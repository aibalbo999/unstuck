"""Real private Redis and normal child; model/source/billing leaves are fixtures."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('mode,case', [(mode, case) for mode in ('v1', 'v2', 'v3', 'v4')
                                     for case in ('published', 'graph_blocked')]
    + [('v4', case) for case in ('downgrade_helper', 'downgrade_dispatch', 'timeout_mismatch',
                               'delivery_failure', 'control_drift', 'warm_stop', 'replay', 'blocked_ledger',
                               'expired_cleanup', 'deadline_stop', 'rq_lost_ack', 'rq_cancelled_ack',
                               'budget_lost_ack', 'ack_receipt_drift', 'scope_missing', 'scope_boolean',
                               'identity_missing', 'identity_boolean', 'identity_hash')])
def test_claimed_canary_uses_original_parent_admission_without_watchdog_file(mode, case, request):
    from test_maintenance_rq_private_integration import private_redis
    def record(label, value):
        request.node.user_properties.append((label, json.dumps(value, sort_keys=True)))
    with private_redis(record) as (root, sock):
        output = root / 'dispatch-evidence.json'
        child = subprocess.Popen([sys.executable, '-I', '-B',
            str(Path(__file__).with_name('test_maintenance_canary_dispatch_child.py')), str(output), mode, case],
            env={'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
                 'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(sock)},
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = child.communicate(timeout=55)
            assert child.returncode == 0, (stdout + stderr).decode(errors='replace')[-6000:]
            record('private_original_parent_dispatch', json.loads(output.read_text()))
        finally:
            if child.poll() is None: child.communicate(timeout=30)
