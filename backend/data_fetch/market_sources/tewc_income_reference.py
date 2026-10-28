"""Replay individual income facts without changing the existing cash-flow contract."""
from decimal import Decimal
from hashlib import sha256
from xml.etree import ElementTree as ET

from .official_xbrl_financial import IX, XBRLI, NUMBER_RE, FilingError, _context_period
from .ordinary_individual_annual import parse_individual_filing
from .tewc_quarterly_reference import MAX_BYTES, replay_reference
from .mops_public_annual import _receipt

SCHEMA = 'tewc-income-reference:v1'
TICKER = '1623.TW'


def _fact(raw, tag, period, *, earnings_per_share=False, optional=False):
    root = ET.fromstring(raw)
    contexts = {n.get('id'): _context_period(n, '1623') for n in root.iter(XBRLI+'context')}
    units = {}
    for node in root.iter(XBRLI+'unit'):
        key = node.get('id')
        if not key or key in units:
            raise FilingError('income unit identity is ambiguous')
        units[key] = node
    nodes = [n for n in root.iter(IX+'nonFraction')
             if n.get('name') == 'ifrs-full:'+tag and contexts.get(n.get('contextRef')) == period]
    if not nodes and optional:
        return None
    if len(nodes) != 1:
        raise FilingError('income fact missing or ambiguous: '+tag)
    node = nodes[0]; unit = units.get(node.get('unitRef')); text = ''.join(node.itertext()).strip()
    allowed_attributes = {'id', 'name', 'contextRef', 'unitRef', 'scale', 'decimals', 'format', 'sign'}
    if list(node) or set(node.attrib) - allowed_attributes:
        raise FilingError('income numeric-node semantics are unsupported: '+tag)
    if unit is None:
        raise FilingError('income fact unit is missing')
    if earnings_per_share:
        if (len(list(unit)) != 1 or len(list(unit[0])) != 2 or unit[0].tag != XBRLI+'divide'
                or [n.tag for n in unit[0]] != [XBRLI+'unitNumerator', XBRLI+'unitDenominator']
                or any(len(list(n)) != 1 or n[0].tag != XBRLI+'measure' or list(n[0]) for n in unit[0])
                or [n[0].text for n in unit[0]] != ['iso4217:TWD', 'xbrli:shares']):
            raise FilingError('income EPS is not explicitly TWD per share')
        scale, decimals = '0', {'2', 'INF'}
    else:
        if (len(list(unit)) != 1 or unit[0].tag != XBRLI+'measure'
                or list(unit[0]) or unit[0].text != 'iso4217:TWD'):
            raise FilingError('income monetary fact is not simple TWD')
        scale, decimals = '3', {'-3', 'INF'}
    if (node.get('format') != 'ixt:numdotdecimal' or node.get('scale') != scale
            or node.get('decimals') not in decimals or node.get('sign') not in (None, '-')
            or len(text) > 40 or not NUMBER_RE.fullmatch(text)):
        raise FilingError('income numeric representation invalid: '+tag)
    value = Decimal(text.replace(',', '')) * (Decimal(10) ** int(scale))
    if node.get('sign') == '-':
        value = -value
    if not value.is_finite() or (not earnings_per_share and value != value.to_integral_value()):
        raise FilingError('income numeric value invalid: '+tag)
    if tag == 'IssuedCapital' and value <= 0:
        raise FilingError('income issued capital is not positive')
    return {'value': float(value) if earnings_per_share else int(value),
            'tag': 'ifrs-full:'+tag, 'context_ref': node.get('contextRef'),
            'period': list(period), 'unit': 'TWD/share' if earnings_per_share else 'TWD',
            'source_scale': int(scale), 'source_decimals': node.get('decimals')}


