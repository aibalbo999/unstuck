"""Server-owned arithmetic for frozen scalars, never certification of a period."""
from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal, ROUND_HALF_UP

POLICY = 'financial-fact-binding:v1-frozen-scalar-period-unverified'
FIELDS = ('net_income_ttm_raw', 'free_cash_flow_raw')


def debt_ratio_basis(data=None):
    """A quote ratio alone cannot establish its numerator or balance date.

    Official supplemental balance facts have a separate replay contract. Do
    not infer this scalar's definition from matching digits or annual equity.
    """
    from official_financial_projection import read_official_financial_projection
    selected = read_official_financial_projection(data) if isinstance(data, dict) else None
    if selected:
        facts = selected['facts']
        return {
            'source_path': 'data.official_financial_projection.facts.ratios.debt_including_leases_to_equity_pct',
            'definition_status': 'verified', 'period_status': 'verified',
            'numerator_twd': facts['balance']['interest_bearing_debt_including_leases'],
            'denominator_twd': facts['balance']['equity'], 'period_end': facts['balance']['as_of'],
            'value_pct': facts['ratios']['debt_including_leases_to_equity_pct'],
            'ratios': facts['ratios'], 'ratio_definitions': facts['ratio_definitions'],
            'debt_components': facts['debt_components'], 'report_scope': facts['report_scope'],
            'source_url': facts['source_url'], 'acquired_at': facts['acquired_at'],
            'raw_scalar_definition_verified': False, 'raw_scalar_period_verified': False,
            'historical_pit_verified': False,
            'reason': '此為另列官方個別財報同日借款含租賃／權益比率；'
                      '總負債／權益另有獨立定義與數值，不認證原 quote 比率的期間或定義。',
        }
    return {
        'source_path': 'data.debt_to_equity',
        'definition_status': 'unverified', 'period_status': 'unverified',
        'numerator_twd': None, 'denominator_twd': None, 'period_end': None,
        'reason': '來源比率未附同期間分子、分母與計算定義；不得自行解釋成總負債／股東權益，'
                  '也不能拿不同期間的有息負債、總負債或權益倒推口徑。',
    }


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def financial_basis(data):
    currency = str(dict.get(data, 'financial_currency') or '').upper()
    facts = {}
    for field in FIELDS:
        raw = dict.get(data, field)
        try:
            valid = type(raw) in (int, float) and math.isfinite(raw)
        except OverflowError:
            valid = False
        amount = Decimal(str(raw)) if valid and currency in {'TWD', 'NTD'} else None
        facts[field] = {
            'source_path': 'data.' + field, 'currency': currency,
            'amount_twd': format(amount, 'f') if amount is not None else None,
            'amount_billion_twd': format(amount / Decimal('1000000000'), 'f') if amount is not None else None,
            'amount_yi_twd': format(amount / Decimal('100000000'), 'f') if amount is not None else None,
            'value_status': 'available' if amount is not None else 'unavailable',
            'missing_reason': (None if amount is not None else
                'financial_currency_unverified' if valid else 'raw_amount_missing_or_invalid'),
            # These two scalars have no replayed period contract. A dated annual
            # filing, quote time or matching time series must not date them.
            'period_status': 'unverified', 'period_start': None, 'period_end': None,
            'source_period_label': 'TTM' if field == 'net_income_ttm_raw' else None,
            'period_reason': 'raw_scalar_has_no_verified_period_binding',
        }
    from official_financial_projection import read_official_financial_projection
    selected = read_official_financial_projection(data)
    if selected:
        source = selected['facts']
        facts['free_cash_flow_raw'].update({
            'source_path': 'data.official_financial_projection.facts.cashflows.ttm.free_cash_flow',
            'selected_input_path': 'data.free_cash_flow_raw',
            'period_status': 'verified', 'period_start': source['period_start'], 'period_end': source['period_end'],
            'source_period_label': 'TTM', 'period_reason': 'strict_replayed_official_individual_ttm',
            'report_scope': source['report_scope'], 'definition': source['free_cash_flow_definition'],
            'ttm_formula': source['ttm_formula'], 'source_url': source['source_url'],
            'acquired_at': source['acquired_at'], 'raw_scalar_period_verified': False,
            'historical_pit_verified': False,
        })
    result = {'policy': POLICY, 'ticker': dict.get(data, 'ticker'),
              'analysis_input_hash': dict.get(data, 'analysis_input_hash'),
              'analysis_input_cutoff': dict.get(data, 'analysis_input_cutoff'), 'facts': facts}
    return {**result, 'sha256': fingerprint(result)}


