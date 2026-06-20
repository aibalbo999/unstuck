"""Refresh planning for optional provider sources."""

from __future__ import annotations

from data_freshness import source_is_stale

from .audit_helpers import _append_skipped_fresh_cache_audit
from .types import FetchRequest


OPTIONAL_WORKFLOW_SOURCES = (
    "recent_catalysts",
    "global_market_context",
    "international_news_context",
    "macro_indicators",
    "chip_data",
    "alternative_data",
    "peer_discovery",
)


def collect_optional_providers(request: FetchRequest, registry, data: dict, resolved_ticker: str) -> tuple[list, dict[str, bool]]:
    """Return providers to execute and a per-source refresh decision."""
    cache_hit = bool(data.get("_cache_hit"))
    refresh_by_source = {
        source: (not cache_hit) or source_is_stale(data, source, resolved_ticker)
        for source in OPTIONAL_WORKFLOW_SOURCES
    }
    providers = []
    for source, should_refresh in refresh_by_source.items():
        if should_refresh:
            providers.extend(
                provider
                for provider in registry.for_request(request, source=source)
                if getattr(provider, "execute_in_workflow", True)
            )
        else:
            _append_skipped_fresh_cache_audit(data, (source,))
    return providers, refresh_by_source
