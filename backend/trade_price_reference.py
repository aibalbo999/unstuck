"""Typed price evidence: original quotes and reproducible analysis are distinct."""
import hashlib
import json
import math
import re


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _observation(catalog, ref, role):
    from trade_source_contract import resolve_reference, reference_is_evidence
    if not reference_is_evidence(catalog, ref, role):
        return None
    value = resolve_reference(catalog, ref)
    root = _mapping(catalog.get('short_term_market_context'))
    if not _number(value):
        return None  # A whole bar is not an unambiguous price quotation.
    if '.daily_market_data.bars[' in ref:
        bar = _mapping(resolve_reference(catalog, ref.rsplit('.', 1)[0]))
        source = _mapping(root.get('daily_market_data'))
        date, window = bar.get('date'), 1
    elif '.technical_indicators.' in ref:
        source = _mapping(root.get('technical_indicators'))
        field = ref.rsplit('.', 1)[-1]
        period = re.fullmatch(r'(?:sma|ema|atr)_(\d+)|(?:high|low)_(\d+)d', field)
        date = source.get('as_of')
        window = int(next(v for v in period.groups() if v)) if period else None
    else:
        return None
    return {'ref': ref, 'value': value, 'observed_date': date,
            'window_sessions': window, 'price_basis': source.get('price_adjustment_basis'),
            'source': source.get('source')}


_YFINANCE_ADJ_CLOSE_BASIS = "yfinance adjusted OHLC = raw provider OHLC * (Adj Close / Close); equivalent auto_adjust=True basis;not exchange raw"


def _equivalent_close_basis(declared, observation):
    """Interpret a close-only alias using explicit, captured provider semantics.

    The raw descriptive basis remains intact. This is not an alias for raw
    prices, split-only adjustments, generic adjusted series or high/low/ATR.
    """
    ref = str(observation.get('ref') or '')
    close_only = bool(re.fullmatch(
        r'short_term_market_context\.(?:technical_indicators\.(?:sma|ema)_\d+|daily_market_data\.bars\[\d+\]\.close)', ref))
    return (declared == 'adjusted_close' and close_only
            and observation.get('source') == 'yfinance 5y history'
            and observation.get('price_basis') == _YFINANCE_ADJ_CLOSE_BASIS)


