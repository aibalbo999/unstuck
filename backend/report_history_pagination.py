"""Pagination helpers for read-only report history audits."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _non_negative_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, ArithmeticError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def collection_is_complete(payload: Any) -> bool:
    """Return whether a collector response explicitly reports a complete set."""
    if not isinstance(payload, dict):
        return False
    pagination = payload.get("pagination")
    return not isinstance(pagination, dict) or pagination.get("complete", True) is True


def collect_all_report_pages(
    list_reports: Callable[..., dict],
    *,
    page_size: int = 100,
    **kwargs: Any,
) -> dict:
    """Load every report row through the existing paginated list contract."""
    page_size = max(1, int(page_size))
    first = list_reports(page=1, limit=page_size, **kwargs)
    first_reports_value = first.get("reports") if isinstance(first, dict) else None
    first_reports = first_reports_value if isinstance(first_reports_value, list) else []
    first_pagination = first.get("pagination") if isinstance(first, dict) else {}
    pagination = first_pagination if isinstance(first_pagination, dict) else {}
    declared_total = pagination.get("total")
    total = len(first_reports)
    complete = isinstance(first, dict) and isinstance(first_reports_value, list)
    if declared_total is not None:
        parsed_total = _non_negative_integer(declared_total)
        if parsed_total is None:
            complete = False
        else:
            total = parsed_total
    elif len(first_reports) >= page_size:
        complete = False
    if (
        len(first_reports) > page_size
        or len(first_reports) > total
        or total > len(first_reports) and len(first_reports) < page_size
    ):
        complete = False
    total_pages = max((total + page_size - 1) // page_size, 1)
    reports = first_reports
    for page in range(2, total_pages + 1):
        payload = list_reports(page=page, limit=page_size, **kwargs)
        page_reports_value = payload.get("reports") if isinstance(payload, dict) else None
        if not isinstance(page_reports_value, list):
            complete = False
            break
        page_pagination = payload.get("pagination")
        if isinstance(page_pagination, dict) and page_pagination.get("total") is not None:
            page_total = _non_negative_integer(page_pagination.get("total"))
            if page_total is None or page_total != total:
                complete = False
        if len(page_reports_value) > page_size:
            complete = False
        if page < total_pages and len(page_reports_value) < page_size:
            complete = False
        reports.extend(page_reports_value)
    if len(reports) != total:
        complete = False
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
            "complete": complete,
        },
    }
