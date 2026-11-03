"""Mixed insurance/merchandise income must not become revenue or bank income."""
import base64
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

CAPTURE=json.loads((Path(__file__).parent/'fixtures/source_acquisition/mops_public_2905_20261103.json').read_text())


def body(year,statement):
    return base64.b64decode(next(x['body_b64']for x in CAPTURE['documents']if x['year']==year and x['statement']==statement))


def transport(mutate=None):
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,INDEX_URL
    def respond(request):
        url=str(request.url)
        if url==INDEX_URL:raw=base64.b64decode(CAPTURE['index']['body_b64'])
        elif '/assets/'in url:raw=base64.b64decode(next(x['body_b64']for x in CAPTURE['templates']if x['url']==url))
        else:
            p=json.loads(request.content);year=int(p['year'])+1911
            raw=base64.b64decode(next(x['body_b64']for x in CAPTURE['documents']if x['year']==year and x['url']==url))
        if mutate:raw=mutate(request,raw)
        return httpx.Response(200,content=raw,headers={'Content-Type':'application/json'if '/api/'in url else'text/javascript'if '/assets/'in url else'text/html'})
    return PublicMopsHttp(client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(respond),**kw))


def captured_value():
    from data_fetch.market_sources.mixed_income_annual import fetch_histories
    return fetch_histories('2905.TW',transport=transport())


def test_complete_originals_preserve_reported_income_parent_scope_and_restatement():
    from data_fetch.market_sources.mixed_income_annual import project_history
    value=captured_value();projected=project_history(value,'2905.TW')
    assert projected is not None
    rows=value['raw_twd_by_year']
    assert rows['2021']['total_income']==188373202000
    assert rows['2025']['net_income_attributable']==755071000
    assert rows['2025']['net_income_attributable']!=-421009000  # comprehensive income
    assert rows['2021']['operating_cash_flow']==66501638000
    assert rows['2021']['free_cash_flow']==61404624000
    assert value['comparative_revisions']==[{'year':2021,'fact':'operating_cash_flow','original_twd':66479018000,'revised_twd':66501638000,'original_filing_year':2021,'comparative_filing_year':2022,'kind':'restatement'}]
    assert all(projected[k]==[None]*5 for k in ('revenue_history','gross_profit_history','operating_income_history'))
    assert 'net_revenue_history'not in projected


@pytest.mark.parametrize('change',['parent_in_comprehensive','parent_duplicate','header_value','missing_header','header_order','income_total','tax','attribution','balance','equity','issuer','scope','period','unit','null','boolean','missing_purchase','positive_purchase','duplicate_key','template'])
def test_bad_source_metadata_scopes_and_equations_fail_closed(change):
    from data_fetch.market_sources.mixed_income_annual import parse_statement
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    s='BalanceSheet'if change in ('balance','equity')else'CashflowStatement'if 'purchase'in change else'IncomeStatement'
    v=json.loads(body(2025,s));r=v['result'];rows=r['reportList']
    def row(label):return next(x for x in rows if x[0].strip()==label)
    if change=='parent_in_comprehensive':row('母公司業主')[1]='-421,009'
    elif change=='parent_duplicate':rows.insert(rows.index(row('母公司業主')),deepcopy(row('母公司業主')))
    elif change=='header_value':row('淨利（淨損）歸屬於：')[1]='0'
    elif change=='missing_header':rows.remove(row('淨利（淨損）歸屬於：'))
    elif change=='header_order':
        a=rows.index(row('淨利（淨損）歸屬於：'));b=rows.index(row('綜合損益總額歸屬於：'));rows[a],rows[b]=rows[b],rows[a]
    elif change=='income_total':row('收入合計')[1]='160,442,000'
    elif change=='tax':row('所得稅費用（利益）')[1]='0'
    elif change=='attribution':row('非控制股權')[1]='0'
    elif change=='balance':row('資產總計')[1]='1'
    elif change=='equity':row('非控制權益')[1]='0'
    elif change=='issuer':r['urlList'][0]['url']=r['urlList'][0]['url'].replace('2905','2330')
    elif change=='scope':r['reportType']='個別'
    elif change=='period':r['year']='113'
    elif change=='unit':r['currency']='USD'
    elif change=='null':row('收入合計')[1]=None
    elif change=='boolean':row('收入合計')[1]=True
    elif change=='missing_purchase':rows.remove(row('取得無形資產'))
    elif change=='positive_purchase':row('取得無形資產')[1]='1'
    raw=json.dumps(v,ensure_ascii=False).encode()
    if change=='duplicate_key':raw=raw.replace(b'"code": 200',b'"code": 200, "code": 200')
    t=base64.b64decode(next(x['body_b64']for x in CAPTURE['templates']if x['url'].endswith({'BalanceSheet':'03','IncomeStatement':'04','CashflowStatement':'05'}[s]+'.js')))
    if change=='template':t+=b' '
    with pytest.raises(FilingError):parse_statement(raw,'2905.TW',2025,s,t)


