"""Pure metric summaries for the operator job dashboard."""

from __future__ import annotations

import math
from collections import defaultdict


def job_latency_summary(rows: list[dict]) -> dict:
    durations = sorted(
        max(
            0.0,
            float(row.get("finished_at") or row.get("updated_at"))
            - float(row.get("started_at") or row.get("created_at")),
        )
        for row in rows
    )
    if not durations:
        return {
            "completed_count": 0,
            "p50_seconds": None,
            "p95_seconds": None,
            "p99_seconds": None,
            "max_seconds": None,
        }
    return {
        "completed_count": len(durations),
        "p50_seconds": nearest_rank_percentile(durations, 50),
        "p95_seconds": nearest_rank_percentile(durations, 95),
        "p99_seconds": nearest_rank_percentile(durations, 99),
        "max_seconds": round(durations[-1], 1),
    }


def node_telemetry_summary(rows: list[dict]) -> dict:
    node_stats = defaultdict(_blank_telemetry_bucket)
    model_stats = defaultdict(_blank_telemetry_bucket)
    totals = _blank_telemetry_bucket()
    for row in rows:
        node_name = str(row.get("node_name") or "unknown")
        model = str(row.get("model") or "unknown")
        for bucket in (node_stats[node_name], model_stats[model], totals):
            _add_telemetry_row(bucket, row)
        error = str(row.get("error") or "").lower()
        if error:
            if "429" in error or "rate" in error or "quota" in error:
                model_stats[model]["rate_limit_errors"] += 1
            if "timeout" in error or "timed out" in error:
                model_stats[model]["timeout_errors"] += 1
            if " 5" in error or "500" in error or "503" in error or "server" in error:
                model_stats[model]["server_errors"] += 1
    return {
        "sample_size": len(rows),
        "nodes": {name: _finalize_telemetry_bucket(bucket) for name, bucket in sorted(node_stats.items())},
        "models": {name: _finalize_telemetry_bucket(bucket) for name, bucket in sorted(model_stats.items())},
        "totals": _finalize_telemetry_bucket(totals),
    }


def prompt_budget_summary(rows: list[dict]) -> dict:
    totals = _blank_prompt_bucket()
    nodes = defaultdict(_blank_prompt_bucket)
    models = defaultdict(_blank_prompt_bucket)
    for row in rows:
        node_name = str(row.get("node_name") or "unknown")
        model = str(row.get("model") or "unknown")
        for bucket in (totals, nodes[node_name], models[model]):
            _add_prompt_budget_row(bucket, row)
    return {
        **_finalize_prompt_bucket(totals),
        "sample_size": len(rows),
        "nodes": {name: _finalize_prompt_bucket(bucket) for name, bucket in sorted(nodes.items())},
        "models": {name: _finalize_prompt_bucket(bucket) for name, bucket in sorted(models.items())},
    }


def _blank_telemetry_bucket() -> dict:
    return {
        "calls": 0,
        "successes": 0,
        "failures": 0,
        "retry_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_hits": 0,
        "quality_gate_failures": 0,
        "latencies": [],
        "rate_limit_errors": 0,
        "timeout_errors": 0,
        "server_errors": 0,
    }


def _add_telemetry_row(bucket: dict, row: dict) -> None:
    status = str(row.get("status") or "").lower()
    bucket["calls"] += 1
    if status == "success":
        bucket["successes"] += 1
    else:
        bucket["failures"] += 1
    bucket["retry_count"] += int(row.get("retry_count") or 0)
    bucket["input_tokens"] += int(row.get("input_tokens") or 0)
    bucket["output_tokens"] += int(row.get("output_tokens") or 0)
    bucket["cache_hits"] += int(bool(row.get("cache_hit")))
    if row.get("quality_gate_pass") == 0:
        bucket["quality_gate_failures"] += 1
    latency = row.get("latency_ms")
    if latency is not None:
        try:
            bucket["latencies"].append(float(latency))
        except (TypeError, ValueError):
            pass


def _finalize_telemetry_bucket(bucket: dict) -> dict:
    calls = int(bucket["calls"])
    latencies = sorted(bucket["latencies"])
    finalized = {
        "calls": calls,
        "successes": int(bucket["successes"]),
        "failures": int(bucket["failures"]),
        "failure_rate": round(bucket["failures"] / calls, 4) if calls else 0.0,
        "retry_count": int(bucket["retry_count"]),
        "input_tokens": int(bucket["input_tokens"]),
        "output_tokens": int(bucket["output_tokens"]),
        "cache_hit_rate": round(bucket["cache_hits"] / calls, 4) if calls else 0.0,
        "quality_gate_failures": int(bucket["quality_gate_failures"]),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "p95_latency_ms": nearest_rank_percentile(latencies, 95) if latencies else None,
    }
    for key in ("rate_limit_errors", "timeout_errors", "server_errors"):
        if bucket.get(key):
            finalized[key] = int(bucket[key])
    return finalized


def _blank_prompt_bucket() -> dict:
    return {
        "tokenized_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_hit_count": 0,
        "estimated_cached_input_tokens": 0,
    }


def _add_prompt_budget_row(bucket: dict, row: dict) -> None:
    input_tokens = int(row.get("input_tokens") or 0)
    output_tokens = int(row.get("output_tokens") or 0)
    if input_tokens or output_tokens:
        bucket["tokenized_calls"] += 1
    bucket["input_tokens"] += input_tokens
    bucket["output_tokens"] += output_tokens
    if row.get("cache_hit"):
        bucket["cache_hit_count"] += 1
        bucket["estimated_cached_input_tokens"] += input_tokens


def _finalize_prompt_bucket(bucket: dict) -> dict:
    tokenized_calls = int(bucket["tokenized_calls"])
    input_tokens = int(bucket["input_tokens"])
    output_tokens = int(bucket["output_tokens"])
    total_tokens = input_tokens + output_tokens
    return {
        "tokenized_calls": tokenized_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "avg_input_tokens": round(input_tokens / tokenized_calls, 1) if tokenized_calls else 0.0,
        "avg_output_tokens": round(output_tokens / tokenized_calls, 1) if tokenized_calls else 0.0,
        "avg_total_tokens": round(total_tokens / tokenized_calls, 1) if tokenized_calls else 0.0,
        "cache_hit_count": int(bucket["cache_hit_count"]),
        "estimated_cached_input_tokens": int(bucket["estimated_cached_input_tokens"]),
    }


def nearest_rank_percentile(sorted_values: list[float], percentile: int) -> float | None:
    if not sorted_values:
        return None
    rank = max(1, math.ceil((percentile / 100) * len(sorted_values)))
    return round(sorted_values[min(rank, len(sorted_values)) - 1], 1)
