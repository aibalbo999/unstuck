"""Public boundary checks. Original private-data replay cases remain local."""
import pytest
import test_ordinary_individual_annual as helpers

@pytest.fixture
def h():
    return helpers
from types import SimpleNamespace

def test_normal_capital_notes_do_not_relabel_individual_as_broker_consolidated(h):
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.yfinance_capital_notes import build_capital_structure_notes
    result, calls = h.fetch()
    value = result['value']
    assert value is not None and len(calls) == 6
    p = project_source_value(value, h.TICKER)
    note = build_capital_structure_notes(SimpleNamespace(), {}, revenue_history=p['revenue_history'], net_income_history=p['net_income_history'], total_assets_history=p['total_assets_history'], total_equity_history=p['total_equity_history'], market_cap=1000000000.0, total_debt=100000000.0, financial_history_data={**p, 'ticker': h.TICKER})
    text = note['equity_multiplier_note'] + ' ' + note['dupont_identity_note']
    assert '個別' in text and all((x not in text for x in ['證券商', '合併資產', '母公司'])), text

def test_normal_payload_does_not_compare_unverified_ttm_with_individual_annual(h):
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.yfinance_core_context import build_yfinance_payload_vars, _PAYLOAD_KEYS, _QUALITY_INPUT_KEYS
    result, _ = h.fetch()
    p = project_source_value(result['value'], h.TICKER)
    fields = {k: None for k in (*_PAYLOAD_KEYS, *_QUALITY_INPUT_KEYS)}
    fields.update(p, ticker=h.TICKER, info={}, data_source_notes=[], current_price=20, market_cap=1000000000.0, pe_ratio=10, week_52_high=30, week_52_low=10, shares_outstanding=50000000.0, revenue_ttm=1000000000.0, free_cash_flow=100000000.0, trailing_eps=2, revenue_growth=0.1, earnings_growth=0.1, profit_margin=0.1)
    payload, _ = build_yfinance_payload_vars(fields)
    assert payload['ttm_vs_latest_annual_revenue_change'] is None, payload['ttm_vs_latest_annual_revenue_change']
import asyncio
from copy import deepcopy
import pytest

@pytest.mark.parametrize('mutation', ['index_before_last_year', 'foreign_receipt', 'boolean_http_status'])
def test_original_receipt_cannot_be_reassigned_or_predate_report_close(h, mutation):
    from data_fetch.annual_financial_source_provider import project_source_value
    result, _ = h.fetch()
    v = deepcopy(result['value'])
    if mutation == 'index_before_last_year':
        v['published_index_receipt']['retrieved_at'] = 1704038400
    elif mutation == 'foreign_receipt':
        v['documents'][0]['raw_receipt']['source_url'] = v['documents'][0]['url'].replace('2646', '2647')
    else:
        v['documents'][0]['raw_receipt']['http_status'] = True
    assert project_source_value(v, h.TICKER) is None

def test_explicit_scope_conflict_in_native_original_prevents_public_acquisition(h):
    raw = h.synthetic_filing(2024).replace('星宇航空股份有限公司'.encode(), '其他航空股份有限公司'.encode())
    result, calls = h.fetch(bodies={2024: raw})
    assert result['value'] is None and result['audit']['record_count'] == 0
    assert len(calls) == 5