@pytest.mark.parametrize('change',['raw_value','revision','bool_year','bool_fact','wrong_ticker','wrong_scope','request','hash','index_missing','index_incomplete','newer_individual','template_receipt'])
def test_replay_rejects_saved_value_manifest_and_index_tampering(change):
    from data_fetch.market_sources.mixed_income_annual import project_history
    from data_fetch.market_sources.mops_public_annual import INDEX_URL
    from official_response_evidence import archive_response,read_response
    v=captured_value();part=v['documents'][0]['components'][0]
    if change=='raw_value':v['raw_twd_by_year']['2021']['total_income']+=1000
    elif change=='revision':v['comparative_revisions']=[]
    elif change=='bool_year':v['documents'][0]['year']=True
    elif change=='bool_fact':v['raw_twd_by_year']['2021']['ppe_purchase']=False
    elif change=='wrong_ticker':v['ticker']='2330.TW'
    elif change=='wrong_scope':v['report_scope']='individual'
    elif change=='request':part['request']['companyId']='2330'
    elif change=='hash':part['sha256']='0'*64
    elif change=='index_missing':v.pop('published_index_receipt')
    elif change in ('index_incomplete','newer_individual'):
        old=v['published_index_receipt'];raw=read_response(old)
        raw=raw[:-8]if change=='index_incomplete'else raw.replace(b'</html>',b' /server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=2905&year=2026&season=4&report_id=A </html>')
        v['published_index_receipt']=archive_response(raw,source_url=INDEX_URL,retrieved_at=old['retrieved_at'])
    else:part['unit_template_receipt']['raw_response_sha256']='0'*64
    assert project_history(v,'2905.TW')is None


def test_typed_projection_prompts_and_dcf_keep_distinct_income_contract():
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.financial_history_basis import prompt_history_basis,financial_institution_history_metrics
    from prompt_builder_helpers import _prompt_financial_institution_history
    from quant_input_contract import read_quant_inputs
    v=captured_value();p=project_source_value(v,'2905.TW');assert p is not None
    data={'ticker':'2905.TW',**p}
    assert prompt_history_basis(data)['statement_schema']==v['schema']
    assert financial_institution_history_metrics(data)=={}
    prompt=_prompt_financial_institution_history(data)
    assert prompt['rows'][-1]['total_income_billion_twd']==160.442  # shared four-decimal prompt display
    assert 'not_bank_net_revenue'in prompt['basis_note']
    assert 'mixed_income_fcf_not_normalized_for_dcf'in read_quant_inputs(data)[2]['dcf']
    data['sector_specific_financials']['raw_twd_by_year']['2025']['total_income']+=1000
    assert prompt_history_basis(data)=={}
    assert _prompt_financial_institution_history(data)=={}
    assert 'mixed_income_basis_unverified'in read_quant_inputs(data)[2]['dcf']


def test_normal_source_provider_selects_exact_issuer_without_yahoo_industry_guess(monkeypatch):
    from data_fetch.market_sources import mixed_income_annual as source
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest,FetchOptions
    original=source.fetch_result
    monkeypatch.setattr(source,'fetch_result',lambda ticker:original(ticker,transport=transport()))
    request=FetchRequest(ticker='2905.TW',options=FetchOptions(force_refresh=False))
    from provider_correlation import correlation_scope
    with correlation_scope(replace=True,ticker='2905.TW',fetch_id='isolated-mixed-income-source'):
        result=AnnualFinancialSourceProvider().fetch(request,{'data':{'ticker':'2905.TW','currency':'TWD','financial_currency':'TWD','instrument_type':'EQUITY','sector':'Consumer Cyclical'}})
    assert result.status=='success',result.audit
    assert result.value['schema']==source.SCHEMA
    assert result.audit['record_count']==5


