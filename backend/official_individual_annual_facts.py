"""Dated annual facts replayed from the existing individual filing pair.

Annual observations never replace provider histories, TTM facts, EPS bridges or
valuation inputs. The verifier always reconstructs its source from originals.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

_FIELDS = {'營收': 'reported_revenue', '淨利': 'profit_loss', '自由現金流': 'free_cash_flow'}
_METRICS = {'營收': '營收', '營業收入': '營收', '淨利': '淨利', '稅後淨利': '淨利',
            'FCF': '自由現金流', '自由現金流': '自由現金流'}

def annual_facts_from_replayed_income(income):
    """Build a prompt envelope only after the caller's native original replay."""
    if (income.get('status') != 'income_originals_verified'
            or income.get('ticker') != '1623.TW' or income.get('currency') != 'TWD'
            or income.get('report_scope') != 'individual'):
        return None
    rows = income.get('annual_rows')
    if not isinstance(rows, dict) or len(rows) != 2:
        return None
    years = sorted(rows)
    if (any(not re.fullmatch(r'20\d{2}', year) for year in years)
            or int(years[1]) != int(years[0]) + 1 or int(years[1]) >= date.today().year):
        return None
    filing_year = int(years[-1]); periods = {}
    for year, row in rows.items():
        keys = ('reported_revenue', 'profit_loss', 'free_cash_flow',
                'operating_cash_flow', 'ppe_purchase', 'intangible_purchase')
        if (not isinstance(row, dict) or any(type(row.get(key)) is not int for key in keys)
                or row['free_cash_flow'] != row['operating_cash_flow'] + row['ppe_purchase'] + row['intangible_purchase']):
            return None
        start, end = year + '-01-01', year + '-12-31'
        values = {metric: row[key] for metric, key in _FIELDS.items()}
        prefix = f"{income['issuer_name']}官方個別財報 TWD 年度（{start} 至 {end}）"
        periods[year] = {'period_start': start, 'period_end': end,
            'source_filing_year': filing_year, 'comparative_period': int(year) != filing_year,
            'values_twd': values, 'free_cash_flow_components_twd': {
                key: row[key] for key in ('operating_cash_flow', 'ppe_purchase', 'intangible_purchase')},
            'statements': {metric: prefix + metric + '為 '
                + format(Decimal(value) / Decimal(100000000), 'f') + ' 億元。'
                for metric, value in values.items()}}
    document = income['source_documents'][0]
    return {'schema': 'official-individual-annual-facts:v1', 'status': 'annual_originals_replayed',
        'ticker': income['ticker'], 'issuer_name': income['issuer_name'],
        **({'issuer_english_name': income['issuer_english_name']} if income.get('issuer_english_name') else {}),
        'currency': 'TWD', 'report_scope': 'individual', 'monetary_amount_unit': 'TWD',
        'periods': periods, 'source_document': {key: document[key] for key in ('url', 'sha256')},
        'free_cash_flow_definition': 'operating_cash_flow + signed_ppe_purchase + signed_intangible_purchase',
        'native_acquisition': False, 'historical_pit_verified': False, 'five_year_history_verified': False,
        'freshness_status': 'not_revalidated', 'vendor_history_replaced': False,
        'limitations': '僅核實完整原件中的個別年度及比較期；不授予五年歷史可比性、TTM EPS、估值或歷史首次可得性。不替換供應商數列。'}

def official_fact_container_matches(text, data):
    """Recognize a neutral caption plus already complete source-bound siblings.

    This grants no scope to the current claim. Every sibling must equal a
    canonical statement reconstructed from originals; arbitrary prose, amounts,
    issuers and period qualifiers remain binding and fail closed.
    """
    lines = [re.sub(r'[*`]', '', line).strip()
             for line in str(text or '').splitlines() if line.strip()]
    if (not lines or len(lines) > 4 or re.fullmatch(
            r'-?\s*官方個別年度(?:營收|與\s*TTM\s*(?:淨利|自由現金流))事實[:：]', lines[0]) is None):
        return False
    from official_income_prompt import official_income_prompt_facts
    income = official_income_prompt_facts(data)
    annual = income.get('annual_facts') if isinstance(income, dict) else None
    if not isinstance(annual, dict):
        return False
    statements = {statement for row in annual['periods'].values()
                  for statement in row['statements'].values()}
    return all(line in statements for line in lines[1:])


