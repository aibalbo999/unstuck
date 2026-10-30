import pytest

from evidence_exit_gate import evaluate_report_evidence
from financial_fact_binding import scalar_claim_issues


def source():
    return {'ticker': '2367.TW', 'company_name': '燿華', 'financial_currency': 'TWD', 'years': ['2024', '2025'],
            'fcf_history': [0.5, -0.373162], 'free_cash_flow_raw': -2023845248,
            'net_income_history': [0.2, 0.484], 'net_income_ttm_raw': -459064563.75,
            'revenue_history': [10, 11], 'revenue_ttm_raw': 12e9}


def checked(text, data=None, mode='v2'):
    return evaluate_report_evidence(text, {'pipeline': mode, 'data': source() if data is None else data})['sampled_claims']


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3', 'v4'])
@pytest.mark.parametrize('annual', ['最新全年度', '最新年度', '最近完整年度'])
def test_latest_annual_claim_does_not_inherit_preceding_ttm(mode, annual):
    text = f'TTM 自由現金流為 -20.24 億元，{annual} FCF 為 -3.73 億元。'
    claims = checked(text, mode=mode)
    assert [claim['status'] for claim in claims] == ['unverifiable', 'verified']
    assert claims[0]['financial_arithmetic_consistent'] is True
    assert claims[0]['financial_period_verified'] is False
    assert claims[0]['matched_path'] == 'data.free_cash_flow_raw'
    assert claims[1]['matched_path'] == 'data.fcf_history[1]'
    assert claims[1]['financial_period'] == '2025'
    assert not scalar_claim_issues(text, source())


@pytest.mark.parametrize('wrong', ['-20.24', '-0.373', '3.73'])
def test_latest_annual_wrong_value_still_rejected(wrong):
    claims = checked(f'TTM FCF 為 -20.24 億元，最新全年度 FCF 為 {wrong} 億元。')
    assert claims[1]['status'] == 'mismatch'
    assert claims[1]['matched_path'] == 'data.fcf_history[1]'


@pytest.mark.parametrize('patch', [
    {'years': []}, {'years': ['2025', '2025']}, {'years': ['2024', '2025Q4']},
    {'fcf_history': [0.5]}, {'fcf_history': [0.5, None]}, {'fcf_history': [0.5, True]},
    {'financial_currency': 'USD'}, {'unit_contract': {'money': 'million_twd'}},
])
def test_latest_annual_missing_contract_never_borrows_ttm_or_older_value(patch):
    claims = checked('TTM FCF 為 -20.24 億元，最新全年度 FCF 為 -3.73 億元。', {**source(), **patch})
    assert claims[1]['status'] == 'unverifiable'


@pytest.mark.parametrize('period', ['年度', '全年', '先前年度'])
def test_unspecified_annual_period_does_not_borrow_ttm(period):
    claims = checked(f'TTM FCF 為 -20.24 億元，{period} FCF 為 -3.73 億元。')
    assert claims[1]['status'] == 'unverifiable'


def test_explicit_annual_year_and_peer_identity_still_win():
    assert checked('TTM FCF 為 -20.24 億元，2024年度 FCF 為5億元。')[1]['matched_path'] == 'data.fcf_history[0]'
    claims = checked('## 同業比較\n同業最新全年度 FCF 為 -3.73 億元。')
    assert claims[0]['status'] == 'unverifiable'


@pytest.mark.parametrize('text', [
    '華通最新全年度FCF為-3.73億元。',
    '同業華通TTM FCF為-20.24億元，最新年度FCF為-3.73億元。',
    '同業華通的財務如下。最新全年度FCF為-3.73億元。',
    '2024年度財報顯示，最新全年度FCF為-3.73億元。',
    '以下均採TTM口徑，最新全年度FCF為-3.73億元。',
    '截至2025年9月，最新全年度FCF為-3.73億元。',
    '最新全年度TTM FCF為-3.73億元。',
    'TTM最新全年度 FCF為-3.73億元。',
])
def test_owner_and_period_preamble_cannot_be_discarded(text):
    assert checked(text)[-1]['status'] == 'unverifiable'


def test_annual_preamble_and_explicit_own_subject_are_retained():
    claim = checked('2024年度財報顯示，全年FCF為5億元。')[0]
    assert claim['status'] == 'verified' and claim['matched_path'] == 'data.fcf_history[0]'
    claim = checked('同業華通的財務如下。本公司最新全年度FCF為-3.73億元。')[0]
    assert claim['status'] == 'verified' and claim['matched_path'] == 'data.fcf_history[1]'


