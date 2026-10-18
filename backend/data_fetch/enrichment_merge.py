"""Merge optional HTTP enrichment into legacy-compatible payloads."""

from __future__ import annotations

import time as time_module
from typing import Optional, Sequence

from data_trust import (
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_DEGRADED_ENRICHMENT,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
    finalize_data_trust,
    source_record_count,
)
from config import CATALYST_LOOKBACK_DAYS, SEARCH_CATALYST_MAX_RESULTS, SEARCH_PEER_DISCOVERY_MAX_RESULTS
from report_freshness_summary import safe_bool
from news_freshness_policy import apply_news_freshness
from news_record_utils import parse_news_datetime
from source_applicability import apply_source_applicability
from data_freshness import build_source_freshness_entry
from provider_observation_details import observation_details
from .market_sources.common import _dedupe_records, first_number, is_missing_value

from .audit_helpers import _append_source_fetch_audit, _mark_market_data_fetched, _mark_sources_fetched
from .formatting import format_number


def _merge_optional_http_bundle(
    data: dict,
    http_bundle: dict,
    refreshed_sources: Optional[Sequence[str]] = None,
    source_errors: Optional[dict] = None,
) -> dict:
    """Merge async HTTP-backed enrichment into a base yfinance/FinMind payload."""
    if not data or "error" in data or not http_bundle:
        return data
    refreshed_sources = tuple(refreshed_sources or ())
    source_errors = source_errors or {}
    refresh_epoch = time_module.time()
    ticker = str(data.get("ticker") or "").strip().upper()

    combined_catalysts = [item for key in ("recent_catalysts", "additional_recent_catalysts", "historical_catalysts", "unverified_catalysts", "identity_rejected_catalysts")
                          for item in (data.get(key) or [])]
    combined_catalysts.extend(http_bundle.get("free_news", []) or [])
    combined_catalysts.extend(http_bundle.get("official_company_history", []) or [])
    combined_catalysts.extend(http_bundle.get("tpex_company_history", []) or [])
    combined_catalysts.extend(http_bundle.get("issuer_news", []) or [])
    combined_catalysts.extend(http_bundle.get("official_trading_notices", []) or [])
    combined_catalysts.extend(http_bundle.get("search_catalysts", []) or [])
    combined_catalysts.extend(http_bundle.get("fmp_news", []) or [])
    combined_catalysts.extend(http_bundle.get("yahoo_news", []) or [])
    apply_news_freshness(data, cutoff=refresh_epoch, records=combined_catalysts, limit=SEARCH_CATALYST_MAX_RESULTS)

    from peer_relationship_evidence import POLICY, is_reported_peer_record, peer_selection_diagnostics
    from .market_sources.yahoo_peer_ranking import (
        POLICY as PUBLISHED_PEER_POLICY, is_published_peer_record,
    )
    from .market_sources.moneydj_peer_cohort import (
        POLICY as MONEYDJ_PEER_POLICY, is_moneydj_peer_record,
    )
    from .market_sources.moneydj_medical_peer_cohort import (
        POLICY as MEDICAL_PEER_POLICY,is_medical_peer_record,medical_record_hint,
    )
    from .market_sources.official_segment_discovery import (
        POLICY as SEGMENT_PEER_POLICY, is_segment_discovery_record, segment_record_hint,
    )
    peer_audit = http_bundle.get("_peer_discovery_audit") or {}
    if not peer_audit and "peer_discovery" in refreshed_sources:
        peer_audit = next((entry for entry in reversed(data.get("source_audit", []))
                           if isinstance(entry, dict) and entry.get("source") == "peer_discovery"), {})
    if peer_audit.get("selection_policy") == POLICY and http_bundle.get("_peer_discovery_audit"):
        from data_trust import append_source_audit
        append_source_audit(data, peer_audit)
    peer_audits = [entry for entry in data.get("source_audit", [])
                   if isinstance(entry, dict) and entry.get("source") == "peer_discovery"]
    if peer_audit and peer_audit not in peer_audits:
        peer_audits.append(peer_audit)
    previous_peers = data.get("peer_discovery_results", []) or []
    incoming_peers = [*(http_bundle.get("search_peer_discovery", []) or []),
                      *(http_bundle.get("publisher_peer_discovery", []) or []),
                      *(http_bundle.get("moneydj_peer_discovery", []) or []),
                      *(http_bundle.get("medical_peer_discovery", []) or []),
                      *(http_bundle.get("official_segment_peer_discovery", []) or [])]
    verify_peer = lambda item: (is_segment_discovery_record(item,ticker) if segment_record_hint(item) else
                               is_medical_peer_record(item,ticker) if medical_record_hint(item) else
                               is_reported_peer_record(item,ticker) or is_published_peer_record(item,ticker)
                               or is_moneydj_peer_record(item,ticker))
    policy_active = any(entry.get("selection_policy") in {POLICY, PUBLISHED_PEER_POLICY, MONEYDJ_PEER_POLICY,MEDICAL_PEER_POLICY,SEGMENT_PEER_POLICY}
                        for entry in peer_audits)
    typed_present=any(medical_record_hint(r) or segment_record_hint(r) for r in [*incoming_peers,*previous_peers])
    if (peer_selection_diagnostics(ticker) and policy_active) or typed_present:
        from copy import deepcopy
        archive = data.setdefault("source_record_archive", [])
        # New qualified fields/date win over an old record with the same URL.
        verified_incoming = [item for item in incoming_peers if verify_peer(item)]
        # Aggregate freshness/status must use the newly accepted evidence, not raw input.
        http_bundle = {**http_bundle, "search_peer_discovery": verified_incoming}
        peer_discovery = []
        for records, reason in ((incoming_peers, "incoming_peer_relationship_unverified"),
                                (previous_peers, "legacy_peer_relationship_unverified")):
            for record in records:
                if verify_peer(record):
                    peer_discovery.append(record)
                else:
                    archived = {"source": "peer_discovery", "reason": reason, "record": deepcopy(record)}
                    if archived not in archive:
                        archive.append(archived)
        for audit in peer_audits:
            for archived in audit.get("source_record_archive", []):
                if archived not in archive:
                    archive.append(deepcopy(archived))
        data["peer_discovery_results"] = _dedupe_records(peer_discovery, limit=SEARCH_PEER_DISCOVERY_MAX_RESULTS)
    else:
        peer_discovery = [*previous_peers, *incoming_peers]
        if peer_discovery:
            data["peer_discovery_results"] = _dedupe_records(peer_discovery, limit=SEARCH_PEER_DISCOVERY_MAX_RESULTS)

    global_context = http_bundle.get("global_market_context", {}) or {}
    if isinstance(global_context, dict) and global_context:
        data["global_market_context"] = global_context

    news_context = http_bundle.get("international_news_context", {}) or {}
    if isinstance(news_context, dict) and news_context:
        data["international_news_context"] = news_context

    macro_indicators = http_bundle.get("macro_indicators", {}) or {}
    if isinstance(macro_indicators, dict) and macro_indicators:
        data["macro_indicators"] = macro_indicators

    chip_data = http_bundle.get("chip_data", {}) or {}
    if isinstance(chip_data, dict) and chip_data:
        data["chip_data"] = chip_data

    alternative_data = http_bundle.get("alternative_data", {}) or {}
    if isinstance(alternative_data, dict) and alternative_data:
        data["alternative_data"] = alternative_data

    annual_workforce = http_bundle.get("annual_workforce", {}) or {}
    if isinstance(annual_workforce, dict) and annual_workforce:
        data["annual_workforce"] = annual_workforce

    social_sentiment = http_bundle.get("social_sentiment", {}) or {}
    if isinstance(social_sentiment, dict) and social_sentiment:
        data["social_sentiment"] = social_sentiment
        from source_content_selection import reselect_social_context
        reselect_social_context(data, cutoff=refresh_epoch)
        social_sentiment = data["social_sentiment"]
        sentiment_context = dict(data.get("sentiment_context") or {})
        sentiment_context["social_sentiment"] = social_sentiment
        data["sentiment_context"] = sentiment_context

    sec_edgar = http_bundle.get("sec_edgar", {}) or {}
    if isinstance(sec_edgar, dict) and sec_edgar:
        data["sec_edgar"] = sec_edgar

    taiwan_open_data = http_bundle.get("taiwan_open_data", {}) or {}
    if isinstance(taiwan_open_data, dict) and taiwan_open_data:
        data["taiwan_open_data"] = taiwan_open_data

    official_disclosures = http_bundle.get("official_disclosures", {}) or {}
    if isinstance(official_disclosures, dict) and official_disclosures:
        data["official_disclosures"] = official_disclosures

    earnings_call = http_bundle.get("earnings_call", {}) or {}
    if isinstance(earnings_call, dict) and earnings_call:
        data["earnings_call"] = earnings_call

    fmp_quote = http_bundle.get("fmp_quote", {}) or {}
    if isinstance(fmp_quote, dict) and fmp_quote:
        updated_fields = []
        if is_missing_value(data.get("current_price")):
            current_price = first_number(fmp_quote.get("price"), fmp_quote.get("previousClose"))
            if current_price is not None:
                data["current_price"] = current_price
                data["current_price_fmt"] = f"NT${current_price:.2f}"
                updated_fields.append("current_price")
        if is_missing_value(data.get("market_cap_raw")):
            market_cap = first_number(fmp_quote.get("marketCap"))
            if market_cap is not None:
                data["market_cap_raw"] = market_cap
                data["market_cap_fmt"] = format_number(market_cap, "億")
                updated_fields.append("market_cap")
        if is_missing_value(data.get("pe_ratio_raw")):
            pe_ratio = first_number(fmp_quote.get("pe"), fmp_quote.get("peRatio"))
            if pe_ratio is not None:
                data["pe_ratio_raw"] = pe_ratio
                data["pe_ratio"] = f"{pe_ratio:.1f}x"
                updated_fields.append("pe_ratio")
        if is_missing_value(data.get("week_52_high")):
            week_52_high = first_number(fmp_quote.get("yearHigh"), fmp_quote.get("priceAvg200"))
            if week_52_high is not None:
                data["week_52_high"] = week_52_high
                data["week_52_high_fmt"] = f"NT${week_52_high:.2f}"
                updated_fields.append("week_52_high")
        if is_missing_value(data.get("week_52_low")):
            week_52_low = first_number(fmp_quote.get("yearLow"))
            if week_52_low is not None:
                data["week_52_low"] = week_52_low
                data["week_52_low_fmt"] = f"NT${week_52_low:.2f}"
                updated_fields.append("week_52_low")

        if updated_fields:
            _mark_market_data_fetched(
                data,
                ticker,
                fetched_at_epoch=refresh_epoch,
                cache_hit=safe_bool(data.get("_cache_hit")),
            )
            _append_source_fetch_audit(
                data,
                "market_data",
                "FMP stable quote",
                AUDIT_STATUS_SUCCESS,
                fetched_at_epoch=refresh_epoch,
                finished_at_epoch=refresh_epoch,
                record_count=len(updated_fields),
                cache_hit=safe_bool(data.get("_cache_hit")),
                stale=False,
                message="async FMP quote bundle 補齊缺漏市場欄位：" + ", ".join(updated_fields),
            )
            data.setdefault("data_source_notes", []).append(
                "部分市場欄位由 async FMP quote bundle 補值：" + ", ".join(updated_fields)
            )

    if refreshed_sources:
        from source_content_selection import select_company_records
        eligible_issuer_rows, _ = select_company_records(
            http_bundle.get('issuer_news') or [], data, cutoff=refresh_epoch,
            lookback_days=CATALYST_LOOKBACK_DAYS,
        )
        prior_audits = {entry.get('source'): entry for entry in data.get('source_audit', []) if isinstance(entry, dict)}
        for source in refreshed_sources:
            count = source_record_count(source, data)
            error_message = str(source_errors.get(source) or "")
            payload = http_bundle.get(source)
            payload = payload if isinstance(payload, dict) else {}
            upstream = prior_audits.get(source, {})
            if source == 'peer_discovery' and count > 0:
                # A later local-only Yahoo exclusion must not degrade an
                # independently successful search (or vice versa).
                peer_observations = [entry for entry in data.get('source_audit', [])
                                     if isinstance(entry, dict) and entry.get('source') == source]
                upstream = next((entry for entry in reversed(peer_observations)
                                 if entry.get('status') == AUDIT_STATUS_SUCCESS
                                 and isinstance(entry.get('record_count'), int)
                                 and entry['record_count'] > 0), upstream)
            aliases = {'recent_catalysts': ('free_news', 'official_company_history', 'tpex_company_history', 'issuer_news', 'official_trading_notices', 'search_catalysts', 'fmp_news', 'yahoo_news'),
                       'peer_discovery': ('search_peer_discovery', 'publisher_peer_discovery', 'moneydj_peer_discovery','medical_peer_discovery','official_segment_peer_discovery')}
            incoming = bool(payload) or any(eligible_issuer_rows if key == 'issuer_news' else http_bundle.get(key)
                                            for key in aliases.get(source, ()))
            if payload and source not in aliases and isinstance(upstream.get('record_count'), int):
                count = max(0, upstream['record_count'])
            coverage = payload.get('status') or upstream.get('coverage_status')
            failed = bool(error_message) or upstream.get('status') in {'error', 'unavailable', 'not_configured'}
            retained = count > 0 and not incoming and (failed or source in aliases)
            stale = retained or safe_bool(payload.get('stale')) or safe_bool(upstream.get('stale'))
            cache_hit = retained or safe_bool(upstream.get('cache_hit')) or safe_bool(payload.get('cache_hit'))
            fetched_epoch = upstream.get('fetched_at_epoch')
            if not fetched_epoch and upstream.get('fetched_at'):
                stamp = parse_news_datetime(upstream['fetched_at'])
                fetched_epoch = stamp.timestamp() if stamp else None
            if not fetched_epoch and not cache_hit and not stale and not failed and source != 'official_disclosures':
                fetched_epoch = refresh_epoch
            observed_empty_documents = (
                source == 'official_disclosures' and count == 0 and bool(fetched_epoch)
                and payload.get('retrieval_status') in {'success', 'valid_empty'}
                and not failed and not stale
            )
            # An official partial row can carry facts without meeting the
            # salary availability gate. Keep its receipt/time, but never
            # promote zero usable records into source health or SLA success.
            observed_partial_workforce = (
                source == 'annual_workforce' and count == 0 and not error_message
                and upstream.get('status') == AUDIT_STATUS_UNAVAILABLE and not upstream.get('error_kind')
                and payload.get('observation_kind') == 'annual_workforce_disclosure'
                and payload.get('ticker') == ticker and payload.get('coverage_status') == 'partial'
                and isinstance(payload.get('available_metric_count'), int)
                and not isinstance(payload['available_metric_count'], bool) and payload['available_metric_count'] > 0
                and isinstance(payload.get('response_sha256'), str) and len(payload['response_sha256']) == 64
                and payload['response_sha256'] == upstream.get('response_sha256') and bool(fetched_epoch)
            )
            if count > 0:
                degraded = stale or failed or coverage in {'partial', 'stale', 'unavailable', 'qualitative_only'} or upstream.get('status') == AUDIT_STATUS_DEGRADED_ENRICHMENT
                status = AUDIT_STATUS_DEGRADED_ENRICHMENT if degraded else AUDIT_STATUS_SUCCESS
                error_kind = str(upstream.get('error_kind') or '')
                message = "optional 外部來源已合併；保留實際來源、取得時間及覆蓋狀態。"
            elif observed_partial_workforce:
                status = AUDIT_STATUS_UNAVAILABLE
                error_kind = ""
                message = str(upstream.get('message') or '已保留官方部分人力欄位；尚未滿足完整來源門檻。')
            elif failed:
                status = AUDIT_STATUS_ERROR
                if upstream.get('status') == 'not_configured':
                    status = 'not_configured'
                error_kind = str(upstream.get('error_kind') or "async_fetch_error")
                message = error_message[:240] or str(upstream.get('message') or 'optional 外部來源取得失敗。')
            else:
                status = AUDIT_STATUS_DEGRADED_ENRICHMENT
                error_kind = ""
                message = "optional 外部來源本次無新增資料，已保留為可接受的補充資料空結果。"
            if fetched_epoch and (count > 0 or observed_empty_documents or observed_partial_workforce) and not retained:
                data.setdefault('source_freshness', {})[source] = build_source_freshness_entry(
                    source, ticker, fetched_epoch, cache_hit, now_epoch=refresh_epoch, source_data=payload)
            if stale:
                data.setdefault('source_freshness', {}).setdefault(source, {}).update(stale=True, is_fresh=False)
            _append_source_fetch_audit(
                data,
                source,
                _optional_provider_label(source) if source in aliases else payload.get('actual_provider') or upstream.get('provider') or _optional_provider_label(source),
                status,
                fetched_at_epoch=fetched_epoch,
                finished_at_epoch=refresh_epoch,
                record_count=count,
                cache_hit=cache_hit,
                stale=stale or (count <= 0 and not observed_empty_documents and not observed_partial_workforce),
                error_kind=error_kind,
                message=message,
            )
            # This merge is a summary, never another upstream request.
            details = observation_details({**upstream, **payload, 'coverage_status': coverage})
            for key in ('event_kind', 'http_request_sent', 'cache_hit', 'stale', 'fetched_at_epoch'):
                details.pop(key, None)
            data['source_audit'][-1].update(details, event_kind='aggregate')
            if retained or (cache_hit and not fetched_epoch):
                data['source_audit'][-1]['fetched_at'] = data.get('source_freshness', {}).get(source, {}).get('fetched_at')
            if source == 'official_disclosures' and not fetched_epoch:
                # The generic audit constructor falls back to completion time;
                # this source explicitly distinguishes no fetch from a fetch.
                data['source_audit'][-1]['fetched_at'] = None

    apply_source_applicability(data)
    finalize_data_trust(data)
    return data


def _optional_provider_label(source: str) -> str:
    if source == "recent_catalysts":
        return "Recent catalysts providers"
    if source == "global_market_context":
        return "Global market context"
    if source == "international_news_context":
        return "International news context"
    if source == "macro_indicators":
        return "FRED macro indicators"
    if source == "chip_data":
        return "TDCC/TWSE/TPEx chip data"
    if source == "alternative_data":
        return "Alternative data providers"
    if source == "social_sentiment":
        return "Social Forum Sentiment"
    if source == "sec_edgar":
        return "SEC EDGAR Filings"
    if source == "taiwan_open_data":
        return "Taiwan Open Data"
    if source == "earnings_call":
        return "MOPS investor conference"
    if source == "official_disclosures":
        return "TWSE/TPEx official disclosures"
    if source == "peer_discovery":
        return "Peer discovery providers"
    return "Optional providers"


def _dedupe_recent_catalysts(records: list[dict], limit: int = 5) -> list[dict]:
    return apply_news_freshness({}, records=records, limit=limit)["recent_catalysts"]
