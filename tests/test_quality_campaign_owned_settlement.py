"""No-spawn proof and exact original-reservation settlement, all private."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from quality_campaign_budget import BudgetDenied
from test_quality_campaign_budget import active, RESERVATION


def test_reserved_job_settlement_is_conditional_and_never_refunds(tmp_path):
    now = [1000.0]
    ledger = active(tmp_path, clock=lambda: now[0], limits={'campaign': {'job_seconds': 1}})
    ledger.reserve_attempt('used', 'job', **RESERVATION)
    before = ledger.snapshot()
    original = copy.deepcopy(before['jobs']['job'])
    wrong = {**original, 'deadline_ms': original['deadline_ms'] + 1}
    now[0] += 2
    with pytest.raises(BudgetDenied, match='reservation'):
        ledger.finish_job('job', status='failed', expected_job=wrong, settlement_evidence_sha256='f' * 64)
    assert ledger.snapshot()['jobs']['job'] == original
    ledger.finish_job('job', status='failed', expected_job=original, settlement_evidence_sha256='f' * 64)
    after = ledger.snapshot()
    assert after['jobs']['job'] == {**original, 'status': 'failed', 'settlement_evidence_sha256': 'f' * 64}
    assert after['blocked'] == 'deadline exceeded'
    assert after['attempts'] == before['attempts'] and after['spent'] == before['spent']
    assert after['batches']['batch']['ended_ms'] is None and after['stages']['S1'] == 'open'
    with pytest.raises(BudgetDenied):
        ledger.finish_job('job', status='failed', expected_job=original, settlement_evidence_sha256='f' * 64)


@pytest.mark.parametrize('operation', [
    "subprocess.run([sys.executable, '-I', '-c', 'pass'])",
    "subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'])",
    'os.fork()',
])
def test_new_owned_lane_never_creates_descendants_even_for_git(tmp_path, operation):
    # Install the real audit hook in a disposable interpreter, never pytest.
    code = '''
import json, os, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
from quality_campaign_safety import install_owned_process_boundary, ReplayAbort
observe = install_owned_process_boundary()
before = observe()
try:
    exec(sys.argv[3])
except ReplayAbort:
    denied = True
else:
    denied = False
print(json.dumps({'before': before, 'after': observe(), 'denied': denied}))
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(tmp_path),
        str(Path(__file__).parent), operation], env={}, capture_output=True, text=True, timeout=3)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence['denied'] is True
    assert evidence['before'] == {'policy': 'deny-python-process-creation-v1', 'denied': 0}
    assert evidence['after'] == {'policy': 'deny-python-process-creation-v1', 'denied': 1}


@pytest.mark.parametrize('method', ['spawn', 'fork', 'forkserver'])
@pytest.mark.parametrize('import_before_guard', [True, False])
def test_owned_boundary_blocks_public_multiprocessing(method, import_before_guard):
    # Exercise the public API: CPython 3.13 spawn uses an unaudited fork_exec.
    # If this regresses, all actually-created private children must still exit.
    code = '''
import json, os, sys
sys.path.insert(0, sys.argv[1])
if sys.argv[3] == 'True':
    import multiprocessing
from quality_campaign_safety import install_owned_process_boundary, ReplayAbort
observe = install_owned_process_boundary()
import multiprocessing
process = multiprocessing.get_context(sys.argv[2]).Process(target=os.getpid)
try:
    process.start()
except ReplayAbort:
    blocked = True
else:
    blocked = False
    process.join(3)
    assert not process.is_alive(), 'Private test child did not exit'
print(json.dumps({'blocked': blocked, 'scope': observe(), 'child_pid': process.pid}))
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code,
        str(Path(__file__).parent), method, str(import_before_guard)],
        env={'PYTHONDONTWRITEBYTECODE': '1'}, capture_output=True, text=True, timeout=6)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence == {'blocked': True, 'child_pid': None,
        'scope': {'policy': 'deny-python-process-creation-v1', 'denied': 1}}
