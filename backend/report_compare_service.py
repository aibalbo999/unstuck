"""Compare two generated report versions for operator review."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from data_trust import normalize_data_trust
from decision_tracking import parse_optional_price
from report_index import is_safe_report_filename
from report_index_metadata import build_report_metadata
from report_paths import report_storage_candidates_for_filename


def _read_json(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _existing_report_path(filename: str, output_dir: str, *, kind: str) -> str:
    for key in report_storage_candidates_for_filename(filename, kind=kind):
        path = os.path.join(output_dir, key)
        if os.path.exists(path):
            return path
    return ""


def _metadata(filename: str, output_dir: str) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not _existing_report_path(filename, output_dir, kind="html"):
        raise HTTPException(status_code=404, detail=f"找不到報告：{filename}")
    metadata = build_report_metadata(filename, output_dir)
    if not metadata:
        raise HTTPException(status_code=400, detail=f"無法讀取報告 metadata：{filename}")
    snapshot = _read_json(_existing_report_path(filename, output_dir, kind="data"))
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
        "decision_freshness": metadata.get("decision_freshness") or {},
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
        "decision_freshness": {
            "status_before": left.get("decision_freshness", {}).get("status"),
            "status_after": right.get("decision_freshness", {}).get("status"),
            "requires_rerun_before": bool(left.get("decision_freshness", {}).get("requires_rerun")),
            "requires_rerun_after": bool(right.get("decision_freshness", {}).get("requires_rerun")),
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


def _parse_side_datetime(side: dict) -> datetime | None:
    for value in (side.get("generated_at"), side.get("date")):
        text = str(value or "").strip()
        if not text:
            continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _date_order(left: dict, right: dict) -> tuple[str, dict]:
    left_dt = _parse_side_datetime(left)
    right_dt = _parse_side_datetime(right)
    if left_dt is None or right_dt is None:
        return "unknown", {}
    if (left_dt.tzinfo is None) != (right_dt.tzinfo is None):
        left_dt = left_dt.replace(tzinfo=None)
        right_dt = right_dt.replace(tzinfo=None)
    if left_dt == right_dt:
        return "same", {}
    if left_dt < right_dt:
        return "chronological", {"left": left.get("filename"), "right": right.get("filename")}
    return "reverse", {"left": right.get("filename"), "right": left.get("filename")}


def _compatibility(left: dict, right: dict) -> dict:
    warnings = []
    same_ticker = left.get("ticker") == right.get("ticker")
    same_pipeline = left.get("pipeline_id") == right.get("pipeline_id")
    order, suggested_order = _date_order(left, right)
    if not same_ticker:
        warnings.append({
            "level": "warning",
            "code": "different_ticker",
            "message": f"兩份報告股票不同：{left.get('ticker') or 'N/A'} vs {right.get('ticker') or 'N/A'}。",
        })
    if not same_pipeline:
        warnings.append({
            "level": "warning",
            "code": "different_pipeline",
            "message": f"兩份報告 pipeline 不同：{left.get('pipeline_id') or 'N/A'} vs {right.get('pipeline_id') or 'N/A'}。",
        })
    if order == "reverse":
        warnings.append({
            "level": "info",
            "code": "reverse_chronology",
            "message": "左側報告時間晚於右側；差異仍依目前左右順序計算。",
        })
    for side_name, side in (("left", left), ("right", right)):
        freshness = side.get("decision_freshness") if isinstance(side.get("decision_freshness"), dict) else {}
        if freshness.get("requires_rerun"):
            label = "左側" if side_name == "left" else "右側"
            warnings.append({
                "level": "warning",
                "code": f"{side_name}_decision_needs_rerun",
                "message": f"{label}報告資料快照已更新，但投資結論尚未重跑。",
            })
    return {
        "same_ticker": same_ticker,
        "same_pipeline": same_pipeline,
        "date_order": order,
        "suggested_order": suggested_order,
        "is_comparable": same_ticker and same_pipeline,
        "warnings": warnings,
    }


def compare_reports(left_filename: str, right_filename: str, *, output_dir: str) -> dict:
    left = _side(_metadata(left_filename, output_dir))
    right = _side(_metadata(right_filename, output_dir))
    return {
        "success": True,
        "left": left,
        "right": right,
        "compatibility": _compatibility(left, right),
        "diff": _diff(left, right),
    }
