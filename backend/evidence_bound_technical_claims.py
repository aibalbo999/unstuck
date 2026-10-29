"""Exact saved-window arithmetic, never exchange truth, PIT, or model plans."""
from datetime import date, datetime, timezone
import math
import re

from evidence_claim_types import public_metadata_claim
from evidence_exit_gate_claims import best_match

FIELDS = frozenset({'rsi_14', 'volume_ratio_20', 'macd', 'macd_signal', 'macd_histogram'})
DELTAS = frozenset({'signed_delta', 'magnitude_delta'})
MACD = frozenset({'macd', 'macd_signal', 'macd_histogram'})
ROOT = 'short_term_market_context.technical_indicators'
KEY = r'macd_histogram|macd_signal|magnitude_delta|volume_ratio_20|signed_delta|rsi_14|macd'
PAIR = re.compile(r'(?<![A-Za-z0-9_])(?P<key>' + KEY + r')\s*[:：=]\s*'
                  r'(?P<number>[-+]?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>元|TWD|%|股|張)?'
                  r'(?=$|[\s,，、。;；()（）])', re.I)
DAY = re.compile(r'(?<!\d)20\d{2}-\d{2}-\d{2}(?!\d)')
PARTIAL_DAY = re.compile(r'(?<![\d-])(?:0?[1-9]|1[0-2])[-/月](?:0?[1-9]|[12]\d|3[01])日?(?![\d-])')
REF = re.compile(r'source\s+ref\s*=\s*([A-Za-z0-9_.\[\]]+)', re.I)
WRONG_BASIS = re.compile(r'新聞|券商|研究|預估|預測|假設|如果|若|情境|目標|forecast|hypothetical|factset|news|research|broker|projected|prediction|future', re.I)
PLAN_LABEL = re.compile(r'支撐|壓力|停損|目標|support|resistance|stop.loss|前日|昨日|previous|yesterday', re.I)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def prepare_bound_technical(snapshot):
    """Only a complete original receipt can admit a new semantic path."""
    try:
        outputs = snapshot.get('rerun_context', {}).get('structured_outputs', {})
        role = outputs.get('24', outputs.get(24, {}))
        if not role.get('source_assessment', {}).get('source_fingerprint'):
            return None
        from report_analysis_evidence import validate_analysis_evidence, _digest
        from saved_trade_source_identity import saved_trade_source_catalog
        from market_session_admission import assess_daily_session_integrity
        from short_term_technical_indicators import calculate_technical_indicators
        packet = validate_analysis_evidence(snapshot.get('analysis_evidence'))
        if packet.get('input_verification') != 'hash_verified' or packet.get('capture_boundary') not in {'analysis_start', 'report_render'}:
            return None
        catalog, receipt = saved_trade_source_catalog(snapshot)
        if receipt.get('status') != 'bound_saved_catalog':
            return None
        data = packet['sections']['analysis_input']['data']
        section = packet['sections']['analysis_input']
        if (packet['capture_boundary'] == 'report_render'
                and packet.get('frozen_market_input_fingerprint') != section.get('fingerprint')):
            return None
        original_hash = packet.get('analysis_input_hash')
        cutoff = datetime.fromisoformat(str(packet.get('analysis_input_cutoff', '')).replace('Z', '+00:00'))
        if (not isinstance(original_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', original_hash)
                or data.get('analysis_input_hash') != original_hash
                or data.get('analysis_input_cutoff') != packet.get('analysis_input_cutoff')
                or cutoff.tzinfo is None or cutoff > datetime.now(timezone.utc)
                or _digest({k: v for k, v in data.items() if k not in {'analysis_input_hash', 'analysis_input_cutoff'}}) != original_hash):
            return None
        if data.get('currency') != 'TWD' or data.get('financial_currency') != 'TWD':
            return None
        ticker = data['ticker']
        if not re.fullmatch(r'[0-9]{4,6}\.TW(?:O)?', ticker):
            return None
        daily, technical = data['daily_market_data'], data['technical_indicators']
        bound = catalog['short_term_market_context']['technical_indicators']
        if technical != bound or daily.get('source') != technical.get('source') or daily.get('as_of') != technical.get('as_of'):
            return None
        source, basis = daily.get('source'), daily.get('price_adjustment_basis')
        if (not isinstance(source, str) or source.lower() in {'', 'unknown', 'unavailable', 'n/a'}
                or not isinstance(basis, str) or basis.lower() in {'', 'unknown', 'unavailable'}
                or basis != technical.get('price_adjustment_basis') or daily.get('volume_unit') != 'shares'
                or daily.get('volume_basis') != technical.get('volume_basis')):
            return None
        bars = daily['bars']
        if not isinstance(bars, list) or not 35 <= len(bars) <= 120:
            return None
        if (bars[-1].get('date') != daily['as_of']
                or date.fromisoformat(daily['as_of']) > date.fromisoformat(receipt['catalog_as_of'])):
            return None
        for bar in bars:
            if (not all(_finite(bar.get(k)) for k in ('close', 'high', 'low', 'volume'))
                    or not 0 < bar['low'] <= bar['close'] <= bar['high'] or bar['volume'] < 0):
                return None
        admission = assess_daily_session_integrity(daily, ticker=ticker)
        if admission.get('eligible') is not True:
            return None
        calculated = calculate_technical_indicators(daily)
        if (technical.get('input_window') != calculated['input_window']
                or technical.get('calculation_policy') != calculated['calculation_policy']
                or technical.get('sample_count') != len(bars)):
            return None
        for key in FIELDS:
            if not _finite(technical.get(key)) or not _finite(calculated.get(key)) or abs(technical[key] - calculated[key]) > 1e-7:
                return None
        if not 0 <= calculated['rsi_14'] <= 100 or calculated['volume_ratio_20'] < 0:
            return None
        comparison = calculated.get('macd_histogram_comparison')
        if (not isinstance(comparison, dict) or technical.get('macd_histogram_comparison') != comparison
                or comparison['observed_date'] != daily['as_of'] or comparison['previous_date'] != bars[-2]['date']
                or comparison['input_bars_sha256'] != calculated['input_window']['bars_sha256']):
            return None
        return {'ticker': ticker, 'calculated': calculated, 'comparison': comparison,
                'as_of': daily['as_of'], 'previous_date': comparison['previous_date'],
                'catalog_fingerprint': receipt['catalog_fingerprint'],
                'bars_sha256': calculated['input_window']['bars_sha256']}
    except Exception:
        return None


def _field(label):
    if not isinstance(label, str) or PLAN_LABEL.search(label):
        return None
    for key in sorted(FIELDS | DELTAS, key=len, reverse=True):
        literal = key.replace('_', '_?')
        if re.search(r'(?<![A-Za-z0-9_])' + literal + r'\s*$', label, re.I):
            return key
    return None


def _nearest_date(text, position):
    days = list(DAY.finditer(text[:position]))
    return days[-1].group() if days else None


def _reference(text, pair, field, prepared):
    """The next reference in the same sentence must own this exact assignment."""
    end = re.search(r'[。；;\n]', text[pair.end():])
    stop = pair.end() + end.start() if end else len(text)
    reference = REF.search(text, pair.end(), stop)
    if reference is None:
        return False
    path = reference.group(1)
    between = list(PAIR.finditer(text, pair.end(), reference.start()))
    if field in DELTAS:
        return path == ROOT + '.macd_histogram_comparison' and all(m['key'].lower() in DELTAS for m in between)
    if path == ROOT + '.' + field:
        return not between
    if field in MACD and path == ROOT:
        return all(m['key'].lower() in MACD and _nearest_date(text, m.start()) == prepared['as_of'] for m in between)
    return False


def check_bound_technical_claim(claim, prepared, *, tolerance_pct):
    """Called only after the existing checker reports missing_semantic_path."""
    if not prepared or claim.get('scenario_projection'):
        return None
    key = _field(claim.get('label'))
    if key is None:
        return None
    text = re.sub(r'[*`]', '', str(claim.get('technical_context_text') or claim.get('raw_text') or ''))
    if len(text) > 16000 or WRONG_BASIS.search(text):
        return None
    explicit_tickers = re.findall(r'(?<![A-Za-z0-9])[0-9]{4,6}\.TW(?:O)?(?![A-Za-z0-9])', text, re.I)
    if any(ticker.upper() != prepared['ticker'] for ticker in explicit_tickers):
        return None
    codes = re.findall(r'(?:股票代號|證券代號|公司代號|ticker|stock_id)\s*[:：=]?\s*([0-9]{4,6})(?![0-9])', text, re.I)
    if any(code != prepared['ticker'].split('.')[0] for code in codes):
        return None
    days = list(DAY.finditer(text))
    if (not days or days[0].group() != prepared['as_of']
            or any(m.group() not in {prepared['as_of'], prepared['previous_date']} for m in days)):
        return None
    for day in days:
        if day.group() == prepared['previous_date'] and not re.search(r'前日|昨日|previous|yesterday', text[max(0, day.start()-24):day.start()], re.I):
            return None
    pairs = [m for m in PAIR.finditer(text) if m['key'].lower() == key]
    if key in DELTAS:
        if {m.group() for m in days} != {prepared['as_of'], prepared['previous_date']}:
            return None
    else:
        pairs = [m for m in pairs if _nearest_date(text, m.start()) == prepared['as_of']]
    if len(pairs) != 1:
        return None
    pair = pairs[0]
    start = max((text.rfind(c, 0, pair.start()) for c in '。；;\n'), default=-1) + 1
    end = re.search(r'[。；;\n]', text[pair.end():])
    clause = text[start:pair.end() + end.start()] if end else text[start:]
    if PARTIAL_DAY.search(DAY.sub(' ', clause)):
        return None
    unit = str(claim.get('unit') or '').lower()
    allowed_units = {''} if key in {'rsi_14', 'volume_ratio_20'} else {'', '元', 'twd'}
    if unit not in allowed_units or str(pair['unit'] or '').lower() not in allowed_units:
        return None
    reported = claim.get('reported_value')
    if not _finite(reported) or float(pair['number'].replace(',', '')) != reported or not _reference(text, pair, key, prepared):
        return None
    expected = prepared['comparison'][key] if key in DELTAS else prepared['calculated'][key]
    suffix = 'macd_histogram_comparison.' + key if key in DELTAS else key
    path = 'analysis_evidence.sections.analysis_input.data.technical_indicators.' + suffix
    matched = best_match(float(reported), [{'path': path, 'value': float(expected)}])
    status = 'verified' if matched['diff_pct'] <= tolerance_pct else 'mismatch'
    return {**public_metadata_claim(claim), 'status': status,
            'verification_reason_code': 'matched_frozen_technical_arithmetic' if status == 'verified' else 'frozen_technical_arithmetic_mismatch',
            'verification_scope': 'saved_window_arithmetic', 'candidate_count': 1,
            'matched_path': path, 'matched_value': float(expected), 'diff_pct': round(matched['diff_pct'], 4),
            'observed_date': prepared['as_of'],
            **({'previous_date': prepared['previous_date']} if key in DELTAS else {}),
            'bars_sha256': prepared['bars_sha256'], 'catalog_fingerprint': prepared['catalog_fingerprint'],
            'independent_primary_source_verified': False, 'historical_point_in_time_verified': False}
