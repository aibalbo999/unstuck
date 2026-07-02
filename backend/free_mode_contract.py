"""Free-mode runtime contract.

This module keeps the local-first system honest: optional paid providers may
exist, but every source used in free mode must have a free or free-with-key path.
"""

from __future__ import annotations

import os
from typing import Any

from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest


FREE_COMPATIBLE_TIERS = {"free", "free_with_key"}


def free_mode_enabled(env: dict[str, str] | None = None) -> bool:
    """Return whether the runtime should enforce free-mode assumptions."""
    env = env or os.environ
    raw = str(env.get("FREE_MODE") or env.get("STOCK_AGENT_FREE_MODE") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def build_free_mode_contract(
    registry: ProviderRegistry | None = None,
    request: FetchRequest | None = None,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Summarize whether current providers can run without paid dependencies."""
    registry = registry or ProviderRegistry()
    request = request or FetchRequest.from_ticker("AAPL")
    enabled = free_mode_enabled(env)
    providers = [
        provider.capability(request)
        for provider in registry.providers
        if provider.supports(request)
    ]
    violations = _free_mode_violations(providers)
    return {
        "enabled": enabled,
        "request": {"ticker": request.ticker},
        "providers": providers,
        "violations": violations if enabled else [],
        "can_run_without_paid_keys": (not enabled) or not violations,
        "free_compatible_tiers": sorted(FREE_COMPATIBLE_TIERS),
    }


def _free_mode_violations(providers: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_source_market: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for provider in providers:
        source = str(provider.get("source") or "unknown")
        for market in provider.get("markets") or ["unknown"]:
            by_source_market.setdefault((source, str(market)), []).append(provider)

    violations = []
    for (source, market), source_providers in sorted(by_source_market.items()):
        if any(str(provider.get("cost_tier")) in FREE_COMPATIBLE_TIERS for provider in source_providers):
            continue
        violations.append({"source": source, "market": market, "reason": "no_free_provider"})
    return violations


__all__ = ["FREE_COMPATIBLE_TIERS", "build_free_mode_contract", "free_mode_enabled"]
