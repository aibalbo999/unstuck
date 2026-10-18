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


def completed_evidence_session(moment):
    from two_week_market_eligibility import completed_session
    local = moment.astimezone(TZ)
    if local.time().replace(tzinfo=None) < RECHECK_TIME:
        local = datetime.combine(local.date(), time.min, TZ) - timedelta(seconds=1)
    return completed_session(local)


def session_cache_scope(moment):
    expected = completed_evidence_session(moment)
    return expected, acquisition_phase(expected, moment)
