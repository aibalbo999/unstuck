"""Refresh an isolated institutional gap without reacquiring healthy core data."""
from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from data_freshness import assess_cached_financial_data
from data_trust import append_source_audit, finalize_data_trust
from institutional_source_refresh import (
    institutional_refresh_session, merge_institutional_source,
    validate_institutional_refresh_context,
)
from news_freshness_policy import apply_news_freshness
from source_applicability import source_is_applicable

from .audit_helpers import _append_cache_audit_entries
from .provider_execution import fetch_provider_results
from .cache_session_alignment import assess_session_aligned_cache


async def recover_cached_institutional(request, registry, cached):
    """Return (payload, replaced) when eligible, otherwise retain the full plan.

    Reuse the existing full-window/official-original admission checks. A failed
    attempt retains the old values and acquisition time, and does not trigger a
    second acquisition of the same provider through the full core collector.
    """
    ticker = request.ticker
    if request.options.force_refresh or cached.get('ticker') != ticker:
        return None
    _, freshness = assess_session_aligned_cache(
        cached, ticker, assessor=assess_cached_financial_data)
    if (freshness.get('stale_sources') != ['institutional_trading']
            or not source_is_applicable('institutional_trading', cached, ticker)):
        return None
    providers = [p for p in registry.for_request(request, source='institutional_trading')
                 if p.name == 'FinMind' and getattr(p, 'execute_in_workflow', True)]
    if len(providers) != 1:
        return None
    try:
        validate_institutional_refresh_context(cached, ticker)
        institutional_refresh_session(ticker)
    except HTTPException:
        return None

    data = deepcopy(cached)
    apply_news_freshness(data)
    data.update(_cache_hit=True, source_audit=[], data_freshness=freshness,
                source_freshness=freshness.get('source_freshness', {}))
    _append_cache_audit_entries(data, ticker)
    result, = await fetch_provider_results(request, providers, {'data': data, 'original_ticker': ticker})
    audit = deepcopy(result.audit)
    publication = _provisional_publication(result.value, ticker)
    if publication is not None:
        # An observed publication must be visible without replacing a mature
        # canonical source or renewing its acquisition clock. This result is
        # request-local only: replaced=False prevents a shared payload write.
        data['institutional_publication_observation'] = publication
    if result.status == 'success':
        try:
            merged = merge_institutional_source(data, data['source_audit'], result.value, [audit], ticker)
        except HTTPException:
            audit.update(status='degraded_enrichment', stale=True, coverage_status='partial',
                         error_kind='institutional_recovery_validation_failed',
                         message='新法人觀測未通過完整窗口或官方原件核對；保留舊內容與原取得時間。')
        else:
            # This is a normal data request, not a saved-report edit. Preserve
            # existing source notes without adding the report-rerun instruction.
            merged['data_source_notes'] = deepcopy(data.get('data_source_notes', []))
            return merged, True

    for entry in audit.get('related_entries') or []:
        if isinstance(entry, dict):
            append_source_audit(data, entry)
    append_source_audit(data, audit)
    finalize_data_trust(data)
    return data, False


def _provisional_publication(value, ticker):
    if not isinstance(value, dict):
        return None
    publication = value.get('publication_observation') or {}
    official = value.get('latest_official_observation') or {}
    proof = official.get('raw_evidence') or {}
    day = value.get('latest_date')
    if (publication.get('status') != 'available_provisional'
            or publication.get('observed_date') != day
            or official.get('date') != day or official.get('ticker') != ticker
            or official.get('market') != ('TPEX' if ticker.endswith('.TWO') else 'TWSE')
            or proof.get('status') != 'archived'
            or proof.get('evidence_kind') != 'raw_http_response_bytes'):
        return None
    return {**deepcopy(publication), 'ticker': ticker, 'eligible': False,
            'raw_evidence': deepcopy(proof), 'retrieved_at': proof.get('retrieved_at'),
            'categories': deepcopy(official.get('categories') or {}),
            'canonical_source_replaced': False,
            'reason': 'published_before_conservative_recheck; canonical values and clocks preserved'}