def price_reference_checks(payload, catalog):
    """Never invent a level, source date, period, basis, or analytical formula."""
    if not isinstance(payload, dict) or not isinstance(catalog, dict):
        return []
    evidence = payload.get('price_level_evidence')
    explicit = isinstance(evidence, list)
    checks = []
    for field, role in (('support_level', 'support_source_refs'), ('resistance_level', 'resistance_source_refs')):
        text = str(payload.get(field) or '').strip().replace(',', '')
        if text.upper() in {'', 'N/A', 'NA', '資料不足'}:
            continue
        scalar = re.fullmatch(r'\d+(?:\.\d+)?', text)
        refs = payload.get(role)
        refs = refs if isinstance(refs, list) else []
        observations = [_observation(catalog, ref, role) for ref in refs]
        matching = [item for item in evidence if isinstance(item, dict) and item.get('field') == field] if explicit else []
        definition = matching[0] if len(matching) == 1 else None
        kind = definition.get('kind') if definition else 'legacy_direct_reference'
        result = {'field': field, 'kind': kind, 'status': 'unverifiable', 'reason_codes': [],
                  'claimed_text': text, 'source_observations': [o for o in observations if o]}
        reasons = result['reason_codes']
        if not scalar:
            reasons.append(field + '_source_scalar_unverified')
        elif not refs or any(o is None for o in observations):
            reasons.append(field + '_source_observation_unverified')
        elif explicit and len(matching) != 1:
            reasons.append(field + '_source_claim_type_missing')
        else:
            values = [o['value'] for o in observations]
            expected = values
            if definition:
                metadata = definition.get('inputs')
                metadata = metadata if isinstance(metadata, list) else []
                if [m.get('ref') for m in metadata if isinstance(m, dict)] != refs:
                    reasons.append(field + '_source_input_refs_mismatch')
                for source, claim in zip(observations, metadata):
                    if not isinstance(claim, dict):
                        reasons.append(field + '_source_metadata_unverified')
                        continue
                    for key, label in (('observed_date', 'date'), ('window_sessions', 'period'), ('price_basis', 'scope')):
                        declared = claim.get(key)
                        if declared is None:
                            continue  # Missing metadata is not a proven contradiction.
                        if source.get(key) is None:
                            reasons.append(field + '_source_' + label + '_unverified')
                        elif declared != source[key]:
                            if key == 'price_basis' and _equivalent_close_basis(declared, source):
                                result.setdefault('basis_normalizations', []).append({
                                    'ref': source['ref'], 'declared_basis': declared,
                                    'source_basis': source[key],
                                    'canonical_basis': 'yfinance_adj_close_factor_close',
                                    'source': source['source'],
                                    'scope': 'close-only provider adjustment equivalence;not exchange raw or execution approval'})
                            elif key == 'price_basis' and declared == 'adjusted_close' and (source[key] in {'unknown', 'unavailable', 'adjusted', 'adjusted_close'} or (source[key] == _YFINANCE_ADJ_CLOSE_BASIS and source.get('source') != 'yfinance 5y history')):
                                reasons.append(field + '_source_scope_unverified')
                            else:
                                reasons.append(field + '_source_' + label + '_mismatch')
                operation = definition.get('operation')
                if kind == 'direct_reference':
                    if operation != 'identity' or len(values) != 1:
                        reasons.append(field + '_source_derivation_unverified')
                elif kind == 'derived':
                    bases = [source.get('price_basis') for source in observations]
                    if not all(bases) or len(set(bases)) != 1:
                        reasons.append(field + '_source_derivation_scope_unverified')
                    if operation == 'min': expected = [min(values)]
                    elif operation == 'max': expected = [max(values)]
                    elif operation == 'mean': expected = [sum(values) / len(values)]
                    else: reasons.append(field + '_source_derivation_unverified')
                else:
                    reasons.append(field + '_source_claim_type_missing')
            # Match the precision actually displayed, with only rounding tolerance.
            decimals = len(text.split('.')[1]) if '.' in text else 0
            tolerance = 0.5 * 10 ** -decimals + 1e-9
            if not any(abs(float(text) - value) <= tolerance for value in expected):
                if not any('unverified' in reason or 'type_missing' in reason for reason in reasons):
                    reasons.append(field + '_source_value_mismatch')
            result['status'] = 'mismatch' if any(reason.endswith('_mismatch') for reason in reasons) else 'unverifiable' if reasons else 'verified'
        result['reason_codes'] = list(dict.fromkeys(reasons))
        checks.append(result)
    return checks


def price_reference_issues(payload, catalog):
    return [reason for check in price_reference_checks(payload, catalog)
            for reason in check['reason_codes']]


def snapshot_price_reference_checks(snapshot):
    """Captured, fingerprint-bound catalog only; never reinterpret old bar indices."""
    snapshot = _mapping(snapshot)
    context = _mapping(snapshot.get('rerun_context'))
    outputs = _mapping(context.get('structured_outputs'))
    payload = outputs.get('24', outputs.get(24))
    if not isinstance(payload, dict):
        payload = _mapping(context.get('parsed')).get('trade_setup')
    evidence = _mapping(snapshot.get('analysis_evidence'))
    section = _mapping(_mapping(evidence.get('sections')).get('trade_source_manifest'))
    manifest = _mapping(section.get('data'))
    catalog = manifest.get('catalog')
    if not isinstance(payload, dict):
        return []
    def unknown_lineage():
        return [{'field':field, 'kind':'unknown', 'status':'unverifiable', 'reason_codes':[field+'_source_lineage_unverified'], 'claimed_text':str(payload[field]), 'source_observations':[]}
                for field in ('support_level','resistance_level') if str(payload.get(field) or '').strip().upper() not in {'','N/A','NA','資料不足'}]
    if not manifest.get('visible') or not isinstance(catalog, dict):
        return unknown_lineage()
    try:
        digest = hashlib.sha256(json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError):
        return unknown_lineage()
    if digest != manifest.get('fingerprint') or digest != _mapping(payload.get('source_assessment')).get('source_fingerprint'):
        return unknown_lineage()  # Unknown lineage cannot prove a contradiction.
    return price_reference_checks(payload, catalog)


def snapshot_price_reference_issues(snapshot):
    return [reason for check in snapshot_price_reference_checks(snapshot)
            if check['status'] == 'mismatch' for reason in check['reason_codes'] if reason.endswith('_mismatch')]
