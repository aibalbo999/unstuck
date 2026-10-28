"""Select replayed official facts for a new analysis, preserving quote provenance."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import math
import re

SCHEMA = 'official-financial-projection:v1'
SELECTED = {'free_cash_flow_raw': 'free_cash_flow', 'operating_cash_flow_raw': 'operating_cash_flow'}
QUOTE_FIELDS = ('financial_currency', 'free_cash_flow_raw', 'operating_cash_flow_raw',
                'free_cash_flow', 'operating_cash_flow',
                'total_debt_raw', 'total_cash_raw', 'debt_to_equity', 'net_income_ttm_raw',
                'net_income_ttm_source', 'revenue_ttm_raw', 'fetch_date', 'fetched_at',
                'source', 'financial_source', 'financial_provenance')


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _selected(facts):
    return {field: facts['cashflows']['ttm'][metric] for field, metric in SELECTED.items()}


def _display(facts):
    from data_fetch.formatting import format_number
    return {field.removesuffix('_raw'): format_number(amount, '億')
            for field, amount in _selected(facts).items()}


def _replay(data, reference):
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    if not isinstance(data, dict) or str(data.get('financial_currency') or '').upper() not in {'TWD', 'NTD'}:
        return None
    facts = replay_reference(reference, data.get('ticker'))
    return facts if facts.get('status') == 'quarterly_originals_verified' else None


def project_official_financials(data, reference):
    """Return a new unfrozen input copy; never rebind a prior analysis or quote.

    Only FCF and OCF are selected. Balance ratios retain an independent official
    source, so no same-day net debt is invented from an undated cash scalar.
    """
    if not isinstance(data, dict):
        raise ValueError('financial projection input is invalid')
    if any(key in data for key in ('analysis_input_hash', 'analysis_input_cutoff', '_analysis_input_evidence')):
        raise ValueError('financial projection cannot replace a frozen analysis input')
    if 'official_financial_projection' in data or 'original_quote_financials' in data:
        raise ValueError('existing financial projection must not be overwritten')
    facts = _replay(data, reference)
    if facts is None:
        raise ValueError('official financial projection source is unverified')
    original = {'schema': 'preserved-quote-financials:v1', 'ticker': data.get('ticker'),
                'period_status': 'unverified', 'definition_status': 'unverified',
                'values': {key: deepcopy(data[key]) for key in QUOTE_FIELDS if key in data}}
    payload = {'schema': SCHEMA, 'status': 'verified_official_analysis_projection',
               'facts': facts, 'reference': deepcopy(reference), 'selected_fields': _selected(facts),
               'selected_display_fields': _display(facts),
               'original_quote_sha256': _fingerprint(original)}
    payload['sha256'] = _fingerprint(payload)
    result = deepcopy(data)
    result['original_quote_financials'] = original
    result['official_financial_projection'] = payload
    result.update(payload['selected_fields'])
    result.update(payload['selected_display_fields'])
    return result


def read_official_financial_projection(data):
    """Replay originals and check the full selection contract on every read.

    ``facts`` is safe public source content. ``reference`` contains server-only
    receipt paths and must not be sent to a model or rendered for a reader.
    """
    try:
        value = data.get('official_financial_projection')
        original = data.get('original_quote_financials')
        if (not isinstance(value, dict) or value.get('schema') != SCHEMA
                or value.get('status') != 'verified_official_analysis_projection'
                or not isinstance(original, dict) or original.get('schema') != 'preserved-quote-financials:v1'
                or original.get('ticker') != data.get('ticker')
                or original.get('period_status') != 'unverified'
                or original.get('definition_status') != 'unverified'
                or value.get('original_quote_sha256') != _fingerprint(original)):
            return None
        unsigned = {key: item for key, item in value.items() if key != 'sha256'}
        if value.get('sha256') != _fingerprint(unsigned):
            return None
        facts = _replay(data, value.get('reference'))
        if (facts is None or value.get('facts') != facts or value.get('selected_fields') != _selected(facts)
                or value.get('selected_display_fields') != _display(facts)):
            return None
        for key, amount in _selected(facts).items():
            raw = data.get(key)
            if type(raw) not in (int, float) or not math.isfinite(raw) or raw != amount:
                return None
        if any(data.get(key) != display for key, display in _display(facts).items()):
            return None
        return {**deepcopy(value), 'facts': facts}
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return None


def official_fcf_period_statement_matches(text, data):
    """Admit only an explicit same-sentence official FCF amount and exact dates.

    This is a narrow exception to the prose period guard, not the numeric
    evidence gate. Ambiguous ownership, forecasts and other currencies retain
    their previous fail-closed handling.
    """
    checked = read_official_financial_projection(data)
    if checked is None:
        return False
    facts = checked['facts']
    text = re.sub(r'[*`#]', '', text).strip()
    if re.search(r'同業|同儕|合併|預估|預測|假設|若|如果|美元|美金|人民幣|USD|CNY|舊|quote|Yahoo', text, re.I):
        return False
    if '個別' not in text or not re.search(r'TTM|近十二個月|近12個月', text, re.I):
        return False
    dates = re.findall(r'20\d{2}-\d{2}-\d{2}', text)
    if dates != [facts['period_start'], facts['period_end']]:
        return False
    if re.search(r'20\d{2}', re.sub(r'20\d{2}-\d{2}-\d{2}', '', text)):
        return False
    metric = re.search(r'自由現金流|\bFCF\b', text, re.I)
    if metric is None:
        return False
    prefix = text[:metric.start()]
    if not re.search(r'本公司|本標的|大東電|\b1623(?:\.TW)?\b', prefix):
        return False
    # Whitelisting the local subject prevents unknown issuers from borrowing
    # the target's label in the same sentence.
    allowed = (r'大東電業廠股份有限公司|大東電|1623\.TW|1623|本公司|本標的|官方|個別|財報|財務報表|'
               r'TTM|近十二個月|近12個月|依據|根據|資料|顯示|的|為|以|[\s，,：:()（）\[\]。-]')
    if re.sub(allowed, '', prefix, flags=re.I):
        return False
    tail = text[metric.end():]
    match = re.match(r'\s*(?:\(\s*FCF\s*\)|（\s*FCF\s*）)?\s*(?:為|是|約為|約)?\s*'
                     r'(?P<value>[+-]?\d+(?:\.\d+)?)\s*'
                     r'(?P<unit>billion_twd|十億(?:新臺幣|新台幣)?|億(?:元)?|TWD|元)(?![A-Za-z])', tail, re.I)
    if match is None:
        return False
    precision = len(match['value'].partition('.')[2])
    if precision > 20 or len(match['value'].lstrip('+-').partition('.')[0]) > 20:
        return False
    unit = match['unit'].lower()
    scale = Decimal('1000000000') if unit.startswith(('billion', '十億')) else Decimal('100000000') if unit.startswith('億') else Decimal(1)
    amount = Decimal(facts['cashflows']['ttm']['free_cash_flow'])
    reported = Decimal(match['value'])
    rounded = (amount / scale).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    if reported != rounded or not (reported * amount > 0 or reported == amount == 0):
        return False
    # Consume the whole remaining sentence. A valid leading amount cannot
    # qualify foreign units, future language, another issuer or contradictory
    # cash-flow direction in the suffix. Unknown wording stays fail-closed.
    number = r'[+-]?\d+(?:\.\d+)?'
    suffix = re.fullmatch(
        r'\s*(?:[（(]\s*(?P<direction>淨流入|淨流出|金額為零)\s*[）)])?'
        r'\s*[，,]\s*涵蓋\s*' + re.escape(facts['period_start'])
        + r'\s*(?:至|到|～|~|—)\s*' + re.escape(facts['period_end'])
        + r'(?:\s*[，,]\s*期間已核實)?'
        + r'(?:\s*[，,]\s*原始金額\s*(?P<raw>' + number + r')\s*TWD'
        + r'\s*[，,]\s*等於\s*(?P<billion>' + number + r')\s*billion_twd)?'
        + r'\s*[。. ]?\s*', text[metric.end() + match.end():], re.I)
    if suffix is None:
        return False
    direction = suffix['direction']
    if direction is not None and direction != ('淨流入' if amount > 0 else '淨流出' if amount < 0 else '金額為零'):
        return False
    if suffix['raw'] is not None:
        for value in (suffix['raw'], suffix['billion']):
            if len(value.partition('.')[2]) > 20 or len(value.lstrip('+-').partition('.')[0]) > 20:
                return False
        if Decimal(suffix['raw']) != amount or Decimal(suffix['billion']) * Decimal('1000000000') != amount:
            return False
    return True
