"""Replay optional operating cash effects; never infer an underlying business motive.

No HTTP, source acquisition credit, historical availability grant or input mutation.
Only a replay-qualified individual filing pair may supply the component reference.
"""
from decimal import Decimal
from hashlib import sha256
from xml.etree import ElementTree as ET

from data_fetch.market_sources.official_xbrl_financial import (
    _context_period, XBRLI, IX, NUMBER_RE, MAX_BYTES,
)

TAGS = {
    'tifrs-SCF:DecreaseIncreaseInAccountsReceivable': 'receivables',
    'ifrs-full:AdjustmentsForDecreaseIncreaseInInventories': 'inventories',
    'tifrs-SCF:ChangesInOperatingAssets': 'operating_assets',
    'tifrs-SCF:ChangesInOperatingLiabilities': 'operating_liabilities',
    'tifrs-SCF:ChangesInOperatingAssetsAndLiabilities': 'operating_assets_and_liabilities',
}


def parse_components(raw, issuer, periods):
    """Return only explicit allowed facts for exact duration periods, in TWD."""
    if (not isinstance(raw, bytes) or len(raw) > MAX_BYTES
            or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper()):
        raise ValueError('Unsafe or oversized component original')
    root = ET.fromstring(raw)
    if root.tag != '{http://www.w3.org/1999/xhtml}html':
        raise ValueError('Component original is not inline XHTML')
    contexts, units = {}, {}
    for node in root.iter(XBRLI + 'context'):
        key = node.get('id')
        if not key or key in contexts:
            raise ValueError('Duplicate or missing component context')
        contexts[key] = _context_period(node, issuer)
    for node in root.iter(XBRLI + 'unit'):
        key = node.get('id')
        if not key or key in units:
            raise ValueError('Duplicate or missing component unit')
        children = list(node)
        units[key] = children[0].text if len(children) == 1 and children[0].tag == XBRLI + 'measure' else None
    result = {}
    for node in root.iter(IX + 'nonFraction'):
        name = TAGS.get(node.get('name'))
        period = contexts.get(node.get('contextRef'))
        if name is None or period not in periods:
            continue
        key = (name, period)
        if key in result:
            raise ValueError('Duplicate component fact')
        if (units.get(node.get('unitRef')) != 'iso4217:TWD'
                or node.get('format') != 'ixt:numdotdecimal' or node.get('scale') != '3'
                or node.get('decimals') not in ('-3', 'INF') or node.get('sign') not in (None, '-')):
            raise ValueError('Unsupported component units or format')
        literal = ''.join(node.itertext()).strip()
        if len(literal) > 40 or not NUMBER_RE.fullmatch(literal):
            raise ValueError('Invalid component amount')
        value = Decimal(literal.replace(',', '')) * 1000
        if value != value.to_integral_value():
            raise ValueError('Nonintegral component amount')
        result[key] = int(value) * (-1 if node.get('sign') == '-' else 1)
    return result


def read_official_cashflow_components(data):
    """Recheck original projection, receipts, identity and all subtotal periods.

    Missing components stay absent. A contradictory original fails the reference
    closed. The combined subtotal is not relabelled as textbook working capital.
    """
    from official_financial_projection import read_official_financial_projection
    from official_response_evidence import read_response
    try:
        source = read_official_financial_projection(data)
        if source is None:
            return None
        facts = source['facts']
        if facts['currency'] != 'TWD' or facts['report_scope'] != 'individual':
            return None
        annual = ('duration', str(facts['prior_annual_year']) + '-01-01', str(facts['prior_annual_year']) + '-12-31')
        current = ('duration', facts['current_ytd_period_start'], facts['period_end'])
        prior = ('duration', facts['prior_ytd_period_start'], facts['prior_ytd_period_end'])
        if current == prior or current[2].endswith('-12-31'):
            return None
        values, hashes, english_names = {}, {}, {}
        issuer = str(facts['ticker']).split('.')[0]
        for key, periods in (('annual_document', (annual,)), ('quarterly_document', (current, prior))):
            doc = source['reference'][key]
            raw = read_response(doc['raw_receipt'], max_bytes=MAX_BYTES)
            if sha256(raw).hexdigest() != doc['sha256']:
                return None
            values.update(parse_components(raw, issuer, periods))
            hashes[key] = doc['sha256']
            if facts['ticker'] == '1623.TW':
                # Use the same strict optional-alias parser as the income
                # reference, on these very same hash-checked filing bytes.
                # Caller display names and a single filing cannot supply it.
                from data_fetch.market_sources.tewc_income_reference import _english_name
                english_names[key] = _english_name(raw, annual if key == 'annual_document' else current)
        components = {}
        for name in TAGS.values():
            if all((name, p) in values for p in (annual, current, prior)):
                amounts = [values[name, p] for p in (annual, current, prior)]
                components[name] = {'period_values_twd': amounts, 'ttm_twd': amounts[0] + amounts[1] - amounts[2]}
        subtotal = ('operating_assets', 'operating_liabilities', 'operating_assets_and_liabilities')
        if all(k in components for k in subtotal):
            a, b, c = [components[k]['period_values_twd'] for k in subtotal]
            if any(x + y != z for x, y, z in zip(a, b, c)):
                return None
        if not components:
            return None
        english = english_names.get('annual_document')
        quarterly_english = english_names.get('quarterly_document')
        if not (english and quarterly_english and english.casefold() == quarterly_english.casefold()):
            english = None
        return {'schema': 'official-cashflow-components:v1', 'ticker': facts['ticker'],
                'issuer_name': facts['issuer_name'], 'currency': 'TWD', 'report_scope': 'individual',
                **({'issuer_english_name': english} if english else {}),
                'period_start': facts['period_start'], 'period_end': facts['period_end'],
                'components': components, 'document_sha256': hashes,
                'formula': 'prior_annual + current_ytd - prior_ytd',
                'native_acquisition': False, 'historical_pit_verified': False,
                'underlying_business_motive': 'unverified'}
    except (KeyError, TypeError, ValueError, AttributeError, OSError, ET.ParseError):
        return None
