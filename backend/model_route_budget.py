"""Model route latency, retry, and token budget summaries."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean
from typing import Any

from report_freshness_summary import safe_bool


SCHEMA_VERSION = "model_route_budget.v1"


def build_model_route_budget(
    rows: list[dict[str, Any]],
    *,
    provider_error_rows: list[dict[str, Any]] | None = None,
    slow_route_p95_ms: int = 60_000,
    retry_storm_threshold: int = 6,
) -> dict[str, Any]:
    telemetry = [row for row in rows or [] if isinstance(row, dict)]
    provider_errors = [row for row in provider_error_rows or [] if isinstance(row, dict)]
    routes = defaultdict(_blank_bucket)
    models = defaultdict(_blank_bucket)
    for row in telemetry:
        model = _model(row)
        route_key = f"{_pipeline(row)}/{model}"
        for bucket in (routes[route_key], models[model]):
            _add_row(bucket, row)
    for row in provider_errors:
        model = _model(row)
        route_key = f"{_pipeline(row)}/{model}"
        for bucket in (routes[route_key], models[model]):
            _add_provider_error(bucket, row)
    finalized_routes = {key: _finalize_bucket(bucket) for key, bucket in sorted(routes.items())}
    finalized_models = {key: _finalize_bucket(bucket) for key, bucket in sorted(models.items())}
    warnings = _warnings(finalized_routes, slow_route_p95_ms=slow_route_p95_ms, retry_storm_threshold=retry_storm_threshold)
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "sample_size": len(telemetry),
            "provider_error_sample_size": len(provider_errors),
            "provider_error_scope": "recent_api_usage_events",
            "route_count": len(finalized_routes),
            "model_count": len(finalized_models),
            "warning_count": len(warnings),
            "estimated_cost_available": False,
            "estimated_cost_usd": None,
        },
        "routes": finalized_routes,
        "models": finalized_models,
        "warnings": warnings,
    }


def _blank_bucket() -> dict[str, Any]:
    return {
        "calls": 0,
        "failures": 0,
        "retry_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "billable_input_tokens": 0,
        "billable_output_tokens": 0,
        "cache_hit_count": 0,
        "quality_gate_failures": 0,
        "provider_error_count": 0,
        "provider_quota_error_count": 0,
        "provider_non_quota_error_count": 0,
        "provider_status_code_counts": {},
        "provider_quota_status_code_counts": {},
        "provider_non_quota_status_code_counts": {},
        "latencies": [],
    }


def _add_row(bucket: dict[str, Any], row: dict[str, Any]) -> None:
    input_tokens = _int(row.get("input_tokens"))
    output_tokens = _int(row.get("output_tokens"))
    cache_hit = safe_bool(row.get("cache_hit"))
    bucket["calls"] += 1
    bucket["failures"] += 0 if str(row.get("status") or "").lower() == "success" else 1
    bucket["retry_count"] += _int(row.get("retry_count"))
    bucket["input_tokens"] += input_tokens
    bucket["output_tokens"] += output_tokens
    if cache_hit:
        bucket["cache_hit_count"] += 1
    else:
        bucket["billable_input_tokens"] += input_tokens
        bucket["billable_output_tokens"] += output_tokens
    quality_gate_pass = row.get("quality_gate_pass")
    if quality_gate_pass is not None and not safe_bool(quality_gate_pass):
        bucket["quality_gate_failures"] += 1
    latency = _float(row.get("latency_ms"))
    if latency is not None:
        bucket["latencies"].append(latency)


def _add_provider_error(bucket: dict[str, Any], row: dict[str, Any]) -> None:
    bucket["provider_error_count"] += 1
    is_quota = str(row.get("status") or "").lower() in {"quota_error", "rate_limited"}
    if is_quota:
        bucket["provider_quota_error_count"] += 1
    else:
        bucket["provider_non_quota_error_count"] += 1
    status_code = _status_code(row.get("provider_status_code"))
    if status_code is not None:
        key = str(status_code)
        bucket["provider_status_code_counts"][key] = int(bucket["provider_status_code_counts"].get(key) or 0) + 1
        target = bucket["provider_quota_status_code_counts"] if is_quota else bucket["provider_non_quota_status_code_counts"]
        target[key] = int(target.get(key) or 0) + 1


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    calls = int(bucket["calls"])
    input_tokens = int(bucket["input_tokens"])
    output_tokens = int(bucket["output_tokens"])
    billable_input = int(bucket["billable_input_tokens"])
    billable_output = int(bucket["billable_output_tokens"])
    latencies = sorted(bucket["latencies"])
    return {
        "calls": calls,
        "failures": int(bucket["failures"]),
        "failure_rate": round(bucket["failures"] / calls, 4) if calls else 0.0,
        "retry_count": int(bucket["retry_count"]),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "billable_input_tokens": billable_input,
        "billable_output_tokens": billable_output,
        "billable_total_tokens": billable_input + billable_output,
        "cache_hit_count": int(bucket["cache_hit_count"]),
        "quality_gate_failures": int(bucket["quality_gate_failures"]),
        "provider_error_count": int(bucket["provider_error_count"]),
        "provider_quota_error_count": int(bucket["provider_quota_error_count"]),
        "provider_non_quota_error_count": int(bucket["provider_non_quota_error_count"]),
        "provider_status_code_counts": _sorted_counts(bucket["provider_status_code_counts"]),
        "provider_quota_status_code_counts": _sorted_counts(bucket["provider_quota_status_code_counts"]),
        "provider_non_quota_status_code_counts": _sorted_counts(bucket["provider_non_quota_status_code_counts"]),
        "avg_latency_ms": round(mean(latencies), 1) if latencies else None,
        "p95_latency_ms": _nearest_rank_percentile(latencies, 95) if latencies else None,
        "estimated_cost_usd": None,
    }


def _warnings(routes: dict[str, dict[str, Any]], *, slow_route_p95_ms: int, retry_storm_threshold: int) -> list[dict[str, Any]]:
    warnings = []
    for route, stats in routes.items():
        if int(stats.get("retry_count") or 0) >= retry_storm_threshold:
            warnings.append(_warning("retry_storm", route, f"{route} retry_count={stats['retry_count']}"))
        if stats.get("p95_latency_ms") is not None and float(stats["p95_latency_ms"]) >= slow_route_p95_ms:
            warnings.append(_warning("slow_route", route, f"{route} p95_latency_ms={stats['p95_latency_ms']}"))
        if int(stats.get("quality_gate_failures") or 0) > 0:
            warnings.append(_warning("quality_gate_failures", route, f"{route} quality_gate_failures={stats['quality_gate_failures']}"))
        provider_error_count = int(stats.get("provider_error_count") or 0)
        provider_quota_error_count = int(stats.get("provider_quota_error_count") or 0)
        provider_non_quota_error_count = int(stats.get("provider_non_quota_error_count") or 0)
        if provider_quota_error_count > 0:
            status_codes = _format_counts(stats.get("provider_quota_status_code_counts"))
            warnings.append(
                _warning(
                    "provider_quota_errors",
                    route,
                    f"{route} provider_quota_error_count={provider_quota_error_count} provider_error_count={provider_error_count}"
                    + (f" provider_status_codes={status_codes}" if status_codes else ""),
                )
            )
        if provider_non_quota_error_count > 0:
            status_codes = _format_counts(stats.get("provider_non_quota_status_code_counts"))
            warnings.append(
                _warning(
                    "provider_errors",
                    route,
                    f"{route} provider_non_quota_error_count={provider_non_quota_error_count} provider_error_count={provider_error_count}"
                    + (f" provider_status_codes={status_codes}" if status_codes else ""),
                )
            )
    return warnings


def _warning(warning_id: str, route: str, message: str) -> dict[str, str]:
    return {"id": warning_id, "route": route, "message": message}


def _status_code(value: Any) -> int | None:
    try:
        code = int(value)
    except (TypeError, ValueError, ArithmeticError):
        return None
    return code if 400 <= code <= 599 else None


def _sorted_counts(value: Any) -> dict[str, int]:
    rows = value if isinstance(value, dict) else {}
    return {str(key): int(rows[key]) for key in sorted(rows, key=lambda item: int(item))}


def _format_counts(value: Any) -> str:
    return ",".join(f"{key}:{count}" for key, count in _sorted_counts(value).items())


def _nearest_rank_percentile(sorted_values: list[float], percentile: int) -> float | None:
    if not sorted_values:
        return None
    index = max(0, min(len(sorted_values) - 1, math.ceil(percentile / 100 * len(sorted_values)) - 1))
    return round(sorted_values[index], 1)


def _pipeline(row: dict[str, Any]) -> str:
    return str(row.get("pipeline_id") or "unknown")


def _model(row: dict[str, Any]) -> str:
    return str(row.get("model") or "unknown")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["SCHEMA_VERSION", "build_model_route_budget"]
