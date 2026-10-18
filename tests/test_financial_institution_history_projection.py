"""Complete holding/bank filings use typed net revenue, never industrial revenue."""
import copy
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/financial_institution_2891_20261009.json'


def statement():
    return json.loads(FIXTURE.read_text())


class NoAnnualSdk:
    @property
    def financials(self):
        raise AssertionError('complete official annual inputs must avoid redundant SDK')
    cashflow = financials
    balance_sheet = financials


def acquired(monkeypatch):
    from data_fetch import yfinance_extractors as source
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    monkeypatch.setattr(source, 'fetch_financial_institution_histories', lambda ticker: statement())
    monkeypatch.setattr(source, 'fetch_finmind_financial_statement_fallback',
                        lambda *a, **kw: pytest.fail('redundant FinMind annual fallback'))
    return source.extract_financial_histories(NoAnnualSdk(), '2891.TW', [], industry_context='金融保險')


def data_from_projection():
    from data_fetch.financial_history_basis import project_financial_institution_histories
    raw = statement()
    projected = project_financial_institution_histories(raw, '2891.TW')
    assert projected is not None
    return {'ticker':'2891.TW', 'financial_currency':'TWD', 'sector':'Financial Services',
            'industry':'Financial Conglomerates', 'sector_specific_financials':raw, **projected}


def test_complete_official_financial_institution_skips_sdk_and_keeps_typed_net_revenue(monkeypatch):
    result = acquired(monkeypatch)
    assert result['years'] == ['2021','2022','2023','2024','2025']
    assert result['net_revenue_history'] == [186.057824,139.252299,136.576427,189.409573,244.894671]
    assert result['revenue_history'] == result['gross_profit_history'] == result['operating_income_history'] == [None]*5
    assert result['net_income_history'][-1] == 80.619233
    assert result['fcf_history'][-1] == 0.067802
    assert result['primary_financial_audit'] is result['finmind_financial_fallback_audit'] is None
    assert result['financial_history_basis']['field_sources']['net_revenue_history']['fact'] == 'tifrs-bsci-fh:NetIncomeLoss'
    assert 'revenue_history' in result['financial_history_basis']['unsupplied_fields']


@pytest.mark.parametrize('change', ['ticker','individual','document_scope','missing_hash','wrong_document_issuer',
                                   'missing_value','bool_value','bad_fcf','positive_capex','insurer_schema',
                                   'non_contiguous','huge_value','malformed_url'])
def test_invalid_receipt_is_ineligible_for_typed_projection(change):
    from data_fetch.financial_history_basis import project_financial_institution_histories
    raw = statement()
    if change=='ticker': raw['ticker']='2882.TW'
    elif change=='individual': raw['report_scope']='individual'
    elif change=='document_scope': raw['documents'][0]['report_scope']='individual'
    elif change=='missing_hash': raw['documents'][0].pop('sha256')
    elif change=='wrong_document_issuer': raw['documents'][0]['url']=raw['documents'][0]['url'].replace('co_id=2891','co_id=2882')
    elif change=='missing_value': raw['raw_twd_by_year']['2021'].pop('net_revenue')
    elif change=='bool_value': raw['raw_twd_by_year']['2021']['assets']=True
    elif change=='bad_fcf': raw['raw_twd_by_year']['2021']['free_cash_flow']+=1
    elif change=='positive_capex': raw['raw_twd_by_year']['2021']['ppe_purchase']=1
    elif change=='insurer_schema': raw['schema']='insurer_individual.v1'
    elif change=='non_contiguous': raw['years'][0]='2020'
    elif change=='huge_value': raw['raw_twd_by_year']['2021']['net_revenue']=10**400
    elif change=='malformed_url': raw['documents'][0]['url']='https://[invalid'
    assert project_financial_institution_histories(raw,'2891.TW') is None


def test_typed_basis_reaches_prompt_state_snapshot_and_unit_checks():
    from prompt_builder import format_data_for_prompt
    from state_memory import initialize_agent_state,state_view_for
    from financial_money_claims import financial_money_claim_issues
    from data_trust import apply_snapshot_size_governance
    data=data_from_projection()
    encoded=format_data_for_prompt(data)
    payload=json.loads(encoded.split('【財務資料 JSON】\n',1)[1].split('\n\n【使用規則】',1)[0])
    row=payload['history']['rows'][-1]
    assert row['revenue_billion_twd'] is None
    assert row['net_revenue_billion_twd']==244.8947
    assert payload['history']['basis']['field_sources']['net_revenue_history']['label']=='金融業合併淨收益'
    view=state_view_for('valuation',initialize_agent_state(data))['normalized_financials']
    assert view['net_revenue_history']==data['net_revenue_history']
    assert view['financial_history_basis']==data['financial_history_basis']
    snapshot=apply_snapshot_size_governance({'data':{**data,'non_core_debug':'x'*20000}},max_bytes=11000)
    assert snapshot['data']['net_revenue_history']==data['net_revenue_history']
    assert financial_money_claim_issues('2025 年合併淨收益為 244.89 億元。',data)
    assert financial_money_claim_issues('2025 年合併淨收益為 2448.95 億元。',data)==[]


