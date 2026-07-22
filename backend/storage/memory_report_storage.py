"""In-memory report storage implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from ._report_keys import normalize_report_key, validate_report_prefix
from .report_storage import StoredReport, StoredReportContent


def _copy_metadata(metadata: StoredReport) -> StoredReport:
    return StoredReport(
        key=metadata.key,
        size=metadata.size,
        content_type=metadata.content_type,
        updated_at=metadata.updated_at,
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
        validated_prefix = validate_report_prefix(prefix)
        with self._lock:
            return [
                _copy_metadata(self._reports[key].metadata)
                for key in sorted(self._reports)
                if key.startswith(validated_prefix)
            ]


__all__ = ["InMemoryStorage"]
