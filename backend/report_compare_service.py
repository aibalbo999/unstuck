"""Compare two generated report versions for operator review."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import HTTPException

from data_trust import data_snapshot_filename_for_report, normalize_data_trust
from decision_tracking import parse_optional_price
from report_index import is_safe_report_filename
from report_index_metadata import build_report_metadata


def _read_json(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _metadata(filename: str, output_dir: str) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(output_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"找不到報告：{filename}")
    metadata = build_report_metadata(filename, output_dir)
    if not metadata:
        raise HTTPException(status_code=400, detail=f"無法讀取報告 metadata：{filename}")
    snapshot = _read_json(os.path.join(output_dir, data_snapshot_filename_for_report(filename)))
    return {**metadata, "snapshot": snapshot}


def _rec_value(recommendation: dict, key: str) -> Any:
    aliases = {
        "recommendation": ("recommendation", "建議", "綜合建議"),
        "current_price": ("current_price", "股價", "當日股價"),
        "target_3m": ("target_3m", "3個月"),
        "target_6m": ("target_6m", "6個月"),
        "target_12m": ("target_12m", "12個月"),
        "confidence": ("confidence", "信心"),
    }
    for alias in aliases.get(key, (key,)):
        for raw_key, value in (recommendation or {}).items():
            if alias in str(raw_key):
                return value
    return ""


def _side(metadata: dict) -> dict:
    snapshot = metadata.get("snapshot") if isinstance(metadata.get("snapshot"), dict) else {}
    trust = normalize_data_trust(metadata.get("data_trust") or snapshot.get("data_trust"))
    recommendation = metadata.get("recommendation") if isinstance(metadata.get("recommendation"), dict) else {}
    return {
        "filename": metadata.get("filename"),
        "ticker": metadata.get("ticker"),
        "company_name": metadata.get("company_name"),
        "date": metadata.get("date"),
        "pipeline_id": metadata.get("pipeline_id"),
        "generated_at": snapshot.get("generated_at"),
        "recommendation": {
            "recommendation": _rec_value(recommendation, "recommendation"),
            "current_price": _rec_value(recommendation, "current_price"),
            "target_3m": _rec_value(recommendation, "target_3m"),
            "target_6m": _rec_value(recommendation, "target_6m"),
            "target_12m": _rec_value(recommendation, "target_12m"),
            "confidence": _rec_value(recommendation, "confidence"),
        },
        "data_trust": trust,
        "decision_tracking": metadata.get("decision_tracking") or {},
        "analysis_text_stale": bool(metadata.get("analysis_text_stale")),
    }


def _numeric_delta(left, right) -> dict:
    before = parse_optional_price(left)
    after = parse_optional_price(right)
    if before is None or after is None:
        return {"before": left, "after": right, "delta": None, "delta_pct": None}
    delta = round(after - before, 4)
    delta_pct = round((after / before - 1) * 100, 4) if before else None
    return {"before": before, "after": after, "delta": delta, "delta_pct": delta_pct}


def _diff(left: dict, right: dict) -> dict:
    rec_left = left.get("recommendation", {})
    rec_right = right.get("recommendation", {})
    return {
        "recommendation_changed": rec_left.get("recommendation") != rec_right.get("recommendation"),
        "recommendation": {
            "before": rec_left.get("recommendation"),
            "after": rec_right.get("recommendation"),
        },
        "current_price": _numeric_delta(rec_left.get("current_price"), rec_right.get("current_price")),
        "target_3m": _numeric_delta(rec_left.get("target_3m"), rec_right.get("target_3m")),
        "target_6m": _numeric_delta(rec_left.get("target_6m"), rec_right.get("target_6m")),
        "target_12m": _numeric_delta(rec_left.get("target_12m"), rec_right.get("target_12m")),
        "confidence": {
            "before": rec_left.get("confidence"),
            "after": rec_right.get("confidence"),
        },
        "data_trust": {
            "status_before": left.get("data_trust", {}).get("status"),
            "status_after": right.get("data_trust", {}).get("status"),
            "score": _numeric_delta(
                left.get("data_trust", {}).get("score"),
                right.get("data_trust", {}).get("score"),
            ),
        },
        "tracking": {
            "return_pct": _numeric_delta(
                left.get("decision_tracking", {}).get("return_pct"),
                right.get("decision_tracking", {}).get("return_pct"),
            ),
            "latest_price": _numeric_delta(
                left.get("decision_tracking", {}).get("latest_price"),
                right.get("decision_tracking", {}).get("latest_price"),
            ),
        },
    }


def compare_reports(left_filename: str, right_filename: str, *, output_dir: str) -> dict:
    left = _side(_metadata(left_filename, output_dir))
    right = _side(_metadata(right_filename, output_dir))
    return {
        "success": True,
        "left": left,
        "right": right,
        "diff": _diff(left, right),
    }
