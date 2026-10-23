"""Explicit observed-fact reuse must preserve every existing quality predicate."""
import copy
import json

import pytest

from structured_output_runtime import process_agent_response
from trade_source_contract import CONTRACT_VERSION, bind_trade_payload

REF = 'short_term_market_context.technical_indicators.sma_5'
TOKEN = '@observed_signal'


def case():
    fact = '2026-10-22 SMA5=110'
    payload = {'trade_direction': 'Neutral', 'entry_zone': 'N/A', 'target_price': 'N/A',
        'stop_loss': 'N/A', 'support_level': 'N/A', 'resistance_level': 'N/A',
        'risk_level': 'High', 'price_level_evidence': [], 'support_source_refs': [],
        'resistance_source_refs': [], 'catalyst_source_refs': [REF],
        'core_catalyst': TOKEN, 'core_catalyst_reference': 'observed_signal',
        'observed_signal': fact, 'observed_source_refs': [REF], 'event_catalyst': None,
        'recheck_condition': '等待量能回升後再重新評估', 'financial_risk_flags': []}
    context = {'data': {'technical_indicators': {'sma_5': 110}}, 'structured_outputs': {},
        '_trade_source_manifest': {'version': CONTRACT_VERSION, 'visible': True,
            'fingerprint': 'fixture-source', 'catalog': {'short_term_market_context': {
            'technical_indicators': {'availability': 'available', 'source': 'fixture',
                'as_of': '2026-10-22', 'sma_5': 110}}}}}
    return payload, context


def test_explicit_fact_reference_renders_exact_validated_observation_once():
    payload, context = case()
    raw = json.dumps(payload)
    process_agent_response(24, raw, context)
    actual = context['structured_outputs'][24]
    assert actual['core_catalyst'] == payload['observed_signal']
    assert actual['source_assessment']['status'] == 'observation'
    receipt = actual['core_catalyst_resolution']
    assert receipt['status'] == 'resolved'
    assert receipt['original_core_catalyst'] == TOKEN
    assert receipt['basis'] == 'explicit_field_reference_after_existing_source_checks'
    assert payload['core_catalyst'] == TOKEN


def test_reference_does_not_replace_a_different_factual_assertion():
    payload, context = case()
    payload['core_catalyst'] = 'SMA5=90，法人已連續買超'
    raw = json.dumps(payload)
    process_agent_response(24, raw, context)
    actual = context['structured_outputs'][24]
    assert actual['source_assessment']['status'] == 'degraded'
    assert 'core_catalyst_semantic_mismatch' in actual['source_assessment']['reason_codes']
    assert actual['source_assessment']['rejection_diagnostics']['original_core_catalyst'] == payload['core_catalyst']
    assert 'core_catalyst_resolution' not in actual


@pytest.mark.parametrize('observed', ['@observed_signal', '觀測值為 @observed_signal'])
def test_reference_cannot_resolve_a_reserved_placeholder_as_an_observation(observed):
    payload, context = case()
    payload['observed_signal'] = observed
    process_agent_response(24, json.dumps(payload), context)
    assert not context['structured_outputs'].get(24)
    assert context['_trade_incomplete_fields']


@pytest.mark.parametrize('change', ['missing_observed', 'invalid_ref', 'not_visible', 'bad_recheck', 'wrong_reference', 'missing_required', 'wrong_refs'])
def test_explicit_reference_cannot_publish_incomplete_or_unsupported_facts(change):
    payload, context = case()
    if change == 'missing_observed': payload['observed_signal'] = None
    if change == 'invalid_ref': payload['observed_source_refs'] = ['short_term_market_context.invented']
    if change == 'not_visible': context['_trade_source_manifest']['visible'] = False
    if change == 'bad_recheck': payload['recheck_condition'] = '外資近5日買超9999千股'
    if change == 'wrong_reference': payload['core_catalyst_reference'] = 'agent_reports.22'
    if change == 'missing_required': payload.pop('risk_level')
    if change == 'wrong_refs': payload['catalyst_source_refs'] = []
    process_agent_response(24, json.dumps(payload), context)
    assert 24 not in context['structured_outputs']
    assert context['_trade_incomplete_fields']


