"""Repair helpers for stale report index metadata rows."""

from __future__ import annotations

import json

from report_index_parsing import parse_recommendation_summary


def recommendation_needs_rebuild(recommendation: dict) -> bool:
    if not isinstance(recommendation, dict):
        return True
    keys = ("recommendation", "current_price", "target_3m", "target_6m", "target_12m")
    return all(str(recommendation.get(key) or "").strip() in {"", "N/A"} for key in keys)


def stored_recommendation_needs_rebuild(row, output_dir: str) -> bool:
    try:
        recommendation = json.loads(row["recommendation_json"])
    except (KeyError, TypeError, json.JSONDecodeError):
        recommendation = {}
    if not recommendation_needs_rebuild(recommendation):
        return False
    rebuilt = parse_recommendation_summary(row["filename"], output_dir=output_dir)
    return not recommendation_needs_rebuild(rebuilt)
