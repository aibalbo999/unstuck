"""Recover the configured observation window without refreshing report conclusions."""
from copy import deepcopy
from datetime import datetime
import json
import re
import time
from zoneinfo import ZoneInfo

from fastapi import HTTPException

SOURCE = 'institutional_trading'


def validate_institutional_refresh_context(data, ticker):
    from source_applicability import instrument_type
    identity = data.get('company_identity') if isinstance(data, dict) else None
    kind = instrument_type(data)
    if (not isinstance(data, dict) or data.get('ticker') != ticker
            or not isinstance(ticker, str) or not re.fullmatch(r'\d{4,6}\.TW(?:O)?', ticker)
            or not isinstance(identity, dict) or kind not in {'EQUITY', 'ETF'}
            or identity.get('ticker') not in (None, '', ticker)
            or identity.get('stock_id') not in (None, '', ticker.split('.')[0])
            or identity.get('instrument_type') not in (None, '', kind)
            or any(data.get(k) not in (None, '', kind) for k in ('instrument_type', 'quote_type', 'quoteType'))
            or data.get(SOURCE) is not None and not isinstance(data[SOURCE], dict)):
        raise HTTPException(status_code=400, detail='指定法人刷新須有一致的台股證券身分與原觀測；原快照保持')
    for key in ('source_record_archive', 'data_source_notes'):
        items = data.get(key, [])
        expected = dict if key == 'source_record_archive' else str
        if not isinstance(items, list) or any(not isinstance(x, expected) for x in items):
            raise HTTPException(status_code=400, detail='原來源封存或說明格式無法安全保留')


def institutional_refresh_session(ticker):
    from market_evidence_policy import acquisition_phase
    from official_institutional_source import expected_sessions
    now = time.time()
    moment = datetime.fromtimestamp(now, ZoneInfo('Asia/Taipei'))
    # The same market calendar and cutoff used by the provider choose the
    # latest mature session. Before today's cutoff, yesterday's completed
    # window can still be recovered; today's provisional rows remain excluded.
    try:
        days = expected_sessions(ticker, now, 1)
    except Exception as exc:
        raise HTTPException(status_code=409, detail='法人交易日曆尚未驗證；原快照保持') from exc
    expected = days[0] if days else None
    phase = acquisition_phase(expected, moment) if expected else 'unknown'
    if not expected or phase != 'post_cutoff':
        raise HTTPException(status_code=409, detail='法人來源尚未到可核驗時段；原快照保持')
    return expected


def merge_institutional_source(old_data, old_audits, value, audits, ticker):
    from config import INSTITUTIONAL_LOOKBACK_DAYS
    from data_freshness import source_max_age_seconds
    from data_trust import source_record_count
    from institutional_observations import summarize_observations
    from official_institutional_source import expected_sessions
    from report_source_admission import institutional_admission
    from report_source_refresh import _timestamp, _reassess_original_freshness

    validate_institutional_refresh_context(old_data, ticker)
    expected = institutional_refresh_session(ticker)
    try:
        if not isinstance(value, dict):
            raise ValueError('missing institutional observations')
        official = value.get('latest_official_observation') or {}
        if official.get('ticker') != ticker or official.get('market') != ('TPEX' if ticker.endswith('.TWO') else 'TWSE'):
            raise ValueError('official security mismatch')
        admission = institutional_admission(value, expected)
        if not admission['eligible'] or value.get('latest_session_admission') != admission:
            raise ValueError('latest original not admitted')
        now = time.time()
        stamp = datetime.fromisoformat(admission['raw_evidence']['retrieved_at']).timestamp()
        ttl = source_max_age_seconds(SOURCE, ticker)
        if not 0 <= now - stamp < ttl:
            raise ValueError('official original expired or future')
        days = expected_sessions(ticker, now, INSTITUTIONAL_LOOKBACK_DAYS)
        records = value.get('daily_category_observations')
        if len(days) != INSTITUTIONAL_LOOKBACK_DAYS or not isinstance(records, list) or len(records) != 3 * len(days):
            raise ValueError('incomplete configured observation window')
        required = {(day, category) for day in days for category in ('foreign', 'investment_trust', 'dealer')}
        seen = set()
        for row in records:
            if (not isinstance(row, dict) or row.get('unit') != 'shares'
                    or type(row.get('net_buy_shares')) is not int
                    or not isinstance(row.get('source'), str) or not row['source']):
                raise ValueError('invalid dated share observation')
            key = (row.get('date'), row.get('category'))
            if key not in required or key in seen:
                raise ValueError('duplicate or unexpected observation')
            seen.add(key)
        rebuilt = summarize_observations(records, ticker, limit=INSTITUTIONAL_LOOKBACK_DAYS)
        for key, item in rebuilt.items():
            if key in {'source', 'daily_category_observations'}:
                continue
            if json.dumps(value.get(key), sort_keys=True, allow_nan=False) != json.dumps(item, sort_keys=True, allow_nan=False):
                raise ValueError('observation summary mismatch')
        if (value.get('stale') is not False or value.get('coverage_status') != 'available'
                or not isinstance(audits, list) or len(audits) != 1):
            raise ValueError('source coverage or audit incomplete')
        audit = audits[0]
        if (not isinstance(audit, dict) or audit.get('source') != SOURCE or audit.get('provider') != 'FinMind'
                or audit.get('status') != 'success' or not audit.get('fetch_id')
                or audit.get('stale') is not False or audit.get('coverage_status') != 'available'
                or audit.get('latest_session_admission') != admission
                or type(audit.get('record_count')) is not int
                or audit['record_count'] != source_record_count(SOURCE, {SOURCE: value})):
            raise ValueError('institutional audit mismatch')
        acquired = _timestamp(audit)
        if acquired is None or not 0 <= now - acquired < ttl or value.get('fetched_at_epoch') != acquired:
            raise ValueError('source acquisition expired or inconsistent')
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail='法人觀測窗、分項數值或官方原件未通過核對；原快照保持') from exc
    merged = deepcopy(old_data)
    archive = merged.setdefault('source_record_archive', [])
    if old_data.get(SOURCE) is not None:
        archive.append({'source': SOURCE, 'reason': 'superseded_by_institutional_source_refresh', 'record': deepcopy(old_data[SOURCE])})
    archive.extend({'source': SOURCE, 'reason': 'superseded_by_institutional_source_refresh', 'audit': deepcopy(a)}
                   for a in old_audits if a.get('source') == SOURCE)
    merged[SOURCE] = deepcopy(value)
    merged['source_audit'] = [deepcopy(a) for a in old_audits if a.get('source') != SOURCE] + deepcopy(audits)
    note = '僅更新法人來源觀測窗，最新交易日以官方原件核對；不宣稱全期逐日官方獨立查驗。股價與其他來源沿原取得時間，分析本文需重新執行。'
    notes = merged.setdefault('data_source_notes', [])
    if note not in notes:
        notes.append(note)
    _reassess_original_freshness(merged, ticker, SOURCE, audits)
    return merged
