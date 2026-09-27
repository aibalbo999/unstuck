"""Pure coverage evidence for already-read Yahoo annual statement frames.

This observes one SDK operation, not HTTP traffic or complete statutory reports.
It does not repair the legacy extractor's values, year alignment or fallback.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import math
import re

import pandas as pd


PROVIDER = "Yahoo annual financial statements"
FIELDS = {
    "financials": {
        "revenue_history": ("Total Revenue",),
        "net_income_history": ("Net Income",),
        "gross_profit_history": ("Gross Profit",),
        "operating_income_history": ("Operating Income",),
    },
    "cashflow": {
        "operating_cash_flow": ("Operating Cash Flow",),
        "capital_expenditure": ("Capital Expenditure",),
    },
    "balance_sheet": {
        "total_assets_history": ("Total Assets",),
        "total_equity_history": ("Stockholders Equity", "Total Equity Gross Minority Interest"),
    },
}


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _period(value):
    if isinstance(value, (date, datetime)) and not pd.isna(value):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass
    return None


def _table_rows(frame, name, cutoff):
    """Use exactly the existing income/balance range; cashflow is keyed by year."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return [], set()
    reasons = set()
    columns = list(frame.columns if name == "cashflow" else frame.columns[:5])
    rows = []
    for position, column in enumerate(columns):
        period = _period(column)
        if period and period > cutoff:
            period = None
            reasons.add("future_period")
        if period is None:
            reasons.add("invalid_period")
        values = {}
        for field, candidates in FIELDS[name].items():
            label = next((candidate for candidate in candidates if candidate in frame.index), None)
            positions = [index for index, item in enumerate(frame.index) if item == label] if label else []
            value = _number(frame.iloc[positions[0], position]) if len(positions) == 1 else None
            values[field] = value
            if value is None:
                reasons.add("missing_required_value")
        rows.append({"period": period, "values": values})
    years = [row["period"][:4] for row in rows if row["period"]]
    if len(years) != len(set(years)):
        reasons.add("duplicate_year")
    return rows, reasons


def observe_financial_statements(*, tables, errors, histories, metadata, started_at, finished_at):
    """Classify primary evidence before any fallback merge, without I/O."""
    evidence = {}
    reasons = {}
    observation_errors = {}
    cutoff = datetime.fromtimestamp(finished_at, timezone.utc).date().isoformat()
    for name in FIELDS:
        try:
            evidence[name], reasons[name] = _table_rows(tables.get(name), name, cutoff)
        except Exception as exc:
            # Telemetry must not turn a legacy tolerated frame/index problem
            # into a core-fetch failure or prevent the existing fallback.
            evidence[name], reasons[name] = [], {"observation_error"}
            observation_errors[name] = type(exc).__name__
        if errors.get(name):
            reasons[name].add("table_exception")

    income_periods = [row["period"] for row in evidence["financials"]]
    expected_periods = [period for period in income_periods if period]
    expected_years = [period[:4] for period in reversed(expected_periods)]
    numeric_years = sorted({int(year) for year in expected_years})
    if numeric_years and numeric_years[-1] - numeric_years[0] + 1 != len(numeric_years):
        reasons["financials"].add("missing_year")
    if not expected_periods or histories.get("years") != expected_years:
        reasons["financials"].add("unverified_output_years")

    for name in ("cashflow", "balance_sheet"):
        actual = [row["period"] for row in evidence[name]]
        if not expected_periods or any(period not in actual for period in expected_periods):
            reasons[name].add("missing_period")
        if name == "balance_sheet" and actual != income_periods:
            reasons[name].add("output_period_alignment")

    # Preserve legacy numeric output. Missing/zero-dropped outputs cannot certify
    # complete coverage even when the SDK frame contains the underlying value.
    for name, fields in FIELDS.items():
        output_fields = ("fcf_history",) if name == "cashflow" else tuple(fields)
        for field in output_fields:
            values = histories.get(field, [])
            if len(values) != len(expected_periods) or any(_number(value) is None for value in values):
                reasons[name].add("missing_output_value")

    usable_periods = set()
    raw_periods = set()
    components = {}
    for name, rows in evidence.items():
        raw_periods.update(row["period"] for row in rows if row["period"])
        available = {row["period"] for row in rows if row["period"]
                     and any(value is not None for value in row["values"].values())}
        usable_periods.update(available)
        status = ("partial" if reasons[name] else "complete") if available else (
            "error" if errors.get(name) else "unknown" if observation_errors.get(name) else "empty")
        components[name] = {
            "status": status,
            "as_of": ",".join(sorted({period[:4] for period in available})),
            "reason_code": ",".join(sorted(reasons[name])),
            "error_kind": errors.get(name) or observation_errors.get(name, ""),
            "retrieval_status": "observation_error" if name in observation_errors else "sdk_read_cache_unknown",
        }

    complete = bool(usable_periods) and all(row["status"] == "complete" for row in components.values())
    failed = bool(errors or observation_errors)
    status = "success" if complete else "degraded_enrichment" if usable_periods or not failed else "error"
    outcome = "complete" if complete else "partial" if usable_periods else "error" if failed else "empty"
    count = len(expected_periods) if complete else len({period[:4] for period in usable_periods})
    fingerprint = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                                           allow_nan=False).encode()).hexdigest()
    return {
        **metadata,
        "event_kind": "sdk_operation",
        "source": "financial_statements",
        "provider": PROVIDER,
        "status": status,
        "record_count": count,
        "fetched_at": datetime.fromtimestamp(finished_at, timezone.utc).isoformat(),
        "fetched_at_epoch": finished_at,
        "duration_ms": max(0, round((finished_at - started_at) * 1000)),
        # The application cache gate was bypassed; SDK/HTTP cache is unknown.
        "cache_hit": False,
        "stale": False,
        "retrieval_status": "observation_error" if observation_errors else "sdk_read_cache_unknown",
        "coverage_status": outcome,
        "outcome": outcome,
        "raw_count": len(raw_periods),
        "usable_count": count,
        "component_statuses": components,
        "data_fingerprint": fingerprint,
        "parser_version": "yahoo-annual-observation.v1",
        "error_kind": "observation_error" if observation_errors else "table_exception" if errors else "",
        "message": "Yahoo 年度三表 SDK 提取觀測；HTTP 與 SDK 快取狀態未觀測。",
    }
