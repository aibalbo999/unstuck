"""Plan cache acquisition against mature sessions without altering admission gates."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import time

from market_evidence_policy import TZ, session_cache_scope
from source_applicability import source_is_applicable


def assess_session_aligned_cache(cached, ticker, *, assessor, now_epoch=None):
    """Keep acquisition clocks intact, but reacquire a missing mature session.

    A recent fetch can contain a previous session. Generic freshness tolerates
    that observation age; this narrower cache planner must still offer it to the
    existing institutional recovery and full-window/official-original checks.
    """
    now_epoch = time.time() if now_epoch is None else now_epoch
    fresh, assessment = assessor(cached, ticker, now_epoch=now_epoch)
    if (cached.get('ticker') != ticker or not ticker.endswith(('.TW', '.TWO'))
            or not source_is_applicable('institutional_trading', cached, ticker)):
        return fresh, assessment
    value = cached.get('institutional_trading')
    if not isinstance(value, dict):
        return fresh, assessment
    expected, _ = session_cache_scope(datetime.fromtimestamp(now_epoch, TZ))
    try:
        observed_day = date.fromisoformat(value.get('latest_date'))
        expected_day = date.fromisoformat(expected)
    except (TypeError, ValueError):
        return fresh, assessment
    if observed_day >= expected_day:
        return fresh, assessment

    assessment = deepcopy(assessment)
    stale_sources = assessment.setdefault('stale_sources', [])
    if 'institutional_trading' not in stale_sources:
        stale_sources.append('institutional_trading')
    source = assessment.setdefault('source_freshness', {}).setdefault('institutional_trading', {})
    source.update(is_fresh=False, stale=True, session_alignment='behind_mature_session',
                  expected_session=expected, observed_session=value['latest_date'])
    return False, assessment
