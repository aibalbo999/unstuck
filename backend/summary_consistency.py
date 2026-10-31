"""Bound generated summaries to the accepted decision and frozen money inputs."""
from __future__ import annotations

import hashlib
import re

from evidence_financial_amounts import check_financial_amount, extract_financial_amounts
from recommendation_labels import CANONICAL_RECOMMENDATIONS

POLICY = 'summary-consistency:v1-frozen-money-exact-classification'
_CLASSIFICATION = re.compile(
    r'(?:研究分類\s*建議\s*維持|(?:研究(?:分類|評級|結論)|投資(?:建議|結論)|綜合建議|建議)\s*(?:為|是|[:：])?)\s*[「【"\s]*'
    r'(買入|買進|持有|避免|放空|觀望|中性觀察|中性|中立|偏多觀察|避險觀察|空方風險觀察)')


def summary_issues(summary, context):
    data = context.get('data') or {}
    recommendation = (context.get('parsed') or {}).get('recommendation') or {}
    expected = recommendation.get('建議')
    issues = []
    from financial_fact_binding import period_assertion_issues, scalar_claim_issues
    issues.extend('摘要財務金額或期間不符：' + item for item in
                  scalar_claim_issues(summary, data) + period_assertion_issues(summary, data))
    classifications = _CLASSIFICATION.findall(summary)
    # A negated/conditional phrasing cannot stand in for the accepted decision.
    for match in _CLASSIFICATION.finditer(summary):
        prefix = re.split(r'[。；;\n]', summary[:match.start()])[-1]
        if re.search(r'(?:不|勿|未|若|假如|倘若|如果)\s*$', prefix):
            issues.append('摘要以否定或假設句表述分類，不能取代已核對的研究分類。')
    if expected in CANONICAL_RECOMMENDATIONS:
        if not classifications:
            issues.append('摘要缺少已核對的研究分類。')
        elif any(label != expected for label in classifications):
            issues.append(f'摘要研究分類與已核對的「{expected}」不一致；觀望／中性不能代稱持有。')
    for claim in extract_financial_amounts(summary, []):
        # Peer facts do not acquire this issuer's financial source.
        if re.search(r'同業|同儕|競爭對手|其他公司', claim.get('financial_period_text', '')):
            continue
        checked = check_financial_amount(claim, {'data': data}, 1.0)
        if checked and checked['status'] == 'mismatch':
            issues.append(f"摘要財務金額與凍結輸入不一致：{claim['financial_metric']}；來源 {checked['matched_path']}。")
        elif (checked and checked['status'] == 'unverifiable'
              and claim.get('financial_actual', True)
              and '官方' in str(claim.get('financial_period_text') or '')):
            issues.append('摘要官方財報來源資格不足：須在該金額明示公司主體、個別範圍、幣別與完整期間，並通過原件核對。')
    if not summary.strip():
        issues.append('摘要為空。')
    if len(summary) > 900:
        issues.append('摘要超過既有900字元界線；不得直接截斷後視為完整。')
    return list(dict.fromkeys(issues))


def summary_reference_prompt(context):
    data = context.get('data') or {}
    from financial_fact_binding import financial_reference_prompt
    lines = ['摘要的研究分類必須逐字使用 recommendation.建議，不得將持有改為中性／觀望；不重新做投資決策。',
             '控制在900字元內，保留完整句子與限制；只摘錄可核對資訊，不新增推論或改換金額單位。',
             '摘要不重複只有歷史snapshot、報表範圍未核實的金額；以文字保留該限制，完整數值仍在原報告。'
             '若引用官方金額，每一項都要有公司主體、個別範圍、TWD與完整起訖；不由首句或前一金額繼承。'
             '篇幅有限時可只述已核淨利與自由現金流，其他算式留在正文，不自行補造數字。']
    lines.append(financial_reference_prompt(data))
    from official_income_prompt import official_income_prompt_facts
    facts = official_income_prompt_facts(data)
    if facts is not None:
        from decimal import Decimal
        amount = format(Decimal(facts['net_income_ttm_raw']) / Decimal(100_000_000), 'f')
        lines.extend([
            '【另列官方個別淨利，非原 quote 的期間認證】',
            '若摘要引用下列官方淨利，整句逐字保留主體、TWD、個別及完整期間；不併句或改為「同期間」。',
            f"{facts['issuer_name']}官方個別財報 TWD TTM（{facts['period_start']} 至 {facts['period_end']}）"
            f"淨利為 {amount} 億元。",
            '來源：data.cash_flow.official_income_facts.source_documents[*].url；完整官方雙原件鏈已重播核對。'
            '不將原 quote 金額混用為此期間的官方淨利；不能由淨利推定 TTM EPS、正常化FCF或目標價。'
            '原始來源的歷史可得性與目前新鮮度仍未核實。',
        ])
        from financial_fact_binding import financial_basis
        fcf = financial_basis(data)['facts']['free_cash_flow_raw']
        if fcf.get('period_status') == 'verified':
            lines.extend([
                '若摘要引用下列官方自由現金流，同樣整句逐字保留；不用重述原始TWD或billion_twd換算。',
                f"{facts['issuer_name']}官方個別財報 TWD TTM（{fcf['period_start']} 至 {fcf['period_end']}）"
                f"自由現金流為 {fcf['amount_yi_twd']} 億元。",
            ])
    return '\n'.join(lines)


def accept_summary(summary, context, *, diagnostics=None, raw_text=None):
    from llm_completion_provenance import completion_diagnostics, completion_is_incomplete
    issues = summary_issues(summary, context)
    if completion_is_incomplete(diagnostics):
        issues.append('摘要供應商回應未完整。')
    elif completion_diagnostics(diagnostics)['finish_reasons'] != ['STOP']:
        issues.append('摘要供應商完成狀態尚未確認。')
    receipt = {'policy': POLICY, 'status': 'rejected' if issues else 'accepted', 'issues': issues,
               'candidate_sha256': hashlib.sha256(summary.encode()).hexdigest(),
               'raw_response_sha256': hashlib.sha256((raw_text if raw_text is not None else summary).encode()).hexdigest()}
    context['tear_sheet_validation'] = receipt
    context.setdefault('structured_outputs', {})['tear_sheet'] = {'summary_validation': receipt}
    if issues:
        # No corrected model prose is adopted. Reuse the existing typed fallback.
        from reporting.tear_sheet_summary import build_tear_sheet_summary
        fallback_context = {**context, 'tear_sheet_summary': ''}
        fallback = build_tear_sheet_summary(fallback_context)
        if summary_issues(fallback, context):
            context.setdefault('blocking_issues', []).append('tear_sheet:invalid_deterministic_summary')
            return False
        context['tear_sheet_summary'] = fallback
        return False
    context['tear_sheet_summary'] = summary
    return True
