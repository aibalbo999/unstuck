"""Private filesystem/process checks; never signals or formal runtime writes."""

import asyncio
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import maintenance_guard as guard


def plan():
    return {'campaign_id': 'private-campaign', 'old_revision': 'a' * 40,
            'new_revision': 'b' * 40, 'control_sha256': 'c' * 64, 'queue_name': 'canary.private',
            'canaries': [{'mode': f'v{i}', 'job_id': f'job-{i}', 'manifest_sha256': 'd' * 64}
                        for i in range(1, 5)]}


def test_uninitialized_admission_and_read_fail_closed(tmp_path):
    root = tmp_path / 'maintenance'
    with pytest.raises(guard.MaintenanceUnavailable):
        guard.read_state(root)
    with pytest.raises(guard.MaintenanceUnavailable):
        with guard.admission(root):
            pytest.fail('missing gate admitted')
    assert not root.exists()


def test_explicit_initialization_persists_private_normal_namespace(tmp_path):
    root = tmp_path / 'maintenance'
    state = guard.initialize(root)
    assert state['phase'] == 'normal'
    assert guard.read_state(root) == state
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE((root / 'state.json').stat().st_mode) == 0o600
    with guard.admission(root):
        assert guard.read_state(root)['phase'] == 'normal'
    assert guard.initialize(root) == state


