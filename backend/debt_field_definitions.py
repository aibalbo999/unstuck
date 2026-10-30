"""Bind debt definitions to actual provider fields before comparing amounts."""
from __future__ import annotations

import math
import re
from datetime import date


SCHEMA = 'financial-field-definition.v1'
COMPARABLE_DEFINITIONS = frozenset({'total_liabilities', 'interest_bearing_debt'})


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def debt_definition(value, definition, provider, source_field, *, currency=None, as_of=None, report_scope=None):
    return {'schema': SCHEMA, 'field': 'total_debt_raw', 'definition': definition,
            'provider': provider, 'source_field': source_field, 'value': _number(value),
            'unit': 'currency', 'currency': currency, 'as_of': as_of,
            'report_scope': report_scope}


def yfinance_debt_definition(context):
    info = context.get('info')
    info = info if isinstance(info, dict) else {}
    value, original = _number(context.get('total_debt')), _number(info.get('totalDebt'))
    meaning = 'interest_bearing_debt' if value is not None and value == original else 'unknown'
    return debt_definition(value, meaning, 'yfinance', 'info.totalDebt',
                           currency=context.get('financial_currency') or None)


def debt_comparison_status(values, definitions):
    """Unknown metadata never becomes agreement; different concepts have no median."""
    selected = {source: definitions.get(source) if isinstance(definitions, dict) else None
                for source in values}
    result = {'source_definitions': selected, 'comparison_status': 'unknown',
              'definition_reason_codes': []}
    for source, value in values.items():
        basis = selected[source]
        if (not isinstance(basis, dict) or basis.get('schema') != SCHEMA
                or basis.get('field') != 'total_debt_raw'
                or not isinstance(basis.get('definition'), str)
                or basis.get('definition') not in COMPARABLE_DEFINITIONS
                or not isinstance(basis.get('provider'), str) or not basis['provider'].strip()
                or not isinstance(basis.get('source_field'), str) or not basis['source_field'].strip()
                or _number(basis.get('value')) != value):
            result['definition_reason_codes'].append('source_definition_unverified:' + source)
    if result['definition_reason_codes']:
        return result
    meanings = {basis['definition'] for basis in selected.values()}
    if len(meanings) != 1:
        return {**result, 'comparison_status': 'different_definition',
                'definition_reason_codes': ['different_financial_concepts']}
    for field in ('unit', 'currency', 'as_of', 'report_scope'):
        facts = [basis.get(field) for basis in selected.values()]
        if any(not isinstance(value, str) or not value.strip() for value in facts):
            result['definition_reason_codes'].append('comparison_basis_missing:' + field)
        elif len(set(facts)) != 1:
            result['definition_reason_codes'].append('comparison_basis_mismatch:' + field)
    for basis in selected.values():
        try:
            valid_date = isinstance(basis.get('as_of'), str) and date.fromisoformat(basis['as_of']).isoformat() == basis['as_of']
        except ValueError:
            valid_date = False
        if (not valid_date or basis.get('unit') != 'currency'
                or not isinstance(basis.get('report_scope'), str)
                or basis['report_scope'] not in {'individual', 'consolidated', 'standalone'}
                or not isinstance(basis.get('currency'), str)
                or re.fullmatch(r'[A-Z]{3}', basis['currency']) is None):
            result['definition_reason_codes'].append('comparison_basis_unverified')
    if result['definition_reason_codes']:
        return result
    if len({basis['provider'] for basis in selected.values()}) < 2:
        return {**result, 'definition_reason_codes': ['independent_source_not_established']}
    return {**result, 'comparison_status': 'comparable'}
