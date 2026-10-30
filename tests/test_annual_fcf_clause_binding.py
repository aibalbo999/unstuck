"""A dated annual cash-flow clause must not borrow the preceding TTM dates."""
import pytest

from test_official_financial_claim_binding import projected

BASE = ('data.cash_flow.official_reference 顯示 TTM 自由現金流為 0.0885 億元'
        '（2025-07-01 至 2026-06-30），且 2025 年度 FCF 為 -0.23 億元。')
TITLE = '- **自由現金流持續淨流出與流動性壓力**（嚴重度：high；信心（0–1）：0.85）：'


def data():
    value = projected()
    value.update(years=['2024', '2025'], fcf_history=[0.08, -0.23])
    return value


def annual(text, value=None):
    from evidence_exit_gate import evaluate_report_evidence
    result = evaluate_report_evidence(text, {'data': data() if value is None else value})
    return next(c for c in result['sampled_claims'] if c.get('financial_metric') == 'FCF')


@pytest.mark.parametrize('prefix', ['', TITLE, '本公司', '大東電'])
def test_explicit_annual_clause_rejects_tenfold_unit_error(prefix):
    claim = annual(prefix + BASE)
    assert claim['status'] == 'mismatch', claim
    assert claim['matched_path'] == 'data.fcf_history[1]'
    assert claim['financial_period'] == '2025'
    assert claim['independent_primary_source_verified'] is False


def test_correct_annual_scale_and_early_repair_feedback():
    from financial_money_claims import financial_money_claim_issues
    value = data()
    assert annual(BASE.replace('FCF 為 -0.23', 'FCF 為 -2.3'), value)['status'] == 'verified'
    assert financial_money_claim_issues(TITLE + BASE, value)
    assert not financial_money_claim_issues(BASE.replace('FCF 為 -0.23', 'FCF 為 -2.3'), value)


@pytest.mark.parametrize('prefix', ['同業', '台積電', '同儕資料：', '美元資料：', '本集團合併'])
def test_foreign_owner_or_scope_is_never_qualified(prefix):
    claim = annual(prefix + BASE.replace('FCF 為 -0.23', 'FCF 為 -2.3'))
    assert claim['status'] == 'unverifiable', claim


@pytest.mark.parametrize('damage', ['undated', 'wrong_ttm_dates', 'source_path', 'missing_receipt', 'currency'])
def test_unqualified_period_or_source_keeps_existing_fail_closed_behavior(damage):
    value = data(); text = BASE.replace('FCF 為 -0.23', 'FCF 為 -2.3')
    if damage == 'undated': text = text.replace('2025 年度', '年度')
    elif damage == 'wrong_ttm_dates': text = text.replace('2025-07-01', '2024-07-01')
    elif damage == 'source_path': text = text.replace('data.cash_flow.official_reference', 'peer.cash_flow.official_reference')
    elif damage == 'missing_receipt': value['official_financial_projection']['reference']['annual_document']['sha256'] = '0' * 64
    else: value['financial_currency'] = 'USD'
    assert annual(text, value)['status'] == 'unverifiable'


@pytest.mark.parametrize('suffix', ['（同業大亞）', '（合併報表）', '（本集團）', '（歐元）',
                                  '（台積電資料）', '（預期數值）', '，此為同業大亞',
                                  '，本數值為合併報表口徑', '，以歐元計價'])
def test_annual_transition_cannot_discard_postfix_owner_scope_or_currency(suffix):
    claim = annual(BASE.replace('FCF 為 -0.23 億元。', 'FCF 為 -2.3 億元' + suffix + '。'))
    assert claim['status'] == 'unverifiable', claim


def test_annual_direction_is_checked_and_repair_feedback_names_the_direction():
    from financial_money_claims import financial_money_claim_issues
    text = BASE.replace('FCF 為 -0.23 億元。', 'FCF 為 -2.3 億元（淨流入）。')
    claim = annual(text)
    assert claim['status'] == 'mismatch', claim
    assert claim['verification_reason_code'] == 'financial_annual_direction_mismatch'
    assert any('方向' in issue for issue in financial_money_claim_issues(text, data()))
    assert annual(text.replace('淨流入', '淨流出'))['status'] == 'verified'


CANDIDATE = ('大東電個別 2025-07-01 至 2026-06-30 TTM FCF 為 -2.47269 億元'
             '（營業現金流 -1.89755 億元、資本支出 0.57514 億元），2025 年單年度 FCF 亦為 -0.23 億元'
             '（轉換率 -28.05%），確實顯示獲利未有效轉化為真實現金流。')


def candidate_annual(text):
    from evidence_exit_gate import evaluate_report_evidence
    result = evaluate_report_evidence(text, {'data': data()})
    return next(c for c in result['sampled_claims'] if c.get('financial_metric') == 'FCF'
                and c.get('reported_value') in (-0.23, -2.3))


def test_real_candidate_abbreviation_and_compound_annual_claim_cannot_hide_unit_error():
    from financial_money_claims import financial_money_claim_issues
    claim = candidate_annual(CANDIDATE)
    assert claim['status'] == 'mismatch', claim
    assert claim['matched_path'] == 'data.fcf_history[1]'
    assert claim['financial_period'] == '2025'
    assert any('2025 FCF' in issue for issue in financial_money_claim_issues(CANDIDATE, data()))
    correct = candidate_annual(CANDIDATE.replace('亦為 -0.23', '亦為 -2.3'))
    assert correct['status'] == 'verified', correct
    assert correct['independent_primary_source_verified'] is False


@pytest.mark.parametrize('damage', ['peer', 'unknown_issuer', 'foreign', 'consolidated', 'wrong_period',
                                  'peer_postfix', 'foreign_postfix', 'future_postfix', 'period_postfix'])
def test_candidate_annual_abbreviation_keeps_scope_and_postfix_guards(damage):
    text = CANDIDATE.replace('亦為 -0.23', '亦為 -2.3')
    if damage == 'peer': text = text.replace('大東電個別', '同業大東電個別')
    elif damage == 'unknown_issuer': text = text.replace('大東電個別', '台積電個別')
    elif damage == 'foreign': text = text.replace('億元', '億美元')
    elif damage == 'consolidated': text = text.replace('個別', '合併')
    elif damage == 'wrong_period': text = text.replace('2025-07-01', '2024-07-01')
    elif damage == 'peer_postfix': text = text.replace('轉換率 -28.05%', '同業大亞')
    elif damage == 'foreign_postfix': text = text.replace('轉換率 -28.05%', '歐元')
    elif damage == 'future_postfix': text = text.replace('轉換率 -28.05%', '預期數值')
    else: text = text.replace('轉換率 -28.05%', '2026年上半年')
    assert candidate_annual(text)['status'] == 'unverifiable'
