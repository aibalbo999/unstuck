import hashlib
import json

import pytest

from evidence_exit_gate import evaluate_report_evidence, flatten_snapshot_numbers


def data():
    return {'financial_currency':'TWD','years':['2024','2025'],
            'revenue_history':[100,10],'net_income_history':[8,2],
            'fcf_history':[100,-1],'free_cash_flow_raw':-2e9,
            'revenue_ttm_raw':11e9,'revenue':100}


def claims(text,source=None,pipeline='v1'):
    return evaluate_report_evidence(text,{'pipeline':pipeline,'data':data() if source is None else source})['sampled_claims']


@pytest.mark.parametrize('pipeline',['v1','v2','v3','v4'])
@pytest.mark.parametrize('text,path,value',[
    ('2025年營收:100 億','data.revenue_history[1]',100),
    ('2024年營收:100 B','data.revenue_history[0]',100),
    ('2025年淨利:20 億','data.net_income_history[1]',20),
    ('2025年FCF:-1 B','data.fcf_history[1]',-1),
    ('TTM FCF:-2 B','data.free_cash_flow_raw',-2),
    ('TTM營收:110 億','data.revenue_ttm_raw',110),
    ('FCF (2025): -1 B','data.fcf_history[1]',-1),
    ('2025 Revenue:10 B','data.revenue_history[1]',10),
])
def test_same_metric_period_currency_and_unit_positive_controls(pipeline,text,path,value):
    checked=claims(text,pipeline=pipeline)
    assert len(checked)==1
    assert checked[0]['status']==('unverifiable' if path=='data.free_cash_flow_raw' else 'verified')
    if path=='data.free_cash_flow_raw':
        assert checked[0]['financial_period_verified'] is False
        assert checked[0]['financial_arithmetic_consistent'] is True
    assert checked[0]['matched_path']==path
    assert checked[0]['matched_value']==value
    assert checked[0]['independent_primary_source_verified'] is False


@pytest.mark.parametrize('text',[
    '2025年FCF:100 B','TTM FCF:100 B','TTM FCF:2 B',
    '2025年營收:100 B','2024年營收:100 億','2025年淨利:20 B',
])
def test_old_positive_or_wrong_units_cannot_override_same_period_negative(text):
    checked=claims(text)
    assert len(checked)==1
    assert checked[0]['status']=='mismatch'
    assert checked[0]['candidate_count']==1


@pytest.mark.parametrize('text',[
    'FCF:100 B','FCF:-2 B','FCF:100','營收:100 億','營收:100 B',
    '2023年FCF:100 B','2025年Q2營收:100 B','2025年營收:100 B USD',
    '2024年TTM FCF:-2 B',
])
def test_unknown_period_currency_or_unit_stays_unknown(text):
    assert all(c['status']=='unverifiable' for c in claims(text))


@pytest.mark.parametrize('mutation',[
    {'financial_currency':'USD'}, {'financial_currency':None},
    {'years':['2025','2025']}, {'years':['2025']},
    {'unit_contract':{'money':'million_twd'}},
])
def test_ambiguous_source_contract_never_verified(mutation):
    source={**data(),**mutation}
    assert all(c['status']=='unverifiable' for c in claims('2025年FCF:-1 B',source))


def test_invalid_current_raw_fcf_never_falls_back_to_positive_history():
    source={**data(),'free_cash_flow_raw':float('nan')}
    assert claims('TTM FCF:100 B',source)[0]['status']=='unverifiable'


def test_table_period_is_metadata_and_actual_amount_still_checked():
    text='|類別|事實|期間|單位|來源|\n|---|---|---|---|---|\n|TAM|全球市場規模|--|未評估|資料不足|\n|SAM|區域市場規模|--|未評估|資料不足|\n|SOM|年度營收（已觀測事實）|2025|100 億元 (10 billion_twd)|data.history.rows|'
    source={**data(),'source_freshness':{'monthly_revenue':{'checked_at':'2026-09-27T12:00:00+08:00'}}}
    checked=claims(text,source)
    assert len(checked)==1
    assert checked[0]['reported_value']==100
    assert checked[0]['status']=='verified'
    assert checked[0]['matched_path']=='data.revenue_history[1]'
    assert claims(text.replace('100 億元','100 B'),source)[0]['status']=='mismatch'


