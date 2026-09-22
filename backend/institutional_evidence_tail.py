"""Closed pair boundaries: every extra amount needs a separately named claim."""
import re
from institutional_evidence_windows import _WINDOW

_SUBJECT = re.compile(r'三大法人|三類法人|法人|外資|投信|自營商')
_AMOUNT = re.compile(r'[+\-−]?\d[\d,]*(?:\.\d+)?(?:千|萬)?(?:股|張)')
_PERIOD_OR_DATE = re.compile(r'\d+(?:個)?(?:交易)?日|近一(?:個)?交易日|\d{1,2}[月/\-]\d{1,2}')


def pair_tail_complete(text, pair_end, ordinary_pattern):
    # Semicolons do not hide an anonymous third amount or contradictory period.
    ending = re.search(r'[。!?！？\n]', text[pair_end:])
    stop = pair_end + ending.start() if ending else len(text)
    line_start = text.rfind('\n', 0, pair_end) + 1
    # A pair may sit inside parentheses opened before its first amount.
    balance = 0
    for char in text[line_start:stop]:
        if char in '(（':
            balance += 1
        elif char in ')）':
            balance -= 1
        if balance < 0:
            return False
    if balance:
        return False
    following = list(ordinary_pattern.finditer(text, pair_end, stop))
    cursor = pair_end
    own_scope_end = stop
    unbound_gaps = []
    for index, match in enumerate(following):
        subject = _SUBJECT.search(text, cursor, match.start())
        if not subject:
            return False
        if index == 0:
            own_scope_end = subject.start()
        unbound_gaps.append(text[cursor:subject.start()])
        cursor = match.end()
    for amount in _AMOUNT.finditer(text, pair_end, stop):
        if not any(match.start() <= amount.start() and amount.end() <= match.end()
                   for match in following):
            return False
    unbound_gaps.append(text[cursor:stop])
    if any(_WINDOW.search(gap) or _PERIOD_OR_DATE.search(gap) for gap in unbound_gaps):
        return False
    # A later explicit subject owns its own date/period; ordinary validation handles it.
    return not _PERIOD_OR_DATE.search(text[pair_end:own_scope_end])
