"""Outcome calibration ledger for backtested report decisions."""

from __future__ import annotations

from statistics import mean
from typing import Any

from mapping_fields import safe_dict_list, safe_text
from strategy_evaluator import evaluate_strategy_artifacts


SCHEMA_VERSION = "outcome_calibration.v1"
LOW_TRUST_STATUSES = {"partial", "stale", "error"}
QUALITY_WARNING_STATUSES = {"warning", "blocked", "rejected", "caution"}


def build_outcome_calibration(*, backtests: list[dict[str, Any]], reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine backtest outcomes with report-time quality signals."""
    report_index = _reports_by_filename(reports)
    details = [_detail(row, report_index.get(_text(_field(row, "report_filename")))) for row in _rows(backtests)]
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": _summary(details),
        "by_pipeline": _group_stats(details, "pipeline_id"),
        "by_horizon": _group_stats(details, "horizon_months"),
        "quality_groups": {
            "data_trust_status": _quality_group_stats(details, "data_trust_status"),
            "content_credibility_status": _quality_group_stats(details, "content_credibility_status"),
            "report_conformance_status": _quality_group_stats(details, "report_conformance_status"),
        },
        "strategy_evaluation": _strategy_evaluation(details),
        "details": details,
    }


def _rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return safe_dict_list(rows)


def _reports_by_filename(reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed = {}
    for report in _rows(reports):
        filename = _first_text(_field(report, "filename"), _field(report, "report_filename"))
        if filename:
            indexed[filename] = report
    return indexed


def _detail(backtest: dict[str, Any], report: dict[str, Any] | None) -> dict[str, Any]:
    signal = _quality_signal(backtest, report if isinstance(report, dict) else {})
    attribution = _miss_attribution(backtest, signal)
    return {
        "report_filename": _text(_field(backtest, "report_filename")),
        "ticker": _first_text(_field(backtest, "ticker"), _field(signal, "ticker")),
        "pipeline_id": _first_text(_field(backtest, "pipeline_id"), _field(signal, "pipeline_id"), fallback="v1"),
        "horizon_months": _text(_field(backtest, "horizon_months")),
        "outcome": _status(_field(backtest, "outcome")) or "miss",
        "strategy_roi_pct": _number(_field(backtest, "strategy_roi_pct")),
        "market_return_pct": _number(_field(backtest, "market_return_pct")),
        "reason": _text(_field(backtest, "reason")),
        "quality_signal": signal,
        "miss_attribution": attribution,
    }


def _quality_signal(backtest: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    data_trust = _dict(_field(report, "data_trust"))
    content_credibility = _dict(_field(report, "content_credibility"))
    conformance = _dict(_field(report, "report_conformance"))
    freshness = _dict(_field(report, "decision_freshness"))
    return {
        "report_filename": _first_text(_field(backtest, "report_filename"), _field(report, "filename")),
        "ticker": _first_text(_field(report, "ticker"), _field(backtest, "ticker")),
        "pipeline_id": _first_text(_field(report, "pipeline_id"), _field(backtest, "pipeline_id"), fallback="v1"),
        "data_trust_status": _first_status(_field(data_trust, "status"), _field(report, "data_trust_status"), fallback="unknown"),
        "data_trust_score": _first_number(_field(data_trust, "score"), _field(data_trust, "data_confidence_score")),
        "content_credibility_status": _status(_field(content_credibility, "status")) or "not_recorded",
        "report_conformance_status": _status(_field(conformance, "status")) or "not_recorded",
        "decision_freshness_status": _status(_field(freshness, "status"))
        or ("needs_rerun" if _safe_bool(_field(freshness, "requires_rerun")) else "unknown"),
    }


def _miss_attribution(backtest: dict[str, Any], signal: dict[str, Any]) -> str:
    if _status(_field(backtest, "outcome")) != "miss":
        return "hit"
    if _field(signal, "data_trust_status") == "unknown" and _field(signal, "content_credibility_status") == "not_recorded":
        return "unknown"
    if str(_field(signal, "data_trust_status") or "") in LOW_TRUST_STATUSES:
        return "data_quality_issue"
    if str(_field(signal, "content_credibility_status") or "") in QUALITY_WARNING_STATUSES:
        return "insufficient_evidence"
    if str(_field(signal, "report_conformance_status") or "") in QUALITY_WARNING_STATUSES:
        return "insufficient_evidence"
    reason = _status(_field(backtest, "reason"))
    if "risk" in reason or "event" in reason:
        return "risk_event"
    if "target" in reason or "timing" in reason:
        return "timing_wrong"
    if reason:
        return "thesis_wrong"
    return "unknown"


def _summary(details: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(details)
    hits = sum(1 for row in details if row["outcome"] == "hit")
    return {
        "total_evaluated": total,
        "hit_count": hits,
        "miss_count": total - hits,
        "hit_rate_pct": _rate(hits, total),
        "average_strategy_roi_pct": _average(details, "strategy_roi_pct"),
        "miss_attribution_counts": _counts(row["miss_attribution"] for row in details if row["outcome"] == "miss"),
        "low_quality_miss_count": sum(
            1 for row in details
            if row["outcome"] == "miss" and row["miss_attribution"] in {"data_quality_issue", "insufficient_evidence"}
        ),
    }


def _group_stats(details: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in details:
        group_key = str(_field(row, key) or "unknown")
        groups.setdefault(group_key, []).append(row)
    return {group_key: _group_summary(rows) for group_key, rows in sorted(groups.items())}


def _quality_group_stats(details: list[dict[str, Any]], signal_key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in details:
        signal = _dict(_field(row, "quality_signal"))
        group_key = str(_field(signal, signal_key) or "unknown")
        groups.setdefault(group_key, []).append(row)
    return {group_key: _group_summary(rows) for group_key, rows in sorted(groups.items())}


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    hits = sum(1 for row in rows if row["outcome"] == "hit")
    return {
        "count": total,
        "hit_count": hits,
        "miss_count": total - hits,
        "hit_rate_pct": _rate(hits, total),
        "average_strategy_roi_pct": _average(rows, "strategy_roi_pct"),
        "content_credibility_warning_count": sum(
            1 for row in rows
            if _field(_dict(_field(row, "quality_signal")), "content_credibility_status") in {"warning", "blocked"}
        ),
        "miss_attribution_counts": _counts(row["miss_attribution"] for row in rows if row["outcome"] == "miss"),
    }


def _strategy_evaluation(details: list[dict[str, Any]]) -> dict[str, Any]:
    artifacts = [
        {
            "pipeline_id": row["pipeline_id"],
            "metrics": {
                "outcome": row["outcome"],
                "strategy_roi_pct": row["strategy_roi_pct"],
                "excess_return_pct": row["strategy_roi_pct"],
            },
        }
        for row in details
    ]
    return evaluate_strategy_artifacts(artifacts)


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _field(mapping: dict[str, Any], key: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    return dict.get(mapping, key, default)


def _status(value: Any) -> str:
    return _text(value).lower()


def _text(value: Any) -> str:
    return safe_text(value).strip()


def _first_text(*values: Any, fallback: str = "") -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return fallback


def _first_status(*values: Any, fallback: str) -> str:
    for value in values:
        status = _status(value)
        if status:
            return status
    return fallback


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _number(value)
        if number is not None:
            return number
    return None


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False


def _average(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(_field(row, key)) for row in rows if _field(row, key) is not None]
    return round(mean(values), 4) if values else 0.0


def _rate(count: int, total: int) -> float:
    return round(count / total * 100, 4) if total else 0.0


__all__ = ["SCHEMA_VERSION", "build_outcome_calibration"]
