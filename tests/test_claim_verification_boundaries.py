"""Regressions from the 22 unverifiable claims; synthetic evidence only."""
import pytest
from evidence_exit_gate import evaluate_report_evidence


def check(text):
    data = {'ticker':'1623.TW','company_name':'大東電','financial_currency':'TWD',
            'revenue_ttm_raw':6.663135232e9,'net_income_ttm_raw':860640000.,
            'free_cash_flow_raw':-461411616.,'years':['2025'],
            'revenue_history':[6.61], 'net_income_history':[.82], 'fcf_history':[-.23],
            'recent_monthly_revenue':['2026年5月: NT$3.56億','2026年8月: NT$4.82億']}
    return evaluate_report_evidence(text, {'data':data})['sampled_claims']


def test_repeated_same_ttm_labels_are_not_ambiguous_periods():
    rows=check('根據 TTM 數據，公司年營收達 6.6631 billion_twd（約66.63億元），TTM 稅後淨利為0.8606 billion_twd（約8.61億元）。')
    assert len(rows)==2
    assert all(r['status']=='verified' for r in rows)
    assert rows[1]['matched_path']=='data.net_income_ttm_raw'


@pytest.mark.parametrize('text',[
    'TTM FCF:-0.4614 billion_twd',
    'TTM 自由現金流為負0.4614 billion_twd',
    '即期自由現金流為 -0.4614 billion_twd',
])
def test_unknown_fcf_source_period_is_never_verified_by_claim_wording(text):
    row=check(text)[0]
    assert row['status']=='unverifiable'
    assert row['financial_arithmetic_consistent'] is True
    assert row['financial_period_verified'] is False


@pytest.mark.parametrize('text',[
    '2026年5月單月營收僅3.56億元，較高點顯著回落。',
    '2026 年 8 月月營收亦回落至4.82億元（recent_monthly_revenue_text）。',
])
def test_explicit_month_binds_local_subject_not_following_commentary(text):
    row=check(text)[0]
    assert row['status']=='verified'
    assert 'recent_monthly_revenue' in row['matched_path']


def test_monthly_peer_and_threshold_remain_unverified():
    for text in ('同業2026年5月單月營收僅3.56億元。','若2026年5月單月營收僅3.56億元。',
                 '2026年5月至8月單月營收僅3.56億元。'):
        assert all(r['status']=='unverifiable' for r in check(text))


def test_wrong_explicit_monthly_amount_is_mismatch():
    assert check('2026年5月單月營收僅4.82億元。')[0]['status']=='mismatch'


def test_debt_to_equity_alias_does_not_certify_total_liability_definition():
    data={'debt_to_equity':'70.65%'}
    plain=evaluate_report_evidence('負債權益比（D/E）：70.65%',{'data':data})['sampled_claims'][0]
    assert plain['status']=='verified'
    wrong=evaluate_report_evidence('負債權益比（D/E）：50%',{'data':data})['sampled_claims'][0]
    assert wrong['status']=='mismatch'
    definition=evaluate_report_evidence('負債權益比（D/E）：70.65%（總負債／股東權益）',{'data':data})['sampled_claims'][0]
    assert definition['status']=='unverifiable'
    assert definition['verification_reason_code']=='financial_ratio_definition_unverified'


@pytest.mark.parametrize('heading',['高成長可執行性檢查（樂觀情境）','成長與估值假設對照'])
def test_current_fcf_inside_scenario_section_is_still_an_unverified_actual(heading):
    text=f'### {heading}\n* **產能與 CapEx 壓力**：即期自由現金流 (FCF) 為 -0.4614 billion_twd（淨流出約4.61億元）。若要支撐30%成長，需額外融資。'
    row=check(text)[0]
    assert row['financial_actual'] is True
    assert row['verification_reason_code']=='financial_arithmetic_consistent_period_unverified'
    assert row['status']=='unverifiable'


def test_forecast_current_label_does_not_override_real_condition():
    assert check('若即期自由現金流為-0.4614 billion_twd，則需融資。')[0]['verification_reason_code']=='financial_projection_not_observed_fact'


def test_dated_month_after_provider_ratios_keeps_its_own_period_and_subject():
    text='更警惕的是，Yahoo 即期獲利成長率呈現 -50.0%、即期營收成長率為 -9.5%（growth），2026 年 8 月月營收亦回落至 4.82 億元（recent_monthly_revenue_text）。'
    rows=check(text)
    assert rows[-1]['status']=='verified'
    assert rows[-1]['financial_period']=='2026-08'
    for prefix in ['同業，','大亞，','以下金額為美元，']:
        assert check(prefix+text)[-1]['status']=='unverifiable'
