"""Current quality notice lookup for report history views."""

from __future__ import annotations

import logging
import sqlite3

from report_history_snapshot_notice import (
    current_quality_notice_context,
    invalid_snapshot_notice_context,
)
from report_repository import ReportListQuery, ReportRepository
from storage.report_storage import ReportStorage


LOGGER = logging.getLogger(__name__)


def report_quality_notice_context(
    filename: str,
    output_dir: str,
    storage: ReportStorage,
    repository: ReportRepository,
) -> dict | None:
    invalid_context = invalid_snapshot_notice_context(storage, filename)
    if invalid_context is not None:
        return invalid_context
    try:
        reports, _ = repository.query(
            ReportListQuery(
                page=1,
                limit=1,
                q=filename,
                include_versions=True,
                output_dir=output_dir,
                sync_metadata=False,
            )
        )
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        LOGGER.debug("Current report quality projection unavailable for %s: %s", filename, exc)
        return None
    current_report = next(
        (
            report
            for report in reports
            if isinstance(report, dict) and report.get("filename") == filename
        ),
        None,
    )
    return current_quality_notice_context(storage, filename, current_report)


__all__ = ["report_quality_notice_context"]
