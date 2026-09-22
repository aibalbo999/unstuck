"""Narrow rendered Signal/ATR assignments; never infer a scalar from nearby prose."""
import re
from datetime import date

from evidence_claim_numbers import clean_number
from evidence_daily_price_claims import DAILY_DATE_RE

_KEY = re.compile(r"(?<![A-Za-z0-9_])(?P<key>Signal|ATR(?:[_ ]?\d+|\(\d+\))?)(?![A-Za-z0-9_])", re.I)
_ASSIGNMENT_KEY = re.compile(_KEY.pattern.replace('Signal|', 'macd_signal|Signal|'), re.I)
_VALUE = re.compile(r"\s*[:：=]\s*(?:NT\$|\$|TWD)?\s*(-?\d[\d,]*(?:\.\d+)?)\s*(?:元|TWD)?(?=$|[\s,，;；）)\"。])", re.I)
_WRONG_BASIS = re.compile(r"昨日|前日|前期|預估|預測|假設|如果|若|目標|previous|yesterday|forecast|projected|hypothetical|新聞|news|券商|factset", re.I)
_PARTIAL_DATE = re.compile(r"(?<!\d)(?:0?[1-9]|1[0-2])\s*[/月]\s*(?:0?[1-9]|[12]\d|3[01])(?:日)?(?!\d)|(?:19|20)\d{2}\s*年")


def technical_assignment_label(label):
    """The named key immediately before ':' owns the value, not preceding RSI prose."""
    found = list(_KEY.finditer(label))
    if found and found[-1].end() == len(label.strip()):
        key = found[-1].group('key')
        if found[-1].start() and (key.lower() == 'signal' or label[found[-1].start()-1] not in '(（'):
            return label
        return 'Signal' if key.lower() == 'signal' else key.upper()
    return label


def explicit_atr14_policy(technical):
    policy = technical.get('calculation_policy')
    if not isinstance(policy, dict):
        return False
    periods = [key for key in policy if re.fullmatch(r'atr_\d+', key)]
    return periods == ['atr_14'] and bool(re.match(r'14\b', str(policy['atr_14'])))


def _assignment_scope(text, offset):
    """Use the containing parentheses, otherwise the same sentence/semicolon clause."""
    stack = []
    for index, char in enumerate(text[:offset]):
        if char in '(（':
            stack.append(index)
        elif char in ')）' and stack:
            stack.pop()
    if stack:
        start = stack[-1]
        close = re.search(r'[)）]', text[offset:])
        if close:
            return text[start:offset + close.end()]
    start = max((text.rfind(c, 0, offset) for c in '。；;\n'), default=-1) + 1
    end = re.search(r'[。；;\n]', text[offset:])
    return text[start:offset + end.start()] if end else text[start:]


def technical_assignment_path(claim):
    label = str(claim.get('label') or '')
    if not _KEY.fullmatch(label):
        return None
    text = re.sub(r'[*`]', '', str(claim.get('technical_context_text') or claim.get('raw_text') or ''))
    if (_WRONG_BASIS.search(text) or str(claim.get('unit') or '').lower() not in {'', '元', 'twd'}):
        return ()
    dates = list(DAILY_DATE_RE.finditer(text))
    if len(dates) > 1 or _PARTIAL_DATE.search(DAILY_DATE_RE.sub(' ', text)):
        return ()
    if dates:
        try:
            observed = date(*(int(part) for part in dates[0].groups())).isoformat()
        except ValueError:
            return ()
        if observed != claim.get('_technical_as_of'):
            return ()
    signal = label.lower() == 'signal'
    if not signal and label.upper() not in {'ATR', 'ATR14', 'ATR_14', 'ATR 14', 'ATR(14)'}:
        return ()
    if label.upper() == 'ATR' and not claim.get('_technical_default_atr14'):
        return ()
    assignments = []
    for match in _ASSIGNMENT_KEY.finditer(text):
        key = match.group('key')
        canonical = re.sub(r'[_ ()]', '', key.lower())
        if canonical not in ({'signal', 'macdsignal'} if signal else {'atr', 'atr14'}):
            continue
        tail = text[match.end():]
        if not re.match(r'\s*[:：=]', tail):
            continue
        scope = _assignment_scope(text, match.start())
        if signal and not re.search(r'(?<![A-Za-z0-9_])MACD\s*[:：=]\s*-?\d', scope, re.I):
            return ()
        value = _VALUE.match(tail)
        assignments.append(clean_number(value.group(1)) if value else None)
    if len(assignments) != 1 or assignments[0] != claim.get('reported_value'):
        return ()
    return ('data.technical_indicators.macd_signal' if signal else 'data.technical_indicators.atr_14',)
