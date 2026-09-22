"""Exact calendar pairs and explicitly dated start/peak flows; no period guessing."""
from dataclasses import dataclass
from datetime import date
import re
from institutional_evidence_tail import pair_tail_complete

_AMOUNT = r'[+\-−]?\d[\d,]*(?:\.\d+)?'
_VERB = r'淨買超|淨賣超|買超|賣超'

def _day(suffix, *, optional_month=False):
    month = rf'(?P<month{suffix}>\d{{1,2}})[月/\-]'
    if optional_month:
        month = '(?:' + month + ')?'
    return rf'(?:(?P<year{suffix}>20\d{{2}})[年/\-])?{month}(?P<day{suffix}>\d{{1,2}})日?'


def _amount(suffix):
    return rf'(?P<number{suffix}>{_AMOUNT})(?P<scale{suffix}>千|萬)?(?P<unit{suffix}>股|張)'

_COMPACT = re.compile(
    _day('1') + r'[與及和、]' + _day('2', optional_month=True)
    + r'(?:(?!外資|投信|自營商|法人|買超|賣超)[^\d。；;\n]){0,18}?分別'
    + rf'(?P<verb>{_VERB})' + _amount('1') + r'[與及和、]' + _amount('2'))
_START_PEAK = re.compile(
    _day('1') + r'(?:至|到)' + _day('end')
    + rf'[)）](?:{_VERB})[，,]單日(?P<verb>{_VERB})(?:量)?由'
    + _amount('1') + r'放大至最高' + _amount('2') + r'[（(]' + _day('2') + r'[)）]')


@dataclass(frozen=True)
class _DatedClaim:
    source: object
    member: int
    kind: str
    ambiguous: bool = False

    def __getitem__(self, key):
        return self.source[key if key == 'verb' else key + str(self.member)]

    def start(self):
        return self.source.start('verb' if self.member == 1 else 'number2')

    def end(self):
        return self.source.end('unit' + str(self.member))


def date_pair_claims(text, existing_claims, ordinary_pattern):
    """Preserve every ordinary claim; expand only a complete two-value grammar."""
    claims = list(existing_claims)
    for kind, pattern in (('ordered_pair', _COMPACT), ('start_peak', _START_PEAK)):
        for pair in pattern.finditer(text):
            # A third date/value changes scope; do not reinterpret a suffix as a pair.
            ambiguous = bool(re.search(r'\d日?[與及和、]$', text[:pair.start()])) or not pair_tail_complete(text, pair.end(), ordinary_pattern)
            claims = [(m, population) for m, population in claims if m.start() != pair.start('verb')]
            claims.extend([(_DatedClaim(pair, 1, kind, ambiguous), None), (_DatedClaim(pair, 2, kind, ambiguous), None)])
    return sorted(claims, key=lambda item: item[0].start())


def _resolve(pair, suffix, records):
    values = pair.groupdict()
    year = values.get('year' + suffix) or values.get('year1')
    month = values.get('month' + suffix) or values.get('month1')
    day = values.get('day' + suffix)
    if year:
        try:
            return date(int(year), int(month), int(day)).isoformat()
        except (ValueError, TypeError):
            return None
    matches = {r['observed_at'] for r in records
               if int(r['observed_at'][5:7]) == int(month) and int(r['observed_at'][8:10]) == int(day)}
    return next(iter(matches)) if len(matches) == 1 else None


def date_pair_window(match, eligible_records):
    """Unknown explicit scope is a nonempty marker, so callers cannot fall back."""
    if not isinstance(match, _DatedClaim):
        return None
    if match.ambiguous:
        return {'kind': 'explicit_date_pair_unknown'}
    first = _resolve(match.source, '1', eligible_records)
    second = _resolve(match.source, '2', eligible_records)
    end = _resolve(match.source, 'end', eligible_records) if match.kind == 'start_peak' else second
    if not (first and second and end and first < second <= end):
        return {'kind': 'explicit_date_pair_unknown'}
    return {'kind': 'day', 'date': first if match.member == 1 else second}