def basis_text(basis):
    lines = ['## 財務數值與期間']
    for field, fact in basis['facts'].items():
        label = 'TTM 稅後淨利' if field == 'net_income_ttm_raw' else '即期自由現金流'
        if fact['amount_twd'] is None:
            reason = ('財報幣別未確認，不能換算新臺幣' if fact['missing_reason'] == 'financial_currency_unverified'
                      else '來源未提供有效的原始金額')
            missing_label = 'TTM 淨利' if field == 'net_income_ttm_raw' else label
            lines.append(f'- {missing_label}無法確認：{reason}；不填零或沿用年度值。')
            continue
        amount = Decimal(fact['amount_twd'])
        direction = ('淨損' if amount < 0 else '淨利') if field == 'net_income_ttm_raw' else ('淨流出' if amount < 0 else '淨流入')
        if amount == 0:
            direction = '金額為零'
        if fact.get('period_status') == 'verified':
            lines.append(f"- 本公司官方個別財報 TTM 自由現金流為 {fact['amount_yi_twd']} 億元（{direction}），"
                         f"涵蓋 {fact['period_start']} 至 {fact['period_end']}，"
                         f"原始金額 {fact['amount_twd']} TWD，等於 {fact['amount_billion_twd']} billion_twd。")
            lines.append('- 定義：' + fact['definition'] + '。此為新分析選用的官方來源，原 quote 另存且期間仍未核實；不證明歷史可得性。')
            continue
        lines.append(f"- {label}為 {fact['amount_yi_twd']} 億元（{direction}）；"
                     f"原始金額 {fact['amount_twd']} TWD，等於 {fact['amount_billion_twd']} billion_twd。")
        label_note = '來源標記為TTM' if fact['source_period_label'] else '來源為即期欄位，未確認是否涵蓋近十二個月'
        lines.append(f'- 此為保存輸入的算術換算。{label_note}，起訖期間尚未核實；'
                     '不等同官方年度財報，也不能由抓取日期推定涵蓋期間。')
    return '\n'.join(lines)


def financial_reference_prompt(data):
    basis = financial_basis(data)
    return '\n'.join((
        ('【分析選用財務金額與來源資格】' if any(f['period_status'] == 'verified' for f in basis['facts'].values())
         else '【凍結輸入金額換算參考，非新增財報證據】'),
        basis_text(basis),
        '1 billion_twd = 10 億元。若在正文引用，只使用上述同一欄位的金額、正負號及期間資格；'
        '年度、預估、同業、每股數字不可代替。財務數值與期間由系統另附固定說明，'
        '不必逐字重抄；自行敘述的矛盾仍會攔截，不會被固定說明蓋過。',
    ))


