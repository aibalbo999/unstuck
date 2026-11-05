"""Request identity for the individually qualified 2646 issuer only.

Common reference/home/methodology requests keep their existing semantic cache
identity. Only the distinct individual issuer's index and income carry a marker.
"""
from urllib.parse import urlencode
from .starair_reference_income import CODE, TICKER, PUBLISHED_COMPANY_LABEL, quarter_end

MARKER = 'individual_reference_issuer'


def spec(kind, *, day=None, year=None, quarter=None):
    if kind in {'home', 'methodology', 'reference'}:
        from .peer_reference_transport import spec as shared_spec
        return shared_spec(kind, day=day)
    if kind == 'index':
        quarter_end(year, 4)
        return {'kind': kind, 'params': {'year': year, MARKER: TICKER},
            'url': 'https://doc.twse.com.tw/server-java/t57sb01?' + urlencode(
                {'co_id': CODE, 'colorchg': '1', 'mtype': 'A', 'step': '1', 'year': str(year-1911)}),
            'method': 'GET', 'data': None, 'mime': 'text/html', 'encoding': 'big5', 'limit': 250000}
    if kind == 'income':
        quarter_end(year, quarter)
        return {'kind': kind, 'params': {'year': year, 'quarter': quarter, MARKER: TICKER},
            'url': 'https://mopsfin.twse.com.tw/compare/report', 'method': 'POST',
            'data': {'compareItem': 'IncomeStatement', 'quarter': 'true', 'ylabel': '', 'ys': f'{year}{quarter}',
                'revenue': 'true', 'bcodeAvg': 'false', 'companyAvg': 'false', 'qnumber': '', 'companyId': PUBLISHED_COMPANY_LABEL},
            'mime': 'text/html', 'encoding': 'utf-8', 'limit': 250000}
    raise ValueError('unsupported individual issuer request')


def canonical_spec(value):
    if not isinstance(value, dict) or value.get('kind') not in {'index', 'income'}:
        raise ValueError('unsupported individual request')
    params = value.get('params')
    if not isinstance(params, dict) or params.get(MARKER) != TICKER:
        raise ValueError('individual request issuer mismatch')
    expected = spec(value['kind'], year=params.get('year'), quarter=params.get('quarter'))
    if value != expected:
        raise ValueError('individual request identity or scope not admitted')
    return expected
