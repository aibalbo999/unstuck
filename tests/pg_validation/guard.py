"""Install a pre-connect guard on a loaded psycopg-compatible driver."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

from .policy import Endpoint, REJECTION_REASON


LIVE_POLICY_REJECTION_REASON = "isolated_pg_live_policy_rejected"
POLICY_ENV = "STOCK_AGENT_PG_VALIDATION_POLICY"
_RUN_RE = re.compile(r"^[0-9a-f]{16}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_PATH = Path("/opt/validation-manifest.json")
_MAX_POLICY_SIZE = 64 * 1024
_MAX_MANIFEST_SIZE = 1024 * 1024
_ENDPOINT_KEYS = {
    "host",
    "port",
    "dbname",
    "user",
    "connect_timeout",
    "sslmode",
}


@dataclass(frozen=True, slots=True)
class RuntimeEvidence:
    """Minimal runtime facts, injectable only for offline contract tests."""

    platform: str
    docker_marker: bool
    uid: int


def _runtime_evidence() -> RuntimeEvidence:
    return RuntimeEvidence(
        platform=sys.platform,
        docker_marker=Path("/.dockerenv").is_file(),
        uid=os.getuid(),
    )


def _policy_reject() -> None:
    raise ValueError(LIVE_POLICY_REJECTION_REASON)


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_fd(fd: int, maximum: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(64 * 1024, maximum + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > maximum:
            _policy_reject()


def _read_policy_at(root_fd: int, runtime: RuntimeEvidence) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    policy_fd = -1
    try:
        policy_fd = os.open("policy.json", flags, dir_fd=root_fd)
        before = os.fstat(policy_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_uid != runtime.uid
            or before.st_size > _MAX_POLICY_SIZE
        ):
            _policy_reject()
        raw = _read_fd(policy_fd, _MAX_POLICY_SIZE)
        if _signature(os.fstat(policy_fd)) != _signature(before):
            _policy_reject()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            _policy_reject()
        return payload
    finally:
        if policy_fd >= 0:
            os.close(policy_fd)


def _read_manifest_hash(
    manifest_path: Path,
    *,
    expected_uid: int,
) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        before_path = manifest_path.lstat()
        fd = os.open(manifest_path, flags)
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or _signature(before) != _signature(before_path)
            or stat.S_IMODE(before.st_mode) != 0o444
            or before.st_uid != expected_uid
            or before.st_size > _MAX_MANIFEST_SIZE
        ):
            _policy_reject()
        raw = _read_fd(fd, _MAX_MANIFEST_SIZE)
        after = os.fstat(fd)
        after_path = manifest_path.lstat()
        if (
            _signature(after) != _signature(before)
            or _signature(after_path) != _signature(before)
        ):
            _policy_reject()
        payload = json.loads(raw.decode("utf-8"))
        value = payload.get("manifest_sha256") if isinstance(payload, dict) else None
        if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
            _policy_reject()
        return value
    finally:
        if fd >= 0:
            os.close(fd)


def _endpoint_from_payload(payload: Any, run_id: str, identity: str) -> Endpoint:
    if not isinstance(payload, dict) or set(payload) != _ENDPOINT_KEYS:
        _policy_reject()
    expected_user = f"{identity}_{run_id}"
    endpoint = Endpoint(
        payload.get("host"),
        payload.get("port"),
        payload.get("dbname"),
        payload.get("user"),
    )
    try:
        if payload != endpoint.values() or endpoint.user != expected_user:
            _policy_reject()
    except (TypeError, ValueError):
        _policy_reject()
    return endpoint


def load_policy(
    path_value: Any,
    *,
    evidence: RuntimeEvidence | None = None,
    manifest_path: Path = _MANIFEST_PATH,
) -> tuple[Endpoint, Endpoint]:
    """Load an attested, run-scoped container policy without connection probes."""

    test_seam = evidence is not None
    runtime = _runtime_evidence() if evidence is None else evidence
    root_fd = -1
    try:
        if (
            not isinstance(runtime, RuntimeEvidence)
            or runtime.platform != "linux"
            or runtime.docker_marker is not True
            or isinstance(runtime.uid, bool)
            or not isinstance(runtime.uid, int)
            or runtime.uid <= 0
            or not isinstance(path_value, str)
        ):
            _policy_reject()
        match = re.fullmatch(
            r"/tmp/pg-validation-([0-9a-f]{16})/policy\.json", path_value
        )
        if match is None:
            _policy_reject()
        requested_manifest = Path(manifest_path)
        if not test_seam and requested_manifest != _MANIFEST_PATH:
            _policy_reject()
        run_id = match.group(1)
        root = Path(f"/tmp/pg-validation-{run_id}")
        root_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        root_fd = os.open(root, root_flags)
        root_info = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(root_info.st_mode)
            or stat.S_IMODE(root_info.st_mode) != 0o700
            or root_info.st_uid != runtime.uid
        ):
            _policy_reject()
        payload = _read_policy_at(root_fd, runtime)
        expected_manifest_uid = runtime.uid if test_seam else 0
        manifest_hash = _read_manifest_hash(
            requested_manifest,
            expected_uid=expected_manifest_uid,
        )
        if (
            not isinstance(payload, dict)
            or set(payload) != {"run_id", "manifest_sha256", "endpoints"}
            or payload.get("run_id") != run_id
            or not _RUN_RE.fullmatch(payload["run_id"])
            or not isinstance(payload.get("manifest_sha256"), str)
            or not _HASH_RE.fullmatch(payload["manifest_sha256"])
            or payload["manifest_sha256"] != manifest_hash
            or not isinstance(payload.get("endpoints"), dict)
            or set(payload["endpoints"]) != {"owner", "app"}
        ):
            _policy_reject()
        owner = _endpoint_from_payload(payload["endpoints"]["owner"], run_id, "owner")
        app = _endpoint_from_payload(payload["endpoints"]["app"], run_id, "app")
        return owner, app
    except ValueError as exc:
        if str(exc) == LIVE_POLICY_REJECTION_REASON:
            raise
        _policy_reject()
    except (KeyError, OSError, TypeError, UnicodeError):
        _policy_reject()
    finally:
        if root_fd >= 0:
            os.close(root_fd)


def _reject() -> None:
    raise ValueError(REJECTION_REASON)


def install(
    driver: Any,
    endpoints: Any = (),
) -> Any:
    """Patch sync, async, and top-level driver entrypoints before connecting.

    An empty endpoint policy means default deny. The guard only parses and
    compares conninfo; it never probes the database for availability.
    """

    policy_state = getattr(driver, "__pg_validation_policy_state__", None)
    if not isinstance(policy_state, dict):
        policy_state = {"endpoints": ()}
        setattr(driver, "__pg_validation_policy_state__", policy_state)
    policy_state["endpoints"] = tuple(endpoints or ())

    sync_connect = driver.Connection.connect.__func__
    async_connect = driver.AsyncConnection.connect.__func__
    top_connect = getattr(driver, "connect", None)
    while getattr(sync_connect, "__pg_validation_wrapper__", False):
        sync_connect = sync_connect.__pg_validation_original__
    while getattr(async_connect, "__pg_validation_wrapper__", False):
        async_connect = async_connect.__pg_validation_original__
    while getattr(top_connect, "__pg_validation_wrapper__", False):
        top_connect = top_connect.__pg_validation_original__

    def check(conninfo: Any, kwargs: dict[str, Any]) -> None:
        if any(name.startswith("PG") for name in os.environ):
            _reject()
        for endpoint in policy_state["endpoints"]:
            try:
                endpoint.validate(conninfo, kwargs)
                return
            except (TypeError, ValueError):
                pass
        _reject()

    def checked_sync(cls: Any, conninfo: Any = "", **kwargs: Any) -> Any:
        check(conninfo, kwargs)
        return sync_connect(cls, conninfo, **kwargs)

    async def checked_async(cls: Any, conninfo: Any = "", **kwargs: Any) -> Any:
        check(conninfo, kwargs)
        return await async_connect(cls, conninfo, **kwargs)

    def checked_top(conninfo: Any = "", **kwargs: Any) -> Any:
        check(conninfo, kwargs)
        return top_connect(conninfo, **kwargs)

    checked_sync.__pg_validation_wrapper__ = True
    checked_sync.__pg_validation_original__ = sync_connect
    checked_async.__pg_validation_wrapper__ = True
    checked_async.__pg_validation_original__ = async_connect
    checked_top.__pg_validation_wrapper__ = True
    checked_top.__pg_validation_original__ = top_connect

    driver.Connection.connect = classmethod(checked_sync)
    driver.AsyncConnection.connect = classmethod(checked_async)
    driver.connect = checked_top
    return driver


install_connection_guard = install

__all__ = [
    "LIVE_POLICY_REJECTION_REASON",
    "POLICY_ENV",
    "RuntimeEvidence",
    "install",
    "install_connection_guard",
    "load_policy",
]
