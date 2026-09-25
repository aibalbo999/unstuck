"""Unavailable target explanations cannot supply prices to trade validation."""

import pytest

from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment
from trade_execution_contract import evaluate_trade_execution


@pytest.mark.parametrize('direction,stop,reference', [
    ('Short', '1050', '908.32'), ('Long', '950', '1200'),
])
@pytest.mark.parametrize('template', [
    'N/A（歷史發行價 {price} 元僅為參考）',
    'N/A（參考舊目標價 NT${price}，尚未評估本次目標）',
    '未評估（2026 Q3 後重新評估；歷史價格 NT${price}）',
])
def test_required_unassessed_target_does_not_verify_a_trade(direction, stop, reference, template):
    result = evaluate_trade_execution(
        direction=direction, entry_zone='1000', target_price=template.format(price=reference),
        stop_loss=stop, transaction_cost=0)
    assert any(issue['id'] == 'invalid_target_price' for issue in result['issues'])
    assert result['details']['target_range'] is None
    assert result['details']['worst_case_risk_reward'] is None
    assert result['details']['net_risk_reward'] is None
    assert result['details']['risk_reward_status'] == 'unverifiable'


@pytest.mark.parametrize('direction,stop', [('Short', '1050'), ('Long', '950')])
def test_optional_unassessed_target_retains_unknown_reward_without_a_false_error(direction, stop):
    result = evaluate_trade_execution(
        direction=direction, entry_zone='1000', target_price='N/A（歷史價格908.32元）',
        stop_loss=stop, transaction_cost=0, require_target=False)
    assert result['issues'] == []
    assert result['details']['target_range'] is None
    assert result['details']['net_risk_reward'] is None
    assert result['details']['risk_reward_status'] == 'unverifiable'


@pytest.mark.parametrize('direction,stop,reference', [('Short', '1050', '908.32'), ('Long', '950', '1200')])
def test_credibility_details_do_not_present_a_reference_as_the_target(direction, stop, reference):
    result = evaluate_trade_setup_alignment(trade_setup={
        'trade_direction': direction, 'entry_zone': '1000',
        'target_price': f'N/A（歷史發行價 {reference} 元僅為參考）',
        'stop_loss': stop, 'transaction_cost': 0, 'risk_level': 'High',
    }, current_price=1000)
    assert {row['id'] for row in result['warnings']} == {'missing_trade_setup_price_inputs'}
    assert result['checks'][0]['status'] == 'warning'
    details = result['checks'][0]['details']
    assert details['target_price'] is None
    assert 'target_price_candidates' not in details
    assert details.get('net_risk_reward') is None


@pytest.mark.parametrize('target', ['1200', 'NT$1200-1300', 'N/A（本次目標價 NT$1200）'])
def test_current_numeric_targets_and_ranges_keep_execution_validation(target):
    result = evaluate_trade_execution(direction='Long', entry_zone='1000', target_price=target,
                                      stop_loss='950', transaction_cost=0)
    assert result['issues'] == []
    assert result['details']['target_range'][0] == 1200
    assert result['details']['risk_reward_status'] == 'net_verified'


def test_current_wrong_direction_claim_is_not_hidden_by_an_na_prefix():
    result = evaluate_trade_execution(direction='Short', entry_zone='1000',
                                      target_price='N/A（本次目標價 NT$1200）', stop_loss='1050', transaction_cost=0)
    assert {issue['id'] for issue in result['issues']} == {'short_target_not_outside_entry'}


@pytest.mark.parametrize('target,expected', [
    ('N/A；目前目標價 NT$900（前次目標價 NT$1200 未採用）', [900, 900]),
    ('N/A；目前目標價 NT$900-950（舊目標價 NT$1200 未採用）', [900, 950]),
])
def test_mixed_current_target_and_unused_reference_use_only_current_price(target, expected):
    result = evaluate_trade_execution(direction='Short', entry_zone='1000', target_price=target,
                                      stop_loss='1050', transaction_cost=0)
    assert result['issues'] == []
    assert result['details']['target_range'] == expected
    assert result['details']['risk_reward_status'] == 'net_verified'
    credibility = evaluate_trade_setup_alignment(trade_setup={
        'trade_direction': 'Short', 'entry_zone': '1000', 'target_price': target,
        'stop_loss': '1050', 'transaction_cost': 0,
    }, current_price=1000)
    assert credibility['blocking_issues'] == credibility['warnings'] == []
    assert credibility['checks'][0]['details']['target_price'] == expected[0]
    assert credibility['checks'][0]['details']['target_range'] == expected


def test_unavailable_non_target_metric_keeps_generic_entry_stop_and_current_price():
    result = evaluate_trade_setup_alignment(trade_setup={
        'trade_direction': 'Short', 'entry_zone': 'NT$1000（EPS N/A）',
        'target_price': 'NT$900', 'stop_loss': 'NT$1050（EPS N/A）', 'transaction_cost': 0,
    }, current_price=1010)
    assert result['blocking_issues'] == result['warnings'] == []
    details = result['checks'][0]['details']
    assert details['current_price'] == 1010
    assert details['entry_range'] == [1000, 1000]
    assert details['stop_range'] == [1050, 1050]
    assert details['risk_reward_status'] == 'net_verified'


def test_neutral_observation_stays_non_executable_and_does_not_show_a_fake_target():
    result = evaluate_trade_setup_alignment(trade_setup={
        'trade_direction': 'Neutral', 'entry_zone': '等待財報後重新評估，不交易。',
        'core_catalyst': '等待財報後重新評估，不交易。', 'risk_level': 'High',
        'target_price': 'N/A（歷史發行價908.32元）', 'stop_loss': 'N/A',
    }, current_price=1000)
    assert result['blocking_issues'] == result['warnings'] == []
    assert result['checks'][0]['details']['execution_status'] == 'no_trade'
    assert result['checks'][0]['details']['target_price'] is None
