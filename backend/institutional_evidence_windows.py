"""Explicit observation windows; dates never substitute for lookback duration."""
import re
from datetime import date

_WINDOW = re.compile(r"(?:近|最近|過去)?(?<![\d./年月\-第])(?P<n>\d+)(?:個)?(?:交易)?日")
_DATE = re.compile(r"(?:(?P<year>20\d{2})[年/\-])?(?P<month>\d{1,2})[月/\-](?P<day>\d{1,2})日?")


def _claimed_date(match, records):
    if match['year']:
        try:
            return date(int(match['year']), int(match['month']), int(match['day'])).isoformat()
        except ValueError:
            return None
    matches = {r['observed_at'] for r in records
               if int(r['observed_at'][5:7]) == int(match['month'])
               and int(r['observed_at'][8:10]) == int(match['day'])}
    return next(iter(matches)) if len(matches) == 1 else None


def _claim_window(prefix, records):
    periods = list(_WINDOW.finditer(prefix))
    dates = list(_DATE.finditer(prefix))
    joins = [prefix[left.end():right.start()] for left, right in zip(dates, dates[1:])]
    if any(re.fullmatch(r'[與及和、]', join) for join in joins):
        days = [_claimed_date(item, records) for item in dates]
        if (len(dates) == 2 and not periods and all(days)
                and re.fullmatch(r'[與及和、]', joins[0])
                and re.search(r'合計|總計|累計', prefix[dates[-1].end():])):
            return {'kind': 'two_explicit_days', 'dates': days}
        return {'kind': 'ambiguous_multi_day'}  # Never silently bind the final day.
    if periods:
        # A lookback's as-of date limits observation freshness, not its duration.
        # Keep explicit single-day dates, even when another as-of date follows.
        dates = [m for m in dates if not re.search(r"截至[:：]?$", prefix[:m.start()])]
    # Only an explicit later single-day marker can supersede an earlier lookback.
    if dates and (not periods or dates[-1].start() > periods[-1].start()):
        last = dates[-1]
        as_of = re.search(r"截至[:：]?$", prefix[:last.start()])
        if as_of and not re.search(r"單日|當日|今日|近一(?:個)?交易日", prefix):
            return None  # An as-of date alone does not declare the duration.
        if not as_of and re.search(r"(?:至|到|[-～~])$", prefix[:last.start()]):
            return None
        observed = _claimed_date(last, records)
        return {"kind": "day", "date": observed} if observed else None
    if periods:
        return {"kind": "trailing_trading_days", "trading_days": int(periods[-1]['n'])}
    if re.search(r"今日|當日|最新交易日", prefix):
        observed = max((r['observed_at'] for r in records), default=None)
        return {"kind": "day", "date": observed} if observed else None
    return None


def _same_window(record, window):
    if record['window'] == window:
        return True
    # One observed trading day is exactly the dated day, never a longer aggregate.
    return bool(window and window.get('kind') == 'day'
                and record['window'] == {'kind': 'trailing_trading_days', 'trading_days': 1}
                and record['observed_at'] == window.get('date'))


def two_day_candidates(window, population, records):
    """Derive a sum only from both visible, unique, adjacent dated observations."""
    if not window or window.get('kind') != 'two_explicit_days':
        return []
    days = window['dates']
    if (date.fromisoformat(days[1]) - date.fromisoformat(days[0])).days != 1:
        return []
    components = []
    values = []
    for day in days:
        rows = [r for r in records if r['population'] == population
                and r['window'] == {'kind': 'day', 'date': day}]
        amounts = {r['value'] * (1000 if r['unit'] == 'thousand_shares' else 1) for r in rows}
        if len(amounts) != 1:
            return []
        components.extend(rows)
        values.append(next(iter(amounts)))
    if len({r['provider'] for r in components}) != 1:
        return []
    unit = 'thousand_shares' if all(r['unit'] == 'thousand_shares' for r in components) else 'shares'
    refs = sorted({r.get('path') or r.get('evidence_ref') for r in components})
    return [{'population': population, 'window': window, 'observed_at': days[-1],
             'unit': unit, 'value': sum(values) / (1000 if unit == 'thousand_shares' else 1),
             'provider': components[0]['provider'], 'path': None,
             'evidence_ref': 'derived_sum(' + ','.join(refs) + ')', 'derived_from': refs}]

