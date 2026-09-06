"""Build a minimal, immutable-by-verification Docker context from Git's index."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
from typing import Any


EXACT = {"backend/requirements.lock", "backend/model_routes.json"}
DENIED = {"cache", "output", ".git", ".venv", "__pycache__"}
REJECTION_REASON = "isolated_pg_bundle_rejected"


def _reject() -> None:
    raise ValueError(REJECTION_REASON)


def allowed_path(name: str) -> bool:
    """Return whether an index path is part of the explicit validation bundle."""

    if not isinstance(name, str):
        return False
    p = PurePosixPath(name)
    if (
        not p.parts
        or p.is_absolute()
        or ".." in p.parts
        or set(p.parts) & DENIED
        or any(part.startswith(".env") for part in p.parts)
    ):
        return False
    if name in EXACT:
        return True
    if p.parts[0] == "backend" and p.suffix == ".py":
        return True
    if name.startswith("backend/templates/") and p.suffix in {".j2", ".html"}:
        return True
    if p.parts[0] == "prompts" and p.suffix in {".md", ".json", ".yaml"}:
        return True
    if name.startswith("tests/pg_validation/"):
        return p.suffix in {".py", ".lock"} or p.name == "Dockerfile"
    return p.parts[0] == "tests" and len(p.parts) == 2 and p.suffix == ".py"


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_verified(source: Path, repo: Path) -> bytes:
    try:
        resolved = source.resolve(strict=True)
        resolved.relative_to(repo)
        before = source.lstat()
    except (OSError, RuntimeError, ValueError):
        _reject()
    if resolved != source or not stat.S_ISREG(before.st_mode):
        _reject()

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        fd = os.open(source, flags)
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or _signature(before) != _signature(opened):
            _reject()
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after_open = os.fstat(fd)
        after_path = source.lstat()
        expected = _signature(before)
        if _signature(after_open) != expected or _signature(after_path) != expected:
            _reject()
        data = b"".join(chunks)
        if len(data) != before.st_size:
            _reject()
        return data
    except ValueError:
        raise
    except OSError:
        _reject()
    finally:
        if fd >= 0:
            os.close(fd)


def _write_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    fd = -1
    try:
        fd = os.open(path, flags, 0o600)
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                _reject()
            view = view[written:]
    except ValueError:
        raise
    except OSError:
        _reject()
    finally:
        if fd >= 0:
            os.close(fd)


def _index_paths(repo: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z"],
            check=True,
            capture_output=True,
            text=False,
            timeout=30,
        )
        raw_names = completed.stdout.split(b"\0")
    except (OSError, subprocess.SubprocessError):
        _reject()
    selected: list[str] = []
    for raw in raw_names:
        if not raw:
            continue
        try:
            name = raw.decode("utf-8")
        except UnicodeDecodeError:
            _reject()
        if allowed_path(name):
            selected.append(name)
    return sorted(set(selected))


def build_context(repo: Path, destination: Path) -> dict[str, Any]:
    """Copy allowed tracked files to a new out-of-tree context and manifest it."""

    try:
        root = Path(repo).resolve(strict=True)
        if not root.is_dir():
            _reject()
        requested = Path(destination)
        try:
            requested.lstat()
        except FileNotFoundError:
            pass
        else:
            _reject()
        target = requested.resolve(strict=False)
        if target == root or target.is_relative_to(root):
            _reject()
        if not target.parent.is_dir():
            _reject()
    except ValueError:
        raise
    except (OSError, RuntimeError, TypeError):
        _reject()

    created = False
    try:
        target.mkdir(mode=0o700, exist_ok=False)
        created = True
        entries: list[dict[str, str | int]] = []
        for name in _index_paths(root):
            source = root.joinpath(*PurePosixPath(name).parts)
            data = _read_verified(source, root)
            output = target.joinpath(*PurePosixPath(name).parts)
            output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _write_exclusive(output, data)
            entries.append(
                {
                    "path": name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        encoded_entries = json.dumps(
            entries, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        manifest: dict[str, Any] = {
            "files": entries,
            "manifest_sha256": hashlib.sha256(encoded_entries).hexdigest(),
        }
        manifest_bytes = (
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        _write_exclusive(target / "manifest.json", manifest_bytes)
        return manifest
    except Exception:
        if created:
            shutil.rmtree(target, ignore_errors=True)
        raise


__all__ = ["DENIED", "EXACT", "allowed_path", "build_context"]