def test_capital_notes_use_financial_institution_scope_and_same_year_without_sdk():
    from data_fetch.yfinance_capital_notes import build_capital_structure_notes
    data=data_from_projection()
    notes=build_capital_structure_notes(NoAnnualSdk(),{},
        **{key:data[key] for key in ('revenue_history','net_income_history','total_assets_history','total_equity_history')},
        market_cap=1e12,total_debt=1e11,financial_history_data=data)
    assert notes['equity_multiplier']!='N/A'
    assert '2025' in notes['equity_multiplier_note'] and '金融業' in notes['equity_multiplier_note']
    assert '合併淨收益' in notes['dupont_identity_note']
    assert '申報營業收入' not in notes['dupont_identity_note']


def test_bank_chart_and_growth_calculations_use_net_revenue_labels_and_paths():
    from reporting.html_chart_context import build_html_chart_context
    from financial_tools import build_financial_tool_context
    data=data_from_projection()
    chart=build_html_chart_context(data,{})
    assert chart['chart_data']['revenue']==[None]*5
    assert chart['chart_data']['netRevenue'][-1]==pytest.approx(2448.94671, abs=0.0001)
    assert chart['chart_data']['incomeSeries']==chart['chart_data']['netRevenue']
    assert chart['chart_data']['incomeLabel']=='年度合併淨收益'
    assert '合併淨收益' in chart['financial_history_chart_title']
    calculations=build_financial_tool_context(data)['calculations']
    assert 'revenue_cagr' not in calculations
    assert calculations['net_revenue_cagr']['source_path']=='data.net_revenue_history'
    assert calculations['net_revenue_cagr']['years']==data['years']
    assert calculations['latest_annual_net_revenue_growth']['growth_pct']>0


def test_changed_typed_net_revenue_requires_rerun():
    from report_refresh_diff import refresh_data_diff,refresh_requires_analysis_rerun
    before={'data':data_from_projection()};after=copy.deepcopy(before)
    after['data']['net_revenue_history'][-1]+=1
    assert refresh_requires_analysis_rerun(before,after,refresh_data_diff(before,after)) is True


def test_rendered_bank_report_keeps_typed_chart_payload_and_heading():
    from bs4 import BeautifulSoup
    from reporting.html_renderer import generate_html_report
    data=data_from_projection()
    html=generate_html_report({'ticker':'2891.TW','data':data,'pipeline_id':'v1','final_report':'資料來源驗證。'})
    soup=BeautifulSoup(html,'html.parser')
    payload=json.loads(soup.select_one('#report-chart-data').string)
    assert payload['incomeLabel']=='年度合併淨收益'
    assert payload['incomeSeries']==payload['netRevenue']
    assert '年度合併淨收益與母公司淨利（億元台幣）' in soup.get_text()


def test_financial_statement_fcf_does_not_become_normalized_industrial_dcf():
    from financial_tools import build_financial_tool_context
    data={**data_from_projection(),'current_price':50,'market_cap_raw':1e12,
          'total_debt_raw':0,'total_cash_raw':0,'shares_raw':1e10,'trailing_eps':3}
    metrics=build_financial_tool_context(data)
    assert metrics['metric_status']['dcf']['status']=='unavailable'
    assert 'financial_institution_fcf_not_normalized_for_dcf' in metrics['metric_status']['dcf']['reason_codes']
    assert 'dcf_scenarios_default' not in metrics['calculations']
    assert metrics['metric_status']['implied_pe']['status']=='available'


def test_invalid_statement_keeps_legacy_sdk_fallback_without_typed_net_revenue(monkeypatch):
    from data_fetch import yfinance_extractors as source
    from test_financial_statement_observation import StatementStock
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','1')
    baseline=source.extract_financial_histories(StatementStock(),'2891.TW',[],data_loader_cls=None,industry_context='金融保險')
    raw=statement();raw['documents'][0].pop('sha256')
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(source,'fetch_financial_institution_histories',lambda ticker:raw)
    result=source.extract_financial_histories(StatementStock(),'2891.TW',[],data_loader_cls=None,industry_context='金融保險')
    assert result['sector_specific_financials'] is None
    assert result['sector_specific_financial_audit']['status']=='degraded_enrichment'
    assert 'net_revenue_history' not in result
    assert result['revenue_history']==baseline['revenue_history']


def test_unverified_typed_array_cannot_supply_money_checks_chart_or_tools():
    from financial_money_claims import financial_money_claim_issues
    from financial_tools import build_financial_tool_context
    from reporting.html_chart_context import build_html_chart_context
    data=data_from_projection();data['net_revenue_history'][-1]+=1
    assert financial_money_claim_issues('2025 年淨收益為 244.89 億元。',data)==[]
    assert 'netRevenue' not in build_html_chart_context(data,{})['chart_data']
    assert 'net_revenue_cagr' not in build_financial_tool_context(data)['calculations']


