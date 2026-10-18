"""Refresh planning for optional provider sources."""

from __future__ import annotations

import math
import time

from data_freshness import source_is_stale, source_timestamp_epoch
from report_freshness_summary import safe_bool
from source_applicability import source_is_applicable

from .audit_helpers import _append_skipped_fresh_cache_audit
from .types import FetchRequest


OPTIONAL_WORKFLOW_SOURCES = (
    "recent_catalysts",
    "earnings_call",
    "global_market_context",
    "international_news_context",
    "macro_indicators",
    "chip_data",
    "alternative_data",
    "annual_workforce",
    "social_sentiment",
    "sec_edgar",
    "taiwan_open_data",
    "official_disclosures",
    "peer_discovery",
)


def _conference_metadata_due(data: dict, ticker: str) -> bool:
    """Metadata has a shorter discovery interval than acquired call content.

    This only schedules the ordinary Taiwan provider; it never bypasses its
    raw cache, retry cooldown, identity checks or content acceptance rules.
    """
    if not str(ticker).upper().endswith(('.TW', '.TWO')):
        return False
    value = data.get('earnings_call')
    if not isinstance(value, dict):
        return False  # Missing source already uses source_is_stale.
    from mops_body_cache import supported, body_discovered, originals_due
    ready_eligible=False
    from .market_sources.mops_presentation import supports as material_supported, validate_context
    if material_supported(ticker) and validate_context(data,ticker):
        ready_eligible=supported(ticker)
        if originals_due(value,ticker):
            return True
    if isinstance(value.get('transcript_excerpt'), str) and value['transcript_excerpt'].strip():
        return False
    documents = value.get('documents')
    if isinstance(documents, list) and any(
        isinstance(doc, dict) and isinstance(doc.get('pages'), list) and any(
            isinstance(page, dict) and isinstance(page.get('text'), str) and page['text'].strip()
            for page in doc['pages']) for doc in documents
    ):
        return False
    if ready_eligible and body_discovered(ticker):
        return True
    stamp = source_timestamp_epoch(data, 'earnings_call')
    if type(stamp) not in (int, float) or not math.isfinite(stamp):
        return True
    age = time.time() - stamp
    return age < 0 or age >= 6 * 60 * 60


def collect_optional_providers(request: FetchRequest, registry, data: dict, resolved_ticker: str, *, sources=None) -> tuple[list, dict[str, bool]]:
    """Return providers to execute and a per-source refresh decision."""
    cache_hit = safe_bool(data.get("_cache_hit"))
    refresh_by_source = {
        source: source_is_applicable(source, data, resolved_ticker) and (
            (not cache_hit) or source_is_stale(data, source, resolved_ticker)
            or source == 'earnings_call' and _conference_metadata_due(data, resolved_ticker))
        for source in OPTIONAL_WORKFLOW_SOURCES if sources is None or source in sources
    }
    providers = []
    for source, should_refresh in refresh_by_source.items():
        if should_refresh:
            providers.extend(
                provider
                for provider in registry.for_request(request, source=source)
                if getattr(provider, "execute_in_workflow", True)
            )
        elif source_is_applicable(source, data, resolved_ticker):
            _append_skipped_fresh_cache_audit(data, (source,))
    return providers, refresh_by_source
