"""Real local child processes, private files/ledger, no provider or runtime."""
import json
import asyncio
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

import quality_campaign_watchdog as watchdog
from quality_campaign_watchdog import CleanupUnconfirmed, WatchdogError, run_reserved_process
from quality_campaign_budget import BudgetDenied, CampaignBudget
from test_quality_campaign_budget import active, IDENTITY, RESERVATION


def command(source):
    return [sys.executable, '-I', '-B', '-c', source]


def output_directory(tmp_path, name='private'):
    output = tmp_path / name
    output.mkdir(mode=0o700)
    return output


def pid_is_gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def run(ledger, output, source, **kwargs):
    return run_reserved_process(ledger, 'job', command(source), env={}, output_dir=output,
                                term_grace=0.05, kill_grace=1, poll_seconds=0.02, **kwargs)


def test_normal_exit_proves_cleanup_without_finishing_or_refunding_job(tmp_path, monkeypatch, capfd):
    ledger = active(tmp_path)
    ledger.reserve_attempt('unknown', 'job', **RESERVATION)
    output = tmp_path / 'private'
    output.mkdir(mode=0o700)
    monkeypatch.setenv('WATCHDOG_AMBIENT_SECRET', 'not-for-child')
    result = run_reserved_process(ledger, 'job', command(
        "import os; assert 'WATCHDOG_AMBIENT_SECRET' not in os.environ; print('PRIVATE-NOT-LOGGED')"),
        env={'PATH': '/usr/bin:/bin'}, output_dir=output, term_grace=0.05)
    assert result['status'] == 'exited'
    assert result['returncode'] == 0
    assert result['cleanup_verified'] is True
    assert json.loads(Path(result['cleanup_path']).read_text()) == result['cleanup']
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'
    assert ledger.snapshot()['spent']['tokens'] == RESERVATION['tokens']
    assert ledger.snapshot()['attempts']['unknown']['actual_tokens'] is None
    assert 'PRIVATE-NOT-LOGGED' not in capfd.readouterr().out


def test_monotonic_deadline_kills_hang_when_wall_clock_does_not_advance(tmp_path):
    ledger = active(tmp_path, limits={'campaign': {'job_seconds': 1}}, clock=lambda: 1000)
    output = output_directory(tmp_path)
    started = time.monotonic()
    result = run(ledger, output,
        "import os,signal,time; open('pid','w').write(str(os.getpid())); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)")
    assert result['cleanup']['stop_reason'] == 'monotonic_deadline'
    assert result['status'] == 'stopped'
    assert time.monotonic() - started < 3
    assert pid_is_gone(int((output / 'pid').read_text()))
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'


