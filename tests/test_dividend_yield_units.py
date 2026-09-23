"""Source-unit evidence, not magnitude, determines dividend-yield conversion."""
import copy
import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

from financial_tools import build_financial_tool_context
from prompt_builder import format_data_for_prompt


def payload(data):
    text = format_data_for_prompt(data, compact_json=True)
    return json.loads(text.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0])


def test_live_percentage_point_source_does_not_become_nineteen_percent_or_high_yield_ddm():
    data = {'ticker':'5314.TWO', 'sector':'Technology', 'dividend_yield':'0.19%',
            'dividend_yield_raw':0.19, 'dividend_rate_raw':0.05, 'current_price':26,
            'gross_margin_raw':0.572, 'payout_ratio_raw':0.25}
    before = copy.deepcopy(data)
    result = payload(data)
    assert result['valuation_metrics']['dividend_yield_pct'] == 0.19
    assert 'ddm_scenarios_default' not in build_financial_tool_context(data)['calculations']
    assert result['valuation_metrics']['payout_ratio_pct'] == 25
    assert result['ttm_financials']['gross_margin_pct'] == 57.2
    assert data == before


@pytest.mark.parametrize('source,pct,ddm', [
    ({'dividend_yield_raw':6.25, 'dividend_yield_raw_unit':'percentage_points'},6.25,True),
    ({'dividend_yield_raw':0.0625, 'dividend_yield_raw_unit':'ratio'},6.25,True),
    ({'dividend_yield_raw':0.19, 'dividend_yield_raw_unit':'percentage_points'},0.19,False),
    ({'dividend_yield_raw':0.19, 'dividend_yield_raw_unit':'ratio'},19.0,True),
    ({'dividend_yield_raw':0, 'dividend_yield_raw_unit':'percentage_points'},0.0,False),
    ({'dividend_yield_raw':5, 'dividend_yield_raw_unit':'percentage_points'},5.0,True),
    ({'dividend_yield_raw':4.99, 'dividend_yield_raw_unit':'percentage_points'},4.99,False),
    ({'dividend_yield_raw':0.025, 'dividend_yield':'2.50%'},2.5,False),
    ({'dividend_yield_raw':6.25, 'dividend_yield':'6.25%'},6.25,True),
    ({'dividend_yield_raw':0.194, 'dividend_yield_raw_unit':'percentage_points', 'dividend_yield':'0.19%'},0.194,False),
])
def test_typed_and_supported_legacy_yields_share_prompt_and_ddm_threshold(source,pct,ddm):
    data = dict(source, sector='Technology',dividend_rate_raw=0.05)
    result = payload(data)
    assert result['valuation_metrics']['dividend_yield_pct'] == pct
    calculated = build_financial_tool_context(data)['calculations']
    assert ('ddm_scenarios_default' in calculated) is ddm
    if ddm:
        assert calculated['ddm_scenarios_default']['dividend_yield_pct'] == pct


@pytest.mark.parametrize('source', [
    {'dividend_yield_raw':0.19},
    {'dividend_yield_raw':6.25},
    {'dividend_yield_raw':0.19,'dividend_yield_raw_unit':'unknown','dividend_yield':'0.19%'},
    {'dividend_yield_raw':0.19,'dividend_yield_raw_unit':{'bad':'unit'}},
    {'dividend_yield_raw':0.19,'dividend_yield_raw_unit':'ratio','dividend_yield':'0.19%'},
    {'dividend_yield_raw':0.19,'dividend_yield':'8%'},
    {'dividend_yield_raw':True,'dividend_yield_raw_unit':'ratio'},
    {'dividend_yield_raw':float('nan'),'dividend_yield_raw_unit':'percentage_points'},
    {'dividend_yield_raw':float('inf'),'dividend_yield_raw_unit':'ratio'},
    {'dividend_yield_raw':-1,'dividend_yield_raw_unit':'percentage_points'},
    {'dividend_yield_raw':None,'dividend_yield_raw_unit':'percentage_points'},
])
def test_unknown_conflicting_or_invalid_units_do_not_make_high_yield_claim(source):
    data = dict(source,sector='Technology',dividend_rate_raw=0.05,current_price=0.001)
    assert payload(data)['valuation_metrics']['dividend_yield_pct'] is None
    assert 'ddm_scenarios_default' not in build_financial_tool_context(data)['calculations']


