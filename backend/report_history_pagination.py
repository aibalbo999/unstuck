"""Pagination helpers for read-only report history audits."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def collect_all_report_pages(
    list_reports: Callable[..., dict],
    *,
    page_size: int = 100,
    **kwargs: Any,
) -> dict:
    """Load every report row through the existing paginated list contract."""
    page_size = max(1, int(page_size))
    first = list_reports(page=1, limit=page_size, **kwargs)
    first_reports = list(first.get("reports") or []) if isinstance(first, dict) else []
    first_pagination = first.get("pagination") if isinstance(first, dict) else {}
    pagination = first_pagination if isinstance(first_pagination, dict) else {}
    total = max(int(pagination.get("total") or len(first_reports)), len(first_reports))
    total_pages = max((total + page_size - 1) // page_size, 1)
    reports = first_reports
    for page in range(2, total_pages + 1):
        payload = list_reports(page=page, limit=page_size, **kwargs)
        if isinstance(payload, dict):
            reports.extend(list(payload.get("reports") or []))
    total = max(total, len(reports))
    return {
        "reports": reports,
        "pagination": {
            **pagination,
            "page": 1,
            "limit": page_size,
            "total": total,
            "total_pages": max((total + page_size - 1) // page_size, 1),
            "has_prev": False,
            "has_next": False,
        },
    }
