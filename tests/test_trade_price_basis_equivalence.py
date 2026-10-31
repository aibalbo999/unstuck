import copy
import json
from pathlib import Path
import pytest
from trade_price_reference import price_reference_checks, _YFINANCE_ADJ_CLOSE_BASIS


def case(field='sma_5', source='yfinance 5y history', basis=_YFINANCE_ADJ_CLOSE_BASIS):
    ref='short_term_market_context.technical_indicators.'+field
    catalog={'short_term_market_context':{'technical_indicators':{'source':source,'availability':'available','as_of':'2026-10-07','price_adjustment_basis':basis,field:73.7}}}
    payload={'support_level':'73.7','resistance_level':'N/A','support_source_refs':[ref],
             'price_level_evidence':[{'field':'support_level','kind':'direct_reference','operation':'identity','inputs':[{'ref':ref,'observed_date':'2026-10-07','window_sessions':5,'price_basis':'adjusted_close'}]}]}
    return payload,catalog


@pytest.mark.parametrize('mode',['v1','v2','v3','v4'])
def test_close_only_provider_alias_is_specific_and_does_not_mutate_inputs(mode):
    payload,catalog=case();payload['pipeline_id']=mode
    before=copy.deepcopy((payload,catalog));result=price_reference_checks(payload,catalog)[0]
    assert result['status']=='verified'
    assert result['basis_normalizations'][0]['canonical_basis']=='yfinance_adj_close_factor_close'
    assert (payload,catalog)==before


@pytest.mark.parametrize('basis', ['unadjusted_exchange_ohlc','unadjusted_provider_ohlc',
    'split_only_adjusted_close','dividend_only_adjusted_close','split_and_dividend_adjusted_close',
    'adjusted','unknown',None])
def test_generic_alias_cannot_normalize_raw_other_adjustment_or_unknown(basis):
    payload,catalog=case(basis=basis)
    result=price_reference_checks(payload,catalog)[0]
    assert result['status']!='verified' and 'basis_normalizations' not in result
    if basis in {'adjusted','unknown',None}:
        assert result['status']=='unverifiable'


def test_missing_or_other_provider_metadata_cannot_establish_equivalence():
    for source in ['',None,'other provider']:
        payload,catalog=case(source=source)
        result=price_reference_checks(payload,catalog)[0]
        assert result['status']!='verified' and 'basis_normalizations' not in result


def test_split_only_and_dividend_adjusted_declarations_are_not_equivalent():
    payload,catalog=case(basis='split_only_adjusted_close')
    payload['price_level_evidence'][0]['inputs'][0]['price_basis']='dividend_only_adjusted_close'
    assert price_reference_checks(payload,catalog)[0]['status']=='mismatch'


@pytest.mark.parametrize('field',['high','low','open','close'])
def test_daily_alias_only_applies_to_close(field):
    payload,catalog=case();ref='short_term_market_context.daily_market_data.bars[0].'+field
    catalog={'short_term_market_context':{'daily_market_data':{'source':'yfinance 5y history','availability':'available','as_of':'2026-10-07','price_adjustment_basis':_YFINANCE_ADJ_CLOSE_BASIS,'bars':[{'date':'2026-10-07',field:73.7}]}}}
    payload['support_source_refs']=[ref];payload['price_level_evidence'][0]['inputs'][0].update(ref=ref,window_sessions=1)
    result=price_reference_checks(payload,catalog)[0]
    assert (result['status']=='verified')==(field=='close')


def test_close_alias_does_not_hide_value_date_or_window_contradictions():
    payload,catalog=case();payload['support_level']='99'
    payload['price_level_evidence'][0]['inputs'][0].update(observed_date='2026-10-06',window_sessions=20)
    result=price_reference_checks(payload,catalog)[0]
    assert result['status']=='mismatch'
    assert result['reason_codes']==['support_level_source_date_mismatch','support_level_source_period_mismatch','support_level_source_value_mismatch']


def test_captured_real_equivalence_and_raw_basis_negative_controls():
    rows=json.loads((Path(__file__).parent/'fixtures/trade_price_basis_cases.json').read_text())
    for row in rows:
        before=copy.deepcopy(row)
        results=price_reference_checks(row['payload'],row['catalog'])
        assert all(r['status']==row['expected_after'] for r in results)
        assert all(bool(r.get('basis_normalizations'))==(row['ticker']=='1216.TW') for r in results)
        assert row==before
