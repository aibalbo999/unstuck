"""Frozen evaluation policies, hashed so they cannot silently drift."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical import content_hash


DEFAULT_POLICIES = {
    "a_horizons_months": [3, 6, 12],
    "a_direction_only": True,
    "d_horizons_trading_days": [5, 10],
    "price_policy": "raw",
    "unknown_cost_is_null": True,
    "benchmark_default": "not_provided",
}


def validate_policies(policies: Mapping[str, Any]) -> str:
    if not isinstance(policies, Mapping) or not policies:
        raise ValueError("policies must be explicit")
    if policies.get("price_policy") != "raw":
        raise ValueError("only raw price policy is supported")
    if policies.get("unknown_cost_is_null") is not True:
        raise ValueError("unknown costs must remain null")
    return content_hash(policies)