@pytest.mark.parametrize('text', [
    'TTM自由現金流為-20.24億元。2024年度財報顯示，最新全年度FCF為-3.73億元。',
    'TTM自由現金流為-20.24億元。以下均採TTM口徑，最新全年度FCF為-3.73億元。',
    'TTM自由現金流為-20.24億元。截至2025年9月，最新全年度FCF為-3.73億元。',
    '同業華通的財務如下。\n最新全年度FCF為-3.73億元。',
    '華通的財務如下。最新全年度FCF為-3.73億元。',
    '華通TTM FCF為-20.24億元，最新全年度FCF為-3.73億元。',
    '華通2025年最新全年度FCF為-3.73億元。',
])
def test_newer_period_or_owner_context_is_not_erased_by_an_earlier_amount(text):
    assert checked(text)[-1]['status'] == 'unverifiable'


def test_explicit_company_comparison_keeps_the_annual_unit_guard():
    from financial_money_claims import financial_money_claim_issues
    assert financial_money_claim_issues('對照公司 2025 年全年營收為 11 億元。', source())
    assert not financial_money_claim_issues('對照公司 2025 年全年營收為 110 億元。', source())


def test_risk_topic_label_is_not_a_company_but_unknown_colon_subject_is_retained():
    text = '- 已納入考量的風險: 現金流與償債壓力：TTM 自由現金流為 -20.24 億元，最新全年度 FCF 為 -3.73 億元。'
    assert checked(text)[-1]['matched_path'] == 'data.fcf_history[1]'
    text = '華通：TTM 自由現金流為 -20.24 億元，最新全年度 FCF 為 -3.73 億元。'
    assert checked(text)[-1]['status'] == 'unverifiable'


def test_sibling_list_claims_do_not_replace_a_list_preamble_or_share_their_owners():
    text = '- 具體佐證: 2026年9月單月營收達14.80億元。\n- 已納入考量的風險: 現金流與償債壓力：TTM FCF為-20.24億元，最新全年度FCF為-3.73億元。'
    assert checked(text)[-1]['matched_path'] == 'data.fcf_history[1]'
    text = '華通的財務如下。\n- TTM FCF為-20.24億元。\n- 最新全年度FCF為-3.73億元。'
    assert checked(text)[-1]['status'] == 'unverifiable'


@pytest.mark.parametrize('parent', ['華通的財務如下。', '同業華通的財務如下。', '2024年度財報顯示：'])
def test_nested_items_keep_parent_owner_and_period(parent):
    assert checked(f'- {parent}\n  - 最新全年度FCF為-3.73億元。')[-1]['status'] == 'unverifiable'


@pytest.mark.parametrize('lead', [
    '同業華通TTM FCF為-20.24億元。本公司2024年度FCF為5億元，',
    '同業華通TTM FCF為-20.24億元。\n本公司2024年度FCF為5億元，',
    '同業華通的財務如下。本公司的財務如下。',
    '華通TTM FCF為-20.24億元。本公司2024年度FCF為5億元，',
])
@pytest.mark.parametrize('amount,expected', [('-3.73', 'verified'), ('5', 'mismatch')])
def test_explicit_issuer_switch_also_resets_subsequent_implicit_claims(lead, amount, expected):
    claim = checked(lead + f'最新全年度FCF為{amount}億元。')[-1]
    assert claim['status'] == expected and claim['matched_path'] == 'data.fcf_history[1]'


@pytest.mark.parametrize('lead', ['同業華通2024年度財務如下。', '同業華通2024年度財務如下。\n'])
def test_explicit_issuer_switch_does_not_inherit_another_company_period(lead):
    claim = checked(lead + '本公司最新全年度FCF為-3.73億元。')[-1]
    assert claim['status'] == 'verified' and claim['matched_path'] == 'data.fcf_history[1]'


@pytest.mark.parametrize('amount,expected', [('-3.73', 'verified'), ('5', 'mismatch')])
def test_explicit_nested_issuer_subject_can_override_a_peer_section(amount, expected):
    text = f'## 同業比較\n- 本公司的財務如下。\n  - 最新全年度FCF為{amount}億元。'
    assert checked(text)[-1]['status'] == expected


@pytest.mark.parametrize('preamble', ['2024年度財報顯示，', '以下均採TTM口徑，', '截至2025年9月，'])
@pytest.mark.parametrize('subject', ['', '本公司'])
@pytest.mark.parametrize('earlier', ['', 'TTM FCF為-20.24億元。'])
def test_issuer_noun_does_not_cancel_the_current_claim_period(preamble, subject, earlier):
    text = earlier + preamble + subject + '最新全年度FCF為-3.73億元。'
    assert checked(text)[-1]['status'] == 'unverifiable'
