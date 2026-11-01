"""Consume exact native fact captions without granting financial evidence."""
import re

_CAPTIONS = {
    '具體佐證': ('淨利', '稅後淨利', '自由現金流', 'FCF'),
    '淨利': ('淨利', '稅後淨利'),
    '獲利事實': ('淨利', '稅後淨利'),
    '自由現金流': ('自由現金流', 'FCF'),
    '現金流事實': ('自由現金流', 'FCF'),
    **{name: (name,) for name in (
        '存貨變動現金影響', '應收帳款變動現金影響',
        '營業資產淨變動現金影響', '營業負債淨變動現金影響',
        '營業資產及負債淨變動現金影響')},
}

def check_captioned_fact(claim, data, tolerance_pct):
    """Recheck one unchanged full dated fact with every ancestor retained."""
    if (claim.get('financial_actual') is False or claim.get('financial_scope_unbound')
            or claim.get('foreign_currency_declared') or claim.get('unit') != '億元'):
        return None
    raw = re.sub(r'[*`]', '', str(claim.get('raw_text') or ''))
    caption = re.fullmatch(
        r'\s*[-*]?\s*(?P<label>(?:官方\s*TTM\s*(?:'
        + '|'.join(map(re.escape, _CAPTIONS)) + r')|具體佐證))\s*[:：]\s*(?P<fact>[^\n]{1,2048})\s*', raw)
    if caption is None:
        return None
    label = re.sub(r'^官方\s*TTM\s*', '', caption['label'])
    if claim.get('financial_metric') not in _CAPTIONS[label]:
        return None
    fact = caption['fact']
    number = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    if re.fullmatch(
            r'(?:大東電業廠股份有限公司|大東電|1623(?:\.TW)?)\s*官方\s*個別\s*財報\s*'
            r'(?:TWD|NTD|新[臺台]幣)\s*TTM\s*[（(]\s*20\d{2}-\d{2}-\d{2}\s*至\s*'
            r'20\d{2}-\d{2}-\d{2}\s*[）)]\s*'
            + re.escape(claim['financial_metric']) + r'\s*為\s*' + number + r'\s*億元[。.]?\s*', fact) is None:
        return None
    from evidence_financial_amounts import extract_financial_amounts, check_financial_amount
    extracted = extract_financial_amounts(fact, [])
    if len(extracted) != 1:
        return None
    local = extracted[0]
    if any(local.get(key) != claim.get(key) for key in ('financial_metric', 'unit', 'reported_value')):
        return None
    for key in ('financial_heading', 'financial_parent_context', '_financial_heading_ancestors'):
        if key in claim:
            local[key] = claim[key]
    checked = check_financial_amount(local, {'data': data}, tolerance_pct)
    if checked is None:
        return None
    checked = {key: value for key, value in checked.items() if key not in local}
    resolution = dict(checked.get('financial_narrative_resolution') or {})
    resolution.setdefault('contract', 'explicit-official-fact-caption:v1')
    resolution.update(original_claim_unchanged=True, structural_label_consumed=label)
    return {**checked, 'financial_narrative_resolution': resolution,
            'official_fact_caption_resolution': {
        'caption': label, 'original_claim_unchanged': True,
        'verification_delegated_to_native_gate': True,
        'all_ancestor_scopes_retained': True, 'new_source_acquisition': False}}
