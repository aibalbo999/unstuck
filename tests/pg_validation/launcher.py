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
from .result import BASE_IMAGE, EXPECTED_CASES, MAX_RESULT_SIZE, RESULT_SCHEMA


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
        "--env",
        f"STOCK_AGENT_PG_VALIDATION_IMAGE_ID={image_id}",
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
            and host["UTSMode"] in {"", "private"}
            and host["UsernsMode"] in {"", "private"}
            and host["CgroupnsMode"] in {"", "private"}
            and _empty(host["Devices"])
            and _empty(host["DeviceRequests"])
            and _empty(host["CapAdd"])
            and host["CapDrop"] == ["ALL"]
            and host["SecurityOpt"] == ["no-new-privileges:true"]
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


def _parse_cid(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    if raw.endswith("\n"):
        raw = raw[:-1]
    return raw if _CID_RE.fullmatch(raw) else None


def _read_cidfile(cidfile: Path) -> str | None:
    try:
        info = cidfile.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 128:
            return None
        return _parse_cid(cidfile.read_text(encoding="ascii"))
    except (OSError, UnicodeError):
        return None


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


def _validate_result_payload(
    payload: Any,
    *,
    run_id: str,
    image_id: str,
    manifest_sha256: str,
    allow_final: bool = False,
) -> bool:
    """Validate the exact structured result schema before accepting evidence."""

    allowed = {
        "schema", "run_id", "manifest_sha256", "base_image", "derived_image",
        "network", "socket", "paths", "status", "collected", "expected",
        "versions", "phases", "counts", "assertions", "exit_code", "server_stop_status",
    }
    if allow_final:
        allowed.add("cleanup_status")
    if not isinstance(payload, dict) or set(payload) != allowed:
        return False
    if (
        payload.get("schema") != RESULT_SCHEMA
        or payload.get("run_id") != run_id
        or payload.get("manifest_sha256") != manifest_sha256
        or payload.get("base_image") != BASE_IMAGE
        or payload.get("derived_image") != image_id
        or payload.get("network") != "none"
        or payload.get("socket") != "unix-local-only"
        or payload.get("paths") != "tmpfs-and-container-layer-only"
    ):
        return False
    versions = payload.get("versions")
    if (
        not isinstance(versions, dict)
        or set(versions) != {"python", "postgres", "psycopg", "libpq"}
        or any(
            not isinstance(value, str)
            or not value
            or len(value) > 128
            or not all(character.isalnum() or character in "._+:-" for character in value)
            for value in versions.values()
        )
    ):
        return False
    expected = payload.get("expected")
    collected = payload.get("collected")
    if expected != sorted(EXPECTED_CASES) or collected != sorted(EXPECTED_CASES):
        return False
    if not isinstance(payload.get("phases"), list):
        return False
    phase_keys: list[tuple[str, str]] = []
    for item in payload["phases"]:
        if not isinstance(item, dict) or set(item) != {"nodeid", "when", "outcome"}:
            return False
        if item["nodeid"] not in EXPECTED_CASES or item["when"] not in {"setup", "call", "teardown"}:
            return False
        if item["outcome"] != "passed":
            return False
        phase_keys.append((item["nodeid"], item["when"]))
    expected_phase_keys = {
        (node, phase)
        for node in EXPECTED_CASES
        for phase in ("setup", "call", "teardown")
    }
    if len(phase_keys) != len(set(phase_keys)) or set(phase_keys) != expected_phase_keys:
        return False
    counts = payload.get("counts")
    if (
        not isinstance(counts, dict)
        or set(counts) != {"expected", "collected", "reports", "collection_errors"}
        or counts != {
            "expected": len(EXPECTED_CASES),
            "collected": len(EXPECTED_CASES),
            "reports": len(EXPECTED_CASES) * 3,
            "collection_errors": 0,
        }
        or len(payload["phases"]) != len(EXPECTED_CASES) * 3
    ):
        return False
    assertions = payload.get("assertions")
    if assertions != {
        "native_external_endpoint": "TEST-NET-only",
        "host_network": "rejected",
        "sqlite_checkpoint": "absent",
    }:
        return False
    if type(payload.get("exit_code")) is not int or payload["exit_code"] != 0:
        return False
    if payload.get("server_stop_status") != "stopped":
        return False
    if payload.get("status") != ("passed" if allow_final else "tests_passed"):
        return False
    if allow_final and payload.get("cleanup_status") != "removed":
        return False
    return True


def _read_result(path: Path) -> dict[str, Any] | None:
    fd = -1
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RESULT_SIZE:
            return None
        expected = _result_signature(info)
        fd = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        if _result_signature(os.fstat(fd)) != expected:
            return None
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(64 * 1024, MAX_RESULT_SIZE + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_RESULT_SIZE:
                return None
        if _result_signature(os.fstat(fd)) != expected:
            return None
        current = path.lstat()
        if _result_signature(current) != expected:
            return None
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    finally:
        if fd >= 0:
            os.close(fd)
    return payload if isinstance(payload, dict) else None


def _result_signature(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _write_final_result(path: Path, payload: dict[str, Any], *, status: str, cleanup_status: str) -> bool:
    final = dict(payload)
    final["status"] = status
    final["cleanup_status"] = cleanup_status
    encoded = (json.dumps(final, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_RESULT_SIZE:
        return False
    temp: Path | None = None
    fd = -1
    try:
        parent = path.parent
        parent_info = parent.lstat()
        if not stat.S_ISDIR(parent_info.st_mode):
            return False
        try:
            destination = path.lstat()
        except FileNotFoundError:
            destination_signature = None
        else:
            if not stat.S_ISREG(destination.st_mode):
                return False
            destination_signature = _result_signature(destination)
        temp = parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        fd = os.open(temp, flags, 0o600)
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                return False
            view = view[written:]
        os.fsync(fd)
        os.close(fd)
        fd = -1
        try:
            current = path.lstat()
        except FileNotFoundError:
            current_signature = None
        else:
            if not stat.S_ISREG(current.st_mode):
                return False
            current_signature = _result_signature(current)
        if current_signature != destination_signature:
            return False
        os.replace(temp, path)
        temp = None
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
    except OSError:
        return False
    finally:
        if fd >= 0:
            os.close(fd)
        if temp is not None:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass
    return True


def _valid_result(path: Path, *, run_id: str, image_id: str, manifest_sha256: str) -> bool:
    payload = _read_result(path)
    return payload is not None and _validate_result_payload(
        payload,
        run_id=run_id,
        image_id=image_id,
        manifest_sha256=manifest_sha256,
    )


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
    create_attempted = False
    outcome = RUN_FAILED
    env: dict[str, str] | None = None
    image_id: str | None = None
    manifest_sha256: str | None = None
    staged_result: Path | None = None
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
        manifest_payload = json.loads((context / "manifest.json").read_text(encoding="utf-8"))
        manifest_sha256 = manifest_payload["manifest_sha256"]
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
        cidfile = workspace / "container.id"
        create_command = create_args(run_id, image_id)
        create_command[2:2] = ["--cidfile", str(cidfile)]
        create_attempted = True
        try:
            created = _call(docker, create_command, env, 60)
        except (Exception, KeyboardInterrupt):
            cid = _read_cidfile(cidfile)
            raise
        stdout_cid = _parse_cid(created.stdout)
        file_cid = _read_cidfile(cidfile)
        if stdout_cid is not None and file_cid is not None and stdout_cid != file_cid:
            cid = file_cid
            raise ValueError("isolated_pg_container_identity_invalid")
        cid = stdout_cid or file_cid
        if cid is None:
            raise ValueError("isolated_pg_container_identity_invalid")
        info = _inspect(docker, cid, env)
        validate_container(info, run_id, image_id)
        _call(docker, ["docker", "start", cid], env, 60)
        waited = _call(docker, ["docker", "wait", cid], env, 10 * 60)
        try:
            container_exit = int(waited.stdout.strip())
        except (AttributeError, TypeError, ValueError):
            raise ValueError("isolated_pg_container_exit_invalid") from None
        if container_exit != 0:
            raise ValueError("isolated_pg_validation_failed")
        staged_result = workspace / "container-result.json"
        _call(
            docker,
            ["docker", "cp", f"{cid}:/results/result.json", str(staged_result)],
            env,
            60,
        )
        if not _valid_result(
            staged_result,
            run_id=run_id,
            image_id=image_id,
            manifest_sha256=manifest_sha256,
        ):
            raise ValueError("isolated_pg_result_invalid")
        outcome = 0
    except (Exception, KeyboardInterrupt):
        outcome = RUN_FAILED
    finally:
        cleanup_ok = cid is not None and env is not None
        if cid is not None and env is not None:
            try:
                # Revalidate identity immediately before the only destructive call.
                cleanup_info = _inspect(docker, cid, env)
                if not _identity_matches(cleanup_info, cid, run_id):
                    outcome = CLEANUP_FAILED
                    cleanup_ok = False
                else:
                    _call(docker, ["docker", "rm", "-f", cid], env, 60)
            except (Exception, KeyboardInterrupt):
                outcome = CLEANUP_FAILED
                cleanup_ok = False
        elif create_attempted:
            outcome = CLEANUP_FAILED
            cleanup_ok = False
        if staged_result is not None and image_id is not None and manifest_sha256 is not None:
            payload = _read_result(staged_result)
            source_valid = payload is not None and _validate_result_payload(
                payload,
                run_id=run_id,
                image_id=image_id,
                manifest_sha256=manifest_sha256,
                allow_final=False,
            )
            if source_valid:
                if outcome == 0 and cleanup_ok:
                    if not _write_final_result(
                        target / "result.json",
                        payload,
                        status="passed",
                        cleanup_status="removed",
                    ):
                        outcome = RUN_FAILED
                elif outcome == CLEANUP_FAILED:
                    _write_final_result(
                        target / "result.json",
                        payload,
                        status="cleanup_failed",
                        cleanup_status="failed",
                    )
        if temporary_context is not None:
            temporary_context.cleanup()
    return outcome


__all__ = [
    "CLEANUP_FAILED",
    "CONTAINER_REJECTION_REASON",
    "RUN_FAILED",
    "create_args",
    "_validate_result_payload",
    "run_validation",
    "validate_container",
]
