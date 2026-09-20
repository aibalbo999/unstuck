"""Explicit metadata types and range checks, separate from financial evidence."""
from __future__ import annotations

from datetime import date
import math
import re

NUMBER_TOKEN = r"[-+]?(?:\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?|[Nn][Aa][Nn]|[Ii][Nn][Ff](?:[Ii][Nn][Ii][Tt][Yy])?)"
_MOAT = {'品牌影響力', '網路效應', '轉換成本', '成本優勢', '專利技術', '整體護城河'}
_OVERHEAT = {'fomo評分', 'fomo過熱評分', 'fomoscore', '聰明錢派發評分', '情緒評分', '情緒過熱評分', '過熱評分'}
_SCALE_RANGE = re.compile(r'[（(]\s*(' + NUMBER_TOKEN + r')\s*(?:-|–|—|~|至)\s*('
                          + NUMBER_TOKEN + r')\s*[)）]\s*$')


def _normalized(label):
    return re.sub(r'[^0-9a-z\u4e00-\u9fff]', '', str(label).lower())


def calendar_metadata_label(label):
    return bool(re.search(r'(?<![A-Za-z0-9_])(?:as_of_date|as_of|data_date|date|資料日期|截至日期)[*_`\s]*$', label, re.I))


def calendar_metadata_match(match):
    """Exclude a valid compact calendar value only under an explicit date key."""
    if match.group('unit') or not calendar_metadata_label(match.group('label')):
        return False
    literal = match.group('num')
    if not re.fullmatch(r'\d{8}', literal):
        return False
    try:
        date(int(literal[:4]), int(literal[4:6]), int(literal[6:]))
        return True
    except ValueError:
        return False


def score_metadata(label, unit, literal, suffix):
    """Known score labels are metadata; currency/count units preserve financial claims."""
    if str(unit or '').lower() not in {'', '%'}:
        return None
    explicit_range = _SCALE_RANGE.search(label)
    type_label = label[:explicit_range.start()] if explicit_range else label
    key = _normalized(type_label)
    terminal = _normalized(re.split(r'[；;（(]', type_label)[-1])
    confidence = bool(re.fullmatch(r'(?:資料)?信心(?:指數|分數|評分)?|(?:data)?confidence(?:score)?', terminal))
    known_analysis = key in _MOAT or key in _OVERHEAT or bool(re.search(r'agent\d+(?:評分|score)$', key))
    if unit == '%' and key in _MOAT:
        return None  # A percentage under a moat dimension can be a financial fact.
    generic_score = bool(re.search(r'(?:評分|score)$', terminal))
    if not (confidence or known_analysis or generic_score):
        return None
    try:
        number = float(literal.replace(',', ''))
    except (ValueError, OverflowError):
        number = math.nan
    denominator = re.match(r'\s*%?\s*[*_`]*\s*/\s*(' + NUMBER_TOKEN + r')', suffix)
    scale = None
    minimum = 1.0 if known_analysis else 0.0
    if explicit_range:
        minimum, scale = (float(value.replace(',', '')) for value in explicit_range.groups())
        basis = 'explicit_label_range'
    elif denominator:
        scale = float(denominator.group(1).replace(',', ''))
        basis = 'explicit_denominator'
    elif unit == '%':
        scale, basis = 100.0, 'explicit_percent'
    elif known_analysis:
        minimum, scale, basis = 1.0, 10.0, 'agent_score_contract_1_10'
    else:
        basis = 'unspecified'
    declared_maxima = []
    if explicit_range:
        declared_maxima.append(scale)
    if denominator:
        declared_maxima.append(float(denominator.group(1).replace(',', '')))
    if unit == '%':
        declared_maxima.append(100.0)
    conflicting_scale = any(not math.isfinite(value) or value != scale for value in declared_maxima)
    if not math.isfinite(number):
        status, reason = 'invalid', 'score_not_finite'
    elif conflicting_scale or (scale is not None and (not math.isfinite(minimum) or not math.isfinite(scale)
                                                     or scale <= 0 or minimum >= scale)):
        status, reason = 'invalid', 'score_scale_invalid'
    elif scale is None:
        status, reason = 'unverifiable', 'score_scale_unspecified'
    elif (known_analysis and (scale != 10 or minimum != 1)) or not (minimum <= number <= scale):
        status, reason = 'invalid', 'score_out_of_range'
    else:
        status, reason = 'valid', 'score_within_declared_range'
    return {'claim_type': 'analysis_score', 'score_kind': 'confidence' if confidence else 'analysis',
            'reported_value': number if math.isfinite(number) else None, 'reported_literal': literal,
            'financial_evidence': False, 'status': status, 'verification_reason_code': reason,
            'scale_min': minimum if math.isfinite(minimum) else None,
            'scale_max': scale if scale is not None and math.isfinite(scale) else None,
            'scale_basis': basis, 'candidate_count': 0, 'matched_path': '', 'matched_value': None, 'diff_pct': None}


def public_metadata_claim(claim):
    return {key: value for key, value in claim.items() if not key.startswith('_') and key not in {
        'context_text', 'technical_context_text', 'series_context_text'}}
