"""Helpers for partitioned report storage paths."""

from __future__ import annotations

import re

from data_trust import data_snapshot_filename_for_report
from report_index_parsing import parse_report_filename


_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_report_path_segment(value: str, *, fallback: str = "unknown") -> str:
    segment = _SAFE_SEGMENT_RE.sub("_", str(value or "").strip()).strip("._-")
    return segment or fallback


def report_storage_prefix_for_filename(filename: str) -> str:
    parsed = parse_report_filename(filename)
    report_date = str(parsed.get("date") or "")
    month = report_date[:7] if re.match(r"^\d{4}-\d{2}", report_date) else "unknown-month"
    ticker = safe_report_path_segment(str(parsed.get("ticker") or "unknown"), fallback="unknown-ticker")
    return f"{month}/{ticker}"


def report_storage_key_for_filename(filename: str) -> str:
    return f"{report_storage_prefix_for_filename(filename)}/{filename}"


def report_markdown_filename_for_report(filename: str) -> str:
    return filename[:-5] + ".md" if filename.endswith(".html") else f"{filename}.md"


def report_storage_candidates_for_filename(filename: str, *, kind: str = "html") -> list[str]:
    if kind == "html":
        basename = filename
    elif kind == "md":
        basename = report_markdown_filename_for_report(filename)
    elif kind == "data":
        basename = data_snapshot_filename_for_report(filename)
    else:
        raise ValueError(f"Unknown report storage kind: {kind}")
    nested = f"{report_storage_prefix_for_filename(filename)}/{basename}"
    return [nested, basename] if nested != basename else [basename]


__all__ = [
    "report_markdown_filename_for_report",
    "report_storage_candidates_for_filename",
    "report_storage_key_for_filename",
    "report_storage_prefix_for_filename",
    "safe_report_path_segment",
]
