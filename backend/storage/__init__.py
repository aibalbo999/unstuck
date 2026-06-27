"""Storage maintenance helpers."""

from .migrations import MigrationRunner, column_names
from .report_storage import (
    InMemoryStorage,
    LocalFileStorage,
    ReportStorage,
    StoredReport,
    StoredReportContent,
    normalize_report_key,
)


def migrate_legacy_reports(*args, **kwargs):
    from .legacy_reports import migrate_legacy_reports as _migrate_legacy_reports

    return _migrate_legacy_reports(*args, **kwargs)


__all__ = [
    "InMemoryStorage",
    "LocalFileStorage",
    "MigrationRunner",
    "ReportStorage",
    "StoredReport",
    "StoredReportContent",
    "column_names",
    "migrate_legacy_reports",
    "normalize_report_key",
]
