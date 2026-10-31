"""Provider execution helpers for data-fetch workflow."""

from __future__ import annotations

import asyncio

from dataclasses import replace
from provider_correlation import current_correlation, source_operation
from .types import FetchRequest, ProviderResult


async def fetch_correlated_provider(provider, request, context, *, capture_errors=False):
    """Bind one invocation, without asserting delivery or changing cached provenance."""
    source = getattr(provider, "source", "unknown")
    name = getattr(provider, "name", provider.__class__.__name__)
    with source_operation(source, name):
        try:
            result = await provider.fetch_async(request, context)
        except Exception as error:
            if not capture_errors:
                raise
            return ProviderResult(
                source=source, provider=name, status="error", value=None,
                audit={**current_correlation(), "source": source, "provider": name,
                       "status": "error", "record_count": 0, "cache_hit": False,
                       "stale": False, "error_kind": error.__class__.__name__,
                       "message": str(error)[:240]},
            )
        audit = dict(result.audit or {})
        # Existing partial provenance belongs to its original invocation too.
        # Mixing it with the current fetch would invent a historical linkage.
        if not any(audit.get(key) for key in ("operation_id", "fetch_id", "job_id", "attempt_id")):
            for key, value in current_correlation().items():
                audit.setdefault(key, value)
        return replace(result, audit=audit)


async def fetch_provider_results(request: FetchRequest, providers: list, context: dict) -> list[ProviderResult]:
    if not providers:
        return []
    return list(await asyncio.gather(
        *(fetch_correlated_provider(provider, request, context, capture_errors=True)
          for provider in providers),
    ))


def provider_value(results: list[ProviderResult], source: str, provider_name: str) -> list:
    for result in results:
        if result.source != source:
            continue
        if provider_name.lower() not in str(result.provider or "").lower():
            continue
        return result.value if isinstance(result.value, list) else []
    return []
