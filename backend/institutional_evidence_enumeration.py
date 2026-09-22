"""Lossless expansion of a narrowly explicit, ordered pair of net-flow claims."""
from dataclasses import dataclass
import re
from institutional_evidence_tail import pair_tail_complete

_POP = r'外資|投信|自營商'
_NAMES = {'外資': 'foreign', '投信': 'investment_trust', '自營商': 'dealer'}
_AMOUNT = r'[+\-−]?\d[\d,]*(?:\.\d+)?'
_PAIR = re.compile(
    rf'(?P<p1>{_POP})[與及和、](?P<p2>{_POP})(?:在|於)?'
    r'(?P<period>(?:近|最近|過去)?\d+(?:個)?(?:交易)?日)(?:呈現)?'
    r'(?P<verb>淨買超|淨賣超|買超|賣超)[，,]?分別(?:達|為)?'
    rf'(?P<number1>{_AMOUNT})(?P<scale1>千|萬)?(?P<unit1>股|張)[與及和、]'
    rf'(?P<number2>{_AMOUNT})(?P<scale2>千|萬)?(?P<unit2>股|張)'
)


@dataclass(frozen=True)
class _PairedClaim:
    source: object
    member: int
    peer_population: str
    scope_valid: bool = True

    def __getitem__(self, key):
        return self.source[key if key == 'verb' else key + str(self.member)]

    def start(self):
        return self.source.start('verb' if self.member == 1 else 'number2')

    def end(self):
        return self.source.end('unit' + str(self.member))


def flow_claims(text, ordinary_pattern):
    """Return original offsets; never silently drop the second paired amount."""
    claims = [(match, None) for match in ordinary_pattern.finditer(text)]
    for pair in _PAIR.finditer(text):
        if pair['p1'] == pair['p2']:
            continue
        # Do not accept a suffix of a longer subject list or prefix of more amounts.
        if re.search(rf'(?:{_POP})[與及和、]$', text[:pair.start()]):
            continue
        if re.match(r'[與及和、](?:[+\-−]?\d|外資|投信|自營商)', text[pair.end():]):
            continue
        first, second = _NAMES[pair['p1']], _NAMES[pair['p2']]
        claims = [(match, population) for match, population in claims
                  if match.start() != pair.start('verb')]
        complete = pair_tail_complete(text, pair.end(), ordinary_pattern)
        claims.extend([(_PairedClaim(pair, 1, second, complete), first),
                       (_PairedClaim(pair, 2, first, complete), second)])
    return sorted(claims, key=lambda item: item[0].start())
