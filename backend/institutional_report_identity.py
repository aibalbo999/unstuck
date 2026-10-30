"""Bind saved metadata to one security, exchange, dataset and requested session.

This validates metadata relationships only, never source bytes or admission.
Unknown fields stay unknown; a conflicting receipt cannot be masked by a fallback.
"""
import re
from datetime import date
from urllib.parse import parse_qs, urlsplit
from mapping_fields import safe_mapping_dict
from institutional_report_sources import failure_details


DATASET = 'TaiwanStockInstitutionalInvestorsBuySell'
SOURCES = {'TWSE T86': ('TWSE', 't86'), 'TPEx dailyTrade': ('TPEX', 'daily'),
           'TPEx institutional OpenAPI': ('TPEX', 'openapi')}


def _text(value):
    return value.strip() if isinstance(value, str) else ''


def _ticker(value):
    value = _text(value).upper()
    return value if re.fullmatch(r'[0-9A-Z]{4,8}\.(TW|TWO)', value) else None


def _day(value):
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) else None
    except ValueError:
        return None


def _url_identity(value, expected_day):
    """Recognize only the saved endpoints used by the official adapters."""
    try:
        url = urlsplit(_text(value))
        if url.scheme != 'https' or url.username or url.password or url.port or url.fragment:
            return None, 'official_endpoint_unknown'
        query = parse_qs(url.query, keep_blank_values=True)
    except ValueError:
        return None, 'official_endpoint_unknown'
    if url.hostname in {'www.twse.com.tw', 'wwwc.twse.com.tw'} and url.path == '/rwd/zh/fund/T86':
        identity = ('TWSE', 't86')
        expected = {'response': ['json'], 'date': [expected_day.replace('-', '')], 'selectType': ['ALLBUT0999']}
    elif url.hostname == 'www.tpex.org.tw' and url.path == '/www/zh-tw/insti/dailyTrade':
        identity = ('TPEX', 'daily')
        expected = {'response': ['json'], 'date': [expected_day.replace('-', '/')], 'type': ['Daily'], 'sect': ['EW']}
    elif url.hostname == 'www.tpex.org.tw' and url.path == '/openapi/v1/tpex_3insti_daily_trading':
        return (('TPEX', 'openapi'), None) if not query else (None, 'official_endpoint_unknown')
    else:
        return None, 'official_endpoint_unknown'
    if query.get('date') != expected['date']:
        return identity, 'official_query_date_mismatch'
    return (identity, None) if query == expected else (identity, 'official_endpoint_unknown')


def _official(row, ticker, market, *, latest=False):
    """The recovery receipt and legacy latest-observation use one URL/date check."""
    if not row:
        return False, []
    issues = []
    day = _day(row.get('date'))
    if not day:
        issues.append('official_date_missing')
    for field, expected in [('ticker', ticker), ('market', market)]:
        raw = row.get(field)
        value = _ticker(raw) if field == 'ticker' else _text(raw).upper()
        if raw is not None and raw != '' and value != expected:
            issues.append('official_' + field + '_mismatch')
        elif latest and not value:
            issues.append('official_' + field + '_missing')
    source = _text(row.get('source'))
    source_identity = SOURCES.get(source)
    if source and not source_identity:
        issues.append('official_source_unknown')
    elif not latest and not source_identity:
        issues.append('official_source_missing')
    if source_identity and source_identity[0] != market:
        issues.append('official_market_mismatch')
    proof = safe_mapping_dict(row.get('raw_evidence')) or {}
    for field, expected in [('ticker', ticker), ('market', market), ('date', day)]:
        if proof.get(field) is not None and proof.get(field) != '':
            value = _ticker(proof[field]) if field == 'ticker' else _day(proof[field]) if field == 'date' else _text(proof[field]).upper()
            if value != expected:
                issues.append('official_raw_' + field + '_mismatch')
    urls = [value for value in (row.get('source_url'), proof.get('source_url')) if value is not None and value != '']
    failed = failure_details(row)['failed']
    # Failed requests may have no raw response, but still need a bound request URL.
    if not urls or (not failed and not _text(proof.get('source_url'))):
        issues.append('official_raw_url_missing')
    for value in urls:
        identity, problem = _url_identity(value, day) if day else (None, 'official_date_missing')
        if problem:
            issues.append(problem)
        if identity and identity[0] != market:
            issues.append('official_market_mismatch')
        if identity and source_identity and identity != source_identity:
            issues.append('official_source_endpoint_mismatch')
    return not issues, list(dict.fromkeys(issues))


def bind_saved_identity(context, data, inst, audit, primary, sources, target):
    """Return usable branches and reasons without choosing away contradictions."""
    issues = list(sources['issues'])
    slots = sources['slots']
    current, official = slots['current']['record'], slots['latest']['record']
    provenance_records = [slots[key]['record'] for key in ('primary', 'archive')]
    daily = safe_mapping_dict(data.get('daily_market_data')) or {}
    values = [obj.get('ticker') for obj in (context, data, inst, audit, primary, daily, *provenance_records)
              if obj.get('ticker') is not None and obj.get('ticker') != '']
    parsed = [_ticker(value) for value in values]
    ticker = parsed[0] if parsed and parsed[0] else ''
    if not parsed or any(not value for value in parsed):
        issues.append('container_ticker_missing_or_invalid')
    if len(set(parsed)) > 1:
        issues.append('container_ticker_conflict')
    market = 'TPEX' if ticker.endswith('.TWO') else 'TWSE' if ticker.endswith('.TW') else 'unknown'
    conflict = bool(issues)
    sdk_bounds = {}
    for name in ('primary', 'archive'):
        slot = slots[name]
        provenance = slot['record']
        query = safe_mapping_dict(provenance.get('query')) or {}
        sdk_issues = []
        if slot['presence'] == 'present':
            for key, expected in [('dataset', DATASET), ('data_id', ticker.split('.')[0])]:
                actual = _text(query.get(key))
                if not actual:
                    sdk_issues.append(name + '_' + key + '_missing')
                elif actual != expected:
                    sdk_issues.append(name + '_' + key + '_mismatch')
            if provenance.get('source_url') is not None and provenance.get('source_url') != 'https://api.finmindtrade.com/api/v4/data':
                sdk_issues.append(name + '_endpoint_unknown')
        sdk_bounds[name] = bool(provenance and not sdk_issues and market != 'unknown')
        issues.extend(sdk_issues)
        conflict = conflict or bool(sdk_issues)
    primary_bound = sdk_bounds[sources['selected_sdk']['name']]
    current_bound, current_issues = _official(current, ticker, market)
    latest_bound, latest_issues = _official(official, ticker, market, latest=True)
    current_bound = current_bound and current.get('date') == target
    latest_bound = latest_bound and official.get('date') == target
    conflict = conflict or bool(current_issues or latest_issues)
    issues.extend(current_issues + latest_issues)
    attempt_bound = bool(market != 'unknown' and sources['attempt']['failed']
                         and not sources['attempt']['issues'] and sources['attempt']['scope'] == 'current')
    return {
        'ticker': ticker, 'market': market,
        'primary_bound': primary_bound,
        'sdk_bounds': sdk_bounds,
        'attempt_bound': attempt_bound,
        'current_bound': current_bound,
        'latest_bound': latest_bound,
        'invalid': conflict or not (primary_bound or current_bound or latest_bound or attempt_bound),
        'limitations': list(dict.fromkeys(issues)),
    }
