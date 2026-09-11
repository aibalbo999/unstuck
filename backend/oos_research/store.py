"""Filesystem-only immutable OOS study store."""

from __future__ import annotations

import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_bytes, sha256_bytes
from .manifest import manifest_hash, validate_manifest
from .records import validate_record


class StoreError(RuntimeError):
    pass


_FORBIDDEN_NAMES = {"backend", "cache", "output", ".git", "artifacts", "reports"}


def _read_regular(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("evidence path is not a regular file")
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _safe_root(root: str | os.PathLike[str]) -> Path:
    if not root:
        raise StoreError("study root must be explicit")
    raw = Path(root)
    if not raw.is_absolute() or ".." in raw.parts:
        raise StoreError("study root must be an absolute, normalized path")
    cursor = raw
    while cursor != cursor.parent:
        if cursor.is_symlink():
            raise StoreError("study root may not contain symlink components")
        cursor = cursor.parent
    if raw.is_symlink():
        raise StoreError("study root may not be a symlink")
    path = raw.expanduser().resolve(strict=False)
    if path == Path(path.anchor) or path.name in _FORBIDDEN_NAMES:
        raise StoreError("unsafe study root")
    if any(part in _FORBIDDEN_NAMES for part in path.parts):
        raise StoreError("study root may not be a production/cache path")
    if any((ancestor / ".git").is_dir() for ancestor in (path, *path.parents)):
        raise StoreError("study root may not be inside a repository")
    return path


class StudyStore:
    """A newly-created root containing exclusive JSON records and blobs."""

    def __init__(self, root: str | os.PathLike[str], *, study_id: str, create: bool = True):
        self.root = _safe_root(root)
        if not study_id or "/" in study_id or "\\" in study_id or ".." in study_id:
            raise StoreError("unsafe study_id")
        if self.root.exists() and not self.root.is_dir():
            raise StoreError("study root is not a directory")
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        elif not self.root.is_dir():
            raise StoreError("study root does not exist")
        self.study_id = study_id
        self.records_dir = self.root / "records"
        self.blobs_dir = self.root / "blobs"
        marker = self.root / ".oos-study"
        marker_data = f"oos-study.v1:{study_id}\n".encode("utf-8")
        if create:
            self.records_dir.mkdir(exist_ok=True)
            self.blobs_dir.mkdir(exist_ok=True)
        elif not self.records_dir.is_dir() or not self.blobs_dir.is_dir() or not marker.is_file():
            raise StoreError("existing study layout is incomplete")
        if self.records_dir.is_symlink() or self.blobs_dir.is_symlink():
            raise StoreError("study evidence directories may not be symlinks")
        if marker.exists():
            try:
                marker_matches = not marker.is_symlink() and _read_regular(marker) == marker_data
            except OSError:
                marker_matches = False
            if not marker_matches:
                raise StoreError("study root belongs to a different study")
        elif create:
            self._exclusive_write(marker, marker_data)
        else:
            raise StoreError("existing study marker is missing")

    def _record_path(self, record_id: str) -> Path:
        if not record_id or "/" in record_id or "\\" in record_id or ".." in record_id:
            raise StoreError("unsafe record_id")
        return self.records_dir / f"{record_id}.json"

    def register_manifest(self, manifest: Mapping[str, Any]) -> str:
        validate_manifest(manifest)
        if manifest["study_id"] != self.study_id:
            raise StoreError("manifest study_id does not match store")
        path = self._record_path("manifest")
        data = canonical_bytes(dict(manifest))
        if path.exists():
            try:
                existing = _read_regular(path)
            except OSError as exc:
                raise StoreError("manifest evidence is unsafe") from exc
            if existing != data:
                raise StoreError("manifest already exists with different content")
            return manifest_hash(manifest)
        self._exclusive_write(path, data)
        return manifest_hash(manifest)

    def put_blob(self, data: bytes, *, digest: str | None = None) -> str:
        actual = sha256_bytes(data)
        if digest is not None and digest != actual:
            raise StoreError("blob digest mismatch")
        path = self.blobs_dir / actual
        if path.exists():
            if path.is_symlink() or self.read_blob(actual) != data:
                raise StoreError("content-addressed blob collision")
            return actual
        self._exclusive_write(path, data)
        return actual

    def read_blob(self, digest: str, *, size_bytes: int | None = None) -> bytes:
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise StoreError("invalid blob digest")
        path = self.blobs_dir / digest
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except (FileNotFoundError, OSError) as exc:
            raise StoreError("blob is missing or unsafe") from exc
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise StoreError("blob is not a regular file")
            chunks = []
            while chunk := os.read(fd, 1024 * 1024):
                chunks.append(chunk)
        finally:
            os.close(fd)
        data = b"".join(chunks)
        if sha256_bytes(data) != digest:
            raise StoreError("blob digest mismatch")
        if size_bytes is not None and (isinstance(size_bytes, bool) or size_bytes != len(data)):
            raise StoreError("blob size mismatch")
        return data

    def put_record(self, record: Mapping[str, Any]) -> None:
        validate_record(record)
        path = self._record_path(str(record["record_id"]))
        data = canonical_bytes(dict(record))
        if path.exists():
            try:
                existing = _read_regular(path)
            except OSError as exc:
                raise StoreError("record evidence is unsafe") from exc
            if existing != data:
                raise StoreError("record already exists with different content")
            return
        self._exclusive_write(path, data)

    def read_record(self, record_id: str) -> dict[str, Any]:
        path = self._record_path(record_id)
        try:
            payload = json.loads(_read_regular(path))
        except FileNotFoundError as exc:
            raise StoreError("record is missing") from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StoreError("record is malformed") from exc
        validate_record(payload)
        return payload

    def list_records(self) -> list[str]:
        records = []
        for path in sorted(self.records_dir.glob("*.json")):
            self.read_record(path.stem) if path.stem != "manifest" else self._validate_manifest_file(path)
            records.append(path.stem)
        return records

    def _validate_manifest_file(self, path: Path) -> None:
        try:
            payload = json.loads(_read_regular(path))
            validate_manifest(payload)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise StoreError("manifest is missing or corrupt") from exc

    @staticmethod
    def _exclusive_write(path: Path, data: bytes) -> None:
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
        try:
            with tmp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp, path)
            except FileExistsError as exc:
                raise StoreError("immutable write conflict") from exc
            finally:
                tmp.unlink(missing_ok=True)
        finally:
            tmp.unlink(missing_ok=True)
