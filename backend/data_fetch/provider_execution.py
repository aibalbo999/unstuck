"""Provider execution helpers for data-fetch workflow."""

from __future__ import annotations

import asyncio
import time

from dataclasses import replace
from provider_correlation import current_correlation, source_operation
from .types import FetchRequest, ProviderResult


async def fetch_correlated_provider(provider, request, context, *, capture_errors=False, error_audit_sink=None):
    """Bind one invocation; optional passive failure sink never changes errors.

    The sink runs before the source context exits. It receives no exception text
    or inferred HTTP state, and does not turn cancellation into a provider error.
    """
    source = getattr(provider, "source", "unknown")
    name = getattr(provider, "name", provider.__class__.__name__)
    from finmind_transport_receipts import receipt_observation_scope
    with source_operation(source, name), receipt_observation_scope(request.options.record_provider_sla):
        started = time.monotonic()
        result_received = False
        try:
            result = await provider.fetch_async(request, context)
            result_received = True
            audit = dict(result.audit or {})
            # Existing provenance belongs to its original invocation.
            if not any(audit.get(key) for key in ("operation_id", "fetch_id", "job_id", "attempt_id")):
                for key, value in current_correlation().items():
                    audit.setdefault(key, value)
            return replace(result, audit=audit)
        except BaseException as error:
            if error_audit_sink is not None and isinstance(error, (Exception, asyncio.CancelledError)):
                cancelled = isinstance(error, asyncio.CancelledError)
                audit = {**current_correlation(), "source": source, "provider": name,
                    "status": "unknown" if cancelled else "error", "record_count": 0,
                    "cache_hit": False, "stale": False, "error_kind": error.__class__.__name__,
                    "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
                    "retrieval_status": "cancelled" if cancelled else "error",
                    "message": "Provider invocation cancelled; transport outcome unknown." if cancelled else
                               "Provider invocation failed; transport outcome unknown."}
                try:
                    error_audit_sink(audit)
                except Exception:
                    pass  # Observability cannot replace the original exception.
            if not capture_errors or result_received or not isinstance(error, Exception):
                raise
            return ProviderResult(
                source=source, provider=name, status="error", value=None,
                audit={**current_correlation(), "source": source, "provider": name,
                       "status": "error", "record_count": 0, "cache_hit": False,
                       "stale": False, "error_kind": error.__class__.__name__,
                       "message": str(error)[:240]},
            )



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
