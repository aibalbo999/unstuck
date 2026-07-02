"""Portfolio CSV risk analysis.

This module deliberately avoids broker integrations. Operators can paste/export
positions as CSV and get concentration and thesis-health checks locally.
"""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any


SCHEMA_VERSION = "portfolio_risk.v1"


def parse_portfolio_csv(csv_text: str) -> list[dict[str, Any]]:
    rows = []
    reader = csv.DictReader(StringIO(str(csv_text or "").strip()))
    raw_rows = [row for row in reader if any(str(value or "").strip() for value in row.values())]
    total_market_value = sum(_float(row.get("market_value")) or 0.0 for row in raw_rows)
    for row in raw_rows:
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        if not ticker:
            continue
        weight = _float(row.get("weight") or row.get("weight_pct"))
        if weight is None:
            market_value = _float(row.get("market_value")) or 0.0
            weight = (market_value / total_market_value * 100) if total_market_value > 0 else 0.0
        rows.append({
            "ticker": ticker,
            "weight_pct": round(weight, 4),
            "sector": str(row.get("sector") or "Unknown").strip() or "Unknown",
            "country": str(row.get("country") or row.get("market") or "Unknown").strip() or "Unknown",
        })
    return rows


def analyze_portfolio_csv(csv_text: str, *, thesis_health: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    positions = sorted(parse_portfolio_csv(csv_text), key=lambda row: row["weight_pct"], reverse=True)
    sector_weights = _group_weights(positions, "sector")
    country_weights = _group_weights(positions, "country")
    flags = []
    top_position = positions[0] if positions else {}
    if float(top_position.get("weight_pct") or 0) > 40:
        flags.append("single_position_over_40_pct")
    if sector_weights and max(sector_weights.values()) > 60:
        flags.append("sector_over_60_pct")
    if country_weights and max(country_weights.values()) > 80:
        flags.append("country_over_80_pct")
    thesis = _thesis_health_summary(positions, thesis_health or {})
    if thesis["invalidated"]:
        flags.append("invalidated_thesis_position")
    return {
        "schema_version": SCHEMA_VERSION,
        "total_positions": len(positions),
        "positions": positions,
        "concentration": {
            "top_position": top_position,
            "sector_weights": sector_weights,
            "country_weights": country_weights,
        },
        "thesis_health": thesis,
        "risk_flags": flags,
    }


def _group_weights(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
    weights: dict[str, float] = {}
    for row in rows:
        key = str(row.get(field) or "Unknown")
        weights[key] = weights.get(key, 0.0) + float(row.get("weight_pct") or 0.0)
    return {key: round(value, 4) for key, value in sorted(weights.items(), key=lambda item: item[1], reverse=True)}


def _thesis_health_summary(positions: list[dict[str, Any]], thesis_health: dict[str, dict[str, Any]]) -> dict[str, Any]:
    invalidated = []
    missing = []
    for position in positions:
        ticker = str(position.get("ticker") or "")
        health = thesis_health.get(ticker)
        if not health:
            missing.append(ticker)
            continue
        if str(health.get("status") or "").lower() in {"invalidated", "broken", "red"}:
            invalidated.append(ticker)
    return {"invalidated": invalidated, "missing": missing}


def _float(value: Any) -> float | None:
    try:
        return float(str(value).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


__all__ = ["SCHEMA_VERSION", "analyze_portfolio_csv", "parse_portfolio_csv"]
