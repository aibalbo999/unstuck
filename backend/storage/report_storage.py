"""Report content storage interfaces and local implementations."""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Protocol, runtime_checkable


_STANDARD_CONTENT_TYPES = {
    ".htm": "text/html",
    ".html": "text/html",
    ".json": "application/json",
    ".markdown": "text/markdown",
    ".md": "text/markdown",
}


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
    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport:
        ...

    def get_report(self, key: str) -> StoredReportContent | None:
        ...

    def delete_report(self, key: str) -> bool:
        ...

    def exists(self, key: str) -> bool:
        ...

    def list_reports(self, *, prefix: str = "") -> list[StoredReport]:
        ...


def normalize_report_key(key: str) -> str:
    """Return a portable relative report key or reject an unsafe path."""
    if not isinstance(key, str):
        raise TypeError("report key must be a string")
    if not key:
        raise ValueError("report key must not be empty")
    if "\\" in key:
        raise ValueError("report key must use forward slashes")
    if "\x00" in key:
        raise ValueError("report key must not contain null bytes")

    posix_path = PurePosixPath(key)
    windows_path = PureWindowsPath(key)
    if posix_path.is_absolute() or windows_path.is_absolute():
        raise ValueError("report key must be relative")
    if any(component in {".", ".."} for component in key.split("/")):
        raise ValueError("report key must not contain dot path components")

    normalized = posix_path.as_posix()
    if normalized in {"", "."}:
        raise ValueError("report key must identify a report")
    return normalized


def _validate_prefix(prefix: str) -> str:
    if not isinstance(prefix, str):
        raise TypeError("report prefix must be a string")
    if not prefix:
        return prefix
    if "\\" in prefix or "\x00" in prefix:
        raise ValueError("report prefix contains an unsafe path character")
    if PurePosixPath(prefix).is_absolute() or PureWindowsPath(prefix).is_absolute():
        raise ValueError("report prefix must be relative")
    if any(component in {".", ".."} for component in prefix.split("/")):
        raise ValueError("report prefix must not contain dot path components")
    return prefix


def _content_type_for_key(key: str) -> str:
    suffix = PurePosixPath(key).suffix.lower()
    if suffix in _STANDARD_CONTENT_TYPES:
        return _STANDARD_CONTENT_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(key, strict=False)
    return guessed or "application/octet-stream"


def _utc_datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _copy_metadata(metadata: StoredReport) -> StoredReport:
    return StoredReport(
        key=metadata.key,
        size=metadata.size,
        content_type=metadata.content_type,
        updated_at=metadata.updated_at,
    )


class LocalFileStorage:
    def __init__(self, root: str | Path):
        self._root = Path(root).expanduser().resolve(strict=False)
        self._root.mkdir(parents=True, exist_ok=True)

    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport:
        normalized, target = self._target(key)
        payload = bytes(content)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(payload)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, target)
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

        return self._metadata(normalized, target)

    def get_report(self, key: str) -> StoredReportContent | None:
        normalized, target = self._target(key)
        try:
            with target.open("rb") as report_file:
                content = report_file.read()
                stat_result = os.fstat(report_file.fileno())
        except (FileNotFoundError, IsADirectoryError):
            return None
        return StoredReportContent(
            metadata=self._metadata(normalized, target, stat_result=stat_result),
            content=content,
        )

    def delete_report(self, key: str) -> bool:
        _, target = self._target(key)
        try:
            target.unlink()
        except FileNotFoundError:
            return False
        return True

    def exists(self, key: str) -> bool:
        _, target = self._target(key)
        return target.is_file()

    def list_reports(self, *, prefix: str = "") -> list[StoredReport]:
        validated_prefix = _validate_prefix(prefix)
        reports: list[StoredReport] = []
        for path in self._root.rglob("*"):
            if not path.is_file() or (path.name.startswith(".") and path.name.endswith(".tmp")):
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
        target = (self._root / normalized).resolve(strict=False)
        try:
            target.relative_to(self._root)
        except ValueError as exc:
            raise ValueError("report key resolves outside storage root") from exc
        return normalized, target

    @staticmethod
    def _metadata(key: str, target: Path, *, stat_result=None) -> StoredReport:
        stat_result = stat_result or target.stat()
        return StoredReport(
            key=key,
            size=stat_result.st_size,
            content_type=_content_type_for_key(key),
            updated_at=_utc_datetime(stat_result.st_mtime),
        )


class InMemoryStorage:
    def __init__(self):
        self._reports: dict[str, StoredReportContent] = {}
        self._lock = RLock()

    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport:
        normalized = normalize_report_key(key)
        payload = bytes(content)
        metadata = StoredReport(
            key=normalized,
            size=len(payload),
            content_type=content_type,
            updated_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._reports[normalized] = StoredReportContent(metadata=metadata, content=payload)
        return _copy_metadata(metadata)

    def get_report(self, key: str) -> StoredReportContent | None:
        normalized = normalize_report_key(key)
        with self._lock:
            stored = self._reports.get(normalized)
            if stored is None:
                return None
            return StoredReportContent(
                metadata=_copy_metadata(stored.metadata),
                content=bytes(stored.content),
            )

    def delete_report(self, key: str) -> bool:
        normalized = normalize_report_key(key)
        with self._lock:
            return self._reports.pop(normalized, None) is not None

    def exists(self, key: str) -> bool:
        normalized = normalize_report_key(key)
        with self._lock:
            return normalized in self._reports

    def list_reports(self, *, prefix: str = "") -> list[StoredReport]:
        validated_prefix = _validate_prefix(prefix)
        with self._lock:
            return [
                _copy_metadata(self._reports[key].metadata)
                for key in sorted(self._reports)
                if key.startswith(validated_prefix)
            ]


__all__ = [
    "InMemoryStorage",
    "LocalFileStorage",
    "ReportStorage",
    "StoredReport",
    "StoredReportContent",
    "normalize_report_key",
]