def test_core_path_uses_same_original_projection_and_preserves_http_components(monkeypatch):
    from data_fetch.market_sources import mixed_income_annual as mixed
    from data_fetch import yfinance_extractors as source
    original=mixed.fetch_result
    monkeypatch.setattr(mixed,'fetch_result',lambda ticker:original(ticker,transport=transport()))
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    class NoSdk:
        def __getattr__(self,name):raise AssertionError('official mixed-income source must avoid redundant SDK '+name)
    notes=[]
    result=source._extract_financial_histories_uncached(NoSdk(),'2905.TW',notes,industry_context='貿易百貨')
    assert result['years']==['2021','2022','2023','2024','2025']
    assert result['revenue_history']==[None]*5
    assert result['net_income_history'][-1]==0.755071
    audit=result['sector_specific_financial_audit']
    assert audit['http_request_count']==len(audit['component_statuses'])==19
    assert all(x['response_complete']is True for x in audit['component_statuses'].values())
    assert '淨收益為獨立欄位'not in audit['message']
    assert notes and all('官方 XBRL 專用科目'not in n for n in notes)


@pytest.mark.parametrize('change',['name','ubn','forbidden'])
def test_explicit_context_identity_conflicts_are_rejected(change):
    from data_fetch.annual_financial_source_provider import validate_context
    data={'ticker':'2905.TW','currency':'TWD','financial_currency':'TWD','instrument_type':'EQUITY','company_identity':{}}
    data['company_identity'][{'name':'legal_name','ubn':'official_ubn','forbidden':'forbidden_aliases'}[change]]={'name':'三商美邦人壽保險股份有限公司','ubn':'00000000','forbidden':['三商']}[change]
    with pytest.raises(ValueError):validate_context(data,'2905.TW')


def test_normal_report_snapshot_prompt_and_chart_keep_unknown_general_revenue():
    from data_fetch.annual_financial_source_provider import project_source_value
    from annual_financial_source_refresh import apply_annual_history_values
    from prompt_builder import format_data_for_prompt
    from reporting.html_chart_context import build_html_chart_context
    from data_fetch.yfinance_capital_notes import build_capital_structure_notes
    v=captured_value();p=project_source_value(v,'2905.TW');data={'ticker':'2905.TW','financial_currency':'TWD'}
    apply_annual_history_values(data,p,v,{'revenue_ttm_raw':123,'free_cash_flow_raw':999})
    assert data['revenue_cagr_5yr']==data['ttm_vs_latest_annual_revenue_change']=='N/A'
    assert data['gross_margin_history']==data['net_margin_history']==[None]*5
    assert data['dupont_identity_note']==''
    prompt=format_data_for_prompt(data)
    payload=json.loads(prompt.split('【財務資料 JSON】\n',1)[1].split('\n\n【使用規則】',1)[0])
    assert payload['history']['rows'][-1]['revenue_billion_twd']is None
    assert payload['history']['financial_institution']['rows'][-1]['total_income_billion_twd']==160.442
    chart=build_html_chart_context(data,{})
    assert chart['chart_data']['incomeSeries']==[None]*5
    assert '一般營收口徑未提供'in chart['financial_history_chart_title']
    class NoSdk:
        def __getattr__(self,name):raise AssertionError(name)
    capital=build_capital_structure_notes(NoSdk(),{},revenue_history=data['revenue_history'],
        net_income_history=data['net_income_history'],total_assets_history=data['total_assets_history'],
        total_equity_history=data['total_equity_history'],market_cap=123,total_debt=12,financial_history_data=data)
    assert capital['dupont_identity_note']==''
    assert capital['equity_multiplier']!='N/A'
    assert '多業務合併'in capital['equity_multiplier_note']
    assert '/Volumes/'not in prompt
    from report_evidence_gap_details import cash_flow_detail
    detail=cash_flow_detail(data)
    assert detail['status']=='sector_annual_originals_verified'
    assert detail['free_cash_flow_twd']==11892101000
    assert detail['industrial_dcf_applicable']is False
