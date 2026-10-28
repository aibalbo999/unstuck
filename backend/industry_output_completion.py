"""Strict raw evidence-JSON completion and TTM explanation for role 11."""
from __future__ import annotations

import hashlib
import json
import re

from evidence_financial_amounts import check_financial_amount, extract_financial_amounts
from financial_money_claims import _finite
from llm_completion_provenance import completion_diagnostics, completion_is_incomplete
from output_sanitizer import sanitize_model_output, strip_generated_audit_sections

POLICY = 'industry-output-completion:v2-bound-financial-basis'


def text_hash(text):
    return hashlib.sha256(sanitize_model_output(strip_generated_audit_sections(str(text or ''))).encode()).hexdigest()


def content_issues(text, data):
    issues = []
    for label, pattern in (('macro', r'總體|宏觀|總經'), ('industry', r'產業|供需'),
                           ('conclusion', r'結論|定調|整體判斷')):
        if not re.search(pattern, text):
            issues.append('missing_industry_' + label)
    if re.search(r'(?:理由|結論|定調|#{1,6}[^\n]*)\s*[:：]?\s*[*_]*\s*$', text):
        issues.append('dangling_industry_conclusion')
    conclusion = re.search(r'#{1,6}[^\n]*(?:結論|定調|整體判斷)[^\n]*\n([\s\S]+)', text)
    if not conclusion or len(re.sub(r'[\s*#]', '', conclusion[1])) < 30:
        issues.append('missing_substantive_industry_conclusion')
    raw = _finite(data.get('net_income_ttm_raw'))
    currency = str(data.get('financial_currency') or '').upper()
    if raw is not None and currency in {'TWD', 'NTD'}:
        matches = []
        for claim in extract_financial_amounts(text, []):
            if claim['financial_metric'] not in {'淨利', '稅後淨利'}:
                continue
            if re.search(r'同業|同儕|其他公司|競爭對手', claim.get('financial_period_text', '')):
                continue
            checked = check_financial_amount(claim, {'data': data}, 1.0)
            if checked and checked.get('matched_path') == 'data.net_income_ttm_raw':
                matches.append(checked)
        if not matches:
            issues.append('missing_current_ttm_net_income_amount')
        elif any(item['status'] != 'verified' for item in matches):
            issues.append('incorrect_current_ttm_net_income_amount')
        if raw < 0 and not re.search(r'淨損|虧損|淨利.{0,12}(?:為負|負值)', text):
            issues.append('missing_ttm_loss_explanation')
        if not re.search(r'(?:TTM|期間|起訖).{0,40}(?:未(?:完全)?(?:經|能|獲)?(?:官方|原件|來源)?(?:完全)?(?:核實|核驗|確認)|無法確認)', text, re.I):
            issues.append('missing_ttm_period_limitation')
    elif not re.search(r'TTM.{0,30}(?:淨利|淨損).{0,40}(?:不足|未提供|異常|未確認|無法|未取得)', text, re.I):
        issues.append('missing_ttm_net_income_gap_reason')
    return issues


