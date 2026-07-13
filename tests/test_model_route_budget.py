from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_model_route_budget_excludes_cache_hits_from_billable_tokens_and_keeps_unknown_cost_null():
    from model_route_budget import build_model_route_budget

    budget = build_model_route_budget([
        {
            "pipeline_id": "v1",
            "node_name": "valuation_agent",
            "model": "gemini-2.5-pro",
            "latency_ms": 2_000,
            "status": "success",
            "retry_count": 0,
            "input_tokens": 1_000,
            "output_tokens": 250,
            "cache_hit": 0,
            "quality_gate_pass": 1,
        },
        {
            "pipeline_id": "v1",
            "node_name": "valuation_agent",
            "model": "gemini-2.5-pro",
            "latency_ms": 100,
            "status": "success",
            "retry_count": 0,
            "input_tokens": 1_000,
            "output_tokens": 250,
            "cache_hit": 1,
            "quality_gate_pass": 1,
        },
    ])

    route = budget["routes"]["v1/gemini-2.5-pro"]
    assert route["calls"] == 2
    assert route["cache_hit_count"] == 1
    assert route["total_tokens"] == 2_500
    assert route["billable_total_tokens"] == 1_250
    assert route["estimated_cost_usd"] is None
    assert budget["summary"]["estimated_cost_available"] is False


def test_model_route_budget_flags_retry_storm_and_slow_routes():
    from model_route_budget import build_model_route_budget

    budget = build_model_route_budget(
        [
            {
                "pipeline_id": "v2",
                "node_name": "agent_7",
                "model": "gemini-2.5-pro",
                "latency_ms": 65_000,
                "status": "failed",
                "retry_count": 3,
                "input_tokens": 800,
                "output_tokens": 200,
                "cache_hit": 0,
                "quality_gate_pass": 0,
            },
            {
                "pipeline_id": "v2",
                "node_name": "agent_7",
                "model": "gemini-2.5-pro",
                "latency_ms": 70_000,
                "status": "failed",
                "retry_count": 2,
                "input_tokens": 900,
                "output_tokens": 250,
                "cache_hit": 0,
                "quality_gate_pass": 0,
            },
        ],
        slow_route_p95_ms=60_000,
        retry_storm_threshold=4,
    )

    route = budget["routes"]["v2/gemini-2.5-pro"]
    assert route["retry_count"] == 5
    assert route["quality_gate_failures"] == 2
    assert route["p95_latency_ms"] == 70_000
    warning_ids = {warning["id"] for warning in budget["warnings"]}
    assert {"retry_storm", "slow_route", "quality_gate_failures"} <= warning_ids
    assert budget["summary"]["warning_count"] == 3


def test_model_route_budget_groups_by_model_without_pipeline_loss():
    from model_route_budget import build_model_route_budget

    budget = build_model_route_budget([
        {"pipeline_id": "v1", "node_name": "agent_1", "model": "model-a", "latency_ms": 1_000, "status": "success"},
        {"pipeline_id": "v2", "node_name": "agent_2", "model": "model-a", "latency_ms": 2_000, "status": "success"},
    ])

    assert set(budget["routes"]) == {"v1/model-a", "v2/model-a"}
    assert budget["models"]["model-a"]["calls"] == 2
    assert budget["models"]["model-a"]["p95_latency_ms"] == 2_000