def test_descendant_is_killed_after_command_leader_exits_and_unrelated_process_survives(tmp_path):
    ledger = active(tmp_path)
    output = output_directory(tmp_path)
    unrelated = subprocess.Popen(command('import time; time.sleep(30)'), env={},
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    try:
        result = run(ledger, output, "import os,signal,time\n"
            "pid=os.fork()\n"
            "if pid:\n"
            " open('descendant','w').write(str(pid))\n"
            " os._exit(0)\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "time.sleep(30)\n")
        assert result['returncode'] == 0
        assert result['cleanup_verified'] is True
        assert pid_is_gone(int((output / 'descendant').read_text()))
        assert unrelated.poll() is None
    finally:
        unrelated.kill()
        unrelated.wait(timeout=3)


@pytest.mark.parametrize('error', [KeyboardInterrupt, RuntimeError, asyncio.CancelledError])
def test_parent_exception_reaps_children_before_raising_and_emitting_cleanup(tmp_path, error):
    ledger = active(tmp_path)
    output = output_directory(tmp_path)
    def cancelled():
        if (output / 'pid').exists():
            raise error('outer cancelled')
        return False
    with pytest.raises(error, match='outer cancelled'):
        run(ledger, output, "import os,time; open('pid','w').write(str(os.getpid())); time.sleep(30)",
            cancel_check=cancelled)
    assert pid_is_gone(int((output / 'pid').read_text()))
    assert json.loads((output / 'watchdog-job.cleanup.json').read_text())['guardian_reaped'] is True
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'


def test_explicit_cancellation_stops_before_another_poll(tmp_path):
    ledger = active(tmp_path)
    output = output_directory(tmp_path)
    result = run(ledger, output, 'import time; time.sleep(30)', cancel_check=lambda: True)
    assert result['cleanup']['stop_reason'] == 'cancelled'
    assert result['status'] == 'stopped'


@pytest.mark.parametrize('violation', ['rollback', 'overrun', 'wall_deadline'])
def test_ledger_denials_stop_child_without_refunding_unknown_attempt(tmp_path, violation):
    clock = [1000]
    ledger = active(tmp_path, clock=lambda: clock[0])
    ledger.reserve_attempt('unknown', 'job', **RESERVATION)
    output = output_directory(tmp_path)
    changed = False
    def mutate_after_child_started():
        nonlocal changed
        if not changed and (output / 'pid').exists():
            changed = True
            if violation == 'rollback': clock[0] -= 1
            elif violation == 'wall_deadline': clock[0] += 4000
            else:
                ledger.settle_attempt('unknown', actual_tokens=RESERVATION['tokens'] + 1,
                    usage_evidence_sha256='f' * 64)
        return False
    result = run(ledger, output, "import os,time; open('pid','w').write(str(os.getpid())); time.sleep(30)",
        cancel_check=mutate_after_child_started)
    assert result['cleanup']['stop_reason'] == 'ledger_denied'
    assert ledger.snapshot()['blocked']
    assert ledger.snapshot()['spent']['http'] == 1
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'
    assert pid_is_gone(int((output / 'pid').read_text()))


def test_same_reserved_job_cannot_relaunch_into_a_new_output_directory(tmp_path):
    ledger = active(tmp_path)
    run(ledger, output_directory(tmp_path, 'first'), 'pass')
    with pytest.raises(FileExistsError):
        run(ledger, output_directory(tmp_path, 'second'), 'pass')


@pytest.mark.parametrize('change', ['overrun', 'rollback', 'finished'])
def test_durable_ledger_change_after_start_claim_prevents_spawn(tmp_path, monkeypatch, change):
    ledger = active(tmp_path, clock=lambda: 1000)
    ledger.reserve_attempt('unknown', 'job', **RESERVATION)
    other_clock = [1000]
    other = CampaignBudget(ledger.path, IDENTITY, clock=lambda: other_clock[0])
    output = output_directory(tmp_path)
    claim = ledger.path.with_name(ledger.path.name + '.job.watchdog-started.json')
    private_json, launched = watchdog._private_json, []
    def mutate_after_durable_claim(path, payload):
        digest = private_json(path, payload)
        assert path == claim and claim.is_file()
        if change == 'overrun':
            other.settle_attempt('unknown', actual_tokens=RESERVATION['tokens'] + 1,
                usage_evidence_sha256='f' * 64)
        elif change == 'rollback':
            other_clock[0] = 999
            with pytest.raises(BudgetDenied, match='clock rollback'):
                other.check()
            other_clock[0] = 1000
        else:
            other.finish_job('job', status='cancelled')
        return digest
    def unexpected_spawn(*args, **kwargs):
        launched.append(True)
        raise AssertionError('durable ledger revocation must prevent spawn')
    monkeypatch.setattr(watchdog, '_private_json', mutate_after_durable_claim)
    monkeypatch.setattr(watchdog.subprocess, 'Popen', unexpected_spawn)
    with pytest.raises(WatchdogError, match='child not started'):
        run(ledger, output, 'pass')
    assert launched == []
    assert json.loads(claim.read_text())['job_id'] == 'job'
    assert not (output / 'watchdog-job.cleanup.json').exists()
    state = ledger.snapshot()
    assert state == other.snapshot()
    assert state['spent']['jobs'] == state['spent']['http'] == 1
    assert state['spent']['tokens'] == RESERVATION['tokens'] + (change == 'overrun')
    assert state['attempts']['unknown']['final_tokens'] is False
    assert state['jobs']['job']['status'] == ('cancelled' if change == 'finished' else 'active')
    assert bool(state['blocked']) is (change != 'finished')


def test_independent_timer_stops_child_even_while_ledger_check_is_blocked(tmp_path, monkeypatch):
    ledger = active(tmp_path, limits={'campaign': {'job_seconds': 1}}, clock=lambda: 1000)
    output = output_directory(tmp_path)
    original_check = ledger.check
    observed = []
    def slow_check():
        if (output / 'pid').exists() and not observed:
            pid = int((output / 'pid').read_text())
            time.sleep(1.5)
            observed.append(pid_is_gone(pid))
        return original_check()
    monkeypatch.setattr(ledger, 'check', slow_check)
    result = run(ledger, output, "import os,time; open('pid','w').write(str(os.getpid())); time.sleep(30)")
    assert observed == [True]
    assert result['cleanup']['stop_reason'] == 'monotonic_deadline'


def test_unconfirmed_group_never_writes_cleanup_evidence(tmp_path, monkeypatch):
    ledger = active(tmp_path)
    output = output_directory(tmp_path)
    killpg = os.killpg
    def cannot_confirm_absence(pgid, sig):
        if sig == 0:
            return None
        return killpg(pgid, sig)
    monkeypatch.setattr(watchdog.os, 'killpg', cannot_confirm_absence)
    with pytest.raises(CleanupUnconfirmed, match='no cleanup receipt'):
        run(ledger, output, 'pass')
    assert not (output / 'watchdog-job.cleanup.json').exists()
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'


@pytest.mark.parametrize('invalid', ['public_output', 'symlink_output', 'relative_executable', 'ambient_env', 'unknown_job'])
def test_invalid_launch_metadata_never_starts_a_process(tmp_path, monkeypatch, invalid):
    ledger = active(tmp_path)
    output = output_directory(tmp_path)
    argv, env, job_id = command('pass'), {}, 'job'
    if invalid == 'public_output': output.chmod(0o755)
    elif invalid == 'symlink_output':
        link = tmp_path / 'symlink'
        link.symlink_to(output, target_is_directory=True)
        output = link
    elif invalid == 'relative_executable': argv[0] = 'python'
    elif invalid == 'ambient_env': env = os.environ
    else: job_id = 'unreserved'
    def unexpected(*args, **kwargs):
        raise AssertionError('unreviewed child must not start')
    monkeypatch.setattr(watchdog.subprocess, 'Popen', unexpected)
    with pytest.raises(WatchdogError):
        run_reserved_process(ledger, job_id, argv, env=env, output_dir=output)


def test_import_does_not_start_processes_open_ledger_or_capture_output(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('import must remain inert')
    monkeypatch.setattr(subprocess, 'Popen', unexpected)
    monkeypatch.setattr(os, 'open', unexpected)
    spec = importlib.util.spec_from_file_location('inert_watchdog', watchdog.__file__)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))


def test_nonzero_child_exit_is_retained_not_promoted_to_stage_success(tmp_path):
    ledger = active(tmp_path)
    result = run(ledger, output_directory(tmp_path), 'raise SystemExit(7)')
    assert result['returncode'] == 7
    assert result['cleanup_verified'] is True
    assert ledger.snapshot()['stages']['S1'] == 'open'


def test_cleanup_owner_construction_failure_occurs_before_any_child_launch(tmp_path, monkeypatch):
    ledger = active(tmp_path)
    output = output_directory(tmp_path)
    launched = []
    def broken_owner(*args, **kwargs):
        raise RuntimeError('cleanup state allocation failed')
    def unexpected_spawn(*args, **kwargs):
        launched.append(True)
        raise AssertionError('child started before cleanup state existed')
    monkeypatch.setattr(watchdog, '_OwnedGroup', broken_owner)
    monkeypatch.setattr(watchdog.subprocess, 'Popen', unexpected_spawn)
    with pytest.raises(RuntimeError, match='cleanup state allocation failed'):
        run(ledger, output, 'pass')
    assert launched == []
    assert not (output / 'watchdog-job.cleanup.json').exists()
    assert ledger.snapshot()['jobs']['job']['status'] == 'active'


def test_timer_start_failure_after_spawn_still_cleans_exact_owned_process(tmp_path, monkeypatch):
    ledger = active(tmp_path)
    output = output_directory(tmp_path)
    spawned = []
    popen = subprocess.Popen
    def recording_spawn(*args, **kwargs):
        process = popen(*args, **kwargs)
        spawned.append(process)
        return process
    def broken_start(*args, **kwargs):
        raise RuntimeError('timer unavailable')
    monkeypatch.setattr(watchdog.subprocess, 'Popen', recording_spawn)
    monkeypatch.setattr(watchdog.threading.Thread, 'start', broken_start)
    with pytest.raises(RuntimeError, match='timer unavailable'):
        run(ledger, output, 'import time; time.sleep(30)')
    assert len(spawned) == 1
    assert spawned[0].returncode is not None
    assert pid_is_gone(spawned[0].pid)
    assert json.loads((output / 'watchdog-job.cleanup.json').read_text())['guardian_reaped'] is True


def test_sigint_during_cleanup_join_does_not_interrupt_group_cleanup(tmp_path):
    ledger = active(tmp_path)
    output = output_directory(tmp_path)
    sender = []
    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    def cancellation():
        if (output / 'pid').exists() and not sender:
            sender.append(threading.Timer(0.04, lambda: os.kill(os.getpid(), signal.SIGINT)))
            sender[0].start()
            return True
        return False
    try:
        with pytest.raises(KeyboardInterrupt):
            run_reserved_process(ledger, 'job', command(
                "import os,time; open('pid','w').write(str(os.getpid())); time.sleep(30)"),
                env={}, output_dir=output, cancel_check=cancellation,
                term_grace=0.2, kill_grace=1, poll_seconds=0.02)
    finally:
        for thread in sender: thread.join(timeout=2)
        signal.signal(signal.SIGINT, previous)
    assert pid_is_gone(int((output / 'pid').read_text()))
    assert json.loads((output / 'watchdog-job.cleanup.json').read_text())['process_group_absent'] is True