def test_arm_blocks_new_owner_before_drain_but_nested_owner_can_finish(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    with guard.admission(root) as lease:
        assert guard.arm(root, plan())['phase'] == 'arming'
        def other_owner():
            with pytest.raises(guard.MaintenanceBlocked):
                with guard.admission(root):
                    pytest.fail('arming admitted new owner')
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(other_owner).result(timeout=2)
        assert guard.wait_drained(root, 0) is False
        assert guard.read_state(root)['phase'] == 'arming'
        with guard.admission(root) as nested:
            assert nested is lease and nested.fileno() >= 0
    assert guard.wait_drained(root, 0) is True
    assert guard.read_state(root)['phase'] == 'cooperatively_drained'
    with pytest.raises(guard.MaintenanceBlocked):
        with guard.admission(root): pass


def test_armed_reopen_and_repeat_initialize_do_not_reset_or_replace_plan(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    registered = plan()
    armed = guard.arm(root, registered)
    registered['campaign_id'] = 'another-campaign'
    assert guard.read_state(root) == armed
    assert guard.initialize(root) == armed
    assert guard.arm(root, plan()) == armed
    with pytest.raises(guard.MaintenanceError):
        guard.arm(root, registered)
    assert guard.read_state(root) == armed


def test_admitted_business_exception_is_not_reclassified_as_guard_failure(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    original = ValueError('business validation')
    with pytest.raises(ValueError) as error:
        with guard.admission(root):
            raise original
    assert error.value is original


def test_child_async_task_cannot_inherit_parent_admission(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    async def scenario():
        with guard.admission(root):
            guard.arm(root, plan())
            with guard.admission(root): pass
            async def child():
                with pytest.raises(guard.MaintenanceBlocked):
                    with guard.admission(root): pytest.fail('child borrowed parent lease')
            await asyncio.create_task(child())
    asyncio.run(scenario())
    assert guard.wait_drained(root, 0)


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'oversize', 'symlink', 'fifo',
    'state_mode', 'root_mode', 'lock_mode', 'lock_inode', 'hardlink'])
def test_missing_corrupt_unsafe_state_never_reinitializes_normal(tmp_path, mutation):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    state = root / 'state.json'
    if mutation in ('missing', 'symlink', 'fifo'):
        state.unlink()
    if mutation == 'duplicate':
        state.write_text('{"phase":"normal",' + state.read_text()[1:])
    elif mutation == 'oversize': state.write_bytes(b' ' * 32769)
    elif mutation == 'symlink':
        target = tmp_path / 'outside'; target.write_text('untouched'); state.symlink_to(target)
    elif mutation == 'fifo': os.mkfifo(state, 0o600)
    elif mutation == 'state_mode': state.chmod(0o644)
    elif mutation == 'root_mode': root.chmod(0o755)
    elif mutation == 'lock_mode': (root / 'admission.lock').chmod(0o644)
    elif mutation == 'lock_inode':
        (root / 'admission.lock').rename(root / 'old.lock')
        (root / 'admission.lock').touch(mode=0o600)
    elif mutation == 'hardlink': os.link(state, root / 'extra-link')
    for operation in (lambda: guard.read_state(root), lambda: guard.initialize(root)):
        with pytest.raises(guard.MaintenanceUnavailable): operation()
    with pytest.raises(guard.MaintenanceUnavailable):
        with guard.admission(root): pytest.fail('invalid state admitted')
    if mutation == 'symlink': assert target.read_text() == 'untouched'


def test_owner_ancestor_and_namespace_replacement_are_rejected(tmp_path, monkeypatch):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    with monkeypatch.context() as patch:
        patch.setattr(guard.os, 'geteuid', lambda: root.stat().st_uid + 1)
        with pytest.raises(guard.MaintenanceUnavailable): guard.read_state(root)
    alias = tmp_path / 'alias'; alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(guard.MaintenanceUnavailable): guard.read_state(alias / 'maintenance')
    with guard.admission(root):
        saved = tmp_path / 'saved'; root.rename(saved); shutil.copytree(saved, root)
        with pytest.raises(guard.MaintenanceUnavailable):
            with guard.admission(root): pytest.fail('namespace replaced inside active lease')
    with pytest.raises(guard.MaintenanceUnavailable): guard.read_state(root)


@pytest.mark.parametrize('mutation', ['secret', 'missing', 'old_hash', 'duplicate_mode', 'duplicate_job'])
def test_plan_closed_schema_never_stores_extra_body_or_changes_normal(tmp_path, mutation):
    root = tmp_path / 'maintenance'; before = guard.initialize(root)
    value = plan()
    if mutation == 'secret': value['source_body'] = 'not accepted or persisted'
    elif mutation == 'missing': value.pop('control_sha256')
    elif mutation == 'old_hash': value['old_revision'] = 'a' * 64
    elif mutation == 'duplicate_mode': value['canaries'][1]['mode'] = 'v1'
    else: value['canaries'][1]['job_id'] = 'job-1'
    with pytest.raises(guard.MaintenanceUnavailable): guard.arm(root, value)
    assert guard.read_state(root) == before


@pytest.mark.parametrize('timeout', [-1, True, None, float('inf'), float('nan')])
def test_invalid_timeouts_never_change_state(tmp_path, timeout):
    root = tmp_path / 'maintenance'; guard.initialize(root); before = guard.arm(root, plan())
    with pytest.raises(guard.MaintenanceUnavailable): guard.wait_drained(root, timeout)
    assert guard.read_state(root) == before


def _child(root, body, *, pass_fds=()):
    code = ('import os,select,sys\n'
            'sys.path.insert(0, sys.argv[1])\n'
            'import maintenance_guard as g\n'
            'root=sys.argv[2]\n' + body)
    return subprocess.Popen([sys.executable, '-B', '-c', code, str(Path(guard.__file__).parent), str(root)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'PYTHONDONTWRITEBYTECODE': '1'},
        pass_fds=pass_fds)


def _ready(child):
    import select
    assert select.select([child.stdout], [], [], 3)[0], 'private child did not become ready'
    assert child.stdout.readline().strip() == 'ready'


def _finish(child):
    out, err = child.communicate('x', timeout=5)
    assert child.returncode == 0, (out, err)


def test_real_child_lease_and_timeout_survive_reopen_until_child_finishes(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    child = _child(root, "with g.admission(root):\n print('ready',flush=True)\n select.select([sys.stdin],[],[],3)\n")
    try:
        _ready(child)
        before = time.monotonic(); guard.arm(root, plan())
        assert time.monotonic() - before < .5
        assert guard.wait_drained(root, .03) is False
        assert guard.initialize(root)['phase'] == 'arming'
    finally: _finish(child)
    assert guard.wait_drained(root, 1) is True


def test_duplicate_fd_keeps_lease_after_parent_context_exit(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    with guard.admission(root) as lease:
        fd = os.dup(lease.fileno())
        child = _child(root, f"held={fd}\nprint('ready',flush=True)\nselect.select([sys.stdin],[],[],3)\nos.close(held)\n", pass_fds=(fd,))
        os.close(fd)
        _ready(child)
    try:
        guard.arm(root, plan())
        assert guard.wait_drained(root, .03) is False
    finally: _finish(child)
    assert guard.wait_drained(root, 1) is True


def test_process_exit_releases_lease_but_never_resets_armed_intent(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    body = "with g.admission(root):\n print('ready',flush=True)\n select.select([sys.stdin],[],[],3)\n os._exit(7)\n"
    child = _child(root, body)
    _ready(child); guard.arm(root, plan()); assert not guard.wait_drained(root, 0)
    child.communicate('x', timeout=5)
    assert child.returncode == 7
    assert guard.read_state(root)['phase'] == 'arming'
    assert guard.wait_drained(root, 1)


def test_other_controller_cannot_reset_intent_while_control_lock_is_held(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root); armed = guard.arm(root, plan())
    body = ("import fcntl\nfd=os.open(os.path.join(root,'control.lock'),os.O_RDWR)\n"
            "fcntl.flock(fd,fcntl.LOCK_EX)\nprint('ready',flush=True)\n"
            "select.select([sys.stdin],[],[],3)\nos.close(fd)\n")
    child = _child(root, body)
    try:
        _ready(child)
        with pytest.raises(guard.MaintenanceBusy): guard.arm(root, plan())
        assert guard.wait_drained(root, .03) is False
        assert guard.read_state(root) == armed
    finally: _finish(child)
    assert guard.wait_drained(root, 1)


def test_import_is_inert_without_config_or_namespace_creation(tmp_path):
    root = tmp_path / 'never-created'
    child = _child(root, "assert 'config' not in sys.modules\nassert not os.path.exists(root)\n")
    out, err = child.communicate(timeout=5)
    assert child.returncode == 0, (out, err)
    assert not root.exists()


def test_missing_entire_initialized_namespace_is_not_a_new_normal_bootstrap(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root); guard.arm(root, plan())
    saved = tmp_path / 'preserved-armed-namespace'; root.rename(saved)
    with pytest.raises(guard.MaintenanceUnavailable): guard.initialize(root)
    assert not root.exists()
    assert json.loads((saved / 'state.json').read_text())['phase'] == 'arming'


@pytest.mark.parametrize('mutation', ['missing', 'inode', 'symlink', 'mode', 'duplicate'])
def test_bootstrap_anchor_cannot_be_removed_replaced_or_made_unsafe(tmp_path, mutation):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    anchor = tmp_path / '.maintenance.bootstrap'
    assert stat.S_IMODE(anchor.stat().st_mode) == 0o600
    if mutation == 'missing': anchor.unlink()
    elif mutation == 'inode':
        content = anchor.read_bytes(); anchor.rename(tmp_path / 'saved-bootstrap')
        anchor.write_bytes(content); anchor.chmod(0o600)
    elif mutation == 'symlink':
        saved = tmp_path / 'saved-bootstrap'; anchor.rename(saved); anchor.symlink_to(saved)
    elif mutation == 'mode': anchor.chmod(0o644)
    else: anchor.write_text('{"namespace_name":"maintenance",' + anchor.read_text()[1:])
    with pytest.raises(guard.MaintenanceUnavailable): guard.read_state(root)
    with pytest.raises(guard.MaintenanceUnavailable): guard.initialize(root)


def test_interrupted_bootstrap_leaves_a_nonresettable_namespace(tmp_path):
    root = tmp_path / 'maintenance'
    child = _child(root, "g._write=lambda *a,**kw: os._exit(6)\ng.initialize(root)\n")
    child.communicate(timeout=5)
    assert child.returncode == 6
    assert (tmp_path / '.maintenance.bootstrap').exists()
    assert root.exists() and not (root / 'state.json').exists()
    with pytest.raises(guard.MaintenanceUnavailable): guard.initialize(root)
    with pytest.raises(guard.MaintenanceUnavailable):
        with guard.admission(root): pytest.fail('incomplete bootstrap admitted')


def test_concurrent_create_once_never_produces_different_namespace_identities(tmp_path):
    root = tmp_path / 'maintenance'
    body = ("print('ready',flush=True)\nselect.select([sys.stdin],[],[],3)\n"
            "try: value=g.initialize(root)\nexcept g.MaintenanceUnavailable: sys.exit(2)\n"
            "print(value['namespace_id'],flush=True)\n")
    children = [_child(root, body) for _ in range(6)]
    for child in children: _ready(child)
    for child in children: child.stdin.write('x'); child.stdin.flush()
    identities = []
    for child in children:
        out, err = child.communicate(timeout=5)
        assert child.returncode in (0, 2), err
        if child.returncode == 0: identities.append(out.strip())
    assert identities and set(identities) == {guard.read_state(root)['namespace_id']}


def test_concurrent_controllers_cannot_overwrite_the_first_fixed_plan(tmp_path):
    root = tmp_path / 'maintenance'; guard.initialize(root)
    children = []
    for index in range(6):
        value = plan(); value['campaign_id'] = f'campaign-{index}'
        body = ("print('ready',flush=True)\nselect.select([sys.stdin],[],[],3)\n"
                f"try: value=g.arm(root,{value!r})\n"
                "except (g.MaintenanceBlocked,g.MaintenanceBusy): sys.exit(2)\n"
                "print(value['plan']['campaign_id'],flush=True)\n")
        children.append(_child(root, body))
    for child in children: _ready(child)
    for child in children: child.stdin.write('x'); child.stdin.flush()
    winners = []
    for child in children:
        out, err = child.communicate(timeout=5)
        assert child.returncode in (0, 2), err
        if child.returncode == 0: winners.append(out.strip())
    assert len(winners) == 1
    assert guard.initialize(root)['plan']['campaign_id'] == winners[0]
    assert guard.read_state(root)['phase'] == 'arming'


def test_default_path_is_explicitly_initialized_and_missing_state_stays_closed(tmp_path, monkeypatch):
    cache = tmp_path / 'cache'; cache.mkdir()
    monkeypatch.delenv('STOCK_AGENT_MAINTENANCE_DIR', raising=False)
    monkeypatch.setenv('CACHE_DIR', str(cache))
    with pytest.raises(guard.MaintenanceUnavailable): guard.read_state()
    guard.initialize(None)
    assert guard.read_state()['phase'] == 'normal'
    chosen = tmp_path / 'chosen'
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(chosen))
    with pytest.raises(guard.MaintenanceUnavailable):
        with guard.admission(): pytest.fail('explicit missing namespace fell back to cache')
    guard.initialize(chosen)
    with guard.admission(): pass
