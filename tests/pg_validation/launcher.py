"""Fail-closed launcher for one disposable PostgreSQL validation container."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import tempfile
from typing import Any, Callable

from .bundle import build_context


CONTAINER_REJECTION_REASON = "isolated_pg_container_rejected"
RUN_FAILED = 1
CLEANUP_FAILED = 2
_RUN_RE = re.compile(r"^[0-9a-f]{16}$")
_IMAGE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CID_RE = re.compile(r"^[0-9a-f]{64}$")
_RUN_LABEL = "stock-agent.validation.run"
_DOCKER_HOST = "unix:///var/run/docker.sock"
_SAFE_PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
_TMPFS_DESTINATIONS = {"/tmp", "/var/lib/postgresql/data"}
_EXPECTED_TMPFS = {
    "/tmp": "rw,nosuid,nodev,size=768m,mode=1777",
    "/var/lib/postgresql/data": (
        "rw,nosuid,nodev,size=768m,uid=999,gid=999,mode=0700"
    ),
}


def _container_reject() -> None:
    raise ValueError(CONTAINER_REJECTION_REASON)


def create_args(run_id: str, image_id: str) -> list[str]:
    """Return the complete fixed argv for creating the isolated container."""

    if not isinstance(run_id, str) or not _RUN_RE.fullmatch(run_id):
        raise ValueError("isolated_pg_run_identity_invalid")
    if not isinstance(image_id, str) or not _IMAGE_RE.fullmatch(image_id):
        raise ValueError("isolated_pg_image_identity_invalid")
    return [
        "docker",
        "create",
        "--name",
        f"stock-agent-pg-{run_id}",
        "--label",
        f"{_RUN_LABEL}={run_id}",
        "--network",
        "none",
        "--ipc",
        "private",
        "--restart",
        "no",
        "--user",
        "999:999",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--cpus",
        "2",
        "--memory",
        "2g",
        "--pids-limit",
        "256",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=768m,mode=1777",
        "--tmpfs",
        (
            "/var/lib/postgresql/data:rw,nosuid,nodev,size=768m,"
            "uid=999,gid=999,mode=0700"
        ),
        image_id,
        run_id,
    ]


def _empty(value: Any) -> bool:
    return value is None or value == [] or value == {}


def validate_container(info: Any, run_id: str, image_id: str) -> None:
    """Reject any inspected shape outside the fixed container isolation policy."""

    try:
        if (
            not isinstance(info, dict)
            or not isinstance(run_id, str)
            or not _RUN_RE.fullmatch(run_id)
            or not isinstance(image_id, str)
            or not _IMAGE_RE.fullmatch(image_id)
        ):
            _container_reject()
        config = info["Config"]
        host = info["HostConfig"]
        labels = config["Labels"]
        restart = host["RestartPolicy"]
        tmpfs = host["Tmpfs"]
        mounts = info["Mounts"]
        valid = (
            info["Image"] == image_id
            and config["User"] == "999:999"
            and isinstance(labels, dict)
            and labels.get(_RUN_LABEL) == run_id
            and host["NetworkMode"] == "none"
            and host["Privileged"] is False
            and _empty(host["Binds"])
            and _empty(host["PortBindings"])
            and host["PublishAllPorts"] is False
            and host["PidMode"] == ""
            and host["IpcMode"] == "private"
            and _empty(host["Devices"])
            and _empty(host["CapAdd"])
            and host["Memory"] == 2 * 1024**3
            and host["NanoCpus"] == 2 * 10**9
            and host["PidsLimit"] == 256
            and isinstance(restart, dict)
            and restart.get("Name") == "no"
            and isinstance(tmpfs, dict)
            and tmpfs == _EXPECTED_TMPFS
            and isinstance(mounts, list)
            and len(mounts) == 2
            and all(
                isinstance(mount, dict)
                and mount.get("Type") == "tmpfs"
                and mount.get("Destination") in _TMPFS_DESTINATIONS
                for mount in mounts
            )
            and {mount["Destination"] for mount in mounts} == _TMPFS_DESTINATIONS
        )
        if not valid:
            _container_reject()
    except ValueError:
        raise
    except (KeyError, TypeError):
        _container_reject()


def _docker_env(config_dir: Path) -> dict[str, str]:
    inherited_host = os.environ.get("DOCKER_HOST")
    inherited_context = os.environ.get("DOCKER_CONTEXT")
    if inherited_host and inherited_host != _DOCKER_HOST:
        raise ValueError("isolated_pg_docker_context_rejected")
    if inherited_context and inherited_context != "default":
        raise ValueError("isolated_pg_docker_context_rejected")
    return {
        "DOCKER_HOST": _DOCKER_HOST,
        "DOCKER_CONFIG": str(config_dir),
        "PATH": _SAFE_PATH,
    }


def _call(
    docker: Callable[..., subprocess.CompletedProcess[str]],
    argv: list[str],
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return docker(
        argv,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
        timeout=timeout,
        env=env,
    )


def _read_image_id(iidfile: Path) -> str:
    try:
        info = iidfile.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 128:
            raise ValueError
        raw = iidfile.read_text(encoding="ascii")
    except (OSError, UnicodeError, ValueError):
        raise ValueError("isolated_pg_image_identity_invalid") from None
    if raw.endswith("\n"):
        raw = raw[:-1]
    if not _IMAGE_RE.fullmatch(raw):
        raise ValueError("isolated_pg_image_identity_invalid")
    return raw


def _inspect(
    docker: Callable[..., subprocess.CompletedProcess[str]],
    cid: str,
    env: dict[str, str],
) -> dict[str, Any]:
    completed = _call(docker, ["docker", "inspect", cid], env, 60)
    try:
        payload = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError):
        _container_reject()
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        _container_reject()
    info = payload[0]
    if info.get("Id") != cid:
        _container_reject()
    return info


def _identity_matches(info: Any, cid: str, run_id: str) -> bool:
    try:
        return (
            isinstance(info, dict)
            and info.get("Id") == cid
            and info["Config"]["Labels"].get(_RUN_LABEL) == run_id
        )
    except (KeyError, TypeError, AttributeError):
        return False


def _valid_result(path: Path) -> bool:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 10 * 1024 * 1024:
            return False
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict)


def _prepare_result_dir(repo: Path, result_dir: Path) -> Path:
    root = repo.resolve(strict=True)
    requested = Path(result_dir)
    try:
        requested.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError("isolated_pg_result_directory_rejected")
    target = requested.resolve(strict=False)
    if target == root or not target.parent.is_dir():
        raise ValueError("isolated_pg_result_directory_rejected")
    if any(part in {"cache", "output"} for part in target.parent.parts):
        raise ValueError("isolated_pg_result_directory_rejected")
    target.mkdir(mode=0o700, exist_ok=False)
    return target


def run_validation(
    repo: Path,
    result_dir: Path,
    *,
    docker: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    """Run one isolated validation lifecycle and return zero only if fully clean."""

    try:
        root = Path(repo).resolve(strict=True)
        target = _prepare_result_dir(root, Path(result_dir))
    except (OSError, RuntimeError, TypeError, ValueError):
        return RUN_FAILED

    run_id = secrets.token_hex(8)
    cid: str | None = None
    identity_seen = False
    outcome = RUN_FAILED
    temporary_context: tempfile.TemporaryDirectory[str] | None = None
    try:
        temporary_context = tempfile.TemporaryDirectory(
            prefix=f"stock-agent-pg-{run_id}-"
        )
        workspace = Path(temporary_context.name)
        context = workspace / "context"
        docker_config = workspace / "docker-config"
        docker_config.mkdir(mode=0o700)
        env = _docker_env(docker_config)
        build_context(root, context)
        iidfile = workspace / "image.id"
        dockerfile = context / "tests/pg_validation/Dockerfile"
        build_args = [
            "docker",
            "build",
            "--platform",
            "linux/arm64",
            "--iidfile",
            str(iidfile),
            "--label",
            f"{_RUN_LABEL}={run_id}",
            "-f",
            str(dockerfile),
            str(context),
        ]
        _call(docker, build_args, env, 15 * 60)
        image_id = _read_image_id(iidfile)
        created = _call(docker, create_args(run_id, image_id), env, 60)
        raw_candidate = created.stdout
        if raw_candidate.endswith("\n"):
            raw_candidate = raw_candidate[:-1]
        candidate = raw_candidate
        if not _CID_RE.fullmatch(candidate):
            raise ValueError("isolated_pg_container_identity_invalid")
        cid = candidate
        info = _inspect(docker, cid, env)
        identity_seen = _identity_matches(info, cid, run_id)
        validate_container(info, run_id, image_id)
        _call(docker, ["docker", "start", cid], env, 60)
        waited = _call(docker, ["docker", "wait", cid], env, 10 * 60)
        try:
            container_exit = int(waited.stdout.strip())
        except (AttributeError, TypeError, ValueError):
            raise ValueError("isolated_pg_container_exit_invalid") from None
        if container_exit != 0:
            raise ValueError("isolated_pg_validation_failed")
        result_file = target / "result.json"
        _call(
            docker,
            ["docker", "cp", f"{cid}:/results/result.json", str(result_file)],
            env,
            60,
        )
        if not _valid_result(result_file):
            raise ValueError("isolated_pg_result_invalid")
        outcome = 0
    except (Exception, KeyboardInterrupt):
        outcome = RUN_FAILED
    finally:
        if cid is not None and identity_seen:
            try:
                # Revalidate identity immediately before the only destructive call.
                cleanup_info = _inspect(docker, cid, env)
                if not _identity_matches(cleanup_info, cid, run_id):
                    outcome = CLEANUP_FAILED
                else:
                    _call(docker, ["docker", "rm", "-f", cid], env, 60)
            except (Exception, KeyboardInterrupt):
                outcome = CLEANUP_FAILED
        elif cid is not None:
            outcome = CLEANUP_FAILED
        if temporary_context is not None:
            temporary_context.cleanup()
    return outcome


__all__ = [
    "CLEANUP_FAILED",
    "CONTAINER_REJECTION_REASON",
    "RUN_FAILED",
    "create_args",
    "run_validation",
    "validate_container",
]
