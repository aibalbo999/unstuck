from copy import deepcopy
import hashlib
import json

import pytest

from evidence_exit_gate import evaluate_report_evidence


def data():
    return {'ticker':'6282.TW','company_name':'康舒','financial_currency':'TWD',
            'years':['2025'],'revenue_history':[31.726761],
            'recent_monthly_revenue':['2026年8月: NT$37.09億','2026年9月: NT$38.33億']}


def claims(text, snapshot=None, pipeline='v3'):
    return evaluate_report_evidence(text, snapshot or {'pipeline':pipeline,'data':data()})['sampled_claims']


@pytest.mark.parametrize('pipeline',['v1','v2','v3','v4'])
@pytest.mark.parametrize('text', ['2026 年 9 月營收達 38.33 億元。',
                               '2026 年 9 月單月營收達 NT$38.33 億。'])
def test_explicit_month_binds_only_same_month_saved_amount(pipeline, text):
    rows = claims(text,pipeline=pipeline)
    assert len(rows)==1
    assert rows[0]['status']=='verified'
    assert rows[0]['financial_period']=='2026-09'
    assert rows[0]['matched_path']=='data.recent_monthly_revenue[1]'
    assert rows[0]['independent_primary_source_verified'] is False


@pytest.mark.parametrize('text',['2026年9月營收:37.09 億','2026年9月營收:38.33 B'])
def test_other_month_or_wrong_unit_is_a_mismatch(text):
    row=claims(text)[0]
    assert row['status']=='mismatch'
    assert row['matched_path']=='data.recent_monthly_revenue[1]'


@pytest.mark.parametrize('text',['9月營收:38.33 億','2025年9月營收:38.33 億',
    '2026年9月平均月營收:38.33 億','2026年9月累計營收:38.33 億',
    '2026年9月預估營收:38.33 億','2026年8月至9月營收:38.33 億',
    '2026年9月季度營收:38.33 億','2026年9月營收:38.33 億美元'])
def test_missing_or_ambiguous_month_scope_stays_unverifiable(text):
    rows=claims(text)
    assert rows and all(r['status']=='unverifiable' for r in rows)


@pytest.mark.parametrize('mutation',[
    {'financial_currency':'USD'}, {'financial_currency':None},
    {'recent_monthly_revenue':['2026年9月: NT$38.33億','2026年9月: NT$37.09億']},
    {'recent_monthly_revenue':['2026年9月: US$38.33億']},
    {'recent_monthly_revenue':[True]}, {'recent_monthly_revenue':None},
])
def test_source_currency_and_unique_month_required(mutation):
    rows=claims('2026年9月營收:38.33 億',{'data':{**data(),**mutation}})
    assert rows and all(r['status']=='unverifiable' for r in rows)


@pytest.mark.parametrize('text', ['台積電2026年9月營收:38.33 億',
    '2026年9月台積電營收:38.33 億', '2026年9月營收（台積電）:38.33 億',
    '2026年9月營收:38.33 億（台積電）', '2026年9月38.33億的營收（台積電）',
    '# 同業比較\n2026年9月營收:38.33 億'])
def test_other_issuer_or_implicit_peer_does_not_borrow_target_series(text):
    rows=claims(text)
    assert rows and all(r['status']=='unverifiable' for r in rows)


def test_explicit_target_in_peer_section_can_use_its_own_series():
    row=claims('# 同業比較\n康舒2026年9月營收:38.33 億')[0]
    assert row['status']=='verified'


@pytest.mark.parametrize('text', ['2026年9月營收累計達38.33 億',
    '2026年9月營收:38.33 億（累計）', '2026年9月營收截至當月達38.33 億',
    '2026年9月營收月平均達38.33 億', '2026年9月營收（第三季合計）38.33 億',
    '2026年9月38.33億的營收（累計）', '2026年9月38.33億的營收（第三季合計）',
    '2026年9月全年營收38.33億', '2026年9月38.33億的全年營收',
    '2026年9月38.33億的年度營收',
    '# 營收預期\n2026年9月營收:38.33 億', '# 進場觸發條件\n2026年9月營收:38.33 億'])
def test_monthly_partial_scopes_and_conditional_headings_stay_unknown(text):
    rows=claims(text)
    assert rows and all(r['status']=='unverifiable' for r in rows)


@pytest.mark.parametrize('text',['2026年9月38.33億的營收', '2026年9月營收達到38.33億'])
def test_unambiguous_actual_month_amount_word_order_binds(text):
    row=claims(text)[0]
    assert row['status']=='verified'
    assert row['financial_period']=='2026-09'


@pytest.mark.parametrize(('ticker','name'), [('2308.TW','台達電'), ('8163.TW','達方')])
def test_company_alias_is_not_corrupted_by_financial_modifier_cleanup(ticker,name):
    snapshot={'data':{**data(),'ticker':ticker,'company_name':name}}
    row=claims(f'# 同業比較\n{name}2026年9月營收達38.33億',snapshot)[0]
    assert row['status']=='verified'
    other=claims(f'{name}及台積電2026年9月營收達38.33億',snapshot)
    assert other and all(r['status']=='unverifiable' for r in other)


def test_refreshed_data_cannot_replace_original_monthly_input():
    from report_analysis_evidence import capture_analysis_evidence
    original=data()
    original['analysis_input_hash']=hashlib.sha256(json.dumps(original,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()
    original['analysis_input_cutoff']='2026-10-09T03:34:35+00:00'
    packet=capture_analysis_evidence({'data':original})
    current={**original,'recent_monthly_revenue':['2026年9月: NT$99.99億']}
    snapshot={'data':current,'analysis_evidence':packet,'refreshed_without_analysis_rerun':True}
    row=claims('2026年9月營收:38.33 億',snapshot)[0]
    assert row['status']=='verified'
    assert row['matched_path']=='analysis_evidence.sections.analysis_input.data.recent_monthly_revenue[1]'
    corrupt=deepcopy(snapshot)
    corrupt['analysis_evidence']['sections']['analysis_input']['data']['recent_monthly_revenue']=['2026年9月: NT$99.99億']
    assert claims('2026年9月營收:99.99 億',corrupt)[0]['status']=='unverifiable'
