"""Observation dates; never infer publication from the scan clock."""

from datetime import date

import pandas as pd


def build_source_dates(institutional, daily, *, scan_date: date,
                       institutional_provider: str, daily_provider: str,
                       institutional_acquired_at: str | None = None, daily_acquired_at: str | None = None) -> dict:
    sources = {}
    for name, frame, provider, acquired_at in (
        ("institutional", institutional, institutional_provider, institutional_acquired_at),
        ("daily_prices", daily, daily_provider, daily_acquired_at),
    ):
        dates = pd.to_datetime(frame["date"], errors="coerce") if "date" in frame else pd.Series(dtype="datetime64[ns]")
        dates = dates.dropna()
        eligible = dates[dates.dt.date <= scan_date]
        observed = eligible.max().date().isoformat() if not eligible.empty else None
        sources[name] = {
            "provider": provider,
            "as_of": observed,
            "acquisition_completed_at": acquired_at,
            "status": "scan_date_observed" if observed == scan_date.isoformat() else "older_observation" if observed else "unavailable",
            "invalid_date_rows": int(len(frame) - len(dates)),
            "future_date_rows": int((dates.dt.date > scan_date).sum()),
        }
    return {
        "requested_date": scan_date.isoformat(),
        "timezone": "Asia/Taipei",
        "sources": sources,
        "both_sources_on_scan_date": all(s["status"] == "scan_date_observed" for s in sources.values()),
        "coverage_basis": "latest observed dates only; not proof of all symbols, categories or exchange sessions",
    }
