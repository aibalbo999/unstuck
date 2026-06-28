"""Decision snapshot and performance tracking for generated reports."""

from __future__ import annotations

import json
import os
from typing import Optional

from confidence_calibration import build_confidence_calibration, has_unresolved_cross_source_conflict
from price_parser import extract_price_numbers
from report_index_parsing import normalize_recommendation_label


def parse_optional_price(value) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    try:
        numbers = extract_price_numbers(str(value))
    except (TypeError, ValueError):
        return None
    if not numbers:
        return None
    return round(float(numbers[0]), 4)


def _pct_change(after: Optional[float], before: Optional[float]) -> Optional[float]:
    if after is None or before is None or before == 0:
        return None
    return round((after / before - 1) * 100, 4)


def _read_snapshot(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return snapshot if isinstance(snapshot, dict) else {}


def _snapshot_current_price(snapshot: dict) -> Optional[float]:
    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    return parse_optional_price(data.get("current_price") or data.get("current_price_fmt"))


def _price_updated_at(snapshot: dict) -> str:
    trust = snapshot.get("data_trust") if isinstance(snapshot.get("data_trust"), dict) else {}
    if trust.get("last_market_data_at"):
        return str(trust.get("last_market_data_at"))
    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    freshness = data.get("source_freshness") if isinstance(data.get("source_freshness"), dict) else {}
    market = freshness.get("market_data") if isinstance(freshness.get("market_data"), dict) else {}
    return str(market.get("fetched_at") or snapshot.get("generated_at") or "")


def _snapshot_refreshed_at(snapshot: dict) -> str:
    return str(snapshot.get("snapshot_refreshed_at") or "")


def _tracking_status(tracking: dict) -> str:
    if tracking.get("latest_price") is None or tracking.get("initial_price") is None:
        return "unavailable"
    target_12m = tracking.get("target_12m")
    latest_price = tracking.get("latest_price")
    recommendation = tracking.get("recommendation")
    if recommendation == "買入" and target_12m and latest_price >= target_12m:
        return "target_hit"
    if recommendation == "避免" and tracking.get("return_pct", 0) < 0:
        return "avoided_loss"
    return "tracked"


def _target_progress(latest: Optional[float], initial: Optional[float], target: Optional[float]) -> Optional[float]:
    if latest is None or initial is None or target is None or target == initial:
        return None
    return round(((latest - initial) / (target - initial)) * 100, 4)


def _target_comparison(latest: Optional[float], target: Optional[float], label: str) -> dict:
    gap_pct = _pct_change(target, latest)
    if latest is None or target is None or gap_pct is None:
        return {"period_label": label, "target": target, "gap_pct": None, "status": "unavailable", "label": "無法比較"}
    if abs(gap_pct) <= 3:
        status, status_label = "near_target", "接近目標"
    elif latest > target:
        status, status_label = "above_target", "已高於目標"
    else:
        status, status_label = "below_target", "低於目標"
    return {"period_label": label, "target": target, "gap_pct": gap_pct, "status": status, "label": status_label}


def _target_comparisons(tracking: dict) -> dict:
    latest = tracking.get("latest_price")
    return {
        "target_3m": _target_comparison(latest, tracking.get("target_3m"), "3月目標"),
        "target_6m": _target_comparison(latest, tracking.get("target_6m"), "6月目標"),
        "target_12m": _target_comparison(latest, tracking.get("target_12m"), "12月目標"),
    }


def _summary_status(comparisons: dict) -> str:
    for key in ("target_12m", "target_6m", "target_3m"):
        item = comparisons.get(key) or {}
        label = str(item.get("period_label") or "").replace("目標", "")
        if item.get("status") == "above_target":
            return f"高於{label}目標"
        if item.get("status") == "near_target":
            return f"接近{label}目標"
    target_12m = comparisons.get("target_12m") or {}
    if target_12m.get("gap_pct") is not None:
        return f"距12月目標 {target_12m['gap_pct']:+.2f}%"
    return "尚無法比較目標"


def _summary(tracking: dict) -> str:
    if tracking.get("status") == "unavailable":
        return "缺少建議時股價或最新股價，尚無法追蹤績效。"
    parts = []
    return_pct = tracking.get("return_pct")
    if return_pct is not None:
        sign = "+" if return_pct > 0 else ""
        parts.append(f"建議後報酬 {sign}{return_pct:.2f}%")
    gap = tracking.get("target_12m_gap_pct")
    if gap is not None:
        sign = "+" if gap > 0 else ""
        parts.append(f"距 12 個月目標 {sign}{gap:.2f}%")
    return "；".join(parts) or "已建立決策追蹤。"


def build_decision_tracking(recommendation: dict, data_snapshot_path: str = "") -> dict:
    """Build a compact decision-performance snapshot for list/report APIs."""
    recommendation = recommendation if isinstance(recommendation, dict) else {}
    snapshot = _read_snapshot(data_snapshot_path)
    initial_price = parse_optional_price(recommendation.get("current_price"))
    latest_price = _snapshot_current_price(snapshot)
    if latest_price is None:
        latest_price = initial_price
    tracking = {
        "status": "unavailable",
        "recommendation": normalize_recommendation_label(recommendation.get("recommendation", "")),
        "initial_price": initial_price,
        "latest_price": latest_price,
        "target_3m": parse_optional_price(recommendation.get("target_3m")),
        "target_6m": parse_optional_price(recommendation.get("target_6m")),
        "target_12m": parse_optional_price(recommendation.get("target_12m")),
        "confidence": str(recommendation.get("confidence") or "N/A"),
        "price_updated_at": _price_updated_at(snapshot),
        "snapshot_refreshed_at": _snapshot_refreshed_at(snapshot),
        "refreshed_without_analysis_rerun": bool(snapshot.get("refreshed_without_analysis_rerun")),
    }
    tracking["return_pct"] = _pct_change(tracking["latest_price"], tracking["initial_price"])
    tracking["target_12m_gap_pct"] = _pct_change(tracking["target_12m"], tracking["latest_price"])
    tracking["target_12m_progress_pct"] = _target_progress(
        tracking["latest_price"],
        tracking["initial_price"],
        tracking["target_12m"],
    )
    tracking["target_comparisons"] = _target_comparisons(tracking)
    tracking["tracking_summary_status"] = _summary_status(tracking["target_comparisons"])
    tracking["confidence_calibration"] = build_confidence_calibration(
        recommendation,
        snapshot.get("data_trust") if isinstance(snapshot.get("data_trust"), dict) else {},
        bool((snapshot.get("circuit_breaker") or {}).get("_ever_opened", False)),
        has_unresolved_cross_source_conflict(snapshot.get("data") if isinstance(snapshot.get("data"), dict) else snapshot),
    )
    tracking["status"] = _tracking_status(tracking)
    tracking["summary"] = _summary(tracking)
    return tracking


def build_decision_freshness(data_snapshot_path: str = "", report_generated_at: str = "") -> dict:
    """Describe whether the investment conclusion matches the current data snapshot."""
    snapshot = _read_snapshot(data_snapshot_path)
    if not snapshot:
        return {
            "status": "unknown",
            "requires_rerun": False,
            "conclusion_generated_at": str(report_generated_at or ""),
            "snapshot_refreshed_at": "",
            "data_snapshot_generated_at": "",
            "requires_rerun_reason": "",
            "message": "尚無資料快照，無法判斷投資結論是否仍對應最新資料。",
        }

    stale = bool(snapshot.get("refreshed_without_analysis_rerun"))
    data_snapshot_generated_at = str(snapshot.get("generated_at") or "")
    conclusion_generated_at = str(
        snapshot.get("conclusion_generated_at")
        or report_generated_at
        or data_snapshot_generated_at
        or ""
    )
    snapshot_refreshed_at = str(
        snapshot.get("snapshot_refreshed_at")
        or (data_snapshot_generated_at if stale else "")
        or ""
    )
    status = str(snapshot.get("decision_validity_status") or ("needs_rerun" if stale else "current"))
    requires_rerun = status == "needs_rerun" or stale
    reason = str(
        snapshot.get("requires_rerun_reason")
        or snapshot.get("analysis_text_stale_message")
        or ""
    )
    if requires_rerun and not reason:
        reason = "資料快照已刷新，但投資結論尚未依最新資料重新產生。"
    return {
        "status": status,
        "requires_rerun": requires_rerun,
        "conclusion_generated_at": conclusion_generated_at,
        "snapshot_refreshed_at": snapshot_refreshed_at,
        "data_snapshot_generated_at": data_snapshot_generated_at,
        "requires_rerun_reason": reason,
        "message": reason if requires_rerun else "投資結論與目前資料快照一致。",
    }
