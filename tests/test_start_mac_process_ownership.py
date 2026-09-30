"""Fake OS ownership guards; cancellation signals target only the test shell."""

import os
from pathlib import Path
import re
import subprocess
import sys
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _guards():
    source = (ROOT / "start_mac.command").read_text()
    functions = []
    for name in ("project_process_matches", "stop_project_pid", "stop_existing_project_api", "stop_pidfile_worker"):
        match = re.search(rf"(?ms)^{name}\(\) \{{.*?^\}}$", source)
        assert match is not None, f"Missing fail-closed launcher guard: {name}"
        functions.append(match[0])
    return "\n".join(functions)


def _run_guard(tmp_path, *, role="api", owner="same", mixed=False, parent="none", cleanup_seconds=0,
               cancel_signal="", launcher_command=""):
    project = tmp_path / "external drive with spaces"
    project.mkdir()
    pidfile = project / "worker.pid"
    pidfile.write_text("555\n")
    env = {**os.environ, "DIR": str(project), "WORKER_PID_FILE": str(pidfile),
           "OWNER": owner, "ROLE": role, "MIXED": "1" if mixed else "0", "PARENT_STATE": parent,
           "CLEANUP_TICKS": str(cleanup_seconds * 2), "CANCEL_SIGNAL": cancel_signal,
           "LAUNCHER_COMMAND": launcher_command}
    traps = "\n".join(re.findall(r"(?m)^trap .+$", (ROOT / "start_mac.command").read_text()))
    fake_os = r'''
RUNNING=1
PARENT_RUNNING=1
ELAPSED_TICKS=0
ps() {
    case "$*" in *ppid=*) [ "$PARENT_STATE" = none ] || printf '777\n'; return 0;; esac
    if [ "$2" = "777" ]; then
        if [ -n "$LAUNCHER_COMMAND" ]; then printf '%s\n' "$LAUNCHER_COMMAND";
        else printf '/bin/bash %s/start_mac.command\n' "$DIR"; fi
        return 0
    fi
    if [ "$OWNER" = "unknown" ] || [ "$2" = "666" ]; then
        printf '%s\n' 'python -m http.server 8080'
    elif [ "$ROLE" = "api" ]; then
        printf '%s\n' '/project/.venv/bin/python -u -m uvicorn api:app --host 127.0.0.1 --port 8080'
    else
        printf '%s\n' '/project/.venv/bin/python -u worker_main.py --role all'
    fi
}
lsof() {
    case "$*" in
        *tcp:8080*|*TCP:8080*) printf '555\n'; [ "$MIXED" != 1 ] || printf '666\n';;
        *) if [ "$OWNER" = "other_checkout" ]; then printf 'n/other/backend\n'; else printf 'n%s/backend\n' "$DIR"; fi;;
    esac
}
kill() {
    if [ "$1" = "-0" ]; then
        if [ "$2" = 777 ]; then
            printf 'CHECK_PARENT\n'
            [ "$PARENT_STATE" != stuck ] || return 0
            if [ "$PARENT_STATE" = slow ]; then [ "$ELAPSED_TICKS" -lt "$CLEANUP_TICKS" ]; return; fi
            if [ "$PARENT_RUNNING" = 1 ]; then PARENT_RUNNING=0; return 0; fi
            return 1
        fi
        [ "$RUNNING" = 1 ]; return
    fi
    printf 'SIGNAL %s\n' "$*"
    RUNNING=0
}
sleep() {
    if [ -n "$CANCEL_SIGNAL" ]; then
        builtin kill -"$CANCEL_SIGNAL" "$$"
        CANCEL_SIGNAL=""
    fi
    case "$1" in
        0.5) ELAPSED_TICKS=$((ELAPSED_TICKS + 1));;
        1) ELAPSED_TICKS=$((ELAPSED_TICKS + 2));;
        *) echo "Unexpected sleep: $1" >&2; return 1;;
    esac
}
cleanup() { echo TEST_CLEANUP; }
'''
    action = "stop_existing_project_api" if role == "api" else "stop_pidfile_worker"
    result = subprocess.run(["/bin/bash", "-c", "set -e\n" + fake_os + traps + "\n" + _guards() + "\n" + action
                             + '\necho RESTART_ALLOWED_AT_TICK_$ELAPSED_TICKS'],
                            env=env, capture_output=True, text=True, timeout=5)
    return result, pidfile