def test_ordinary_outputs_still_obey_exact_semantic_matching():
    payload, context = case()
    payload.pop('core_catalyst_reference')
    payload['core_catalyst'] = '一個與觀測不同的主張'
    original = copy.deepcopy(payload)
    _, assessment = bind_trade_payload(payload, context)
    assert assessment['status'] == 'degraded'
    assert 'core_catalyst_semantic_mismatch' in assessment['reason_codes']
    assert payload == original


def test_runtime_prompt_uses_raw_fact_contract_for_both_upstream_roles(monkeypatch):
    from agent_runtime import prompting
    monkeypatch.setattr(prompting, '_enforce_prompt_token_budget', lambda prompt, *args, **kwargs: prompt)
    for role in (22, 23):
        monkeypatch.setitem(prompting.ANALYSIS_PROMPTS, role, '{{ fin_data }}')
        prompt = prompting.build_prompt(role, {'ticker': '2330.TW', 'company_name': 'fixture'}, {})
        assert '【短線事實與判斷輸出契約】' in prompt
        assert 'agent_reports' in prompt and '獨立證據' in prompt
        assert 'evidence_items' in prompt and 'source_refs' in prompt
        assert 'data.technical_indicators' in prompt if role == 22 else 'institutional_trading' in prompt


def test_optional_reference_is_exposed_without_changing_required_schema():
    from structured_output_risk_models import SwingTradeSetup
    schema = SwingTradeSetup.model_json_schema()
    assert 'core_catalyst_reference' in schema['properties']
    assert 'core_catalyst_reference' not in schema['required']
    assert 'core_catalyst' in schema['required']
    assert schema['properties']['core_catalyst']['type'] == 'string'


def test_reference_schema_remains_serializable_for_genai_without_const():
    from agent_runtime.generation_config import build_generation_config
    from structured_output_risk_models import SwingTradeSetup
    from google.genai import types
    schema = SwingTradeSetup.model_json_schema()
    assert schema['$defs']['TradeCoreReference']['enum'] == ['observed_signal']
    assert '"const"' not in json.dumps(schema)
    config = build_generation_config(24)
    encoded = config.model_dump(mode='json', exclude_none=True)
    assert 'core_catalyst_reference' in encoded['response_schema']['properties']
    assert types.GenerateContentConfig.model_validate(encoded).response_schema


def test_forged_model_resolution_is_not_adopted():
    payload, context = case()
    payload.pop('core_catalyst_reference')
    payload['core_catalyst'] = payload['observed_signal']
    payload['core_catalyst_resolution'] = {'status': 'resolved', 'raw_sha256': 'forged'}
    process_agent_response(24, json.dumps(payload), context)
    assert 'core_catalyst_resolution' not in context['structured_outputs'][24]


def test_provider_incomplete_reference_never_normalizes_as_complete():
    payload, context = case()
    process_agent_response(24, json.dumps(payload), context,
        completion_diagnostics={'finish_reasons': ['MAX_TOKENS'], 'stream_completed': False})
    assert not context['structured_outputs'].get(24)
    assert context['_trade_incomplete_fields'] == ['provider_output_incomplete']


