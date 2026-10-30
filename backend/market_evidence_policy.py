"""Session completion is not proof that a provider's daily data is final."""
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
RECHECK_TIME = time(22, 30)  # Conservative acquisition boundary, not an exchange finality claim.


def acquisition_phase(day, moment=None):
    moment = (moment or datetime.now(TZ)).astimezone(TZ)
    try:
        boundary = datetime.combine(datetime.fromisoformat(day).date(), RECHECK_TIME, TZ)
    except (TypeError, ValueError):
        return 'unknown'
    return 'post_cutoff' if moment >= boundary else 'provisional'


def completed_evidence_session(moment, *, ticker=None):
    from two_week_market_eligibility import completed_session
    local = moment.astimezone(TZ)
    if local.time().replace(tzinfo=None) < RECHECK_TIME:
        local = datetime.combine(local.date(), time.min, TZ) - timedelta(seconds=1)
    return completed_session(local, ticker=ticker)


def session_cache_scope(moment, *, ticker=None):
    expected = completed_evidence_session(moment, ticker=ticker)
    return expected, acquisition_phase(expected, moment)


def acquisition_session_scope(moment, *, ticker=None):
    """A completed session may be published before the conservative recheck.

    This selects a date to *look for*, not proof that anything was published.
    The raw-response admission gate still requires its original post-cutoff
    acquisition timestamp; advancing this clock never upgrades an old receipt.
    """
    from two_week_market_eligibility import completed_session
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        latest = mature = None
    else:
        latest = completed_session(moment, ticker=ticker)
        mature = completed_evidence_session(moment, ticker=ticker)
    return {
        'latest_completed_session': latest,
        'mature_evidence_session': mature,
        'acquisition_phase': acquisition_phase(latest, moment) if latest else 'unknown',
        'conservative_recheck_time': RECHECK_TIME.isoformat(),
        'finality_guaranteed': False,
    }


def calendar_cache_token(ticker, moment):
    """Calendar changes invalidate acquisition planning, not raw source bytes."""
    import hashlib
    import json
    from market_calendar_store import load_market_calendar
    market = 'tw' if str(ticker).endswith(('.TW', '.TWO')) else 'us'
    year = moment.astimezone(TZ).year
    versions = [(y, load_market_calendar(market, y).get('calendar_version'))
                for y in (year - 1, year)]
    return hashlib.sha256(json.dumps(versions).encode()).hexdigest()[:20]


def publication_observation(day, *, moment, provider, retrieved_at=None, raw_evidence=None, ticker=None):
    """Describe an actually returned row without granting candidate admission."""
    scope = acquisition_session_scope(moment, ticker=ticker)
    acquired = None
    try:
        acquired = datetime.fromisoformat(retrieved_at) if retrieved_at else None
        if acquired is not None and acquired.tzinfo is None:
            acquired = None
    except (TypeError, ValueError):
        pass
    phase = acquisition_phase(day, acquired or moment) if day else 'unknown'
    latest = scope['latest_completed_session']
    status = ('unavailable' if not day else 'session_unconfirmed' if not latest or day > latest
              else 'older_observation' if day != latest else
              'available_provisional' if phase == 'provisional' else 'available_requires_admission')
    return {**scope, 'status': status, 'observed_date': day, 'provider': provider,
            'retrieved_at': retrieved_at, 'raw_evidence': raw_evidence,
            'acquisition_phase': phase, 'eligible': False,
            'verification_scope': 'publication_observation_only; separate raw-source admission required'}
