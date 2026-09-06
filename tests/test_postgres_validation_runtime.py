"""Offline contracts for the pinned PostgreSQL validation image and runtime."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest


RUN_ID = "89abcdef01234567"
ROOT = Path(f"/tmp/pg-validation-{RUN_ID}")
SOCKET = ROOT / "socket"
DATA = ROOT / "data"
POLICY = ROOT / "policy.json"
MANIFEST_HASH = "a" * 64


def _runtime_module():
    return importlib.import_module("pg_validation.entrypoint")


def _guard_module():
    return importlib.import_module("pg_validation.guard")


def test_dockerfile_is_the_exact_pinned_nonroot_runtime_contract():
    dockerfile = Path("tests/pg_validation/Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.splitlines()[0] == (
        "FROM --platform=linux/arm64 "
        "postgres:17.11-trixie@sha256:"
        "413da4542e091471785b7f18f1a2258df134bc6506ab4e1e53725aa8bcfdb650"
    )
    assert "python3.13=3.13.5-2+deb13u3" in dockerfile
    assert "python3.13-venv=3.13.5-2+deb13u3" in dockerfile
    assert "COPY backend/requirements.lock /opt/locks/backend.lock" in dockerfile
    assert "COPY tests/pg_validation/binary.lock /opt/locks/binary.lock" in dockerfile
    assert "COPY . " not in dockerfile
    assert "ADD " not in dockerfile
    assert "PSYCOPG_IMPL=binary" in dockerfile
    assert "USER 999:999" in dockerfile
    assert dockerfile.rstrip().endswith(
        'ENTRYPOINT ["/opt/pg-test-venv/bin/python", "-B", "-m", '
        '"pg_validation.entrypoint"]'
    )
    assert "EXPOSE" not in dockerfile
    assert "--publish" not in dockerfile


def test_binary_lock_is_pinned_to_the_requested_hash():
    assert Path("tests/pg_validation/binary.lock").read_text(encoding="ascii") == (
        "psycopg-binary==3.3.4 "
        "--hash=sha256:26df2717e59c0473e4465a97dfb1b7afebaa479277870fd5784d1436470db47c\n"
    )


class FakeSubprocess:
    def __init__(
        self,
        *,
        pytest_exit: int = 0,
        stop_failure: bool = False,
        start_failure: bool = False,
    ):
        self.pytest_exit = pytest_exit
        self.stop_failure = stop_failure
        self.start_failure = start_failure
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, argv, **kwargs):
        command = list(argv)
        self.calls.append((command, kwargs))
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["shell"] is False
        if command[-1] == "start" and self.start_failure:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if command[-1] == "stop" and self.stop_failure:
            raise subprocess.CalledProcessError(1, command)
        if command[:3] == [sys.executable, "-B", "tests/run_prompt_boundary_tests.py"]:
            if self.pytest_exit:
                raise subprocess.CalledProcessError(
                    self.pytest_exit, command, output="private stdout", stderr="private stderr"
                )
            return subprocess.CompletedProcess(command, 0, "private stdout", "")
        return subprocess.CompletedProcess(command, 0, "", "")


@pytest.fixture
def runtime_files(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"manifest_sha256": MANIFEST_HASH}))
    result = tmp_path / "result.json"
    yield manifest, result
    if ROOT.exists():
        import shutil

        shutil.rmtree(ROOT)


def test_entrypoint_runs_fixed_bootstrap_test_and_stop_argv_with_clean_env(
    monkeypatch, runtime_files
):
    entrypoint = _runtime_module()
    manifest, result = runtime_files
    monkeypatch.setenv("PGHOST", "production")
    monkeypatch.setenv("DATABASE_URL", "secret")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy")
    monkeypatch.setenv("GOOGLE_API_KEY", "secret")
    fake = FakeSubprocess()

    assert entrypoint.run(RUN_ID, invoke=fake, manifest_path=manifest, result_path=result) == 0

    commands = [call[0] for call in fake.calls]
    assert commands == [
        [
            "initdb", "-D", str(DATA), "-U", f"owner_{RUN_ID}",
            "--auth-local=trust", "--auth-host=reject", "--no-locale",
        ],
        [
            "pg_ctl", "-D", str(DATA), "-o",
            f"-k {SOCKET} -p 5432 -c listen_addresses=''",
            "-w", "-t", "60", "start",
        ],
        [
            "psql", "-h", str(SOCKET), "-p", "5432", "-U", f"owner_{RUN_ID}",
            "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
            f'CREATE ROLE "app_{RUN_ID}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
        ],
        [
            "psql", "-h", str(SOCKET), "-p", "5432", "-U", f"owner_{RUN_ID}",
            "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
            f'CREATE DATABASE "db_{RUN_ID}" OWNER "app_{RUN_ID}"',
        ],
        [
            sys.executable, "-B", "tests/run_prompt_boundary_tests.py",
            "tests/test_workflow_postgres_live.py", "-q", "-p", "no:cacheprovider",
            "--tb=short",
        ],
        ["pg_ctl", "-D", str(DATA), "-w", "-t", "30", "stop"],
    ]
    assert [call[1]["timeout"] for call in fake.calls] == [120, 120, 60, 60, 600, 30]
    for command, kwargs in fake.calls:
        env = kwargs["env"]
        assert not any(name.startswith("PG") for name in env)
        assert "DATABASE_URL" not in env
        assert "HTTPS_PROXY" not in env
        assert "GOOGLE_API_KEY" not in env
        if command[0] == sys.executable:
            assert env["STOCK_AGENT_PG_VALIDATION_POLICY"] == str(POLICY)
            assert kwargs["cwd"] == "/work"
        else:
            assert "STOCK_AGENT_PG_VALIDATION_POLICY" not in env
    assert stat.S_IMODE(SOCKET.stat().st_mode) == 0o700
    assert stat.S_IMODE(POLICY.stat().st_mode) == 0o600
    policy = json.loads(POLICY.read_text())
    assert policy == {
        "run_id": RUN_ID,
        "manifest_sha256": MANIFEST_HASH,
        "endpoints": {
            "owner": {
                "host": str(SOCKET), "port": "5432", "dbname": f"db_{RUN_ID}",
                "user": f"owner_{RUN_ID}", "connect_timeout": "5", "sslmode": "disable",
            },
            "app": {
                "host": str(SOCKET), "port": "5432", "dbname": f"db_{RUN_ID}",
                "user": f"app_{RUN_ID}", "connect_timeout": "5", "sslmode": "disable",
            },
        },
    }
    assert json.loads(result.read_text()) == {
        "status": "passed", "manifest_sha256": MANIFEST_HASH
    }


@pytest.mark.parametrize("bad", ["", "short", "0123456789ABCDEf", "0" * 17])
def test_entrypoint_rejects_invalid_run_id_before_creating_files(bad, runtime_files):
    entrypoint = _runtime_module()
    manifest, result = runtime_files
    fake = FakeSubprocess()
    assert entrypoint.run(bad, invoke=fake, manifest_path=manifest, result_path=result) != 0
    assert fake.calls == []
    assert not result.exists()


@pytest.mark.parametrize("pytest_exit,stop_failure", [(7, False), (0, True), (7, True)])
def test_entrypoint_failure_or_stop_failure_can_never_become_success(
    pytest_exit, stop_failure, runtime_files
):
    entrypoint = _runtime_module()
    manifest, result = runtime_files
    fake = FakeSubprocess(pytest_exit=pytest_exit, stop_failure=stop_failure)
    assert entrypoint.run(
        RUN_ID, invoke=fake, manifest_path=manifest, result_path=result
    ) != 0
    commands = [call[0] for call in fake.calls]
    assert commands[-1] == ["pg_ctl", "-D", str(DATA), "-w", "-t", "30", "stop"]
    assert json.loads(result.read_text())["status"] == "failed"


def test_entrypoint_start_timeout_still_attempts_exact_bounded_stop(runtime_files):
    entrypoint = _runtime_module()
    manifest, result = runtime_files
    fake = FakeSubprocess(start_failure=True)
    assert entrypoint.run(
        RUN_ID, invoke=fake, manifest_path=manifest, result_path=result
    ) != 0
    assert fake.calls[-1][0] == [
        "pg_ctl", "-D", str(DATA), "-w", "-t", "30", "stop"
    ]
    assert fake.calls[-1][1]["timeout"] == 30


def _write_policy(path: Path, *, run_id: str = RUN_ID, endpoint_mutation=None):
    from pg_validation.policy import Endpoint

    owner = Endpoint(str(SOCKET), "5432", f"db_{RUN_ID}", f"owner_{RUN_ID}").values()
    app = Endpoint(str(SOCKET), "5432", f"db_{RUN_ID}", f"app_{RUN_ID}").values()
    if endpoint_mutation:
        endpoint_mutation(app)
    payload = {
        "run_id": run_id,
        "manifest_sha256": MANIFEST_HASH,
        "endpoints": {"owner": owner, "app": app},
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    path.chmod(0o600)


def _runtime_evidence(guard, *, platform="linux", docker=True, uid=None):
    return guard.RuntimeEvidence(
        platform=platform,
        docker_marker=docker,
        uid=os.getuid() if uid is None else uid,
    )


def test_policy_loader_accepts_only_attested_container_policy(runtime_files):
    guard = _guard_module()
    _write_policy(POLICY)
    endpoints = guard.load_policy(str(POLICY), evidence=_runtime_evidence(guard))
    assert [endpoint.user for endpoint in endpoints] == [f"owner_{RUN_ID}", f"app_{RUN_ID}"]


@pytest.mark.parametrize(
    "case",
    ["wrong_os", "no_docker", "root", "wrong_path", "symlink", "mode", "run", "endpoint"],
)
def test_policy_loader_rejects_invalid_runtime_or_policy(case, tmp_path, runtime_files):
    guard = _guard_module()
    evidence = _runtime_evidence(guard)
    path = POLICY
    mutation = None
    run_id = RUN_ID
    if case == "wrong_os":
        evidence = _runtime_evidence(guard, platform="darwin")
    elif case == "no_docker":
        evidence = _runtime_evidence(guard, docker=False)
    elif case == "root":
        evidence = _runtime_evidence(guard, uid=0)
    elif case == "wrong_path":
        path = tmp_path / "policy.json"
    elif case == "run":
        run_id = "fedcba9876543210"
    elif case == "endpoint":
        mutation = lambda endpoint: endpoint.update(host="/tmp/other")
    _write_policy(path if case != "symlink" else POLICY.with_suffix(".real"), run_id=run_id, endpoint_mutation=mutation)
    if case == "symlink":
        POLICY.symlink_to(POLICY.with_suffix(".real"))
    if case == "mode":
        POLICY.chmod(0o644)
    with pytest.raises(ValueError, match="^isolated_pg_live_policy_rejected$"):
        guard.load_policy(str(path), evidence=evidence)


def test_runner_installs_default_deny_without_policy_and_uses_policy_only_on_opt_in(monkeypatch):
    runner = importlib.import_module("run_prompt_boundary_tests")
    calls = []
    fake_driver = object()
    monkeypatch.delenv("STOCK_AGENT_PG_VALIDATION_POLICY", raising=False)
    monkeypatch.setenv("PGHOST", "production")
    monkeypatch.setattr(runner, "_import_psycopg", lambda: fake_driver)
    monkeypatch.setattr(runner, "_install_pg_guard", lambda driver, endpoints: calls.append((driver, endpoints)))
    assert runner.configure_postgres_boundary() is True
    assert calls == [(fake_driver, ())]
    assert "PGHOST" not in os.environ


def test_runner_requires_driver_when_live_policy_is_requested(monkeypatch):
    runner = importlib.import_module("run_prompt_boundary_tests")
    monkeypatch.setenv("STOCK_AGENT_PG_VALIDATION_POLICY", str(POLICY))
    monkeypatch.setattr(runner, "_import_psycopg", lambda: None)
    assert runner.configure_postgres_boundary() is False


def test_runner_loads_endpoints_only_when_live_policy_is_explicit(monkeypatch):
    runner = importlib.import_module("run_prompt_boundary_tests")
    fake_driver = object()
    endpoints = (object(), object())
    calls = []
    monkeypatch.setenv("STOCK_AGENT_PG_VALIDATION_POLICY", str(POLICY))
    monkeypatch.setattr(runner, "_import_psycopg", lambda: fake_driver)
    monkeypatch.setattr(runner, "_load_pg_policy", lambda path: endpoints if path == str(POLICY) else ())
    monkeypatch.setattr(runner, "_install_pg_guard", lambda driver, loaded: calls.append((driver, loaded)))
    assert runner.configure_postgres_boundary() is True
    assert calls == [(fake_driver, endpoints)]