def assess_industry_completion(raw_text, data, diagnostics=None, prior=None, *, bind_financials=False):
    from memo_output_completion import assess_memo_completion
    from assessment_output_completion import _unique_object, _invalid_constant
    from json_utils import _strip_code_fence
    observed = completion_diagnostics(diagnostics)
    sha = hashlib.sha256(str(raw_text or '').encode()).hexdigest()
    if (isinstance(prior, dict) and prior.get('contract_version') == POLICY and prior.get('raw_sha256') == sha
            and prior.get('status') == 'incomplete' and not observed['finish_reasons']):
        return dict(prior)
    memo = assess_memo_completion(raw_text, diagnostics)
    issues = list(memo['issues'])
    try:
        payload = json.loads(_strip_code_fence(raw_text or ''), object_pairs_hook=_unique_object,
                             parse_constant=_invalid_constant)
    except (ValueError, TypeError):
        payload = None
        issues.append('incomplete_or_invalid_json')
    body = payload.get('analysis_markdown') if isinstance(payload, dict) else ''
    if isinstance(body, str):
        clean = sanitize_model_output(body)
        if bind_financials:
            from financial_fact_binding import financial_basis, basis_text, period_assertion_issues, scalar_claim_issues
            from financial_money_claims import financial_money_claim_issues
            # Check the original narrative before appending deterministic facts.
            # An omitted scalar is rendered; a contradictory assertion is rejected.
            issues.extend(period_assertion_issues(clean, data))
            issues.extend(scalar_claim_issues(clean, data))
            if financial_money_claim_issues(clean, data):
                issues.append('incorrect_financial_amount_assertion')
            narrative = content_issues(clean, data)
            issues.extend(issue for issue in narrative if issue.startswith(('missing_industry_',
                'dangling_industry_', 'missing_substantive_industry_')))
            clean += '\n\n' + basis_text(financial_basis(data))
        issues.extend(content_issues(clean, data))
    if completion_is_incomplete(observed):
        issues.insert(0, 'provider_output_incomplete')
    elif not observed['finish_reasons'] or any(reason != 'STOP' for reason in observed['finish_reasons']):
        issues.insert(0, 'provider_completion_unconfirmed')
    return {'contract_version': POLICY, 'status': 'incomplete' if issues else 'complete',
            'raw_sha256': sha, 'text_sha256': text_hash(raw_text),
            'finish_reasons': observed['finish_reasons'], 'provider_finish_observed': bool(observed['finish_reasons']),
            'raw_json_complete': isinstance(payload, dict),
            'raw_schema_complete': not memo['issues'],
            'basis': 'provider_finish_raw_evidence_schema_narrative_and_ttm_net_income', 'issues': list(dict.fromkeys(issues))}


def industry_output_issues(text, data, output):
    receipt = output.get('output_completion') if isinstance(output, dict) else None
    reasons = []
    if not isinstance(receipt, dict) or receipt.get('contract_version') != POLICY:
        reasons.append('industry_completion_receipt_missing')
    else:
        if receipt.get('status') != 'complete':
            reasons.extend(receipt.get('issues') or ['industry_completion_unconfirmed'])
        if receipt.get('text_sha256') != text_hash(text):
            reasons.append('industry_text_receipt_mismatch')
    from financial_fact_binding import binding_issues, period_assertion_issues
    reasons.extend(binding_issues(output, data))
    if isinstance(output, dict):
        reasons.extend(period_assertion_issues(output.get('model_analysis_markdown') or '', data))
    body = output.get('analysis_markdown') if isinstance(output, dict) else None
    reasons.extend(content_issues(body if isinstance(body, str) else text, data))
    return ['產業段落完整性／TTM 淨利說明未通過：' + reason + '；須完整重寫，不能省略凍結數值或補造期間。'
            for reason in dict.fromkeys(reasons)]


def cached_industry_valid(cached):
    if not isinstance(cached, dict):
        return False
    output = cached.get('structured_output')
    if not isinstance(output, dict):
        return False
    receipt = output.get('output_completion')
    if not isinstance(receipt, dict):
        return False
    from financial_fact_binding import binding_issues
    return (not binding_issues(output) and receipt.get('contract_version') == POLICY and receipt.get('status') == 'complete'
            and receipt.get('finish_reasons') == ['STOP']
            and receipt.get('text_sha256') == text_hash(cached.get('text')))


def industry_instruction():
    return (
        '\n\nAgent 11 完整性契約：只輸出一份完整JSON與結尾大括號，保留既有as_of_date、confidence、evidence_items、analysis_markdown必要欄位，'
        '每筆evidence_items仍須保留finding、source_refs、freshness_note及counterevidence。'
        '以精煉analysis_markdown完成總體經濟、產業週期與宏觀結論三節，最後結論須有完整理由與反證，'
        '不能只留標題或理由標籤。保留所有必要證據與風險，不以縮短來源代替分析。'
        '系統會依凍結輸入另附TTM淨利、FCF金額與期間資格，不必在正文重抄固定數字。'
        '若引用金額，只使用原生換算參考，負值為淨損或淨流出，與年度數字區分；'
        '來源稱TTM但起訖期間尚未核實，'
        '不可補造日期。若數值或財報幣別缺少，明說TTM淨利無法核對的實際原因，不填零或沿用年度值。'
        '以500–800字精煉重複背景，必要完整性與證據規則優先；輸出上限、來源、安全及品質門檻不變。'
    )