def check_individual_annual_claim(claim, data, tolerance_pct):
    metric = _METRICS.get(claim.get('financial_metric'))
    raw = re.sub(r'[*`]', '', str(claim.get('raw_text') or ''))
    if metric is None or re.search(
            r'官方\s*(?:個別|合併)?\s*財報\s*(?:[A-Z]{3}|新[臺台]幣)?\s*年度[（(]', raw) is None:
        return None
    unknown = {'status': 'unverifiable', 'verification_reason_code': 'official_individual_annual_scope_unbound',
               'candidate_count': 0, 'independent_primary_source_verified': False}
    if (claim.get('financial_actual') is False or claim.get('financial_scope_unbound')
            or claim.get('foreign_currency_declared') or claim.get('unit') != '億元'):
        return unknown
    from official_income_prompt import official_income_prompt_facts
    income = official_income_prompt_facts(data)
    facts = income.get('annual_facts') if isinstance(income, dict) else None
    if not isinstance(facts, dict):
        return unknown
    from evidence_official_income_claims import _identity, _context_matches, _native_report_title, _INCOMPATIBLE
    identity = _identity(facts); ancestors = claim.get('_financial_heading_ancestors')
    heading = str(claim.get('financial_heading') or ''); parent = str(claim.get('financial_parent_context') or '')
    if (not isinstance(ancestors, list) or len(ancestors) > 6
            or (heading and (not ancestors or ancestors[-1] != heading))
            or (not heading and ancestors)):
        return unknown
    def structural(value):
        return (isinstance(value, str) and not _INCOMPATIBLE.search(value)
                and (re.fullmatch(r'\s*#{1,6}\s*(?:[一二三四五六七八九十]+[、.]\s*)?(?:已核實年度財務|營收成長分析)\s*', value) is not None
                     or _native_report_title(value, facts) or _context_matches(value, identity)
                     or official_fact_container_matches(value, data)))
    if any(not structural(value) for value in ancestors) or (parent.strip() and not structural(parent)):
        return unknown
    names = [facts['issuer_name'], *identity['company_identity']['allowed_aliases']]
    number = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    match = re.fullmatch(r'\s*[-*]?\s*(?:' + '|'.join(map(re.escape, names))
        + r')\s*官方\s*個別\s*財報\s*TWD\s*年度[（(]\s*(?P<start>20\d{2}-\d{2}-\d{2})\s*至\s*'
          r'(?P<end>20\d{2}-\d{2}-\d{2})\s*[）)]\s*' + re.escape(claim['financial_metric'])
        + r'\s*為\s*(?P<number>' + number + r')\s*億元[。.]?\s*', raw)
    if match is None:
        return unknown
    year = match['start'][:4]; row = facts['periods'].get(year)
    if not row or (match['start'], match['end']) != (row['period_start'], row['period_end']):
        return unknown
    literal = match['number'].replace(',', ''); precision = len(literal.partition('.')[2])
    if len(literal) > 64 or precision > 20:
        return unknown
    try:
        reported = Decimal(literal); expected = Decimal(row['values_twd'][metric]) / Decimal(100000000)
        tolerance = Decimal(str(tolerance_pct))
        if not all(value.is_finite() for value in (reported, expected, tolerance)) or tolerance < 0:
            return unknown
        if reported != Decimal(str(claim['reported_value'])):
            return unknown
        rounded = expected.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        difference = abs(reported - expected) / max(abs(expected), Decimal('1e-12')) * 100
        # A known original must match the precision actually asserted. A broad
        # percentage tolerance could otherwise certify a nearby TTM amount.
        matched = reported * expected >= 0 and reported == rounded
    except (InvalidOperation, ValueError, TypeError, KeyError):
        return unknown
    return {'status': 'verified' if matched else 'mismatch', 'candidate_count': 1,
        'verification_reason_code': 'official_individual_annual_matched' if matched else 'official_individual_annual_mismatch',
        'verification_scope': 'replayed_official_individual_annual_fact',
        'matching_policy': 'exact_rounding_to_reported_precision',
        'expected_value_raw_twd': row['values_twd'][metric], 'matched_value': float(expected), 'diff_pct': float(difference),
        'matched_path': f'official_income_prompt_facts(data).annual_facts.periods.{year}.values_twd.{metric}',
        'financial_period': row['period_start'] + '/' + row['period_end'],
        'financial_report_scope': 'individual', 'financial_currency': 'TWD',
        'source_filing_year': row['source_filing_year'], 'comparative_period': row['comparative_period'],
        'financial_source_documents': [facts['source_document']],
        'source_url': facts['source_document']['url'],
        'source_document_sha256': facts['source_document']['sha256'],
        'independent_primary_source_verified': True,
        'native_acquisition': False, 'historical_pit_verified': False, 'five_year_history_verified': False,
        'vendor_history_replaced': False}
