"""Plan per-source acquisition dates without weakening evidence admission."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import time

from market_evidence_policy import TZ, acquisition_session_scope
from source_applicability import source_is_applicable


def assess_session_aligned_cache(cached, ticker, *, assessor, now_epoch=None):
    """Keep acquisition clocks intact, but require each source's observed day.

    A recent fetch can contain a previous session. Generic freshness tolerates
    that observation age; this narrower cache planner must still offer it to the
    existing institutional recovery and full-window/official-original checks.
    """
    now_epoch = time.time() if now_epoch is None else now_epoch
    fresh, assessment = assessor(cached, ticker, now_epoch=now_epoch)
    if not ticker.endswith(('.TW', '.TWO')):
        return fresh, assessment
    assessment = deepcopy(assessment)
    scope = acquisition_session_scope(datetime.fromtimestamp(now_epoch, TZ), ticker=ticker)
    expected = scope['latest_completed_session']
    stale_sources = assessment.setdefault('stale_sources', [])
    def invalidate(name, observed, reason, **details):
        assessment['is_fresh'] = False
        if name not in stale_sources:
            stale_sources.append(name)
        source = assessment.setdefault('source_freshness', {}).setdefault(name, {})
        source.update(is_fresh=False, stale=True, session_alignment=reason,
                      expected_session=expected, observed_session=observed,
                      acquisition_scope=scope, **details)

    if cached.get('ticker') != ticker:
        invalidate('market_data', None, 'cached_security_identity_mismatch')
        return False, assessment
    from market_session_admission import assess_daily_session_integrity
    daily = cached.get('daily_market_data') or {}
    if not isinstance(daily, dict):
        daily = {}
    integrity = assess_daily_session_integrity(daily, ticker=ticker)
    observed = daily.get('as_of')
    if not expected or observed != expected or not integrity['eligible']:
        invalidate('market_data', observed, 'completed_market_session_unconfirmed',
                   session_integrity=integrity)
    elif scope['acquisition_phase'] in {'provisional', 'post_cutoff'}:
        admission = _price_source_admission(daily, ticker, now_epoch)
        market = assessment.setdefault('source_freshness', {}).setdefault('market_data', {})
        market.update(price_source_admission=admission, acquisition_scope=scope)
        # A same-day date cannot renew an 18:00 official receipt at 22:31.
        # Mark the core source stale so the outer workflow cannot choose only
        # institutional recovery and bypass the inner price-admission gate.
        if scope['acquisition_phase'] == 'post_cutoff' and not admission['eligible']:
            invalidate('market_data', observed, 'post_cutoff_official_price_recheck_required',
                       price_source_admission=admission)

    if source_is_applicable('institutional_trading', cached, ticker):
        value = cached.get('institutional_trading')
        observed = value.get('latest_date') if isinstance(value, dict) else None
        # Equality rejects malformed/future dates as well as old observations.
        # A current provisional row can be retained for display; source admission
        # separately decides whether its original evidence may support a claim.
        if not expected or observed != expected:
            invalidate('institutional_trading', observed, 'latest_publication_session_unconfirmed')
        elif scope['acquisition_phase'] in {'provisional', 'post_cutoff'}:
            clocks = cached.get('source_freshness')
            clock = clocks.get('institutional_trading') if isinstance(clocks, dict) else None
            admission = _institutional_source_admission(value, ticker, expected, now_epoch, clock)
            source = assessment.setdefault('source_freshness', {}).setdefault('institutional_trading', {})
            source.update(institutional_source_admission=admission, acquisition_scope=scope)
            # Replay the original rather than cached stale/eligible labels.
            # A price-admitted payload can then use the existing single-source
            # recovery; a failed attempt must keep this old value and clock.
            if scope['acquisition_phase'] == 'post_cutoff' and not admission['eligible']:
                invalidate('institutional_trading', observed,
                           'post_cutoff_official_institutional_recheck_required',
                           institutional_source_admission=admission)
    return bool(fresh and not stale_sources), assessment


def _price_source_admission(daily, ticker, now_epoch):
    from report_source_admission import price_admission
    try:
        admission = price_admission(daily, ticker)
        if admission['eligible']:
            proof = admission['raw_evidence']
            acquired = datetime.fromisoformat(proof['retrieved_at'])
            if acquired.tzinfo is None or not 0 < acquired.timestamp() <= now_epoch:
                return {**admission, 'eligible': False, 'reason': 'official_price_acquisition_time_invalid'}
        return admission
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return {'eligible': False, 'reason': 'official_price_raw_evidence_invalid',
                'expected_date': daily.get('as_of'), 'finality_guaranteed': False,
                'historical_point_in_time_verified': False}


def _institutional_source_admission(value, ticker, expected, now_epoch, clock):
    from report_source_admission import institutional_admission
    result = {'eligible': False, 'expected_date': expected,
              'historical_point_in_time_verified': False, 'finality_guaranteed': False}
    try:
        official = value.get('latest_official_observation') or {}
        if (official.get('ticker') != ticker
                or official.get('market') != ('TPEX' if ticker.endswith('.TWO') else 'TWSE')):
            return {**result, 'reason': 'official_institutional_security_mismatch'}
        admission = institutional_admission(value, expected)
        if admission['eligible']:
            proof = admission['raw_evidence']
            acquired = datetime.fromisoformat(proof['retrieved_at'])
            if acquired.tzinfo is None or not 0 < acquired.timestamp() <= now_epoch:
                return {**admission, 'eligible': False, 'reason': 'official_institutional_acquisition_time_invalid'}
            # Source age must come from its own recorded clock, never the
            # financial payload's regenerated aggregate timestamp.
            import math
            stamp = clock.get('fetched_at_epoch') if isinstance(clock, dict) else None
            if stamp is None and isinstance(clock, dict) and clock.get('fetched_at'):
                parsed = datetime.fromisoformat(clock['fetched_at'])
                stamp = parsed.timestamp() if parsed.tzinfo is not None else None
            if type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 < stamp <= now_epoch:
                return {**admission, 'eligible': False, 'reason': 'institutional_source_acquisition_time_invalid'}
        return admission
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return {**result, 'reason': 'official_institutional_raw_evidence_invalid'}
