"""Actual flow observations and future rechecks must not borrow each other's proof."""
import copy
import json
from pathlib import Path
import pytest
from trade_source_contract import bind_trade_payload


def case():
    fixture = json.loads((Path(__file__).parent / 'fixtures/trade_catalyst_2882_20260922.json').read_text())
    payload = copy.deepcopy(fixture['payload'])
    records = fixture['manifest']['catalog']['short_term_market_context']['institutional_evidence']['records']
    index = next(i for i, r in enumerate(records) if r['population'] == 'total' and r['window'].get('trading_days') == 5)
    payload['catalyst_source_refs'] = [f'short_term_market_context.institutional_evidence.records[{index}]']
    return payload, {'_trade_source_manifest': fixture['manifest']}


def test_real_2882_numeric_observation_with_future_recheck_is_not_a_claim_of_continuity():
    payload, ctx = case()
    # Keep the report's actual core text, supplying the exact cited record for the
    # well-defined five-day observation; do not claim the future condition is true.
    result, assessment = bind_trade_payload(payload, ctx)
    assert assessment['status'] == 'observation'
    assert result['catalyst_source_refs'] == payload['catalyst_source_refs']


@pytest.mark.parametrize('fact', [
    '外資近5日淨賣超2313.29千股',  # Total is not foreign flow.
    '法人近5日淨賣超2313.29千張',
    '法人近5日持續賣超2313.29千股',  # Sum is not continuity.
    '法人近5日淨賣超9999千股',
])
def test_future_condition_does_not_hide_invalid_present_facts(fact):
    payload, ctx = case()
    payload['core_catalyst'] = fact + '；等待法人連續買超後再重新評估。'
    assert bind_trade_payload(payload, ctx)[1]['status'] == 'degraded'


@pytest.mark.parametrize('tail', [
    '；等待法人回補，但外資已連續買超，然後重新評估。',
    '；等待重新評估，目前法人持續買超。',
    '；等待法人近5日買超9999千股後重新評估。',
    '；等待量能回升後再重新評估。外資買超9999千股，後續再觀察。',
    '；等待量能回升後再重新評估；外資買超9999千股後再觀察。',
    '；等待量能回升，外資買超9999千股，後續再評估。',
])
def test_ambiguous_tail_with_new_actual_assertions_is_not_ignored(tail):
    payload, ctx = case()
    payload['core_catalyst'] = '法人近5日淨賣超2313.29千股' + tail
    assert bind_trade_payload(payload, ctx)[1]['status'] == 'degraded'


def test_future_only_neutral_recheck_does_not_claim_institutional_evidence():
    payload, ctx = case()
    payload.update(core_catalyst='等待法人連續買超後再重新評估。', catalyst_source_refs=[])
    assert bind_trade_payload(payload, ctx)[1]['status'] == 'observation'
    payload['trade_direction'] = 'Long'
    assert bind_trade_payload(payload, ctx)[1]['status'] == 'degraded'
