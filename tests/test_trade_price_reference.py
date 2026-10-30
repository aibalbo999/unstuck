"""Offline public checks; original-data replay remains in the local private corpus."""
import copy

import json

from pathlib import Path

from trade_price_reference import price_reference_issues, snapshot_price_reference_issues

def catalog():
    return {'short_term_market_context': {'daily_market_data': {'availability':'available','source':'fixture','as_of':'2026-10-07','price_adjustment_basis':'fixture adjusted','bars':[{'date':'2026-09-11','low':846,'high':930,'close':900}]}}}

def payload():
    return {'support_level':'846','resistance_level':'930','support_source_refs':['short_term_market_context.daily_market_data.bars[0].low'],'resistance_source_refs':['short_term_market_context.daily_market_data.bars[0].high']}

def test_exact_historical_prices_are_allowed():
    assert price_reference_issues(payload(), catalog()) == []

def test_both_numeric_contradictions_are_rejected_without_replacement():
    p=payload();p['support_level']='889';p['resistance_level']='922';before=copy.deepcopy(p)
    assert price_reference_issues(p,catalog()) == ['support_level_source_value_mismatch','resistance_level_source_value_mismatch']
    assert p == before

def test_missing_or_invalid_reference_is_not_claimed_as_proven_mismatch():
    p=payload();p['support_source_refs']=['short_term_market_context.daily_market_data.bars[9].low']
    assert price_reference_issues(p,catalog()) == ['support_level_source_observation_unverified']

def test_prose_or_range_does_not_pretend_to_be_direct_quote():
    p=payload();p['support_level']='分析區間 840–850'
    assert price_reference_issues(p,catalog()) == ['support_level_source_scalar_unverified']

def typed_payload(kind='direct_reference', operation='identity'):
    p=payload()
    p['price_level_evidence']=[{'field':field,'kind':kind,'operation':operation,'inputs':[{'ref':p[role][0],'observed_date':'2026-09-11','window_sessions':1,'price_basis':None}]} for field,role in [('support_level','support_source_refs'),('resistance_level','resistance_source_refs')]]
    return p

def test_typed_direct_quote_and_metadata():
    assert price_reference_issues(typed_payload(),catalog()) == []

def test_date_period_and_price_scope_are_not_numeric_match():
    p=typed_payload();p['price_level_evidence'][0]['inputs'][0].update(observed_date='2026-10-07',window_sessions=52,price_basis='exchange raw')
    c=catalog();c['short_term_market_context']['daily_market_data']['price_adjustment_basis']='adjusted'
    assert price_reference_issues(p,c)==['support_level_source_date_mismatch','support_level_source_period_mismatch','support_level_source_scope_mismatch']

def test_reproducible_derived_price_is_not_required_to_equal_an_input():
    p=typed_payload();refs=[p['support_source_refs'][0],p['resistance_source_refs'][0]]
    p['support_source_refs']=refs;p['support_level']='888'
    p['price_level_evidence'][0]={'field':'support_level','kind':'derived','operation':'mean','inputs':[{'ref':ref,'observed_date':'2026-09-11','window_sessions':1} for ref in refs]}
    assert price_reference_issues(p,catalog())==[]
    p['support_level']='846'
    assert price_reference_issues(p,catalog())==['support_level_source_value_mismatch']

def test_derived_label_without_reproducible_formula_cannot_bypass_gate():
    p=typed_payload('derived','invented');p['support_level']='888'
    assert 'support_level_source_derivation_unverified' in price_reference_issues(p,catalog())

def test_unknown_basis_is_unverified_and_never_declared_mismatch():
    p=typed_payload();p['price_level_evidence'][0]['inputs'][0]['price_basis']='exchange raw'
    c=catalog();c['short_term_market_context']['daily_market_data'].pop('price_adjustment_basis')
    assert price_reference_issues(p,c)==['support_level_source_scope_unverified']

def test_sma_window_and_rounding_are_checked():
    p=typed_payload();ref='short_term_market_context.technical_indicators.sma_20';p['support_source_refs']=[ref];p['support_level']='846'
    p['price_level_evidence'][0]['inputs']=[{'ref':ref,'observed_date':'2026-10-07','window_sessions':20}]
    c=catalog();c['short_term_market_context']['technical_indicators']={'availability':'available','source':'fixture','as_of':'2026-10-07','sma_20':846.123}
    assert price_reference_issues(p,c)==[]
    p['price_level_evidence'][0]['inputs'][0]['window_sessions']=5
    assert price_reference_issues(p,c)==['support_level_source_period_mismatch']

def test_typed_fields_survive_runtime_normalization():
    from structured_output_normalize_dispatch import normalize_structured_output
    from test_trade_source_completion import setup_payload
    raw=setup_payload();raw['price_level_evidence']=typed_payload()['price_level_evidence']
    normalized=normalize_structured_output(24,raw)
    assert normalized['price_level_evidence']==raw['price_level_evidence']

def test_derived_inputs_with_unknown_or_different_price_basis_are_unverified():
    p=typed_payload();p['support_level']='888';refs=[p['support_source_refs'][0],p['resistance_source_refs'][0]]
    p['support_source_refs']=refs;p['price_level_evidence'][0]={'field':'support_level','kind':'derived','operation':'mean','inputs':[{'ref':ref} for ref in refs]}
    c=catalog();c['short_term_market_context']['daily_market_data'].pop('price_adjustment_basis')
    assert price_reference_issues(p,c)==['support_level_source_derivation_scope_unverified']

def test_new_contract_requires_typed_field_and_schema_exposes_formula():
    from trade_source_contract import missing_trade_fields,CONTRACT_VERSION
    from structured_output_risk_models import SwingTradeSetup
    from test_trade_source_completion import setup_payload
    p=setup_payload();context={'_trade_source_manifest':{'version':CONTRACT_VERSION}}
    assert 'price_level_evidence' in missing_trade_fields(p,context=context)
    p['price_level_evidence']=[]
    assert 'price_level_evidence' not in missing_trade_fields(p,context=context)
    assert SwingTradeSetup.model_json_schema()['$defs']['PriceLevelEvidence']['properties']['kind']['enum']==['direct_reference','derived']

def test_runtime_contract_keeps_typed_proof_and_degrades_proven_mismatch():
    from trade_source_contract import bind_trade_payload,CONTRACT_VERSION
    from test_trade_source_completion import setup_payload
    p=setup_payload();p.update(typed_payload());p.update(trade_direction='Neutral',entry_zone='N/A',target_price='N/A',stop_loss='N/A',core_catalyst='等待確認後再重新評估',catalyst_source_refs=[])
    context={'data':{},'_trade_source_manifest':{'version':CONTRACT_VERSION,'visible':True,'catalog':catalog(),'fingerprint':'fixture'}}
    _,assessment=bind_trade_payload(p,context)
    assert assessment['status']=='observation'
    assert assessment['price_reference_checks'][0]['kind']=='direct_reference'
    p['support_level']='889';_,assessment=bind_trade_payload(p,context)
    assert assessment['status']=='degraded'
    assert assessment['price_reference_checks'][0]['status']=='mismatch'
    assert 'support_level_source_value_mismatch' in assessment['reason_codes']