@pytest.mark.parametrize("owner", ["unknown", "other_checkout"])
def test_unknown_port_owner_is_preserved_and_launcher_refuses(tmp_path, owner):
    result, _ = _run_guard(tmp_path, owner=owner)
    assert result.returncode != 0
    assert "SIGNAL" not in result.stdout


def test_all_port_owners_are_checked_before_any_signal(tmp_path):
    result, _ = _run_guard(tmp_path, mixed=True)
    assert result.returncode != 0
    assert "SIGNAL" not in result.stdout


def test_verified_project_api_can_be_stopped(tmp_path):
    result, _ = _run_guard(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SIGNAL -TERM 555" in result.stdout


def test_launcher_waits_for_previous_launcher_cleanup_before_reusing_redis(tmp_path):
    result, _ = _run_guard(tmp_path, parent="exiting")
    assert result.returncode == 0, result.stdout + result.stderr
    # No signal to the parent; observe its normal cleanup after stopping its API.
    assert result.stdout.count("CHECK_PARENT") >= 2
    assert "SIGNAL -TERM 777" not in result.stdout


def test_relative_launcher_invocation_waits_for_owned_cleanup(tmp_path):
    result, _ = _run_guard(tmp_path, parent="slow", cleanup_seconds=12,
                           launcher_command="/bin/bash ./start_mac.command")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESTART_ALLOWED_AT_TICK_24" in result.stdout
    assert result.stdout.count("CHECK_PARENT") >= 12
    assert "SIGNAL -TERM 777" not in result.stdout


def test_similar_relative_script_is_not_treated_as_project_launcher(tmp_path):
    result, _ = _run_guard(tmp_path, parent="slow", cleanup_seconds=12,
                           launcher_command="/bin/bash ./start_mac.command.backup")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CHECK_PARENT" not in result.stdout


def test_launcher_refuses_to_start_when_old_launcher_cleanup_does_not_finish(tmp_path):
    result, _ = _run_guard(tmp_path, parent="stuck")
    assert result.returncode != 0
    assert "SIGNAL -TERM 555" in result.stdout
    assert "SIGNAL -TERM 777" not in result.stdout
    assert "RESTART_ALLOWED" not in result.stdout


@pytest.mark.parametrize("cleanup_seconds", [12, 120, 180])
def test_launcher_continues_same_start_after_slow_owned_cleanup(tmp_path, cleanup_seconds):
    result, _ = _run_guard(tmp_path, parent="slow", cleanup_seconds=cleanup_seconds)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"RESTART_ALLOWED_AT_TICK_{cleanup_seconds * 2}" in result.stdout
    assert [line for line in result.stdout.splitlines() if line.startswith("SIGNAL")] == ["SIGNAL -TERM 555"]


def test_launcher_cleanup_wait_is_bounded_and_explained(tmp_path):
    result, _ = _run_guard(tmp_path, parent="slow", cleanup_seconds=181)
    assert result.returncode != 0
    assert "RESTART_ALLOWED" not in result.stdout
    assert [line for line in result.stdout.splitlines() if line.startswith("SIGNAL")] == ["SIGNAL -TERM 555"]
    assert "180 秒" in result.stderr
    assert "等待" in result.stdout
    assert result.stdout.count("CHECK_PARENT") <= 181


@pytest.mark.parametrize("cancel_signal,exit_code", [("INT", 130), ("TERM", 143)])
def test_cancelling_during_cleanup_wait_exits_without_restarting(tmp_path, cancel_signal, exit_code):
    result, _ = _run_guard(tmp_path, parent="slow", cleanup_seconds=12, cancel_signal=cancel_signal)
    assert result.returncode == exit_code, result.stdout + result.stderr
    assert "RESTART_ALLOWED" not in result.stdout
    assert result.stdout.count("TEST_CLEANUP") == 1
    assert [line for line in result.stdout.splitlines() if line.startswith("SIGNAL")] == ["SIGNAL -TERM 555"]


@pytest.mark.parametrize("cancel_signal", ["INT", "TERM"])
def test_stop_signal_during_exit_cleanup_preserves_worker_then_redis_shutdown(cancel_signal):
    source = (ROOT / "start_mac.command").read_text()
    cleanup = re.search(r"(?ms)^cleanup\(\) \{.*?^\}$", source)
    assert cleanup is not None
    traps = "\n".join(re.findall(r"(?m)^trap .+$", source))
    # Real signals reach only this disposable shell; all owned resources are fake.
    script = r'''set -e
SERVER_PID=555
WORKER_PID=666
REDIS_PID=777
WORKER_PID_FILE=/unused/test-worker.pid
kill() { printf 'OWNED_STOP %s\n' "$*"; }
wait() { if [ "$1" = 555 ]; then sleep 0.2; fi; }
rm() { printf 'PIDFILE_REMOVE\n'; }
wait_for_project_workers_to_stop() { printf 'PROJECT_WORKERS_STOPPED\n'; }
''' + cleanup[0] + "\n" + traps + f'\n(sleep 0.05; builtin kill -{cancel_signal} $$) &\nexit 0\n'
    result = subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True, timeout=3)
    assert result.stdout.splitlines() == [
        "OWNED_STOP 555", "OWNED_STOP 666", "PIDFILE_REMOVE",
        "PROJECT_WORKERS_STOPPED", "OWNED_STOP 777",
    ], (result.returncode, result.stdout, result.stderr)
    assert result.returncode == 0


