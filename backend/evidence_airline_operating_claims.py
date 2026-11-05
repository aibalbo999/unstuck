"""Narrow same-carrier, same-period operating facts; never a financial proxy."""
from decimal import Decimal, InvalidOperation
import re
from evidence_claim_numbers import valid_claim_number

METRICS = {
    '旅客人數': 'passengers', '載客率': 'passenger_load_factor',
    '貨運噸數（含郵件、貨物及行李）': 'cargo_tonnes', '載貨率': 'cargo_load_factor',
}
_METRIC = r'(?:旅客人數|載客率|貨運噸數(?:（含郵件、貨物及行李）)?|載貨率)'
_VALUE = r'-?\d[\d,]*(?:\.\d+)?'
_SCOPED = re.compile(rf'(?P<metric>{_METRIC})\s*[:：]\s*(?P<num>{_VALUE})\s*(?P<unit>[^\s，,。；;|]*)')
_CANONICAL = re.compile(
    rf'(?:[-*]\s+)?民航局\s+(?P<issuer>\S+)\s+'
    rf'(?P<year>20\d{{2}})年(?:(?P<ytd>1至))?(?P<month>[1-9]|1[0-2])月(?P<cumulative>累計)?\s+'
    rf'全球(?P<metric>{_METRIC})\s*[:：]\s*(?P<num>{_VALUE})\s*(?P<unit>人|公噸|%)。?'
)


def extract_operating_claims(markdown, existing):
    """Catch person/tonne units locally, without broadening financial extraction."""
    added = []; in_code = False
    for line_number, raw in enumerate(str(markdown or '').splitlines(), 1):
        line = raw.strip()
        if line.startswith('```'):
            in_code = not in_code
            continue
        if in_code or line.startswith('#') or not ('民航局' in line or 'operating_metrics_official' in line):
            continue
        for match in _SCOPED.finditer(line):
            number = float(match['num'].replace(',', ''))
            if not valid_claim_number(number):
                continue
            added.append({'label': match['metric'], 'reported_value': number, 'unit': match['unit'],
                          'line_number': line_number, 'raw_text': line, 'claim_type': 'operating',
                          '_caa_operating_claim': True})
    if not added:
        return existing
    # Replace only the same scoped operating token; retain other same-line facts.
    existing = [c for c in existing if not any(
        c.get('line_number') == a['line_number'] and c.get('reported_value') == a['reported_value']
        and a['label'] in str(c.get('label') or '') for a in added)]
    return [{**c, 'id': i} for i, c in enumerate(sorted(existing + added, key=lambda c: c['line_number']), 1)]


def operating_claim(claim, snapshot):
    if not claim.get('_caa_operating_claim'):
        return None
    result = {**claim, 'status': 'unverifiable', 'candidate_count': 0,
              'verification_scope': 'native_carrier_operating_fact',
              'verification_reason_code': 'carrier_period_unit_or_scope_unbound'}
    line = str(claim.get('raw_text') or '')
    match = _CANONICAL.fullmatch(line)
    if not match or bool(match['ytd']) != bool(match['cumulative']):
        return result
    data = snapshot.get('data')
    data = data if isinstance(data, dict) else {}
    alternative = data.get('alternative_data')
    value = alternative.get('operating_metrics_official') if isinstance(alternative, dict) else None
    from data_fetch.market_sources.caa_operating_evidence import verified_count
    from data_fetch.market_sources.caa_operating_identity import PROFILES
    if verified_count(value, data) != 1:
        return {**result, 'verification_reason_code': 'carrier_complete_originals_or_owners_unverified'}
    if match['issuer'] != PROFILES[data['ticker']][5] or int(match['year']) != value['year']:
        return result
    frequency = 'year_to_date' if match['ytd'] else 'monthly'
    rows = [value['year_to_date']] if match['ytd'] else value['monthly_history']
    rows = [r for r in rows if r['frequency'] == frequency and r['year'] == int(match['year']) and r['month'] == int(match['month'])]
    field = METRICS.get(match['metric'])
    if len(rows) != 1 or not field:
        return result
    metric = rows[0]['values'][field]
    if match['unit'] != metric['unit']:
        return result
    try:
        reported = Decimal(match['num'].replace(',', ''))
        observed = Decimal(metric['native_display'].replace(',', ''))
    except InvalidOperation:
        return result
    if not reported.is_finite() or not observed.is_finite():
        return result
    # Exact published precision, not a 1% allowance on headcounts or tonnes.
    return {**result, 'status': 'verified' if reported == observed else 'mismatch',
            'verification_reason_code': 'matched_native_carrier_period_value' if reported == observed else 'native_carrier_period_value_mismatch',
            'candidate_count': 1, 'matched_value': float(observed),
            'matched_path': f'data.alternative_data.operating_metrics_official.{frequency}[{match["year"]}-{int(match["month"]):02d}].values.{field}.native_display'}