def test_unknown_table_year_keeps_amount_unverifiable_not_silent_drop():
    text='|類別|事實|期間|單位|來源|\n|---|---|---|---|---|\n|SOM|年度營收|2023|100 億元|data.history.rows|'
    checked=claims(text)
    assert len(checked)==1 and checked[0]['status']=='unverifiable'


def test_real_valuation_horizon_annotation_never_matches_revenue():
    text='| 最終投資建議 | 建議: 避免；3個月: N/A／未評估，股價處於極端敘事驅動階段，短期波動受法人派發速度主導，缺乏穩定價格證據。；6個月: N/A／未評估，需等待連續兩季財報驗證液冷產品對營收之實質貢獻度。；12個月: 518.44 TWD (DCF 基準估值)；此為基本面底線。 |'
    snapshot={'data':{**data(),'revenue_ttm':229.22},'rerun_context':{'parsed':{'recommendation':{'長期目標（12個月）':'518.44 TWD (DCF 基準估值)；此為基本面底線。'}}}}
    checked=evaluate_report_evidence(text,snapshot)['sampled_claims']
    assert len(checked)==1
    assert checked[0]['status']=='unverifiable'
    assert checked[0]['matched_path'].endswith('長期目標（12個月）')
    assert checked[0]['verification_reason_code']=='generated_analysis_not_independent_evidence'
    snapshot['rerun_context']['parsed']['recommendation']['長期目標（12個月）']='400 TWD'
    checked=evaluate_report_evidence(text,snapshot)['sampled_claims']
    assert checked[0]['status']=='mismatch'
    assert checked[0]['verification_reason_code']=='generated_analysis_value_mismatch'


def test_dates_never_financial_values_but_legacy_full_flattener_preserved():
    snapshot={'source_freshness':{'monthly_revenue':{'checked_at':'2026-09-27T12:00:00+08:00'}},'data':{'years':['2025']}}
    assert flatten_snapshot_numbers(snapshot)
    assert flatten_snapshot_numbers(snapshot,eligible_only=True)==[]


def test_projection_is_not_observed_financial_fact():
    assert claims('2025年預估營收:100 億')[0]['verification_reason_code']=='financial_projection_not_observed_fact'


def test_actual_rounding_and_negative_sign_are_preserved():
    source={**data(),'revenue_history':[100,16.246291],'free_cash_flow_raw':-25_623_500}
    assert claims('2025年營收:162.5 億',source)[0]['status']=='verified'
    assert claims('TTM自由現金流:負0.2562 億',source)[0]['status']=='unverifiable'
    assert claims('TTM自由現金流:0.2562 億',source)[0]['status']=='mismatch'


@pytest.mark.parametrize('text',[
    '2025年平均月營收:16.9 億','2025年月均營收（約16.9億元）',
    '2025年營收從71.76B躍升至139.64B',
    '2025年營收達2.97十億新臺幣、單月營收維持在4.5億至5.79億之間。',
])
def test_monthly_averages_and_change_endpoints_never_compare_to_annual_total(text):
    source={**data(),'revenue_history':[100,2.97]} if '2.97十億' in text else data()
    checked=claims(text,source)
    assert checked and not any(c['status']=='mismatch' for c in checked)
    assert any(c['verification_reason_code']=='financial_amount_scope_unbound' for c in checked)


