"""Saved content defects: improve generation inputs without rewriting reports."""
import copy
import gzip
import json
from decimal import Decimal
from pathlib import Path
import pytest
from trade_source_guidance import price_source_observations, technical_comparison_facts, source_guidance_text
from trade_price_reference import price_reference_checks
from financial_tools import build_financial_tool_context

CASES = json.loads(gzip.decompress((Path(__file__).parent/'fixtures/report_renderer_oct8_saved.json.gz').read_bytes()))
REJECTED = json.loads(gzip.decompress((Path(__file__).parent/'fixtures/report_content_rejected_oct8.json.gz').read_bytes()))

def catalog(case):
    return case['catalog'] if 'catalog' in case else case['snapshot']['analysis_evidence']['sections']['trade_source_manifest']['data']['catalog']

def payload(case):
    return case['payload'] if 'payload' in case else case['snapshot']['rerun_context']['structured_outputs']['24']

PRICES = [c for c in CASES if c['ticker'] in {'1101.TW','2851.TW','2912.TW','6214.TW'}] + REJECTED

@pytest.mark.parametrize('case', PRICES, ids=lambda c:c['ticker'])
def test_original_six_scope_errors_are_not_accepted_but_exact_source_receipt_removes_guessing(case):
    sources=catalog(case);before=copy.deepcopy(sources);original=copy.deepcopy(payload(case))
    checks=price_reference_checks(original,sources)
    assert any('source_scope_mismatch' in code for check in checks for code in check['reason_codes'])
    corrected=copy.deepcopy(original);receipts={row['ref']:row for row in price_source_observations(sources)}
    for row in corrected['price_level_evidence']:
        for item in row['inputs']:
            receipt=receipts[item['ref']]
            for key in ('observed_date','window_sessions','price_basis'):item[key]=receipt[key]
    after=price_reference_checks(corrected,sources)
    assert after and all(row['status']=='verified' for row in after)
    assert corrected['trade_direction']==original['trade_direction']
    assert corrected['support_level']==original['support_level']
    assert corrected['resistance_level']==original['resistance_level']
    assert sources==before and payload(case)==original
    # This checks input-contract truth, not overall recommendation admission.
    prompt=source_guidance_text(sources)
    assert all(json.dumps(row,ensure_ascii=False) in prompt for row in receipts.values())

def test_saved_walsin_signal_is_arithmetically_wrong_and_prompt_supplies_correct_same_basis_relation():
    case=next(c for c in CASES if c['ticker']=='1605.TW')
    assert '跌破 5 日線' in payload(case)['observed_signal']
    facts=technical_comparison_facts(catalog(case))
    row=next(row for row in facts if row.get('source_refs',[])[-1].endswith('sma_5'))
    assert row['close']>row['average'] and row['relation']=='above'
    assert row['close']==pytest.approx(39.1) and row['average']==pytest.approx(38.98)

def test_saved_taiwan_cement_bullish_order_is_not_supported_by_visible_values():
    case=next(c for c in CASES if c['ticker']=='1101.TW')
    assert '多頭排列' in payload(case)['observed_signal']
    row=next(row for row in technical_comparison_facts(catalog(case)) if 'sma_5_10_20' in row)
    assert row['bullish_order'] is False
    assert row['sma_5_10_20'][0]<row['sma_5_10_20'][1]

@pytest.mark.parametrize('fault',['date','basis','missing_basis','missing_average','nonfinite'])
def test_relative_position_requires_compatible_source_scope_and_finite_input(fault):
    case=next(c for c in CASES if c['ticker']=='1605.TW');source=copy.deepcopy(catalog(case));root=source['short_term_market_context']
    if fault=='date':root['technical_indicators']['as_of']='2026-10-07'
    if fault=='basis':root['technical_indicators']['price_adjustment_basis']='exchange raw'
    if fault=='missing_basis':root['technical_indicators'].pop('price_adjustment_basis')
    if fault=='missing_average':root['technical_indicators'].pop('sma_5')
    if fault=='nonfinite':root['technical_indicators']['sma_5']=float('nan')
    facts=technical_comparison_facts(source)
    if fault in {'date','basis','missing_basis'}:assert facts==[]
    else:assert not any(row.get('source_refs',[])[-1].endswith('sma_5') for row in facts)

