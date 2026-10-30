"""Session-bound overnight research; the clock alone never admits evidence."""
from datetime import datetime, time, timedelta
import os
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
START = time(22, 35)
END = time(7, 0)
POLICY = 'nightly-analysis.v1'


def enabled():
    return os.getenv('NIGHTLY_TAIWAN_ANALYSIS_ENABLED', '0').lower() in {'1', 'true', 'yes'}


def domestic(ticker):
    return str(ticker).endswith(('.TW', '.TWO'))


def session_for_acquisition(now):
    if now.tzinfo is None:
        raise ValueError('nightly time must include timezone')
    local = now.astimezone(TZ)
    clock = local.time().replace(tzinfo=None)
    if clock >= START:
        return local.date().isoformat()
    if clock < END:
        return (local.date() - timedelta(days=1)).isoformat()
    return None


def delivery_session(now):
    return (now.astimezone(TZ).date() - timedelta(days=1)).isoformat()


def session_state(session, ticker):
    from market_calendar_store import session_day_status
    if not domestic(ticker):
        return 'unknown'
    return session_day_status(session, exchange='TPEX' if ticker.endswith('.TWO') else 'TWSE')['state']


def session_open(session, ticker):
    return session_state(session, ticker) == 'open'


def source_readiness(data, session, ticker):
    from report_source_admission import institutional_admission, price_admission
    from market_session_admission import assess_daily_session_integrity
    reasons = []
    if data.get('ticker') != ticker or not session_open(session, ticker):
        reasons.append('security_or_session_unverified')
    daily = data.get('daily_market_data') or {}
    if daily.get('as_of') != session:
        reasons.append('price_session_mismatch')
    integrity = assess_daily_session_integrity(daily, ticker=ticker)
    if not integrity['eligible']:
        reasons.append('price_window_session_unverified')
    inst = data.get('institutional_trading') or {}
    observation = inst.get('latest_official_observation') or {}
    if observation.get('ticker') != ticker or observation.get('market') != ('TPEX' if ticker.endswith('.TWO') else 'TWSE'):
        reasons.append('institutional_security_or_market_mismatch')
    institutional = institutional_admission(inst, session)
    price = price_admission(daily, ticker)
    from market_price_reconciliation import reconcile
    reconciliation = reconcile(daily)
    if reconciliation["price_status"] != "matched_sample_session":
        reasons.append("official_provider_price_mismatch_or_unverified")
    for result in (institutional, price):
        if not result.get('eligible'):
            reasons.append(result.get('reason') or 'source_unverified')
    return {'eligible': not reasons, 'session_date': session, 'reason_codes': reasons,
            'institutional': institutional, 'price': price, 'price_reconciliation': reconciliation,
            'scope': 'post-cutoff official source admission; not PIT, finality or trading permission'}