def replay_income_reference(value, ticker):
    """Read qualified originals; never certify a provider scalar or combine EPS.

    The v1 cash-flow projection remains byte-for-byte compatible. Extra facts
    are opted into with a new reference and do not upgrade five-year coverage,
    provider freshness, historical availability, or a price-target assumption.
    """
    failure = {'status': 'unverified', 'historical_pit_verified': False,
               'native_acquisition': False, 'five_year_history_verified': False,
               'ttm_eps_verified': False}
    try:
        if (ticker != TICKER or not isinstance(value, dict) or value.get('schema') != SCHEMA
                or value.get('ticker') != ticker or set(value) != {'schema', 'ticker', 'financial_reference'}):
            raise FilingError('income reference identity or schema invalid')
        reference = value['financial_reference']; base = replay_reference(reference, ticker)
        if base.get('status') != 'quarterly_originals_verified':
            raise FilingError('income parent financial originals are unverified')
        annual = reference['annual_document']; quarterly = reference['quarterly_document']
        ar = _receipt(annual['raw_receipt'], annual['url'], MAX_BYTES)
        qr = _receipt(quarterly['raw_receipt'], quarterly['url'], MAX_BYTES)
        if sha256(ar).hexdigest() != annual['sha256'] or sha256(qr).hexdigest() != quarterly['sha256']:
            raise FilingError('income source changed during replay')
        year = annual['year']; current = quarterly['year']; end = base['period_end']
        parsed = parse_individual_filing(ar, '1623', year, reference_only=True)
        keys = ('reported_revenue', 'profit_loss', 'operating_cash_flow', 'ppe_purchase',
                'intangible_purchase')
        annual_rows = {str(y): {k: parsed[y][k] for k in keys} for y in (year-1, year)}
        from .ordinary_individual_annual import FIELDS
        tags = {field: tag for tag, field in FIELDS.items()}
        for y in (year-1, year):
            period = ('duration', f'{y}-01-01', f'{y}-12-31')
            for field in keys:
                if _fact(ar, tags[field], period)['value'] != annual_rows[str(y)][field]:
                    raise FilingError('income annual fact differs from native parse: '+field)
        for row in annual_rows.values():
            row['free_cash_flow'] = (row['operating_cash_flow'] + row['ppe_purchase']
                                    + row['intangible_purchase'])
        periods = {'current_ytd': ('duration', f'{current}-01-01', end),
                   'prior_ytd': ('duration', f'{year}-01-01', base['prior_ytd_period_end'])}
        income = {key: _fact(qr, 'ProfitLoss', period) for key, period in periods.items()}
        ttm_net_income = (annual_rows[str(year)]['profit_loss'] + income['current_ytd']['value']
                          - income['prior_ytd']['value'])
        eps = {key: _fact(qr, 'BasicEarningsLossPerShare', period, earnings_per_share=True, optional=True)
               for key, period in periods.items()}
        eps['prior_annual'] = _fact(ar, 'BasicEarningsLossPerShare',
            ('duration', f'{year}-01-01', f'{year}-12-31'), earnings_per_share=True, optional=True)
        capital = {end: _fact(qr, 'IssuedCapital', ('instant', end), optional=True),
                   f'{year}-12-31': _fact(qr, 'IssuedCapital', ('instant', f'{year}-12-31'), optional=True)}
        fcf = base['cashflows']['ttm']['free_cash_flow']
        return {**failure, 'status': 'income_originals_verified', 'ticker': ticker,
                'report_scope': 'individual', 'currency': 'TWD', 'issuer_name': base['issuer_name'],
                'capture_boundary': 'archived_official_evidence_replay', 'freshness_status': 'not_revalidated',
                'period_start': base['period_start'], 'period_end': end, 'annual_rows': annual_rows,
                'income_components': income, 'net_income_ttm_raw': ttm_net_income,
                'net_income_ttm_formula': 'prior_annual + current_ytd - prior_ytd',
                'fcf_conversion_ttm_pct': fcf / ttm_net_income * 100 if ttm_net_income > 0 else None,
                'reported_basic_eps': eps, 'issued_capital': capital,
                'share_count_bridge_verified': False,
                'ttm_eps_unavailable_reason': 'No qualified weighted-average-share bridge; annual and YTD EPS cannot be added across capital changes.',
                'source_documents': [{k: doc[k] for k in ('url', 'sha256')} for doc in (annual, quarterly)]}
    except (KeyError, TypeError, ValueError, OSError, EOFError, OverflowError, ET.ParseError) as exc:
        return {**failure, 'reason': str(exc)[:240] if isinstance(exc, FilingError) else 'income original validation failed'}
