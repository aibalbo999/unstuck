# Independent behavior checks copied without staged import overlay.
import pytest
import test_ordinary_individual_annual as helpers

@pytest.fixture
def h():
    return helpers

from types import SimpleNamespace

def test_normal_capital_notes_do_not_relabel_individual_as_broker_consolidated(h):
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.yfinance_capital_notes import build_capital_structure_notes
    result,calls=h.fetch()
    value=result['value'];assert value is not None and len(calls)==6
    p=project_source_value(value,h.TICKER)
    note=build_capital_structure_notes(SimpleNamespace(),{},
      revenue_history=p['revenue_history'],net_income_history=p['net_income_history'],
      total_assets_history=p['total_assets_history'],total_equity_history=p['total_equity_history'],
      market_cap=1e9,total_debt=1e8,financial_history_data={**p,'ticker':h.TICKER})
    text=note['equity_multiplier_note']+' '+note['dupont_identity_note']
    assert '個別' in text and all(x not in text for x in ['證券商','合併資產','母公司']), text

def test_normal_payload_does_not_compare_unverified_ttm_with_individual_annual(h):
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.yfinance_core_context import build_yfinance_payload_vars,_PAYLOAD_KEYS,_QUALITY_INPUT_KEYS
    result,_=h.fetch();p=project_source_value(result['value'],h.TICKER)
    fields={k:None for k in (*_PAYLOAD_KEYS,*_QUALITY_INPUT_KEYS)}
    fields.update(p,ticker=h.TICKER,info={},data_source_notes=[],current_price=20,market_cap=1e9,
      pe_ratio=10,week_52_high=30,week_52_low=10,shares_outstanding=5e7,revenue_ttm=1e9,
      free_cash_flow=1e8,trailing_eps=2,revenue_growth=.1,earnings_growth=.1,profit_margin=.1)
    payload,_=build_yfinance_payload_vars(fields)
    assert payload['ttm_vs_latest_annual_revenue_change'] is None, payload['ttm_vs_latest_annual_revenue_change']

"""Isolated original replay and real saved-report boundaries, no live acquisition."""
import asyncio
from copy import deepcopy
import json
import time
import pytest

def test_source_only_saved_report_roundtrip_keeps_individual_and_analysis(h,tmp_path,monkeypatch):
    from test_report_annual_financial_source_refresh import report,init_db
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from data_fetch.annual_financial_source_provider import project_source_value
    import data_fetch.market_sources.ordinary_individual_annual as m
    init_db();storage,name,keys,old=report(h.TICKER)
    old['data'].update(h.context())
    old['data']['company_identity']={'ticker':h.TICKER,'stock_id':'2646','official_name':'星宇航空','legal_name':'星宇航空股份有限公司','quote_type':'EQUITY'}
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    http,calls=h.transport();monkeypatch.setattr(m,'IndividualMopsHttp',lambda:http)
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    saved=json.loads(storage.get_report(keys.data_key).content);data=saved['data']
    assert len(calls)==6 and data['financial_history_basis']['report_scope']=='individual'
    assert project_source_value(data['sector_specific_financials'],h.TICKER) is not None
    assert data['ttm_vs_latest_annual_revenue_change']=='N/A'
    for k in ['current_price','revenue_ttm_raw','free_cash_flow_raw','operating_cash_flow_raw','recent_catalysts','earnings_call']:
        assert data[k]==old['data'][k]
    for k in ['analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance']:
        assert saved[k]==old[k]
    assert storage.get_report(keys.html_key).content==storage.get_report(keys.md_key).content==b'original conclusions'

@pytest.mark.parametrize('mutation',['index_before_last_year','foreign_receipt','boolean_http_status'])
def test_original_receipt_cannot_be_reassigned_or_predate_report_close(h,mutation):
    from data_fetch.annual_financial_source_provider import project_source_value
    result,_=h.fetch();v=deepcopy(result['value'])
    if mutation=='index_before_last_year':v['published_index_receipt']['retrieved_at']=1704038400
    elif mutation=='foreign_receipt':v['documents'][0]['raw_receipt']['source_url']=v['documents'][0]['url'].replace('2646','2647')
    else:v['documents'][0]['raw_receipt']['http_status']=True
    assert project_source_value(v,h.TICKER) is None


def test_explicit_scope_conflict_in_native_original_prevents_public_acquisition(h):
    raw=h.synthetic_filing(2024).replace('星宇航空股份有限公司'.encode(),'其他航空股份有限公司'.encode())
    result,calls=h.fetch(bodies={2024:raw})
    assert result['value'] is None and result['audit']['record_count']==0
    assert len(calls)==5

def test_real_2025_native_two_year_amounts_survive_public_service_and_money_checks(h,monkeypatch):
    """2021–24 primary originals are synthetic; only 2025 + comparative2024 native."""
    from hashlib import sha256
    import data_fetch.market_sources.ordinary_individual_annual as m
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest
    from data_fetch.annual_financial_source_provider import project_source_value
    from financial_money_claims import financial_money_claim_issues
    raw=(h.D/'2646-2025-research.body').read_bytes()
    assert sha256(raw).hexdigest()=='e4639afec6e44c15cfbab5cb89e89abf2f249cc803ee77ab3cf9acf606d4d1d7'
    http,calls=h.transport(bodies={2025:raw});monkeypatch.setattr(m,'IndividualMopsHttp',lambda:http)
    out=asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker(h.TICKER),'financial_statements',context={'data':h.context()}))
    assert len(calls)==6 and out.source_audit[0]['status']=='success'
    value=out.data['financial_statements'];data={**h.context(),**project_source_value(value,h.TICKER)}
    r=value['raw_twd_by_year']
    assert r['2025']['profit_loss']==272608000 and r['2024']['profit_loss']==1324438000
    assert r['2025']['equity']==31396288000 and r['2024']['equity']==29838451000
    assert r['2025']['free_cash_flow']==8060298000-13188668000-97647000==-5226017000
    assert r['2024']['free_cash_flow']==10965481000-23810211000-64111000==-12908841000
    assert data['net_income_history'][-1]==.272608
    for text in ['2025年本公司個別本期損益為2.72608億元。','2024年本公司個別本期損益為13.24438億元。','2025年本公司個別權益總額為313.96288億元。']:
        assert financial_money_claim_issues(text,data)==[],text
    errors=financial_money_claim_issues('2025年本公司個別本期損益為2726.08億元。',data)
    assert any('金額單位紅線'in x for x in errors),errors
    errors=financial_money_claim_issues('2025年本公司合併淨利為2.72608億元。',data)
    assert any('個別財報範圍紅線'in x for x in errors),errors