def test_saved_century_fcf_conversion_has_tenfold_difference_from_original_prose():
    case=next(c for c in CASES if c['ticker']=='5314.TWO');data=case['snapshot']['analysis_evidence']['sections']['analysis_input']['data'];before=copy.deepcopy(data)
    assert 'FCF）為負值（-0.0256 億元）' in case['markdown']
    tool=build_financial_tool_context(data)
    receipt=next(row for row in tool['money_display_receipts'] if row['field']=='free_cash_flow_raw')
    assert Decimal(receipt['twd'])==Decimal('-25623500')
    assert Decimal(receipt['billion_twd'])==Decimal('-0.0256235')
    assert Decimal(receipt['yi_twd'])==Decimal('-0.256235')
    assert receipt['period_verified'] is False
    assert tool['metric_status']['dcf']['status']=='unavailable'
    assert data==before

def test_display_conversions_do_not_convert_eps_shares_or_create_missing_fcf():
    data={'ticker':'TEST.TW','current_price':10,'eps_ttm_raw':1.2,'shares_outstanding_raw':1000}
    tool=build_financial_tool_context(data)
    assert not any(row['field'] in {'eps','shares_raw','free_cash_flow_raw'} for row in tool['money_display_receipts'])

def test_actual_mode_d_technical_prompt_contains_correct_saved_comparison_without_model_call():
    from agent_runtime.prompting import build_prompt
    from google_prompt_safety import sanitize_google_prompt
    case=next(c for c in CASES if c['ticker']=='1605.TW');data=copy.deepcopy(case['snapshot']['analysis_evidence']['sections']['analysis_input']['data'])
    context={'data':data,'pipeline_id':'v4','analyses':{},'structured_outputs':{}}
    prompt=sanitize_google_prompt(build_prompt(22,data,context))
    assert '同日同價格基準的可重算相對位置' in prompt
    assert '"relation": "above"' in prompt
    assert '不證明穿越' in prompt and '不得把高於寫成跌破' in prompt

@pytest.mark.parametrize('mode,agent',[('v1',1),('v2',14),('v3',19),('v4',24)])
def test_money_receipts_reach_actual_prompt_wire_for_each_mode_without_changing_mode_purpose(mode,agent):
    from agent_runtime.prompting import build_prompt
    data={'ticker':'TEST.TW','company_name':'Test','current_price':26,'free_cash_flow_raw':-25623500}
    context={'data':data,'pipeline_id':mode,'analyses':{},'structured_outputs':{}}
    prompt=build_prompt(agent,data,context)
    assert 'money_display_receipts' in prompt and '-0.256235' in prompt
    if mode!='v4':assert '逐引用價格輸入收據' not in prompt and '同日同價格基準的可重算相對位置' not in prompt

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['ticker'])
def test_common_saved_disclaimer_unit_definition_is_not_company_profit(case):
    from evidence_exit_gate_claims import extract_numeric_claims
    claims=extract_numeric_claims(case['markdown'])
    assert not any(row.get('financial_metric')=='淨利' and row['reported_value']==10 and 'Billion TWD (10億台幣)' in row['raw_text'] for row in claims)

def test_real_company_amount_on_same_line_is_still_checked_with_unit_definition():
    from evidence_exit_gate import evaluate_report_evidence
    markdown='歷史營收、淨利等資料單位為 Billion TWD (10億台幣)；2025年淨利為10億元。'
    source={'data':{'financial_currency':'TWD','years':['2025'],'net_income_history':[0.1]}}
    result=evaluate_report_evidence(markdown,source)
    assert result['failed_count']>=1 and result['verdict']=='rejected'
    assert any(row.get('financial_metric')=='淨利' and row.get('financial_actual') for row in result['sampled_claims'])