def period_assertion_issues(text, data=None):
    """Reject affirmative certification, not absence of one preferred disclaimer."""
    issues = []
    previous_scope = heading_scope = None
    def subject_scope(prefix):
        if re.search(r'同業|同儕', prefix) and not re.search(r'本公司|本標的', prefix):
            return 'other'
        if not re.search(r'TTM', prefix, re.I) and re.search(
                r'年度|20\d{2}\s*年\s*(?:自由現金流|FCF)', prefix, re.I):
            return 'annual'
        scopes = list(re.finditer(r'TTM|起訖|自由現金流|\bFCF\b|年度', prefix, re.I))
        return ('annual' if scopes[-1][0] == '年度' else 'current') if scopes else None

    for sentence in re.split(r'[。；;\n]', text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if sentence.startswith('#'):
            heading_scope = subject_scope(sentence)
        scope = subject_scope(sentence)
        for match in re.finditer(
                r'(?:已(?:經)?|確認為|確定為).{0,16}?(?:核實|核驗|確認|驗證)'
                r'|(?:涵蓋|起訖|期間|截至|covers|period).{0,12}?20\d{2}', sentence, re.I):
            before = sentence[:match.start()]
            claim_scope = subject_scope(before)
            if claim_scope is None and re.fullmatch(r'(?:其|該|此)?(?:的)?\s*', before):
                claim_scope = previous_scope or heading_scope
            if claim_scope != 'current':
                continue
            # Commas end negation scope: "金額未變，涵蓋..." asserts a period.
            prefix = re.split(r'[，,]', before)[-1][-16:]
            if re.search(r'(?:未|不|無法|不能|不得|不可|尚待|若|假設|如果).{0,8}$', prefix):
                continue
            if (not re.search(r'20\d{2}', match[0])
                    and re.search(r'換算|算術|金額', prefix)
                    and not re.search(r'起訖|期間|涵蓋', prefix)):
                continue
            if isinstance(data, dict):
                from official_financial_projection import official_fcf_period_statement_matches
                if official_fcf_period_statement_matches(sentence, data):
                    continue
            issues.append('unsupported_ttm_period_certification')
        previous_scope = scope
    return list(dict.fromkeys(issues))


def scalar_claim_issues(text, data, *, require_available=True):
    """Bind current scalar assertions by local owner and period, before rendering.

    This complements the annual/source checker, which deliberately leaves an
    undated or wrong-currency value unverifiable. A generated current-scalar
    assertion must not turn that unknown result into permission to publish it.
    """
    from evidence_financial_amounts import extract_financial_amounts
    from financial_money_claims import _PERIOD, _SCALES, _target_revenue_scope, financial_period_scope
    from output_sanitizer import strip_generated_audit_sections
    from source_content_selection import company_aliases
    facts = financial_basis(data)['facts']
    aliases = ['本公司', '本標的', '本集團', *company_aliases(data)]
    issues = []
    for claim in extract_financial_amounts(strip_generated_audit_sections(text), []):
        if not claim.get('financial_actual', True) or claim.get('foreign_currency_declared'):
            continue
        metric = claim['financial_metric']
        field = ('free_cash_flow_raw' if metric in {'FCF', '自由現金流'} else
                 'net_income_ttm_raw' if metric in {'淨利', '稅後淨利'} else None)
        if field is None:
            continue
        prefix = claim.get('financial_period_text', '')
        local = re.split(r'[，,]|但是|然而|但', prefix)[-1]
        if any(alias and alias in local for alias in aliases):
            prefix = local  # An explicit new subject does not inherit a peer's year.
        prefix = financial_period_scope(data, prefix)
        if prefix is None:
            continue
        periods = _PERIOD.findall(prefix)
        if periods and any(period.upper() != 'TTM' for period in periods):
            continue  # Annual and other dated claims retain their own source checker.
        if not periods and (field != 'free_cash_flow_raw' or not re.search(r'即期|當前|目前|原始欄位', prefix)):
            continue
        scope = re.sub(r'即期|當前|目前|原始欄位', '', prefix)
        if not _target_revenue_scope(data, scope, claim.get('financial_heading', '')):
            continue
        fact = facts[field]
        if fact['amount_twd'] is None:
            if require_available:
                issues.append('unverified_scalar_currency_or_amount:' + field)
            continue
        unit = str(claim['unit']).lower()
        scale = _SCALES.get(unit.removesuffix('元'), _SCALES.get(unit))
        if scale is None or claim.get('financial_scope_unbound'):
            issues.append('unbound_current_scalar_amount:' + field)
            continue
        expected = Decimal(fact['amount_twd'])
        reported = Decimal(str(claim['reported_value']))
        scale = Decimal(str(scale))
        precision = max(0, min(20, claim.get('financial_display_precision', 0)))
        rounded = (expected / scale).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        same_sign = reported * expected > 0 or reported == expected == 0
        if not same_sign or not (abs(reported * scale - expected) <= abs(expected) * Decimal('.01') or reported == rounded):
            issues.append('current_scalar_amount_mismatch:' + field)
    return list(dict.fromkeys(issues))


def bind_industry_financials(output, data):
    body = output.get('analysis_markdown', '')
    basis = financial_basis(data)
    output['model_analysis_markdown'] = body
    output['financial_basis'] = basis
    output['analysis_markdown'] = body + '\n\n' + basis_text(basis)
    output['output_completion']['financial_binding_sha256'] = fingerprint({
        'raw_sha256': output['output_completion']['raw_sha256'],
        'model_analysis_markdown': body, 'financial_basis': basis,
        'analysis_markdown': output['analysis_markdown']})


def binding_issues(output, data=None):
    if not isinstance(output, dict):
        return ['financial_binding_missing']
    basis = output.get('financial_basis')
    body = output.get('model_analysis_markdown')
    if not isinstance(basis, dict) or not isinstance(body, str) or basis.get('policy') != POLICY:
        return ['financial_binding_missing']
    if data is not None and basis != financial_basis(data):
        return ['financial_binding_input_mismatch']
    try:
        if (basis.get('sha256') != fingerprint({key: value for key, value in basis.items() if key != 'sha256'})
                or output.get('analysis_markdown') != body + '\n\n' + basis_text(basis)
                or (output.get('output_completion') or {}).get('financial_binding_sha256') != fingerprint({
                    'raw_sha256': (output.get('output_completion') or {}).get('raw_sha256'),
                    'model_analysis_markdown': body, 'financial_basis': basis,
                    'analysis_markdown': output.get('analysis_markdown')})):
            return ['financial_binding_content_mismatch']
    except (KeyError, TypeError, ValueError):
        return ['financial_binding_invalid']
    return []
