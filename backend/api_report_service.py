"""Deprecated compatibility facade for report API services."""

from __future__ import annotations

from data_trust import data_snapshot_filename_for_report
from report_index import is_safe_report_filename
from report_history_service import (
    cleanup_expired_reports,
    cleanup_orphan_markdown_reports,
    delete_report_files,
    download_report_file,
    get_report_file,
    list_reports,
    parse_recommendation_summary,
)
from report_refresh_service import (
    ANALYSIS_TEXT_STALE_MESSAGE,
    refresh_data_diff,
    refresh_report_data_snapshot,
)
from report_rerun_service import (
    RERUN_SCOPE_LABELS,
    normalize_rerun_scope,
    parse_agent_sections_from_markdown,
    rerun_report_analysis,
)


__all__ = [
    "ANALYSIS_TEXT_STALE_MESSAGE",
    "RERUN_SCOPE_LABELS",
    "cleanup_expired_reports",
    "cleanup_orphan_markdown_reports",
    "data_snapshot_filename_for_report",
    "delete_report_files",
    "download_report_file",
    "get_report_file",
    "is_safe_report_filename",
    "list_reports",
    "normalize_rerun_scope",
    "parse_agent_sections_from_markdown",
    "parse_recommendation_summary",
    "refresh_data_diff",
    "refresh_report_data_snapshot",
    "rerun_report_analysis",
]
