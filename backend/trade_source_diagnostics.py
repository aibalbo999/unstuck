"""Response-bound source rejection detail; does not change admission or fill refs."""
import hashlib
import json
import re

from trade_source_guidance import canonical_catalog, source_guidance_text


def _preview(value, depth=0):
    """A diagnostic preview, never a replacement for the full visible catalog."""
    if depth >= 3:
        return {'preview_omitted': True}
    if isinstance(value, str):
        return value[:600]
    if isinstance(value, list):
        return {'type': 'list', 'length': len(value), 'preview_omitted': True}
    if isinstance(value, dict):
        keys = ('path', 'value', 'unit', 'population', 'window', 'kind', 'trading_days',
                'date', 'observed_at', 'provider', 'source_ref', 'title', 'published_at',
                'high', 'low', 'close', 'threshold', 'source', 'label')
        return {k: _preview(value[k], depth + 1) for k in keys if k in value}
    return value


def candidate_fingerprint(output):
    from trade_source_contract import TEXT_FIELDS, REF_FIELDS
    fields = {k: output.get(k) for k in (*TEXT_FIELDS, *REF_FIELDS, 'transaction_cost')}
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_rejection_diagnostics(payload, manifest, reasons, normalized_input):
    from trade_source_contract import REF_FIELDS, reference_is_evidence, resolve_reference
    from institutional_evidence import institutional_evidence_diagnostics
    from trade_catalog_evidence import institutional_catalyst_has_numeric_claim, news_catalyst_supported
    from trade_catalyst_claims import catalyst_observation_text

    from structured_output_normalizer import normalize_structured_output
    catalog = manifest.get('catalog', {})
    text = str(payload.get('core_catalyst') or '')
    observation = catalyst_observation_text(text)
    refs = {key: [ref[:256] for ref in payload.get(key, [])[:8] if isinstance(ref, str)]
            if isinstance(payload.get(key), list) else [] for key in REF_FIELDS}
    fields = []
    for role, values in refs.items():
        for ref in values:
            source = resolve_reference(catalog, ref)
            fields.append({'field': role, 'ref': ref,
                           'admissible_for_field': bool(manifest.get('visible')) and reference_is_evidence(catalog, ref, role),
                           'catalog_value': _preview(source)})
    canonical = canonical_catalog(catalog)
    claim_refs = [r for r in refs['catalyst_source_refs'] if '.institutional_evidence.records[' in r]
    claims = institutional_evidence_diagnostics(observation, canonical, allowed_paths=claim_refs)[:6]
    for claim in claims:
        claim['context'] = claim.get('context', '')[-400:]
        claim['claim'] = claim.get('claim', '')[:300]
        for key in ('same_scope_sources', 'available_population_sources'):
            claim[key] = [_preview(r) for r in claim.get(key, [])[:4]]
    # Descriptive sub-reasons only; the existing gate remains the sole admission rule.
    scope = []
    if 'catalyst_evidence_scope_mismatch' in reasons:
        if re.search(r'連續|持續|逐日|加速|趨勢|轉買|轉賣', observation):
            scope.append('continuous_trend_not_established')
        if not institutional_catalyst_has_numeric_claim(observation):
            scope.append('each_population_requires_own_numeric_period_claim')
        scope.append('every_flow_or_ownership_assertion_requires_matching_typed_record')
    news = []
    for ref in refs['catalyst_source_refs']:
        if '.recent_news.items[' not in ref:
            continue
        record = resolve_reference(catalog, ref)
        if isinstance(record, dict) and not news_catalyst_supported(text, [record]):
            news.append({'ref': ref, 'expected_literal_title': str(record.get('title') or '')[:600],
                         'published_at': record.get('published_at'),
                         'requirement': 'literal_attributed_title_not_future_scheduled_event'})
    return {'version': 'trade-source-rejection:v1', 'source_fingerprint': manifest.get('fingerprint'),
            'normalized_candidate_sha256': candidate_fingerprint(normalize_structured_output(24, normalized_input)),
            'candidate_sha256': hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            'original_core_catalyst': text[:1200], 'core_catalyst_truncated': len(text) > 1200,
            'original_refs': refs, 'refs_truncated': any(isinstance(payload.get(k), list) and
                (len(payload[k]) > 8 or any(isinstance(r, str) and len(r) > 256 for r in payload[k])) for k in REF_FIELDS),
            'reasons': list(dict.fromkeys(reasons)), 'reference_checks': fields,
            'scope_requirements': scope, 'institutional_claims': claims, 'news_claims': news}


def source_repair_feedback(assessment, manifest, output=None):
    receipt = assessment.get('rejection_diagnostics')
    detail = ''
    if (isinstance(receipt, dict) and receipt.get('version') == 'trade-source-rejection:v1'
            and receipt.get('source_fingerprint') and receipt.get('source_fingerprint') == manifest.get('fingerprint')
            and isinstance(output, dict) and receipt.get('normalized_candidate_sha256') == candidate_fingerprint(output)):
        detail = ('\n【原候選來源退件診斷；不代表任何主張已獲採用】\n'
                  'original_refs 是清空前的原引用；catalog_value 是該路徑原值，不是替代答案。'
                  'available_population_sources 是可用範圍，不可按相似數字更换主體/期間。'
                  '先修正每一個越界主張，再由完整 gate 重新判定。\n'
                  + json.dumps(receipt, ensure_ascii=False, separators=(',', ':')))
    return detail + source_guidance_text(manifest.get('catalog', {}))
