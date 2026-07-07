"""Decision tracking refresh workflow helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


RefreshReportCallable = Callable[..., Awaitable[dict]]


@dataclass(frozen=True)
class TrackingTickerRefreshResult:
    ticker: str
    refreshed_reports_count: int
    refreshed_data: dict
    report_results: list[dict]


async def refresh_ticker_reports(
    ticker: str,
    reports: list[dict],
    *,
    output_dir: str,
    refresh_service: Any,
    refresh_report: RefreshReportCallable | None = None,
) -> TrackingTickerRefreshResult:
    if refresh_report is None:
        from report_refresh_service import refresh_report_data_snapshot

        refresh_report = refresh_report_data_snapshot

    refreshed_data: dict | None = None
    report_results: list[dict] = []
    for report in reports:
        filename = str(report.get("filename") or "").strip()
        if not filename:
            raise ValueError("tracking refresh report is missing filename")
        refresh_result = await refresh_report(
            filename,
            output_dir=output_dir,
            refresh_service=refresh_service,
            refreshed_data=refreshed_data,
            return_refreshed_data=refreshed_data is None,
        )
        report_results.append(refresh_result)
        if refreshed_data is None:
            refreshed = refresh_result.get("refreshed_data")
            if not isinstance(refreshed, dict):
                raise RuntimeError("first tracking refresh did not return refreshed_data")
            refreshed_data = refreshed

    return TrackingTickerRefreshResult(
        ticker=str(ticker or "").strip().upper(),
        refreshed_reports_count=len(report_results),
        refreshed_data=refreshed_data or {},
        report_results=report_results,
    )


__all__ = ["TrackingTickerRefreshResult", "refresh_ticker_reports"]
