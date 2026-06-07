"""Storage maintenance helpers."""

from .migrations import MigrationRunner, column_names


def migrate_legacy_reports(*args, **kwargs):
    from .legacy_reports import migrate_legacy_reports as _migrate_legacy_reports

    return _migrate_legacy_reports(*args, **kwargs)


__all__ = ["MigrationRunner", "column_names", "migrate_legacy_reports"]