@pytest.mark.parametrize('diagnostics', [{}, {'finish_reasons': []}, {'stream_completed': True}])
def test_unobserved_reparse_cannot_replace_known_incomplete_reference(diagnostics):
    payload, context = case()
    raw = json.dumps(payload)
    process_agent_response(24, raw, context,
        completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    process_agent_response(24, raw, context, completion_diagnostics=diagnostics)
    assert not context['structured_outputs'].get(24)
    assert context['_trade_incomplete_fields'] == ['provider_output_incomplete']


def test_explicit_reference_with_false_population_or_period_stays_incomplete():
    payload, context = case()
    ref = 'short_term_market_context.institutional_evidence.records[0]'
    context['_trade_source_manifest']['catalog']['short_term_market_context']['institutional_evidence'] = {
        'records': [{'population': 'total', 'window': {'kind': 'trailing_trading_days', 'trading_days': 5},
        'unit': 'thousand_shares', 'value': 100, 'observed_at': '2026-10-22', 'provider': 'fixture'}]}
    payload.update(observed_signal='截至2026-10-22，外資近30個交易日淨買超100千股。',
        observed_source_refs=[ref], catalyst_source_refs=[ref])
    process_agent_response(24, json.dumps(payload), context)
    assert not context['structured_outputs'].get(24)
    assert 'catalyst_evidence_scope_mismatch' in context['_trade_core_reference_rejection']['reason_codes']


def test_identical_core_can_record_explicit_resolution_without_changing_fact():
    payload, context = case()
    payload['core_catalyst'] = payload['observed_signal']
    process_agent_response(24, json.dumps(payload), context)
    actual = context['structured_outputs'][24]
    assert actual['core_catalyst'] == payload['observed_signal']
    assert actual['source_assessment']['status'] == 'observation'
    assert actual['core_catalyst_resolution']['status'] == 'resolved'


def test_fact_guidance_does_not_upgrade_generated_plans_to_evidence():
    from evidence_exit_gate import evaluate_report_evidence
    # Repeating an upstream plan still lacks independent raw evidence.
    snapshot = {'rerun_context': {'structured_outputs': {'24': {'support_level': '95'}}}}
    result = evaluate_report_evidence('- 支撐位: 95元', snapshot)
    assert result['unverifiable_count'] == 1
    assert result['sampled_claims'][0]['verification_reason_code'] == 'generated_analysis_not_independent_evidence'
    # Dated, explicitly named raw SMA facts bind without borrowing plan prices.
    snapshot = {'data': {'technical_indicators': {'availability': 'available', 'source': 'fixture',
        'as_of': '2026-10-22', 'sma_5': 95, 'missing_indicators': []}}}
    result = evaluate_report_evidence('- 2026-10-22 SMA5: 95元', snapshot)
    assert result['verified_count'] == 1 and result['failed_count'] == 0
    result = evaluate_report_evidence('- 2026-10-22 SMA5: 105元', snapshot)
    assert result['failed_count'] == 1


def test_upstream_fact_examples_have_exact_raw_refs_and_keep_source_limits(monkeypatch):
    from trade_output_contract_guidance import trade_fact_output_instruction
    technical = {'availability': 'available', 'source': 'fixture', 'as_of': '2026-10-22',
        'sma_5': 110, 'sma_10': 109, 'missing_indicators': []}
    prompt = trade_fact_output_instruction(22, {'technical_indicators': technical})
    assert '2026-10-22 SMA5: 110元（source ref=data.technical_indicators.sma_5）' in prompt
    assert 'SMA10: 109元' in prompt
    technical['availability'] = 'unavailable'
    assert 'SMA5: 110' not in trade_fact_output_instruction(22, {'technical_indicators': technical})
    data = {'ticker': '2330.TW', 'company_name': 'fixture', 'institutional_trading': {'source': 'FinMind TaiwanStockInstitutionalInvestorsBuySell', 'latest_date': '2026-10-22',
        'lookback_trading_days': 30, 'net_buy_thousand_shares_by_category': {'foreign': -100}}}
    from agent_runtime import prompting
    monkeypatch.setattr(prompting, '_enforce_prompt_token_budget', lambda prompt, *args, **kwargs: prompt)
    monkeypatch.setitem(prompting.ANALYSIS_PROMPTS, 23, '{{ fin_data }}')
    prompt = prompting.build_prompt(23, data, {})
    assert '外資近30個交易日淨賣超100千股' in prompt
    assert 'institutional_trading.net_buy_thousand_shares_by_category.foreign' in prompt
    assert '連續買超' in prompt  # documented limit, never a generated finding.


def test_subset_core_fact_still_rejected_even_if_each_individual_fact_is_valid():
    payload, context = case()
    payload.pop('core_catalyst_reference')
    payload['core_catalyst'] = '2026-10-22 SMA5=110'
    payload['observed_signal'] += '；2026-10-22 SMA10=109'
    ref = 'short_term_market_context.technical_indicators.sma_10'
    payload['observed_source_refs'].append(ref)
    context['_trade_source_manifest']['catalog']['short_term_market_context']['technical_indicators']['sma_10'] = 109
    process_agent_response(24, json.dumps(payload), context)
    actual = context['structured_outputs'][24]
    assert 'core_catalyst_semantic_mismatch' in actual['source_assessment']['reason_codes']
    assert actual['source_assessment']['status'] == 'degraded'
