"""P/E parsing preserves grouped numbers without relaxing evidence checks."""
import pytest

from evidence_derived_claims import derived_pe_claims


@pytest.mark.parametrize('price,expected', [('1,710',1710),('1710',1710),('1,710.00',1710),('12,345.50',12345.5)])
def test_grouped_price_is_not_read_as_its_first_digit(price,expected):
    text=f'市場 Forward EPS 為 NT$77.74，當前股價 NT${price} 對應 Forward P/E 為 {expected/77.74:.4f}x。'
    result=derived_pe_claims(text,{'data':{'currency':'TWD','financial_currency':'TWD'}})[0]
    assert result['arithmetic_inputs']['price_per_share']==expected
    assert 'pe_arithmetic_mismatch' not in result['issues']
    assert result['status']=='unverifiable'  # Forward fiscal basis was not independently bound.


def test_actual_arithmetic_currency_and_period_errors_remain_visible():
    text='2025年 EPS 為 NT$77.74，當前股價 NT$1,710 對應 TTM P/E 為 30.0x。'
    result=derived_pe_claims(text,{'data':{'currency':'TWD','financial_currency':'USD','trailing_eps':20}})[0]
    assert result['status']=='mismatch'
    assert 'pe_arithmetic_mismatch' in result['issues']
    assert 'annual_eps_used_for_ttm_pe' in result['issues']
    assert 'price_eps_currency_mismatch' in result['issues']


@pytest.mark.parametrize('price',['1,71','1,710,00','1,2,345'])
def test_malformed_grouping_cannot_be_certified_as_a_partial_price(price):
    result=derived_pe_claims(f'EPS 為 2，股價 {price} 對應 P/E 為 5x。',{'data':{}})
    assert not result


@pytest.mark.parametrize('text', [
    '2025年 EPS 為 2，股價 100 對應 P/E 為 7.',
    '2025年 EPS 為 2, 股價 100 對應 P/E 為 7.',
    '2025年 EPS 為 2,股價 100 對應 P/E 為 7。',
])
def test_sentence_punctuation_cannot_hide_real_arithmetic_errors(text):
    result = derived_pe_claims(text, {'data': {}})
    assert result and 'pe_arithmetic_mismatch' in result[0]['issues']
