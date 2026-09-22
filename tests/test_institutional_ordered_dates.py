"""Saved paired dates bind each flow amount, without widening numeric tolerance."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from institutional_evidence import institutional_evidence_issues, institutional_evidence_diagnostics

ROWS=json.loads((Path(__file__).parent/'fixtures/institutional_date_pairs_20260922.json').read_text())

def exact_pair():
    return ROWS[0]['text'].replace('634 張', '634.53 張').replace('1,318 張','1,318.28 張')


def test_2441_original_truncation_keeps_value_errors_but_correct_dates():
    result=institutional_evidence_diagnostics(ROWS[0]['text'],ROWS[0]['data'])
    pair=[d for d in result if '634' in d['claim'] or '1,318' in d['claim']]
    assert len(pair)==2
    assert [d['window'] for d in pair]==[{'kind':'day','date':'2026-09-14'}, {'kind':'day','date':'2026-09-15'}]
    assert all('同主體同期間淨額不符' in d['reason'] for d in pair)


def test_explicit_dates_exact_values_pass_without_using_five_day_aggregate():
    assert institutional_evidence_issues(exact_pair(),ROWS[0]['data'])==[]


def test_6715_original_first_day_and_explicit_dated_peak_both_pass():
    assert institutional_evidence_issues(ROWS[1]['text'],ROWS[1]['data'])==[]

@pytest.mark.parametrize('old,new', [('634.53','999'),('1,318.28','999'),('14 日與 15 日','13 日與 15 日'),('法人合計','外資'),('張','千張')])
def test_paired_dates_wrong_value_date_population_and_unit_stay_blocked(old,new):
    assert institutional_evidence_issues(exact_pair().replace(old,new),ROWS[0]['data'])

@pytest.mark.parametrize('old,new', [('55.77','999'),('354.47','999'),('09-16','09-17'),('09-14 至 09-17','09-13 至 09-17'),('單日買超量','單日賣超量')])
def test_ordered_range_wrong_first_or_peak_value_date_direction_stay_blocked(old,new):
    assert institutional_evidence_issues(ROWS[1]['text'].replace(old,new),ROWS[1]['data'])

@pytest.mark.parametrize('index', [0,1])
def test_missing_or_invisible_daily_sources_never_borrow_aggregate(index):
    text=exact_pair() if index==0 else ROWS[index]['text']
    data=deepcopy(ROWS[index]['data']);data['institutional_trading']['daily_total_net_buy_last_10']=[]
    assert institutional_evidence_issues(text,data)
    assert institutional_evidence_issues(text,ROWS[index]['data'],allowed_paths=[])


def test_second_date_value_is_checked_even_when_first_is_valid():
    text=exact_pair();data=deepcopy(ROWS[0]['data'])
    data['institutional_trading']['daily_total_net_buy_last_10'][-1]['net_buy_thousand_shares']=3000
    assert institutional_evidence_issues(text,data)


def test_explicit_peak_outside_range_is_not_allowed():
    text=ROWS[1]['text'].replace('09-16','09-18')
    data=deepcopy(ROWS[1]['data']);data['institutional_trading']['daily_total_net_buy_last_10'].append({'date':'2026-09-18','net_buy_thousand_shares':354.47})
    assert institutional_evidence_issues(text,data)

@pytest.mark.parametrize('text', [
    '法人9月14日與15日分別買超634.53張與1,318.28張',
    '法人2026年9月14日與9月15日分別買超634.53張與1,318.28張',
])
def test_explicit_pair_without_previous_lookback_has_correct_scope(text):
    assert institutional_evidence_issues(text, ROWS[0]['data']) == []

@pytest.mark.parametrize('text', [
    '法人9月14日與15日分別買超634.53張與999張',
    '外資9月14日與15日分別買超634.53張與1,318.28張',
    '法人9月15日與14日分別買超1,318.28張與634.53張',
    '法人2025年9月14日與15日分別買超634.53張與1,318.28張',
    '法人9月14日與32日分別買超634.53張與1,318.28張',
])
def test_invalid_or_other_pair_scope_has_no_fallback(text):
    assert institutional_evidence_issues(text, ROWS[0]['data'])


def test_multiple_possible_years_do_not_guess_pair_year():
    data = deepcopy(ROWS[0]['data'])
    data['institutional_trading']['daily_total_net_buy_last_10'].append({'date':'2025-09-14','net_buy_thousand_shares':634.53})
    assert institutional_evidence_issues(exact_pair(), data)


def test_missing_peak_date_keeps_scope_unknown():
    assert institutional_evidence_issues(ROWS[1]['text'].replace('（09-16）',''), ROWS[1]['data'])

@pytest.mark.parametrize('tail', [
    '，及999張。', ',及999張。', '、999張。', '與999張。', '，999張。',
    '（近5日）。', '(近5日)。', '（2026-09-18）。',
])
def test_date_pair_cannot_ignore_third_amount_or_attached_conflicting_scope(tail):
    text='法人9月14日與15日分別買超634.53張與1318.28張'+tail
    assert institutional_evidence_issues(text,ROWS[0]['data'])


def test_unrelated_following_sentence_does_not_change_pair_scope():
    text='法人9月14日與15日分別買超634.53張與1318.28張。9月15日法人買超1318.28張。'
    assert institutional_evidence_issues(text,ROWS[0]['data'])==[]


def test_rejected_pair_tail_keeps_diagnostic_offsets_on_original_amounts():
    text='法人 9月14日與15日分別買超 634.53 張與 1318.28 張，及999張。'
    diagnostics=institutional_evidence_diagnostics(text,ROWS[0]['data'])
    assert diagnostics
    assert all(text[slice(*d['span'])]==d['claim'] for d in diagnostics)
    assert all(d['window']=={'kind':'explicit_date_pair_unknown'} for d in diagnostics)
