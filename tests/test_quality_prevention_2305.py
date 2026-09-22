import copy
import json
from pathlib import Path
import pytest
from institutional_evidence import institutional_evidence_issues
from trade_execution_contract import contains_trade_order
from final_audit_mode_contracts import v4_trade_setup_contract_issues

FIXTURE=json.loads((Path(__file__).parent/'fixtures/institutional_2305_20260922.json').read_text())

@pytest.mark.parametrize('candidate',[c for c in FIXTURE['candidates'] if c['agent']==24],ids=lambda c:str(c['event_id']))
def test_real_neutral_reassessment_is_not_an_order(candidate):
    value=json.loads(candidate['raw'])
    assert not contains_trade_order(value['core_catalyst'])
    assert v4_trade_setup_contract_issues(value)==[]

@pytest.mark.parametrize('text',[
 '等待突破後買入。','重新評估後立即進場。',
 '重新評估是否有明確進場時點；確認後買入10張。',
 '重新評估進場條件。次日開倉。',
 '重新評估是否有明確進場時點並立即進場。',
])
def test_actual_orders_still_blocked(text):
    assert contains_trade_order(text)


def test_precise_diagnostics_reference_the_original_span_and_available_scope():
    import institutional_evidence as module
    assert hasattr(module,'institutional_evidence_diagnostics')
    text='- **外資** 累積淨買超 10,252.25 千股。'
    result=module.institutional_evidence_diagnostics(text,FIXTURE['data'])
    assert len(result)==1
    item=result[0]
    assert text[slice(*item['span'])]==item['claim']=='淨買超 10,252.25 千股'
    assert item['population']=='foreign' and item['window'] is None
    assert item['same_scope_sources']==[]
    assert all(r['population']=='foreign' and r['window']['trading_days']==30 for r in item['available_population_sources'])
    assert item['available_population_sources']


def test_typed_source_prompt_has_explicit_scope_and_preserves_source():
    from institutional_evidence_prompt import build_institutional_source_prompt
    before=copy.deepcopy(FIXTURE['data'])
    prompt=build_institutional_source_prompt(FIXTURE['data'])
    assert '近30個交易日' in prompt and '截至2026-09-22' in prompt
    assert 'institutional_trading.net_buy_thousand_shares_by_category.foreign' in prompt
    assert '10252.25千股' in prompt and '投信' in prompt and '19千股' in prompt
    assert FIXTURE['data']==before
    assert institutional_evidence_issues(prompt,FIXTURE['data'])==[]


def test_retry_instruction_keeps_exact_diagnostics_without_reflection_provider():
    from agent_runtime.repair_reflection import build_audit_retry_instruction
    text='外資累積淨買超10252.25千股。'
    prompt=build_audit_retry_instruction(23,['法人證據紅線'],previous_text=text,data=FIXTURE['data'])
    assert '淨買超10252.25千股' in prompt and 'foreign' in prompt
    assert 'trading_days' in prompt and '30' in prompt
    assert '不得' in prompt


def test_no_source_or_malformed_source_does_not_become_a_verified_fact():
    from institutional_evidence_prompt import build_institutional_source_prompt
    for data in ({}, {'ticker':'2305.TW','institutional_evidence':{'records':[None,{}, {'value':None}]}}):
        assert '沒有可逐項核驗' in build_institutional_source_prompt(data)


@pytest.mark.parametrize('mutation', [
    '外資近5個交易日淨買超10252.25千股。',
    '投信近30個交易日淨買超10252.25千股。',
    '外資近30個交易日淨買超10252.25千張。',
    '外資近30個交易日淨賣超10252.25千股。',
    '截至2026-09-21，外資近30個交易日淨買超10252.25千股。',
    '外資近30個交易日淨買超11252.25千股。',
])
def test_typed_fact_semantic_mutations_stay_blocked(mutation):
    from institutional_evidence import institutional_evidence_diagnostics
    assert institutional_evidence_issues(mutation,FIXTURE['data'])
    assert institutional_evidence_diagnostics(mutation,FIXTURE['data'])


def test_allowed_refs_remain_a_hard_diagnostic_boundary():
    from institutional_evidence import institutional_evidence_diagnostics
    result=institutional_evidence_diagnostics('外資近30日買超10252.25千股。',FIXTURE['data'],allowed_paths=[])
    assert result and result[0]['same_scope_sources']==[]
    assert result[0]['available_population_sources']==[]


def test_agent23_production_prompt_includes_verified_facts_without_dropping_input():
    from agent_runtime.prompting import build_prompt
    data={**FIXTURE['data'],'company_name':'fixture2305','source_sentinel':'complete_original_input'}
    prompt=build_prompt(23,data,{'pipeline_id':'v4','analyses':{}})
    assert '法人逐項來源契約' in prompt and '近30個交易日' in prompt
    assert 'institutional_trading.net_buy_shares_by_category.foreign' in prompt
    assert 'daily_total_net_buy_last_10' in prompt


def test_typed_catalog_without_raw_path_keeps_stable_record_reference():
    from institutional_evidence import institutional_evidence_records, institutional_evidence_diagnostics
    from institutional_evidence_prompt import build_institutional_source_prompt
    record=copy.deepcopy(next(r for r in institutional_evidence_records(FIXTURE['data']) if r['population']=='foreign'))
    record.pop('path')
    data={'ticker':'2305.TW','short_term_market_context':{'institutional_evidence':{'records':[{},record]}}}
    prompt=build_institutional_source_prompt(data)
    assert 'source ref=short_term_market_context.institutional_evidence.records[1]' in prompt
    diagnostic=institutional_evidence_diagnostics('外資買超1千股。',data)[0]
    assert diagnostic['available_population_sources'][0]['source_ref'].endswith('records[1]')


@pytest.mark.parametrize('field,value',[('unit','unknown'),('observed_at',None),('value',None),('provider','')])
def test_invalid_typed_record_does_not_enter_fact_prompt(field,value):
    from institutional_evidence import institutional_evidence_records
    from institutional_evidence_prompt import build_institutional_source_prompt
    record=copy.deepcopy(institutional_evidence_records(FIXTURE['data'])[0]);record[field]=value
    assert '沒有可逐項核驗' in build_institutional_source_prompt({'institutional_evidence':{'records':[record]}})
