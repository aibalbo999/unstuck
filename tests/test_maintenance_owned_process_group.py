"""Original owned groups: observe kernel absence, never signal/adopt descendants."""
import inspect
import json
import os
import sys
import time

import pytest
from test_maintenance_owned_process import binding, module, wait_path


def start_owned(controller, code, root):
    options = {'owned_session': True} if 'owned_session' in inspect.signature(controller.start).parameters else {}
    controller.start([sys.executable, '-I', '-B', '-c', code, str(root)], env={}, cwd=root, **options)


def test_owned_canary_group_is_not_the_controller_or_any_ordinary_group(tmp_path):
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    controller = module().OwnedProcess(namespace, binding())
    try:
        start_owned(controller, '''
import json, os, sys
from pathlib import Path
Path(sys.argv[1], 'identity.json').write_text(json.dumps({'pid': os.getpid(), 'pgid': os.getpgrp(), 'sid': os.getsid(0)}))
''', tmp_path)
        state = controller.wait_for_exit(5)
        identity = json.loads((tmp_path / 'identity.json').read_text())
        assert identity['pid'] == identity['pgid'] == identity['sid'], identity
        assert identity['pgid'] != os.getpgrp()
        assert state['owned_session'] is True and state['process_group_id'] == identity['pgid']
        proof = controller.observe_process_group()
        assert proof['process_group_absence_verified'] is True
        assert proof['descendant_settlement_verified'] is proof['handover_verified'] is False
        assert controller.observe_process_group()['journal_sha256'] == proof['journal_sha256']
    finally:
        if controller.process is not None: controller.process.wait(timeout=5)
        controller.close()


def test_leader_exit_does_not_certify_a_live_descendant_is_gone(tmp_path):
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    controller = module().OwnedProcess(namespace, binding())
    try:
        start_owned(controller, r'''
import os, subprocess, sys, time
from pathlib import Path
root = Path(sys.argv[1])
child = subprocess.Popen([sys.executable, '-I', '-B', '-c',
    "import sys,time; from pathlib import Path; p=Path(sys.argv[1]); (p/'descendant-ready').touch(); end=time.monotonic()+8; exec(\"while not (p/'release-descendant').exists() and time.monotonic()<end: time.sleep(.01)\"); (p/'descendant-done').touch()", str(root)], env={})
end = time.monotonic() + 3
while not (root / 'descendant-ready').exists() and time.monotonic() < end: time.sleep(.01)
assert (root / 'descendant-ready').exists()
''', tmp_path)
        assert controller.wait_for_exit(5)['process_exited'] is True
        proof = controller.observe_process_group()
        assert proof['process_group_absence_verified'] is False, proof
        assert proof['descendant_settlement_verified'] is False
        (tmp_path / 'release-descendant').touch()
        end = time.monotonic() + 5
        while time.monotonic() < end:
            proof = controller.observe_process_group()
            if proof['process_group_absence_verified']: break
            time.sleep(.01)
        assert (tmp_path / 'descendant-done').exists()
        assert proof['process_group_absence_verified'] is True, proof
    finally:
        (tmp_path / 'release-descendant').touch()
        if controller.process is not None: controller.process.wait(timeout=5)
        controller.close()


def test_legacy_unowned_group_cannot_be_probed_as_exclusive(tmp_path):
    adapter = module()
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    controller = adapter.OwnedProcess(namespace, binding())
    try:
        controller.start([sys.executable, '-I', '-B', '-c', 'pass'], env={}, cwd=tmp_path)
        controller.wait_for_exit(5)
        with pytest.raises(adapter.ProcessUnavailable): controller.observe_process_group()
    finally:
        if controller.process is not None: controller.process.wait(timeout=5)
        controller.close()