def test_reused_worker_pid_is_preserved_and_not_unlinked(tmp_path):
    result, pidfile = _run_guard(tmp_path, role="worker", owner="unknown")
    assert result.returncode != 0
    assert "SIGNAL" not in result.stdout
    assert pidfile.exists()


def test_verified_project_worker_pid_can_be_stopped(tmp_path):
    result, pidfile = _run_guard(tmp_path, role="worker")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SIGNAL -TERM 555" in result.stdout
    assert not pidfile.exists()


@pytest.mark.parametrize("inherited", [False, True])
def test_queue_settings_preserve_env_file_and_explicit_parent_environment(tmp_path, inherited):
    source = (ROOT / "start_mac.command").read_text()
    match = re.search(r"(?ms)^load_queue_environment\(\) \{.*?^\}$", source)
    assert match is not None, "Launcher must load existing queue configuration before applying defaults"
    project = tmp_path / "external drive with spaces"
    (project / "backend").mkdir(parents=True)
    marker = project / "must-not-execute"
    literal = f"$(touch '{marker}')"
    (project / "backend/.env").write_text(f"TASK_QUEUE_BACKEND=local\nREDIS_URL=redis://example.invalid:6381/3\nTASK_QUEUE_NAME={literal}\n")
    env = {key: value for key, value in os.environ.items() if key not in {"TASK_QUEUE_BACKEND", "REDIS_URL", "TASK_QUEUE_NAME"}}
    env.update(DIR=str(project), PYTHON_BIN=sys.executable)
    if inherited:
        env.update(TASK_QUEUE_BACKEND="rq", REDIS_URL="redis://parent.invalid:6382/4", TASK_QUEUE_NAME="parent-queue")
    harness = match[0] + '\nload_queue_environment\n"$PYTHON_BIN" -c \'import json,os; print(json.dumps({k:os.environ[k] for k in ("TASK_QUEUE_BACKEND","REDIS_URL","TASK_QUEUE_NAME")}))\''
    result = subprocess.run(["/bin/bash", "-c", harness], env=env, text=True, capture_output=True, check=True, timeout=5)
    actual = json.loads(result.stdout)
    assert actual == ({"TASK_QUEUE_BACKEND": "rq", "REDIS_URL": "redis://parent.invalid:6382/4", "TASK_QUEUE_NAME": "parent-queue"}
                      if inherited else {"TASK_QUEUE_BACKEND": "local", "REDIS_URL": "redis://example.invalid:6381/3", "TASK_QUEUE_NAME": literal}), result.stderr
    assert not marker.exists()
