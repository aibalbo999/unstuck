"""Report content storage interfaces and local implementations."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable

from ._local_file_operations import (
    atomic_write,
    exclusive_storage_lock,
    fsync_directory,
    is_internal_storage_file,
    metadata_path,
)
from ._report_keys import (
    content_type_for_key, is_sha256_hexdigest, normalize_report_key, validate_report_prefix,
)


@dataclass(frozen=True)
class StoredReport:
    key: str
    size: int
    content_type: str
    updated_at: datetime

@dataclass(frozen=True)
class StoredReportContent:
    metadata: StoredReport
    content: bytes

@runtime_checkable
class ReportStorage(Protocol):
    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport: ...

    def get_report(self, key: str) -> StoredReportContent | None: ...

    def delete_report(self, key: str) -> bool: ...

    def exists(self, key: str) -> bool: ...

    def list_reports(self, *, prefix: str = "") -> list[StoredReport]: ...


def _utc_datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


class LocalFileStorage:
    def __init__(self, root: str | Path):
        root_path = Path(root).expanduser()
        if root_path.is_symlink():
            raise ValueError("report storage root must not be a symlink")
        root_path.mkdir(parents=True, exist_ok=True)
        if root_path.is_symlink():
            raise ValueError("report storage root must not be a symlink")
        self._root = root_path.resolve(strict=True)

    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport:
        payload = bytes(content)
        content_digest = hashlib.sha256(payload).hexdigest()
        with exclusive_storage_lock(self._root):
            normalized, target = self._target(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            self._assert_no_symlink_components(normalized)
            sidecar_path = metadata_path(target)
            if sidecar_path.is_symlink():
                raise ValueError("report metadata path must not be a symlink")

            previous_sidecar = self._read_existing_sidecar(sidecar_path)
            metadata_payload = json.dumps(
                {"content_type": content_type, "sha256": content_digest},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            atomic_write(sidecar_path, metadata_payload)
            try:
                atomic_write(target, payload)
            except Exception:
                self._restore_sidecar(sidecar_path, previous_sidecar)
                raise

            return self._metadata(normalized, target, content_type=content_type)

    def get_report(self, key: str) -> StoredReportContent | None:
        with exclusive_storage_lock(self._root):
            normalized, target = self._target(key)
            try:
                with target.open("rb") as report_file:
                    content = report_file.read()
                    stat_result = os.fstat(report_file.fileno())
            except (FileNotFoundError, IsADirectoryError):
                return None
            return StoredReportContent(
                metadata=self._metadata(
                    normalized,
                    target,
                    stat_result=stat_result,
                    content_digest=hashlib.sha256(content).hexdigest(),
                ),
                content=content,
            )

    def delete_report(self, key: str) -> bool:
        with exclusive_storage_lock(self._root):
            _, target = self._target(key)
            sidecar_path = metadata_path(target)
            if sidecar_path.is_symlink():
                raise ValueError("report metadata path must not be a symlink")
            try:
                target.unlink()
            except FileNotFoundError:
                return False
            sidecar_path.unlink(missing_ok=True)
            fsync_directory(target.parent)
            return True

    def exists(self, key: str) -> bool:
        with exclusive_storage_lock(self._root):
            _, target = self._target(key)
            return target.is_file()

    def list_reports(self, *, prefix: str = "") -> list[StoredReport]:
        validated_prefix = validate_report_prefix(prefix)
        with exclusive_storage_lock(self._root):
            reports: list[StoredReport] = []
            for path in self._root.rglob("*"):
                if not path.is_file() or is_internal_storage_file(path):
                    continue
                key = path.relative_to(self._root).as_posix()
                if not key.startswith(validated_prefix):
                    continue
                try:
                    normalized, target = self._target(key)
                    reports.append(self._metadata(normalized, target))
                except (FileNotFoundError, ValueError):
                    continue
            return sorted(reports, key=lambda report: report.key)

    def _target(self, key: str) -> tuple[str, Path]:
        normalized = normalize_report_key(key)
        if any(
            is_internal_storage_file(Path(component))
            for component in PurePosixPath(normalized).parts
        ):
            raise ValueError("report key contains a reserved storage name")
        self._assert_no_symlink_components(normalized)
        return normalized, self._root / normalized

    def _assert_no_symlink_components(self, normalized: str) -> None:
        current = self._root
        for component in PurePosixPath(normalized).parts:
            current /= component
            if current.is_symlink():
                raise ValueError("report path must not contain symlinks")

    def _metadata(
        self,
        key: str,
        target: Path,
        *,
        stat_result=None,
        content_type: str | None = None,
        content_digest: str | None = None,
    ) -> StoredReport:
        stat_result = stat_result or target.stat()
        return StoredReport(
            key=key,
            size=stat_result.st_size,
            content_type=(
                content_type
                if content_type is not None
                else self._read_content_type(key, target, content_digest=content_digest)
            ),
            updated_at=_utc_datetime(stat_result.st_mtime),
        )

    @staticmethod
    def _read_content_type(
        key: str, target: Path, *, content_digest: str | None = None
    ) -> str:
        sidecar_path = metadata_path(target)
        if sidecar_path.is_symlink():
            return content_type_for_key(key)
        try:
            metadata = json.loads(sidecar_path.read_text(encoding="utf-8"))
            content_type = metadata.get("content_type")
            expected_digest = metadata.get("sha256")
        except (
            AttributeError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ):
            return content_type_for_key(key)
        if content_digest is None:
            try:
                content_digest = hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError:
                return content_type_for_key(key)
        digest_matches = is_sha256_hexdigest(expected_digest) and hmac.compare_digest(
            expected_digest,
            content_digest,
        )
        if digest_matches and isinstance(content_type, str) and content_type:
            return content_type
        return content_type_for_key(key)

    @staticmethod
    def _read_existing_sidecar(sidecar_path: Path) -> bytes | None:
        try:
            return sidecar_path.read_bytes()
        except FileNotFoundError:
            return None

    @staticmethod
    def _restore_sidecar(sidecar_path: Path, previous: bytes | None) -> None:
        if previous is None:
            sidecar_path.unlink(missing_ok=True)
            fsync_directory(sidecar_path.parent)
        else:
            atomic_write(sidecar_path, previous)


from .memory_report_storage import InMemoryStorage


__all__ = [
    "InMemoryStorage",
    "LocalFileStorage",
    "ReportStorage",
    "StoredReport",
    "StoredReportContent",
    "normalize_report_key",
]
