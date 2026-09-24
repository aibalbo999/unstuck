"""Concrete source feedback must survive normalization without accepting bad claims."""
import asyncio
import copy
import json
import pytest
from datetime import date

from trade_source_contract import bind_trade_payload, source_block
from structured_output_runtime import process_agent_response
from agent_runtime.trade_source_repair import repair_trade_sources
from test_trade_catalog_expansion import data
from test_trade_source_completion import setup_payload


REF = 'short_term_market_context.institutional_evidence.records[0]'


def source_context():
    value = data()
    value['institutional_trading'] = {
        'source': 'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date': date.today().isoformat(), 'lookback_trading_days': 30,
        'net_buy_thousand_shares_by_category': {'foreign': -3005.03},
    }
    block, catalog, fingerprint = source_block(value)
    return block, {'data': value, 'structured_outputs': {}, 'analyses': {22: 'kept22', 23: 'kept23'},
        '_trade_source_manifest': {'version': 'trade-sources:v2', 'visible': True,
                                  'catalog': catalog, 'fingerprint': fingerprint}}


def test_initial_source_block_has_validated_fact_with_exact_catalog_reference():
    block, ctx = source_context()
    fact = f'截至{date.today().isoformat()}，外資近30個交易日淨賣超3005.03千股。'
    assert fact in block
    assert fact + ' source ref=' + REF in block
    assert '新聞報導「2033 佳大公告營收」' in block
    assert ctx['_trade_source_manifest']['catalog']['short_term_market_context']['institutional_evidence']['records'][0]['value'] == -3005.03


def test_normalized_rejection_retains_original_refs_and_exact_scope_feedback():
    _, ctx = source_context()
    payload = setup_payload()
    payload.update(core_catalyst='外資近5日淨賣超3005.03千股；等待量能回升後再重新評估。',
                   catalyst_source_refs=[REF])
    process_agent_response(24, json.dumps(payload, ensure_ascii=False), ctx)
    output = ctx['structured_outputs'][24]
    assert output['catalyst_source_refs'] == []
    diagnostic = output['source_assessment'].get('rejection_diagnostics', {})
    assert diagnostic.get('original_refs', {}).get('catalyst_source_refs') == [REF]
    assert diagnostic.get('original_core_catalyst') == payload['core_catalyst']
    assert diagnostic.get('source_fingerprint') == ctx['_trade_source_manifest']['fingerprint']
    claims = diagnostic.get('institutional_claims', [])
    assert claims and claims[0]['population'] == 'foreign'
    assert claims[0]['window']['trading_days'] == 5
    assert claims[0]['available_population_sources'][0]['window']['trading_days'] == 30
    assert claims[0]['available_population_sources'][0]['source_ref'] == REF


def test_repair_receives_rejected_reference_value_and_does_not_edit_upstream():
    _, ctx = source_context()
    payload = setup_payload()
    payload.update(core_catalyst='外資近30個交易日持續淨賣超3005.03千股。', catalyst_source_refs=[REF],
                   resistance_source_refs=['short_term_market_context.daily_market_data.bars[999].high'])
    text = process_agent_response(24, json.dumps(payload, ensure_ascii=False), ctx)
    upstream = copy.deepcopy(ctx['analyses'])
    prompts = []
    async def run(*args):
        prompts.append(ctx['_audit_retry_instruction'])
        return 'candidate'
    asyncio.run(repair_trade_sources(text, ctx['data'], ctx, None, run))
    assert len(prompts) == 1
    assert 'bars[999].high' in prompts[0]
    assert 'continuous_trend_not_established' in prompts[0]
    assert '"value":-3005.03' in prompts[0]
    assert REF in prompts[0]
    assert '外資近30個交易日淨賣超3005.03千股。' in prompts[0]
    assert ctx['analyses'] == upstream


def test_reference_receipt_is_bounded_even_for_invalid_parent_object_refs():
    _, ctx = source_context()
    payload = setup_payload()
    payload['core_catalyst'] = 'x' * 20000
    payload['catalyst_source_refs'] = ['short_term_market_context.daily_market_data'] * 100
    ctx['_trade_source_manifest']['catalog']['short_term_market_context']['daily_market_data']['large_extra'] = ['y' * 20000] * 100
    _, assessment = bind_trade_payload(payload, ctx)
    receipt = assessment['rejection_diagnostics']
    assert receipt['core_catalyst_truncated'] is True
    assert receipt['refs_truncated'] is True
    assert len(json.dumps(receipt)) < 30000


def test_news_examples_that_fail_existing_scope_gate_are_not_suggested():
    from trade_source_guidance import source_fact_cards
    _, ctx = source_context()
    catalog = ctx['_trade_source_manifest']['catalog']
    catalog['short_term_market_context']['recent_news']['items'][0]['title'] = '2033 將於下週公布重大消息'
    assert not any('.recent_news.' in card['ref'] for card in source_fact_cards(catalog))


