"""Saved report failures: syntax, financial dimensions, signs and populations."""
import pytest

from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims
from financial_money_claims import financial_money_claim_issues
from financial_output_validator import validate_analysis_output


SCENARIOS = ('情境推論: 三情境價格依據 Forward EPS (NT$34.4124) 與歷史 PER 分位數倍數進行推估：'
             ' 1. 熊市情境（NT$633.19）：假設18.4x（34.4124 × 18.4 = 633.19）。')
RIVER = ('依據FinMind 5年PER分位數歷史資料，2025年EPS為15.29元對應之河流圖區間為：'
         '12.8倍（195.71元）、18.4倍（281.34元）、26.8倍（409.77元）、41.5倍（634.53元）'
         '（source ref=local_valuation_context.pe_river_chart）')


def test_inline_list_number_is_not_a_price_claim():
    assert not any(c['reported_value'] == 1 and not c['unit'] for c in extract_numeric_claims(SCENARIOS))


@pytest.mark.parametrize('value', ['1元', '1.0元', 'NT$1.00', '1.00', '1。', '1. 暫估仍低於市價'])
def test_real_one_dollar_targets_are_still_checked(value):
    result = evaluate_report_evidence('熊市情境：' + value,
        {'data': {}, 'oos_evaluation_inputs': {'price_targets': {'熊市情境': 633.19}}}, sample_ratio=1.0)
    assert result['failed_count'] == 1


def river_snapshot():
    return {'data': {'pe_river_chart': {'years': ['2025'], 'eps_twd': [15.29],
        'multiples': [12.8, 18.4, 26.8, 41.5],
        'bands': {'12.8x': [195.71], '18.4x': [281.34], '26.8x': [409.77], '41.5x': [634.53]}}}}


def test_eps_and_per_keep_their_own_values_and_dimensions():
    result = evaluate_report_evidence(RIVER, river_snapshot(), sample_ratio=1.0)
    assert result['failed_count'] == 0
    claims = result['sampled_claims']
    assert any(c['reported_value'] == 15.29 and 'eps_twd' in c.get('matched_path', '') for c in claims)
    assert any(c['reported_value'] == 12.8 and 'multiples' in c.get('matched_path', '') for c in claims)
    assert not any(c['unit'] == '倍' and 'eps' in c.get('matched_path', '') for c in claims)


@pytest.mark.parametrize('original,wrong', [('15.29元', '25.29元'), ('12.8倍', '92.8倍')])
def test_wrong_eps_or_per_is_not_hidden_by_a_neighboring_metric(original, wrong):
    result = evaluate_report_evidence(RIVER.replace(original, wrong), river_snapshot(), sample_ratio=1.0)
    assert result['failed_count'] >= 1


@pytest.mark.parametrize('amount', ['-NT$215.7', 'NT$-215.7', '負215.7', '−NT$215.7', '- NT$ 215.7'])
def test_currency_prefix_preserves_the_negative_sign(amount):
    data = {'financial_currency': 'TWD', 'free_cash_flow_raw': -21565024256}
    text = f'TTM FCF {amount}億元。'
    assert financial_money_claim_issues(text, data) == []
    claims = [c for c in extract_numeric_claims(text) if c.get('financial_amount')]
    assert claims and all(c['reported_value'] == -215.7 for c in claims)


@pytest.mark.parametrize('amount', ['NT$215.7', '+NT$215.7', '-NT$21.57'])
def test_sign_and_tenfold_errors_remain_blocked(amount):
    assert financial_money_claim_issues(f'TTM FCF {amount}億元。',
        {'financial_currency': 'TWD', 'free_cash_flow_raw': -21565024256})


def flows():
    return {'ticker': '1623.TW', 'institutional_trading': {
        'source': 'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date': '2026-10-16', 'lookback_trading_days': 30,
        'total_net_buy_thousand_shares': -155.34,
        'net_buy_thousand_shares_by_category': {'foreign': -160.83, 'investment_trust': 0, 'dealer': 5.49}}}


@pytest.mark.parametrize('agent', [19, 21, 23, 24])
def test_factual_counterevidence_under_hypothesis_heading_is_checked(agent):
    text = ('### 一、檢驗空方核心假設之反證查核\n'
            '- **空方假設二：外資法人持續調節，籌碼結構瓦解**\n'
            '  - **反證事實**：依據institutional_trading，截至2026-10-16近30個交易日，'
            '三大法人合計淨賣超155.34千股，其中外資淨賣超160.83千股。'
            '相對於66,000千股的總股本，外資30日賣超155.34張的量能僅占股本約0.235%。')
    assert any('法人' in i for i in validate_analysis_output(agent, text, flows()))


@pytest.mark.parametrize('text', [
    '### 未來情境\n若外資30日賣超155.34張，才考慮進場。',
    '### 未來情境\n預估外資30日賣超155.34張。',
    '### 未來情境\n外資30日賣超155.34張。',
    '### 反證查核\n若外資30日賣超155.34張，才考慮進場。',
    '### 假設反證查核\n- **反證事實**：預估外資30日賣超155.34張。',
    '### 假設反證查核\n- **反證事實**：若外資30日賣超155.34張，才考慮進場。',
])
def test_actual_forecasts_and_thresholds_remain_nonobservations(text):
    assert not any('法人' in i for i in validate_analysis_output(19, text, flows()))
