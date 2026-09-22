"""September 22 retained input/report excerpts; no regenerated financial values."""
import copy
import json
from pathlib import Path
import pytest
from institutional_evidence import institutional_evidence_issues
from test_institutional_evidence import data

ROWS=json.loads((Path(__file__).parent/'fixtures/institutional_20260922_blocked.json').read_text())


def check(row):
    return institutional_evidence_issues(row['analysis'], {'ticker':row['ticker'],'institutional_trading':row['institutional_data']})


@pytest.mark.parametrize('ticker', ['2883.TW','2618.TW','2033.TW','6715.TW','4958.TW','2610.TW'])
def test_original_reports_bind_explicit_subject_and_verified_period(ticker):
    row = next(r for r in ROWS if r['ticker']==ticker)
    assert check(row) == []
    changed = copy.deepcopy(row)
    for unit in ('shares', 'thousand_shares'):
        changed['institutional_data'][f'net_buy_{unit}_by_category']['foreign'] = 999999999
    assert check(changed)  # A pass must still depend on the actual numeric source.


@pytest.mark.parametrize('row', [r for r in ROWS if r['ticker'] in {'6168.TW','2321.TW','2891.TW','3605.TW'}], ids=lambda r:r['job_id'][:8])
def test_original_wrong_or_ambiguous_reports_remain_blocked(row):
    assert check(row)
    if row['ticker'] in {'6168.TW','2321.TW','2891.TW'}:
        assert institutional_evidence_issues(row['raw_responses'][-1],
            {'ticker':row['ticker'],'institutional_trading':row['institutional_data']})


def test_bare_trading_days_are_a_statistical_window():
    row=next(r for r in ROWS if r['ticker']=='0050.TW')
    text='根據30個交易日統計，外資累計賣超47,933.12千股，投信累計買超18,988.01千股，自營商累計買超71,773.82千股，三大法人合計淨買超42,828.72千股。'
    assert institutional_evidence_issues(text,{'ticker':row['ticker'],'institutional_trading':row['institutional_data']}) == []


@pytest.mark.parametrize('text', [
    '外資與投信近30日呈現買超趨勢，外資累計買超1576.69千股。',
    '外資近5日呈現買超，累計達1576.69千股。',
    '外資近30日買超1,528,58千股。',
    '法人近5日買超1576.69千張。',
    '法人2026年9月30日買超1599.24千股。',
    '法人2026-09-30買超1599.24千股。',
    '外資近30日買超1528.58千股。投信近5日買超0千股。',
    '法人近30日買超1599.24千股，近5日買超1576.69千股。其中外資買超1528.58千股。',
    '法人近30日買超1599.24千股。\n## 新觀測\n同期間外資買超1528.58千股。',
    '法人近30日買超1599.24千股。2026-09-18其中外資買超1528.58千股。',
    '法人近30日買超1599.24千股。\n\n同期間外資買超1528.58千股。',
])
def test_subject_period_scope_and_numeric_errors_are_not_skipped(data,text):
    assert institutional_evidence_issues(text,data)


@pytest.mark.parametrize('zero', [None, 1])
def test_zero_activity_words_need_same_period_zero_source(data,zero):
    for key in ['net_buy_shares_by_category','net_buy_thousand_shares_by_category']:
        data['institutional_trading'][key]['investment_trust']=zero
    text='外資近30日買超1528.58千股，自營商買超70.67千股，投信無買賣超，合計買超1599.24千股。'
    assert institutional_evidence_issues(text,data)


def test_zero_activity_total_does_not_allow_two_subgroups(data):
    assert institutional_evidence_issues('外資近30日買超1528.58千股，投信無買賣超，合計買超1599.24千股。',data)


@pytest.mark.parametrize('prefix', [
    '法人近30日買超9999千股。',
    '法人近30日買超1599.24千張。',
    '法人2026-09-18買超965.04千股。',
    '法人近5日買超1576.69千股。',
])
def test_unverified_or_different_window_cannot_license_following_claim(data,prefix):
    assert institutional_evidence_issues(prefix+'其中外資買超1528.58千股。',data)


def test_zero_evidence_and_antecedent_must_be_among_allowed_refs(data):
    from institutional_evidence import institutional_evidence_records
    rows=institutional_evidence_records(data)
    text='外資近30日買超1528.58千股，自營商買超70.67千股，投信無成交紀錄，合計買超1599.24千股。'
    refs=[r['path'] for r in rows if r['population']!='investment_trust']
    assert institutional_evidence_issues(text,data,allowed_paths=refs)


def test_malformed_commas_do_not_become_valid_even_if_stripped_number_matches(data):
    for unit in ('shares','thousand_shares'):
        data['institutional_trading'][f'net_buy_{unit}_by_category']['foreign']=4716033 * (1000 if unit=='shares' else 1)
    assert institutional_evidence_issues('外資近30日買超47,160,33千股。',data)


def test_inherited_observation_uses_the_matched_record_not_first_same_window():
    rows=[]
    for population,value,day in [('total',999,'2026-09-20'),('total',1599.24,'2026-09-21'),
                                ('foreign',111,'2026-09-20'),('foreign',222,'2026-09-21')]:
        rows.append({'population':population,'value':value,'unit':'thousand_shares',
                     'window':{'kind':'trailing_trading_days','trading_days':30},
                     'observed_at':day,'provider':'verified fixture'})
    data={'ticker':'2033.TW','institutional_evidence':{'records':rows}}
    assert institutional_evidence_issues('法人近30日買超1599.24千股。其中外資買超111千股。',data)
    assert institutional_evidence_issues('法人近30日買超1599.24千股。其中外資買超222千股。',data)==[]


def test_zero_activity_cannot_borrow_an_older_observation_of_same_window(data):
    from institutional_evidence import institutional_evidence_records
    rows=institutional_evidence_records(data)
    old=[]
    for row in rows:
        if row['population']=='investment_trust':
            old.append({**row,'observed_at':'2026-09-20'})
            row['value']=1
        if row['population']=='total' and row['window'].get('trading_days')==30:
            old.append({**row,'observed_at':'2026-09-20','value':999})
    context={'ticker':'2033.TW','institutional_evidence':{'records':rows+old}}
    text='外資近30日買超1528.58千股，自營商買超70.67千股，投信無買賣超，合計買超1599.24千股。'
    assert institutional_evidence_issues(text,context)


@pytest.mark.parametrize('switch', ['改看近5日。', '改看2026-09-18觀測。'])
def test_intervening_sentence_scope_switch_blocks_earlier_verified_window(data,switch):
    text='法人近30日買超1599.24千股。'+switch+'其中外資買超1528.58千股。'
    assert institutional_evidence_issues(text,data)