def test_receipt_from_different_source_is_not_replayed_but_current_facts_remain():
    from trade_source_diagnostics import source_repair_feedback
    _, ctx = source_context()
    assessment = {'rejection_diagnostics': {'version': 'trade-source-rejection:v1',
        'source_fingerprint': 'other', 'original_core_catalyst': 'stale rejected claim'}}
    feedback = source_repair_feedback(assessment, ctx['_trade_source_manifest'])
    assert 'stale rejected claim' not in feedback
    assert '外資近30個交易日淨賣超3005.03千股。' in feedback


def test_unknown_period_unit_or_missing_provider_cannot_gain_fact_example():
    from trade_source_guidance import source_fact_cards
    _, ctx = source_context()
    for field, value in [('unit', 'unknown'), ('window', {}), ('provider', '')]:
        catalog = copy.deepcopy(ctx['_trade_source_manifest']['catalog'])
        catalog['short_term_market_context']['institutional_evidence']['records'][0][field] = value
        assert not any('.institutional_evidence.' in c['ref'] for c in source_fact_cards(catalog))


def test_current_claim_remains_rejected_when_feedback_exists_and_correct_fact_is_admissible():
    from trade_source_guidance import source_fact_cards
    _, ctx = source_context()
    original = copy.deepcopy(ctx['_trade_source_manifest']['catalog'])
    payload = setup_payload()
    payload.update(core_catalyst='外資近5日買超3005.03千張。', catalyst_source_refs=[REF])
    result, assessment = bind_trade_payload(payload, ctx)
    assert assessment['status'] == 'degraded' and result['catalyst_source_refs'] == []
    fact = next(c['fact'] for c in source_fact_cards(original) if c['ref'] == REF)
    payload['core_catalyst'] = fact
    assert bind_trade_payload(payload, ctx)[1]['status'] == 'source_bound'
    assert ctx['_trade_source_manifest']['catalog'] == original


def test_same_catalog_different_candidate_cannot_replay_old_rejection_receipt():
    _, ctx = source_context()
    payload = setup_payload()
    payload.update(core_catalyst='外資近5日淨賣超3005.03千股。', catalyst_source_refs=[REF])
    text = process_agent_response(24, json.dumps(payload, ensure_ascii=False), ctx)
    ctx['structured_outputs'][24]['core_catalyst'] = '新候選只有技術觀望，等待重新評估。'
    prompts = []
    async def run(*args):
        prompts.append(ctx['_audit_retry_instruction'])
        return 'candidate'
    asyncio.run(repair_trade_sources(text, ctx['data'], ctx, None, run))
    assert '外資近5日淨賣超3005.03千股' not in prompts[0]
    assert '新候選只有技術觀望' in prompts[0]


def test_news_fact_example_cannot_bypass_other_catalyst_scope_gates():
    from trade_source_guidance import source_fact_cards
    _, ctx = source_context()
    catalog = ctx['_trade_source_manifest']['catalog']
    catalog['short_term_market_context']['recent_news']['items'][0]['title'] = '2033 外資持續買超'
    assert not any('.recent_news.' in card['ref'] for card in source_fact_cards(catalog))


def test_optional_malformed_catalog_sections_do_not_break_usable_technical_guidance():
    from trade_source_guidance import source_fact_cards
    _, ctx = source_context()
    catalog = ctx['_trade_source_manifest']['catalog']
    for kind, value in [('institutional_evidence', None), ('ownership_evidence', {'records': None})]:
        catalog['short_term_market_context'][kind] = value
    assert any('.technical_indicators.' in c['ref'] for c in source_fact_cards(catalog))


@pytest.mark.parametrize('root', [None, [], 'unavailable'])
def test_unknown_catalog_root_keeps_source_rejection_without_workflow_crash(root):
    payload = setup_payload()
    payload.update(trade_direction='Neutral', core_catalyst='技術觀望，等待重新評估。',
                   catalyst_source_refs=['short_term_market_context.unknown'])
    catalog = {'short_term_market_context': root}
    original = copy.deepcopy(catalog)
    _, assessment = bind_trade_payload(payload, {'_trade_source_manifest': {
        'version': 'trade-sources:v2', 'visible': True, 'fingerprint': 'same', 'catalog': catalog}})
    assert assessment['status'] == 'degraded'
    assert 'invalid_catalyst_source_refs' in assessment['reason_codes']
    assert catalog == original


@pytest.mark.parametrize('root', [None, [], 'unavailable'])
def test_unknown_catalog_root_cannot_gain_fact_cards(root):
    from trade_source_guidance import source_fact_cards
    catalog = {'short_term_market_context': root}
    original = copy.deepcopy(catalog)
    assert source_fact_cards(catalog) == []
    assert catalog == original
