"""Non-root bootstrap for one disposable PostgreSQL validation run."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from typing import Any, Callable

from .guard import POLICY_ENV
from .policy import Endpoint
from .result import RESULT_SCHEMA


RUN_FAILED = 1
USAGE_FAILED = 2
_RUN_RE = re.compile(r"^[0-9a-f]{16}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_CHILD_ENV = {"PATH", "LANG", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PSYCOPG_IMPL"}
_MANIFEST_PATH = Path("/opt/validation-manifest.json")
_RESULT_PATH = Path("/results/result.json")
_IMAGE_ENV = "STOCK_AGENT_PG_VALIDATION_IMAGE_ID"
_RUN_ENV = "STOCK_AGENT_PG_VALIDATION_RUN_ID"
_MANIFEST_ENV = "STOCK_AGENT_PG_VALIDATION_MANIFEST_SHA256"


def _paths(run_id: str) -> tuple[Path, Path, Path]:
    root = Path(f"/tmp/pg-validation-{run_id}")
    return root, root / "socket", root / "data"


def _env() -> dict[str, str]:
    return {name: os.environ[name] for name in _CHILD_ENV if name in os.environ}


def _call(
    invoke: Callable[..., subprocess.CompletedProcess[str]],
    argv: list[str],
    *,
    env: dict[str, str],
    timeout: int,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, Any] = {
        "check": True,
        "capture_output": True,
        "text": True,
        "shell": False,
        "timeout": timeout,
        "env": env,
    }
    if cwd is not None:
        kwargs["cwd"] = cwd
    return invoke(argv, **kwargs)


def _write_private_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short private JSON write")
            view = view[written:]
    finally:
        os.close(fd)


def _write_private_log(path: Path, value: Any) -> None:
    if value is None:
        data = b""
    elif isinstance(value, bytes):
        data = value
    else:
        data = str(value).encode("utf-8", errors="replace")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short private log write")
            view = view[written:]
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short result write")
        view = view[written:]


def _file_signature(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_private_json(path: Path, maximum: int) -> tuple[dict[str, Any], tuple[int, ...]]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
        raise OSError("result is not a bounded regular file")
    expected = _file_signature(info)
    fd = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        opened = os.fstat(fd)
        if _file_signature(opened) != expected:
            raise OSError("result changed before read")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(64 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise OSError("result is too large")
        if _file_signature(os.fstat(fd)) != expected:
            raise OSError("result changed during read")
    finally:
        os.close(fd)
    payload = json.loads(b"".join(chunks).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("result is not an object")
    return payload, expected


def _atomic_replace_private(path: Path, encoded: bytes, expected: tuple[int, ...]) -> None:
    parent = path.parent
    parent_info = parent.lstat()
    if not stat.S_ISDIR(parent_info.st_mode):
        raise OSError("result parent is not a directory")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or _file_signature(before) != expected:
        raise OSError("result changed during update")
    temp = parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    fd = -1
    try:
        fd = os.open(temp, flags, 0o600)
        _write_all(fd, encoded)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        current = path.lstat()
        if _file_signature(current) != expected:
            raise OSError("result changed during update")
        os.replace(temp, path)
        dir_fd = os.open(
            parent,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _update_result_stop_status(path: Path, *, stop_status: str) -> bool:
    """Bind server shutdown to the structured result without logging data."""

    try:
        payload, expected = _read_private_json(path, 1024 * 1024)
        if payload.get("schema") != RESULT_SCHEMA:
            return False
        payload["server_stop_status"] = stop_status
        if stop_status != "stopped":
            payload["status"] = "tests_failed"
        encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(encoded) > 1024 * 1024:
            return False
        _atomic_replace_private(path, encoded, expected)
        return True
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _manifest_hash(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("manifest_sha256") if isinstance(payload, dict) else None
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ValueError("isolated_pg_manifest_invalid")
    return value


def _sql_commands(run_id: str) -> tuple[str, str]:
    # The run token has already matched lowercase hex exactly, so these are
    # closed-form identifiers rather than caller-provided SQL fragments.
    app = f'"app_{run_id}"'
    database = f'"db_{run_id}"'
    return (
        f"CREATE ROLE {app} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION",
        f"CREATE DATABASE {database} OWNER {app}",
    )


def run(
    run_id: Any,
    *,
    invoke: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    manifest_path: Path = _MANIFEST_PATH,
    result_path: Path = _RESULT_PATH,
) -> int:
    """Bootstrap, test, and stop PostgreSQL; return success only after cleanup."""

    if not isinstance(run_id, str) or not _RUN_RE.fullmatch(run_id):
        return USAGE_FAILED
    root, socket_dir, data_dir = _paths(run_id)
    owner = f"owner_{run_id}"
    app = f"app_{run_id}"
    database = f"db_{run_id}"
    policy_path = root / "policy.json"
    base_env = _env()
    initialized = False
    passed = False
    manifest_hash = ""
    test_stdout: Any = None
    test_stderr: Any = None
    stop_status = "not_started"
    try:
        root.mkdir(mode=0o700, exist_ok=False)
        socket_dir.mkdir(mode=0o700, exist_ok=False)
        if stat.S_IMODE(socket_dir.stat().st_mode) != 0o700:
            raise ValueError("isolated_pg_socket_permissions_invalid")
        manifest_hash = _manifest_hash(Path(manifest_path))
        _call(
            invoke,
            [
                "initdb", "-D", str(data_dir), "-U", owner,
                "--auth-local=trust", "--auth-host=reject", "--no-locale",
            ],
            env=base_env,
            timeout=120,
        )
        initialized = True
        _call(
            invoke,
            [
                "pg_ctl", "-D", str(data_dir), "-o",
                f"-k {socket_dir} -p 5432 -c listen_addresses=''",
                "-l", str(root / "postgres.log"),
                "-w", "-t", "60", "start",
            ],
            env=base_env,
            timeout=120,
        )
        create_role, create_database = _sql_commands(run_id)
        psql_prefix = [
            "psql", "-h", str(socket_dir), "-p", "5432", "-U", owner,
            "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
        ]
        _call(invoke, [*psql_prefix, create_role], env=base_env, timeout=60)
        _call(invoke, [*psql_prefix, create_database], env=base_env, timeout=60)
        endpoint_owner = Endpoint(str(socket_dir), "5432", database, owner)
        endpoint_app = Endpoint(str(socket_dir), "5432", database, app)
        _write_private_json(
            policy_path,
            {
                "run_id": run_id,
                "manifest_sha256": manifest_hash,
                "endpoints": {
                    "owner": endpoint_owner.values(),
                    "app": endpoint_app.values(),
                },
            },
        )
        child_env = dict(base_env)
        child_env[POLICY_ENV] = str(policy_path)
        child_env[_RUN_ENV] = run_id
        child_env[_MANIFEST_ENV] = manifest_hash
        child_env[_IMAGE_ENV] = os.environ.get(_IMAGE_ENV, "")
        completed = _call(
            invoke,
            [
                sys.executable, "-B", "tests/run_prompt_boundary_tests.py",
                "tests/test_workflow_postgres_live.py", "-q", "-p",
                "no:cacheprovider", "-p", "pg_validation.result", "--tb=short",
            ],
            env=child_env,
            timeout=600,
            cwd="/work",
        )
        test_stdout = completed.stdout
        test_stderr = completed.stderr
        try:
            payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
            passed = isinstance(payload, dict) and payload.get("status") == "tests_passed"
        except (OSError, UnicodeError, json.JSONDecodeError):
            passed = False
    except subprocess.SubprocessError as exc:
        test_stdout = exc.stdout
        test_stderr = exc.stderr
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        pass
    finally:
        if initialized:
            try:
                _call(
                    invoke,
                    ["pg_ctl", "-D", str(data_dir), "-w", "-t", "30", "stop"],
                    env=base_env,
                    timeout=30,
                )
                stop_status = "stopped"
            except (OSError, subprocess.SubprocessError):
                passed = False
                stop_status = "stop_failed"
        if _update_result_stop_status(Path(result_path), stop_status=stop_status) is False:
            passed = False
        if root.is_dir():
            try:
                _write_private_log(root / "pytest.stdout.log", test_stdout)
                _write_private_log(root / "pytest.stderr.log", test_stderr)
            except OSError:
                passed = False
        # The pytest plugin owns the structured payload.  Never replace it by
        # a permissive summary: the host launcher validates its allowlist and
        # identity before accepting or exporting evidence.
    return 0 if passed else RUN_FAILED


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        return USAGE_FAILED
    return run(args[0])


if __name__ == "__main__":
    raise SystemExit(main())