def original_snapshot():
    from report_analysis_evidence import capture_analysis_evidence
    original=data();original['analysis_input_hash']=hashlib.sha256(json.dumps(original,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    original['analysis_input_cutoff']='2026-09-24T02:00:00+08:00'
    packet=capture_analysis_evidence({'data':original})
    assert packet['input_verification']=='hash_verified'
    current={**original,'free_cash_flow_raw':100e9}
    return {'data':current,'analysis_evidence':packet,'refreshed_without_analysis_rerun':True}


def test_refresh_cannot_replace_original_ttm_financial_facts():
    snapshot=original_snapshot()
    checked=evaluate_report_evidence('TTM FCF:-2 B',snapshot)['sampled_claims'][0]
    assert checked['status']=='unverifiable'
    assert checked['financial_arithmetic_consistent'] is True
    assert checked['financial_period_verified'] is False
    assert checked['matched_path']=='analysis_evidence.sections.analysis_input.data.free_cash_flow_raw'
    assert checked['analysis_input_cutoff']=='2026-09-24T02:00:00+08:00'
    assert evaluate_report_evidence('TTM FCF:100 B',snapshot)['sampled_claims'][0]['status']=='mismatch'


def test_corrupt_original_packet_never_repairs_from_current_financials():
    snapshot=original_snapshot();snapshot['analysis_evidence']['sections']['analysis_input']['data']['free_cash_flow_raw']=100e9
    checked=evaluate_report_evidence('TTM FCF:100 B',snapshot)['sampled_claims'][0]
    assert checked['status']=='unverifiable'
    assert checked['verification_reason_code']=='financial_original_input_unavailable'


def test_missing_original_packet_after_refresh_stays_unknown():
    checked=evaluate_report_evidence('TTM FCF:-2 B',{'data':data(),'snapshot_refreshed_at':'2026-10-07T00:00:00+08:00'})['sampled_claims'][0]
    assert checked['status']=='unverifiable' and checked['candidate_count']==0


def test_identical_amounts_in_two_periods_keep_both_claims():
    checked=claims('2024年營收100B，2025年營收100B')
    assert len(checked)==2
    assert [c['status'] for c in checked]==['verified','mismatch']
    assert [c['financial_period'] for c in checked]==['2024','2025']


@pytest.mark.parametrize('text',[
    '2025年營收（平均每月）:100 億','2025年每月平均營收:100 億',
    '|事實|期間|單位|\n|---|---|---|\n|平均月營收|2025|100 B|',
])
def test_monthly_averages_in_annotations_and_tables_keep_unknown_scope(text):
    checked=claims(text)
    assert checked and all(c['status']=='unverifiable' for c in checked)
    assert all(c['verification_reason_code']=='financial_amount_scope_unbound' for c in checked)


@pytest.mark.parametrize('text',[
    '2025 Revenue:100 B (forecast)',
    '2025年10B的營收 (forecast)',
    '|Fact|Period|Unit|\n|---|---|---|\n|Revenue forecast|2025|100 B|',
])
def test_forecasts_in_english_annotations_and_tables_are_not_observed_facts(text):
    checked=claims(text)
    assert checked and all(c['status']=='unverifiable' for c in checked)
    assert all(c['verification_reason_code']=='financial_projection_not_observed_fact' for c in checked)


@pytest.mark.parametrize('text',[
    '# 預測情境\n2025年營收:100 B',
    '# Forecast\n2025 Revenue:10 B',
    '# 預測情境\n|事實|期間|單位|\n|---|---|---|\n|年度營收|2025|100 億|',
])
def test_forecast_heading_applies_to_money_claims(text):
    checked=claims(text)
    assert checked and all(c['verification_reason_code']=='financial_projection_not_observed_fact' for c in checked)


def test_new_actual_heading_restores_observed_financial_checks():
    checked=claims('# Forecast\n2025 Revenue:100 B\n# 已觀測年度財報\n2025年營收:100 億')
    assert [c['status'] for c in checked]==['unverifiable','verified']


def test_explicit_foreign_currency_note_does_not_use_twd_source():
    checked=claims('2025年營收:100 億，單位為美元')
    assert len(checked)==1 and checked[0]['status']=='unverifiable'


def test_postfix_amounts_bind_to_their_own_metric():
    checked=claims('2025年已實現10 billion_twd的年度營收與2 billion_twd的淨利。')
    assert len(checked)==2
    assert [c['financial_metric'] for c in checked]==['營收','淨利']
    assert all(c['status']=='verified' for c in checked)
    checked=claims('2025年已實現10 billion_twd的年度營收與10 billion_twd的淨利。')
    assert [c['status'] for c in checked]==['verified','mismatch']


def test_per_unit_profit_explanation_is_not_total_income():
    checked=claims('TTM獲利品質：每賺進1元淨利，實際卻流出超過1元現金。')
    assert checked and all(c['status']=='unverifiable' for c in checked)
    assert checked[0]['verification_reason_code']=='financial_amount_scope_unbound'