@pytest.mark.parametrize('bank', [True, False])
def test_client_chart_configuration_uses_the_declared_series_and_label(bank):
    import shutil,subprocess
    from reporting.html_chart_context import build_html_chart_context
    node=shutil.which('node')
    if node is None: pytest.skip('Node required for chart configuration behavior')
    raw=data_from_projection() if bank else {'years':['2024','2025'],'revenue_history':[1,2], 'net_income_history':[0.4,0.6]}
    chart=build_html_chart_context(raw,{})['chart_data']
    templates=Path(__file__).parents[1]/'backend/templates/includes/charts'
    runtime=(templates/'runtime.html.j2').read_text().split('window.StockAgentReportTraceability',1)[0]
    financial=(templates/'financial.html.j2').read_text()
    script="""
const fs=require('fs'),vm=require('vm');const d=JSON.parse(fs.readFileSync(0,'utf8'));
const configurations=[];
const document={getElementById:id=>id==='report-chart-data'?{textContent:JSON.stringify(d.payload)}:
    ['revenueChart','marginChart','fcfChart','roeChart'].includes(id)?{getContext:()=>id}:null};
const sandbox={document,Chart:function(id,configuration){configurations.push({id,datasets:configuration.data.datasets});}};
vm.runInNewContext(d.runtime+d.financial,sandbox);
process.stdout.write(JSON.stringify(configurations));
"""
    result=subprocess.run([node,'-e',script],input=json.dumps({'payload':chart,'runtime':runtime,'financial':financial}),
                          capture_output=True,text=True,check=True,timeout=5)
    configs=json.loads(result.stdout)
    revenue=next(c for c in configs if c['id']=='revenueChart')['datasets'][0]
    if bank:
        assert revenue['label']=='年度合併淨收益'
        assert revenue['data']==chart['netRevenue']
        margin=next(c for c in configs if c['id']=='marginChart')['datasets'][-1]
        assert margin['label']=='母公司淨利／合併淨收益'
        assert margin['data']==chart['netRevenueMargin']
    else:
        assert revenue['label']=='年度營收'
        assert revenue['data']==[10,20]


def test_net_revenue_cannot_be_claimed_as_unqualified_industrial_revenue():
    from financial_money_claims import financial_money_claim_issues
    data=data_from_projection()
    assert financial_money_claim_issues('2025 年營業收入為 2448.95 億元。',data)
    assert financial_money_claim_issues('2025 年合併淨收益為 2448.95 億元。',data)==[]


@pytest.mark.parametrize('change', ['array_mismatch','missing_basis','missing_document_hash'])
def test_financial_dcf_restriction_cannot_reopen_on_projection_damage(change):
    from financial_tools import build_financial_tool_context
    data={**data_from_projection(),'current_price':50,'market_cap_raw':1e12,
          'total_debt_raw':0,'total_cash_raw':0,'shares_raw':1e10,'trailing_eps':3}
    if change=='array_mismatch': data['net_revenue_history'][-1]+=1
    elif change=='missing_basis': data.pop('financial_history_basis')
    else: data['sector_specific_financials']['documents'][0].pop('sha256')
    metrics=build_financial_tool_context(data)
    assert metrics['metric_status']['dcf']['status']=='unavailable'
    assert 'dcf_scenarios_default' not in metrics['calculations']


@pytest.mark.parametrize('text', ['2025 年台積電營業收入為 30000 億元。',
                                 '## 同業比較\n台積電 2025 年營收為 30000 億元。'])
def test_other_issuer_revenue_does_not_borrow_target_net_revenue_scope(text):
    from financial_money_claims import financial_money_claim_issues
    data=data_from_projection()
    data['company_identity']={'ticker':'2891.TW','official_name':'中信金','stock_id':'2891',
        'aliases':['中信金','中國信託金融控股股份有限公司']}
    assert financial_money_claim_issues(text,data)==[]


def test_target_issuer_revenue_label_remains_rejected_inside_peer_section():
    from financial_money_claims import financial_money_claim_issues
    data=data_from_projection()
    data['company_identity']={'ticker':'2891.TW','official_name':'中信金','stock_id':'2891',
        'aliases':['中信金','中國信託金融控股股份有限公司']}
    assert financial_money_claim_issues('## 同業比較\n中信金 2025 年營收為 2448.95 億元。',data)


def test_other_issuer_net_revenue_does_not_use_target_amount_for_unit_check():
    from financial_money_claims import financial_money_claim_issues
    data=data_from_projection()
    data['company_identity']={'ticker':'2891.TW','official_name':'中信金'}
    assert financial_money_claim_issues('2025 年富邦金合併淨收益為 244.89 億元。',data)==[]
    assert financial_money_claim_issues('## 同業比較\n2025 年合併淨收益為 244.89 億元。',data)==[]
    assert financial_money_claim_issues('中信金2025 年合併淨收益為 244.89 億元。',data)


def test_target_stock_code_keeps_typed_money_checks_and_sector_scope_is_not_borrowed():
    from financial_money_claims import financial_money_claim_issues
    data=data_from_projection();data['company_identity']={'ticker':'2891.TW','official_name':'中信金'}
    assert financial_money_claim_issues('中信金（2891）2025 年合併淨收益為 244.89 億元。',data)
    assert financial_money_claim_issues('2025 年金融業合併淨收益為 244.89 億元。',data)==[]
