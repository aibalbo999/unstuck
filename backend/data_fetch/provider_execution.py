"""Provider execution helpers for data-fetch workflow."""

from __future__ import annotations

import asyncio

from .types import FetchRequest, ProviderResult


async def fetch_provider_results(request: FetchRequest, providers: list, context: dict) -> list[ProviderResult]:
    if not providers:
        return []
    gathered = await asyncio.gather(
        *(provider.fetch_async(request, context) for provider in providers),
        return_exceptions=True,
    )
    results = []
    for provider, result in zip(providers, gathered):
        if isinstance(result, Exception):
            results.append(
                ProviderResult(
                    source=getattr(provider, "source", "unknown"),
                    provider=getattr(provider, "name", provider.__class__.__name__),
                    status="error",
                    value=None,
                    audit={
                        "source": getattr(provider, "source", "unknown"),
                        "provider": getattr(provider, "name", provider.__class__.__name__),
                        "status": "error",
                        "record_count": 0,
                        "cache_hit": bool((context.get("data") or {}).get("_cache_hit")),
                        "stale": False,
                        "error_kind": result.__class__.__name__,
                        "message": str(result)[:240],
                    },
                )
            )
            continue
        results.append(result)
    return results


def provider_value(results: list[ProviderResult], source: str, provider_name: str) -> list:
    for result in results:
        if result.source != source:
            continue
        if provider_name.lower() not in str(result.provider or "").lower():
            continue
        return result.value if isinstance(result.value, list) else []
    return []
