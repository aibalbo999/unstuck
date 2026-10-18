"""Consistency binding for already admitted ordinary MOPS announcement records.

This is not a signature or a substitute for native-original/source admission.
Legacy records are never upgraded by a consumer of this module.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit

POLICY = 'ordinary-mops-event-v1'
ENGLISH_POLICY = 'ordinary-mops-event-en-v1'
FIELDS = ('official_event', 'official_event_sha256')
PROVIDER = 'TWSE company announcement history'
TAIPEI = timezone(timedelta(hours=8))


def _components(record):
    if (not isinstance(record, dict) or record.get('source') != PROVIDER
            or record.get('source_type') != 'official_disclosure'
            or record.get('issuer_identity_basis') not in {
                'TWSE company ID + MOPS detail header',
                'TWSE English company ID + English MOPS detail header',
            }
            or record.get('content_truncated') is not False):
        raise ValueError('not an ordinary complete announcement')
    ticker = record.get('ticker')
    if not isinstance(ticker, str) or not re.fullmatch(r'[1-9]\d{3,5}\.TW', ticker):
        raise ValueError('invalid issuer')
    stock_id = ticker.split('.')[0]
    url = record.get('link')
    if not isinstance(url, str):
        raise ValueError('invalid original URL')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.fragment:
        raise ValueError('invalid original URL')
    if (record['issuer_identity_basis'] == 'TWSE company ID + MOPS detail header'
            and parsed.netloc == 'mopsov.twse.com.tw' and parsed.path == '/mops/web/ajax_t05sr01_1'):
        params = parse_qs(parsed.query, keep_blank_values=True)
        required = {'COMPANY_ID', 'SPOKE_DATE', 'SPOKE_TIME', 'SEQ_NO'}
        if (not required <= set(params) <= required | {'firstin', 'stp', 'step'}
                or any(len(values) != 1 for values in params.values())
                or params['COMPANY_ID'] != [stock_id]
                or any(params.get(k, [v]) != [v] for k, v in [('firstin', 'true'), ('stp', '1'), ('step', '1')])
                or not re.fullmatch(r'\d{8}', params['SPOKE_DATE'][0])
                or not re.fullmatch(r'\d{1,6}', params['SPOKE_TIME'][0])
                or not re.fullmatch(r'\d{1,10}', params['SEQ_NO'][0])
                or int(params['SEQ_NO'][0]) <= 0):
            raise ValueError('invalid event parameters')
        day, clock = params['SPOKE_DATE'][0], params['SPOKE_TIME'][0].zfill(6)
        sequence = str(int(params['SEQ_NO'][0]))
        policy = POLICY
        canonical = 'https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1?' + urlencode({
            'COMPANY_ID': stock_id, 'SPOKE_DATE': day, 'SPOKE_TIME': clock, 'SEQ_NO': sequence})
    elif (record['issuer_identity_basis'] == 'TWSE English company ID + English MOPS detail header'
            and parsed.netloc == 'emops.twse.com.tw' and parsed.path == '/server-java/t05sr01_1_e'):
        query_text = parsed.query[1:] if parsed.query.startswith('&') else parsed.query
        params = parse_qs(query_text, keep_blank_values=False, strict_parsing=True)
        required = {'isNew', 'co_id', 'spoke_date', 'spoke_time', 'seq_no'}
        if (set(params) != required or any(len(values) != 1 for values in params.values())
                or params['isNew'] != ['Y'] or params['co_id'] != [stock_id]
                or not re.fullmatch(r'\d{8}', params['spoke_date'][0])
                or not re.fullmatch(r'\d{1,6}', params['spoke_time'][0])
                or not re.fullmatch(r'\d{1,6}', params['seq_no'][0])
                or int(params['seq_no'][0]) <= 0):
            raise ValueError('invalid English event parameters')
        day, clock = params['spoke_date'][0], params['spoke_time'][0].zfill(6)
        sequence = str(int(params['seq_no'][0]))
        policy = ENGLISH_POLICY
        canonical = 'https://emops.twse.com.tw/server-java/t05sr01_1_e?' + urlencode({
            'isNew': 'Y', 'co_id': stock_id, 'spoke_date': day, 'spoke_time': clock, 'seq_no': sequence})
    else:
        raise ValueError('invalid original URL')
    observed = datetime.strptime(day + clock, '%Y%m%d%H%M%S').replace(tzinfo=TAIPEI)
    for field in ('date', 'published_at', 'published_date'):
        if field not in record and field == 'published_date':
            continue
        value = record.get(field)
        if not isinstance(value, str):
            raise ValueError('missing event time')
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp != observed:
            raise ValueError('event time mismatch')
    title, text = record.get('title'), record.get('text')
    if (not isinstance(title, str) or not title.strip() or not isinstance(text, str)
            or not 20 <= len(text) <= 12_000
            or record.get('content_sha256') != hashlib.sha256(text.encode()).hexdigest()):
        raise ValueError('event body mismatch')
    event = {'policy': policy, 'issuer': stock_id, 'date': day, 'time': clock,
             'sequence': sequence}
    digest = hashlib.sha256(json.dumps([event, canonical, title, text], ensure_ascii=False,
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return event, digest


def bind_collected_event(record):
    """Called only after the collector's existing original/issuer/time gates."""
    try:
        event, digest = _components(record)
    except (ValueError, TypeError, OverflowError):
        return
    record['official_event'], record['official_event_sha256'] = event, digest


def ordinary_event_key(record, ticker):
    """Return a dedupe key only when the stored binding still matches this issuer."""
    if not isinstance(ticker, str) or record.get('ticker') != ticker:
        return None
    try:
        event, digest = _components(record)
        if record.get('official_event') != event or record.get('official_event_sha256') != digest:
            return None
    except (ValueError, TypeError, OverflowError):
        return None
    return tuple(event[k] for k in ('policy', 'issuer', 'date', 'time', 'sequence'))