def test_financial_sector_ddm_can_remain_applicable_without_inventing_yield():
    data = {'sector':'Financial Services','dividend_rate_raw':2,'dividend_yield_raw':0.19}
    ddm = build_financial_tool_context(data)['calculations']['ddm_scenarios_default']
    assert ddm['dividend_yield_pct'] is None


def test_yfinance_payload_declares_percentage_point_unit_without_changing_raw():
    from data_fetch.yfinance_payload import build_legacy_payload
    source = defaultdict(lambda:None, dividend_yield=0.19)
    result = build_legacy_payload(source)
    assert result['dividend_yield_raw'] == 0.19
    assert result['dividend_yield'] == '0.19%'
    assert result['dividend_yield_raw_unit'] == 'percentage_points'
    assert result['dividend_yield_source'] == 'yfinance info.dividendYield'


def test_saved_final_report_input_corrected_at_prompt_only_when_available():
    path = os.environ.get('DIVIDEND_YIELD_SNAPSHOT')
    if not path:
        pytest.skip('optional private frozen 5314 input')
    data=json.loads(Path(path).read_text())['data'];before=copy.deepcopy(data)
    result=payload(data)
    assert result['valuation_metrics']['dividend_yield_pct']==0.19
    assert 'ddm_scenarios_default' not in result['deterministic_financial_tool_results']['calculations']
    assert data==before


def test_actual_agent_prompt_hash_and_step_cache_key_change_for_same_frozen_input(monkeypatch):
    from agent_runtime.prompting import build_prompt
    from agent_runtime.step_cache import build_agent_step_cache_key
    from google_prompt_safety import sanitize_google_prompt
    import prompt_builder
    import financial_tools
    source_path=os.environ.get('DIVIDEND_YIELD_SNAPSHOT')
    if source_path:
        saved=json.loads(Path(source_path).read_text())
        data=saved['data'];context=copy.deepcopy(saved['rerun_context']);context['data']=data
    else:
        data={'ticker':'5314.TWO','dividend_yield':'0.19%','dividend_yield_raw':0.19,
              'dividend_rate_raw':0.05,'sector':'Technology'}
        context={'pipeline_id':'v3','data':data,'analyses':{},'structured_outputs':{}}
    before=copy.deepcopy(data)
    new_prompt=sanitize_google_prompt(build_prompt(19,data,copy.deepcopy(context)))
    with monkeypatch.context() as patch:
        old=lambda data: data.get('dividend_yield_raw')*100
        patch.setattr(prompt_builder,'dividend_yield_pct',old)
        patch.setattr(financial_tools,'dividend_yield_pct',old)
        old_prompt=sanitize_google_prompt(build_prompt(19,data,copy.deepcopy(context)))
    assert new_prompt!=old_prompt
    new_key=build_agent_step_cache_key(19,data,context,'gemini-3.5-flash-lite',new_prompt)
    old_key=build_agent_step_cache_key(19,data,context,'gemini-3.5-flash-lite',old_prompt)
    assert new_key!=old_key
    assert data==before


@pytest.mark.parametrize('source,expected', [
    ({'dividend_yield':'2.50%'},2.5),
    ({'dividend_yield_raw':0.025,'dividend_yield':'2.50%', 'current_price':9999, 'dividend_rate_raw':0.001},2.5),
    ({'dividend_yield_raw':0.19,'dividend_yield':'not a percentage'},None),
    ({'dividend_yield_raw':0.19,'dividend_yield_raw_unit':'percentage_points','dividend_yield':'19%'},None),
])
def test_display_evidence_is_bounded_and_dividend_price_is_not_an_inferred_unit(source,expected):
    assert payload(source)['valuation_metrics']['dividend_yield_pct']==expected
