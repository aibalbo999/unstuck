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
    if name.startswith("backend/prompts/") and p.suffix in {".md", ".json", ".yaml"}:
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


def _read_verified(repo_fd: int, name: str) -> bytes:
    path = PurePosixPath(name)
    if not allowed_path(name) or not path.parts:
        _reject()

    common_flags = getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | common_flags
    file_flags = os.O_RDONLY | common_flags
    current_fd = repo_fd
    opened_directories: list[int] = []
    directory_chain: list[tuple[int, str, int, tuple[int, int, int, int, int, int]]] = []
    file_fd = -1
    try:
        for part in path.parts[:-1]:
            before_directory = os.stat(
                part, dir_fd=current_fd, follow_symlinks=False
            )
            if not stat.S_ISDIR(before_directory.st_mode):
                _reject()
            child_fd = os.open(part, directory_flags, dir_fd=current_fd)
            opened_directories.append(child_fd)
            opened_directory = os.fstat(child_fd)
            if (
                not stat.S_ISDIR(opened_directory.st_mode)
                or _signature(before_directory) != _signature(opened_directory)
            ):
                _reject()
            directory_chain.append(
                (current_fd, part, child_fd, _signature(before_directory))
            )
            current_fd = child_fd

        leaf = path.parts[-1]
        before = os.stat(leaf, dir_fd=current_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            _reject()
        file_fd = os.open(leaf, file_flags, dir_fd=current_fd)
        opened = os.fstat(file_fd)
        if not stat.S_ISREG(opened.st_mode) or _signature(before) != _signature(opened):
            _reject()
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after_open = os.fstat(file_fd)
        after_path = os.stat(leaf, dir_fd=current_fd, follow_symlinks=False)
        expected = _signature(before)
        if _signature(after_open) != expected or _signature(after_path) != expected:
            _reject()
        for parent_fd, part, child_fd, directory_signature in reversed(
            directory_chain
        ):
            after_directory = os.stat(
                part, dir_fd=parent_fd, follow_symlinks=False
            )
            if (
                _signature(os.fstat(child_fd)) != directory_signature
                or _signature(after_directory) != directory_signature
            ):
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
        if file_fd >= 0:
            os.close(file_fd)
        for directory_fd in reversed(opened_directories):
            os.close(directory_fd)


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
    repo_fd = -1
    try:
        target.mkdir(mode=0o700, exist_ok=False)
        created = True
        root_before = root.lstat()
        root_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        repo_fd = os.open(root, root_flags)
        root_opened = os.fstat(repo_fd)
        if (
            not stat.S_ISDIR(root_opened.st_mode)
            or _signature(root_before) != _signature(root_opened)
        ):
            _reject()
        entries: list[dict[str, str | int]] = []
        for name in _index_paths(root):
            data = _read_verified(repo_fd, name)
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
        if (
            _signature(os.fstat(repo_fd)) != _signature(root_before)
            or _signature(root.lstat()) != _signature(root_before)
        ):
            _reject()
        return manifest
    except Exception:
        if created:
            shutil.rmtree(target, ignore_errors=True)
        raise
    finally:
        if repo_fd >= 0:
            os.close(repo_fd)


__all__ = ["DENIED", "EXACT", "allowed_path", "build_context"]
