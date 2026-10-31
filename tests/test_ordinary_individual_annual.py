"""Five-year fixtures are explicitly synthetic; only saved 2025 is native."""
from pathlib import Path
from copy import deepcopy
import json
import time
from xml.etree import ElementTree as ET
import httpx
import pytest

S=Path(__file__).resolve().parent
D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261016/remaining-source-expansion/financial-next-capability'
TICKER='2646.TW'
TAGS=['Revenue','ProfitLoss','GrossProfit','ProfitLossFromOperatingActivities','Assets','Equity',
      'CashFlowsFromUsedInOperatingActivities','PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities',
      'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities']

def synthetic_filing(year,*,issuer='2646',company_name='星宇航空股份有限公司',category='Individual report',
                     omit_intangible=False,reconcile_investing=False,reconcile_delta=0):
    contexts=''.join(f'<xbrli:context id="{kind}{y}"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">{issuer}</xbrli:identifier></xbrli:entity><xbrli:period>'+(
        f'<xbrli:instant>{y}-12-31</xbrli:instant>'if kind=='i'else f'<xbrli:startDate>{y}-01-01</xbrli:startDate><xbrli:endDate>{y}-12-31</xbrli:endDate>')+'</xbrli:period></xbrli:context>'for y in(year-1,year)for kind in('i','d'))
    meta={'CompanyID':issuer,'CompanyChineseName':company_name,'Year':str(year),'Quarter':'4','ReportCategory':category,'ReportType':'Financial report (general)','IndustrySector':'Commercial and industrial'}
    notes=''.join(f'<ix:nonNumeric name="tifrs-notes:{k}" contextRef="d{year}">{v}</ix:nonNumeric>'for k,v in meta.items())
    facts='';investing_by_code={};investing_totals=[]
    for y in(year-1,year):
        investing_total=0
        for i,tag in enumerate(TAGS):
            kind='i'if tag in('Assets','Equity')else'd';sign=' sign="-"'if tag.startswith('PurchaseOf')else''
            value=10 if tag.startswith('PurchaseOf')else 1000+i+y
            if tag=='PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'and omit_intangible:continue
            fact=f'<ix:nonFraction name="ifrs-full:{tag}" contextRef="{kind}{y}" unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal"{sign}>{value}</ix:nonFraction>'
            if reconcile_investing and tag in ('PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities','PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'):
                code='B02700'if tag=='PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'else'B07100'
                investing_by_code.setdefault(code,[]).append(fact)
                investing_total+=(-value if sign else value)*1000
            else:facts+=fact
        if reconcile_investing:
            other='<ix:nonFraction name="tifrs-SCF:IncreaseInPrepaymentsForBusinessFacilities" contextRef="d'+str(y)+'" unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal">1</ix:nonFraction>'
            investing_by_code.setdefault('B03800',[]).append(other);investing_total+=1000+reconcile_delta
            total_sign=' sign="-"'if investing_total<0 else''
            total=f'<ix:nonFraction name="tifrs-SCF:NetCashFlowsFromUsedInInvestingActivities" contextRef="d{y}" unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal"{total_sign}>{abs(investing_total)//1000}</ix:nonFraction>'
            investing_totals.append(total)
    investing_rows=''.join(f'<tr><td>{code}</td><td>{"".join(facts)}</td></tr>'for code,facts in investing_by_code.items())
    if reconcile_investing:investing_rows+='<tr><td>BBBB</td><td>'+''.join(investing_totals)+'</td></tr>'
    table=('<table><tr><td>投資活動之現金流量 Cash flows from (used in) investing activities</td></tr>'+investing_rows+'</table>')if reconcile_investing else''
    return ('<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><!-- SYNTHETIC CONTRACT FIXTURE, NOT A NATIVE RECEIPT -->'+contexts+'<xbrli:unit id="TWD"><xbrli:measure>iso4217:TWD</xbrli:measure></xbrli:unit>'+notes+facts+table+'</html>').encode()

def index(a=range(2021,2026),c=(),issuer='2646'):
    return ('<html>SYNTHETIC INDEX'+''.join(f'<a href="/server-java/FileDownLoad?functionName=t164sb01&amp;step=9&amp;co_id={issuer}&amp;year={y}&amp;season=4&amp;report_id={scope}">year</a>'for scope,years in(('A',a),('C',c))for y in years)+'</html>').encode()

def transport(*,bodies=None,index_body=None,status=None,headers=None):
    from data_fetch.market_sources.ordinary_individual_annual import IndividualMopsHttp
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        if 'ajax_t203sb01' in request.url.path:
            return httpx.Response(200,content=index()if index_body is None else index_body,headers={'content-type':'text/html'})
        year=int(request.url.params['year'])
        if status:return httpx.Response(status,headers={'retry-after':'120'},content=b'rejected')
        return httpx.Response(200,content=(bodies or{}).get(year,synthetic_filing(year)),headers=headers or{'content-type':'application/xml'})
    client=httpx.MockTransport(handler)
    return IndividualMopsHttp(client_factory=lambda **kw:httpx.Client(transport=client,**kw)),calls

def fetch(ticker=TICKER,**kwargs):
    from data_fetch.market_sources.ordinary_individual_annual import fetch_annual_result
    http,calls=transport(**kwargs);return fetch_annual_result(ticker,transport=http),calls

def context():
    return {'ticker':TICKER,'stock_id':'2646','company_name':'星宇航空','quote_type':'EQUITY','currency':'TWD','financial_currency':'TWD','sector':'Industrials','industry':'Airlines'}

def test_full_five_year_individual_has_typed_basis_and_six_actual_requests():
    from data_fetch.annual_financial_source_provider import project_source_value
    result,calls=fetch();assert result['audit']['status']=='success';assert len(calls)==6
    value=result['value'];assert value['schema']=='ordinary_individual.v1';assert value['report_scope']=='individual'
    assert value['years']==['2021','2022','2023','2024','2025']
    projected=project_source_value(value,TICKER);assert projected is not None
    basis=projected['financial_history_basis'];assert basis['report_scope']=='individual'
    assert basis['field_sources']['net_income_history']['fact']=='ifrs-full:ProfitLoss'
    assert basis['field_sources']['total_equity_history']['fact']=='ifrs-full:Equity'
    assert all('net_income_attributable'not in r for r in value['raw_twd_by_year'].values())
    assert result['audit']['http_request_count']==6

def test_2033_five_year_individual_source_preserves_issuer_and_scope():
    from data_fetch.market_sources.ordinary_individual_annual import ISSUERS, select_basis
    ticker='2033.TW';issuer='2033';company='佳大世界股份有限公司'
    assert ISSUERS.get(ticker)==company
    assert select_basis(index(a=range(2013,2026),issuer=issuer),issuer)==('individual',[2021,2022,2023,2024,2025])
    bodies={year:synthetic_filing(year,issuer=issuer,company_name=company) for year in range(2021,2026)}
    result,calls=fetch(ticker,index_body=index(a=range(2013,2026),issuer=issuer),bodies=bodies)
    assert result['audit']['status']=='success' and len(calls)==6
    value=result['value']
    assert value['ticker']==ticker and value['years']==['2021','2022','2023','2024','2025']
    assert value['schema']=='ordinary_individual.v1' and value['report_scope']=='individual'

def test_missing_intangible_is_zero_only_when_official_investing_detail_reconciles():
    from data_fetch.market_sources.ordinary_individual_annual import parse_individual_filing
    issuer='2033';company='佳大世界股份有限公司'
    raw=synthetic_filing(2025,issuer=issuer,company_name=company,omit_intangible=True,reconcile_investing=True)
    parsed=parse_individual_filing(raw,issuer,2025)
    assert parsed[2025]['intangible_purchase']==0
    proof=next(item for item in parsed['inferred_zero_facts']if item['period_year']==2025)
    assert proof['fact']=='PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'
    assert proof['value_twd']==0 and proof['filing_year']==2025
    assert proof['proof']=='mops_individual_investing_detail_reconciles'
    assert proof['detail_sum_twd']==proof['statement_total_twd'] and proof['detail_row_count']==2
    mismatched=synthetic_filing(2025,issuer=issuer,company_name=company,omit_intangible=True,
                                reconcile_investing=True,reconcile_delta=1000)
    rejected=parse_individual_filing(mismatched,issuer,2025)
    assert 'intangible_purchase' not in rejected[2025]
    assert not any(item['period_year']==2025 for item in rejected['inferred_zero_facts'])

def test_2033_full_history_replays_reconciled_zero_evidence():
    from data_fetch.annual_financial_source_provider import project_source_value
    issuer='2033';company='佳大世界股份有限公司';ticker='2033.TW'
    bodies={year:synthetic_filing(year,issuer=issuer,company_name=company,omit_intangible=True,reconcile_investing=True)
            for year in range(2021,2026)}
    result,_=fetch(ticker,index_body=index(a=range(2013,2026),issuer=issuer),bodies=bodies)
    assert result['audit']['status']=='success'
    assert len(result['value']['inferred_zero_facts'])==5
    assert all(item['value_twd']==0 and item['proof']=='mops_individual_investing_detail_reconciles'
               for item in result['value']['inferred_zero_facts'])
    assert all(row['intangible_purchase']==0 for row in result['value']['raw_twd_by_year'].values())
    assert project_source_value(result['value'],ticker) is not None
    tampered=deepcopy(result['value']);tampered['inferred_zero_facts'][0]['statement_total_twd']+=1
    assert project_source_value(tampered,ticker) is None

def test_2033_source_context_accepts_only_verified_issuer_names():
    from data_fetch.annual_financial_source_provider import validate_context as validate_annual_context
    from data_fetch.market_sources.ordinary_individual_annual import ISSUERS
    ticker='2033.TW'
    data={'ticker':ticker,'stock_id':'2033','quote_type':'EQUITY','currency':'TWD','financial_currency':'TWD',
          'sector':'Basic Materials','industry':'Steel',
          'company_identity':{'official_name':'佳大','legal_name':ISSUERS[ticker]}}
    validate_annual_context(data,ticker)
    wrong=deepcopy(data);wrong['company_identity']['official_name']='星宇航空'
    with pytest.raises(ValueError,match='ordinary_individual_name_conflict'):
        validate_annual_context(wrong,ticker)

def test_2033_annual_provider_routes_verified_history_through_individual_adapter(monkeypatch):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    import data_fetch.market_sources.ordinary_individual_annual as module
    ticker='2033.TW';issuer='2033';company='佳大世界股份有限公司'
    bodies={year:synthetic_filing(year,issuer=issuer,company_name=company) for year in range(2021,2026)}
    result,_=fetch(ticker,index_body=index(a=range(2013,2026),issuer=issuer),bodies=bodies)
    assert result['audit']['status']=='success'
    result['audit'].pop('fetch_id',None)
    seen=[]
    monkeypatch.setattr(module,'fetch_annual_result',lambda current:(seen.append(current) or deepcopy(result)))
    data={'ticker':ticker,'stock_id':issuer,'quote_type':'EQUITY','currency':'TWD','financial_currency':'TWD',
          'sector':'Basic Materials','industry':'Steel',
          'company_identity':{'official_name':'佳大','legal_name':company}}
    output=AnnualFinancialSourceProvider().fetch(FetchRequest(ticker),{'data':data})
    assert seen==[ticker] and output.status=='success'
    assert output.provider==module.PROVIDER
    assert output.value['schema']=='ordinary_individual.v1' and output.value['report_scope']=='individual'
    assert output.value['years']==['2021','2022','2023','2024','2025']

@pytest.mark.parametrize('a,c',[(range(2022,2026),()),([2021,2022,2024,2025],()),(range(2021,2026),[2024])])
def test_incomplete_or_mixed_scope_index_stops_before_any_filing(a,c):
    result,calls=fetch(index_body=index(a,c));assert result['value']is None;assert len(calls)==1

def test_c_priority_is_explicit_and_does_not_read_a(monkeypatch):
    import data_fetch.market_sources.ordinary_individual_annual as m
    seen=[]
    def c(ticker,http,index_original=None):seen.append(index_original);raise ValueError('sentinel C collector')
    monkeypatch.setattr(m,'_fetch_consolidated',c)
    result,calls=fetch(index_body=index(c=range(2021,2026)))
    assert len(seen)==1 and len(calls)==1 and result['value']is None

@pytest.mark.parametrize('replace',[
    (b'Individual report',b'Consolidated report'),(b'>2646<',b'>2647<'),
    (b'iso4217:TWD',b'iso4217:USD'),(b'scale="3"',b'scale="0"'),
    (b'sign="-"',b'sign="+"'),(b'2025-01-01',b'2025-07-01'),
    (b'ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities',b'ifrs-full:Unknown'),
])
def test_bad_filing_fails_closed(replace):
    raw=synthetic_filing(2025).replace(*replace);result,_=fetch(bodies={2025:raw});assert result['value']is None

def test_changed_raw_original_cannot_be_projected():
    from data_fetch.annual_financial_source_provider import project_source_value
    result,_=fetch();value=deepcopy(result['value']);value['raw_twd_by_year']['2025']['profit_loss']+=1
    assert project_source_value(value,TICKER)is None

def test_actual_native_2025_has_nine_individual_fields_and_no_standalone_claim():
    from data_fetch.market_sources.ordinary_individual_annual import parse_individual_filing
    parsed=parse_individual_filing((D/'2646-2025-research.body').read_bytes(),'2646',2025)
    assert parsed[2025]['profit_loss']==272608000 and parsed[2024]['intangible_purchase']==-64111000
    assert parsed[2025]['equity']==31396288000

def test_normal_source_provider_does_not_misroute_nonfinancial_typed_basis(monkeypatch):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    import data_fetch.market_sources.ordinary_individual_annual as m
    result,_=fetch();seen=[]
    # Replayed callback fixture uses the caller's correlation, never another fetch.
    result['audit'].pop('fetch_id',None)
    monkeypatch.setattr(m,'fetch_annual_result',lambda ticker:(seen.append(ticker)or deepcopy(result)))
    data={**context(),'financial_history_basis':{'statement_schema':'ordinary_individual.v1'}}
    out=AnnualFinancialSourceProvider().fetch(FetchRequest(TICKER),{'data':data})
    assert seen==[TICKER]and out.status=='success'

def test_prompt_state_claims_quant_and_refresh_keep_individual_semantics():
    from data_fetch.annual_financial_source_provider import project_source_value
    from prompt_builder import format_data_for_prompt
    from quant_input_contract import read_quant_inputs
    from financial_money_claims import financial_money_claim_issues
    from state_memory import initialize_agent_state,state_view_for
    from annual_financial_source_refresh import apply_annual_history_values
    result,_=fetch();value=result['value'];projected=project_source_value(value,TICKER)
    data={**context(),**projected,'shares_raw':1e8,'current_price':20,'market_cap_raw':2e9,'total_debt_raw':1e8,'total_cash_raw':1e8,'free_cash_flow_raw':1e8,'trailing_eps':2}
    text=format_data_for_prompt(data)
    assert 'ordinary_individual.v1'in text and 'ifrs-full:ProfitLoss'in text and 'individual'in text
    state=state_view_for(4,initialize_agent_state(data));assert state['normalized_financials']['financial_history_basis']['report_scope']=='individual'
    assert 'ordinary_individual_group_basis_unverified'in read_quant_inputs(data)[2]['dcf']
    wrong='2025年本公司合併淨利為0.03026億元。'
    assert any('個別' in issue for issue in financial_money_claim_issues(wrong,data))
    merged=deepcopy(data);apply_annual_history_values(merged,projected,value,data)
    assert merged['financial_history_basis']['report_scope']=='individual'
    assert 'individual'in merged['equity_multiplier_note']
    assert merged['ttm_vs_latest_annual_revenue_change']=='N/A'


def test_older_complete_c_cannot_hide_newer_a_basis():
    result,calls=fetch(index_body=index(c=range(2020,2024)))
    assert result['value'] is None
    assert len(calls)==1, 'C 2020–2023 overlaps newer A 2021–2025: reject before renderers'


@pytest.fixture(autouse=True)
def isolated_provider_guards():
    import cache_store
    from cache_backends import InMemoryCache
    from provider_resilience import clear_provider_circuits
    from provider_throttle import clear_provider_throttles
    cache_store.set_cache_backend(InMemoryCache())
    clear_provider_circuits();clear_provider_throttles()
    yield
    clear_provider_circuits();clear_provider_throttles();cache_store.reset_cache_store_for_tests()


def test_next_year_is_selected_from_new_index_not_fixed_file(monkeypatch):
    import data_fetch.market_sources.ordinary_individual_annual as m
    from datetime import date
    class NextYear(date):
        @classmethod
        def today(cls):return cls(2027,3,31)
    monkeypatch.setattr(m,'date',NextYear)
    assert m.select_basis(index(a=range(2021,2027)),'2646')==('individual',[2022,2023,2024,2025,2026])
    assert m.select_basis(index(a=range(2021,2027),c=range(2022,2027)),'2646')==('consolidated',[2022,2023,2024,2025,2026])


@pytest.mark.parametrize('status',[403,429])
def test_restricted_response_stops_without_retry_and_next_fetch_is_local(status):
    first,calls=fetch(status=status)
    assert first['value'] is None and len(calls)==2
    assert first['audit']['error_kind']==('access_denied'if status==403 else'rate_limited')
    second,calls=fetch()
    assert second['value'] is None and calls==[]
    assert second['audit']['http_request_sent'] is False


@pytest.mark.parametrize('provider',['TWSE MOPS public annual JSON','TWSE MOPS issuer annual statements'])
def test_existing_aggregate_circuit_is_honored_before_http(provider):
    from provider_resilience import get_circuit_breaker
    breaker=get_circuit_breaker(provider);breaker.state='OPEN';breaker.last_failure_time=time.time()
    result,calls=fetch()
    assert result['value'] is None and calls==[]
    assert result['audit']['event_kind']=='local_block'


def test_total_deadline_is_not_extended_by_index_or_completed_originals():
    from data_fetch.market_sources.ordinary_individual_annual import fetch_annual_result
    http,calls=transport();http.deadline=time.monotonic()-1
    result=fetch_annual_result(TICKER,transport=http)
    assert result['value']is None and calls==[] and result['audit']['error_kind']=='timeout'


def test_explicit_comparative_can_fill_missing_older_intangible_but_never_zero():
    from data_fetch.market_sources.ordinary_individual_annual import IX
    root=ET.fromstring(synthetic_filing(2021))
    for node in list(root):
        if node.tag==IX+'nonFraction'and node.get('contextRef')=='d2021'and node.get('name').endswith('IntangibleAssetsClassifiedAsInvestingActivities'):
            root.remove(node)
    result,_=fetch(bodies={2021:ET.tostring(root,encoding='utf-8',xml_declaration=True)})
    assert result['audit']['status']=='success'
    value=result['value'];assert value['raw_twd_by_year']['2021']['intangible_purchase']==-10000
    assert value['comparative_revisions']==[{'year':2021,'fact':'intangible_purchase','original_twd':None,'revised_twd':-10000,'original_filing_year':2021,'comparative_filing_year':2022,'kind':'missing_fact_fill'}]


def test_conflicting_incomplete_comparative_cannot_revise_primary():
    from data_fetch.market_sources.ordinary_individual_annual import IX
    root=ET.fromstring(synthetic_filing(2022))
    for node in list(root):
        if node.tag!=IX+'nonFraction' or node.get('contextRef')!='d2021':continue
        if node.get('name').endswith('IntangibleAssetsClassifiedAsInvestingActivities'):root.remove(node)
        elif node.get('name')=='ifrs-full:Revenue':node.text='9999'
    result,_=fetch(bodies={2022:ET.tostring(root,encoding='utf-8',xml_declaration=True)})
    assert result['value']is None and 'conflicting incomplete'in result['audit']['message']


@pytest.mark.parametrize('change',[
    lambda v:v.update(report_scope='consolidated'),
    lambda v:v['raw_twd_by_year']['2025'].update(profit_loss=float(v['raw_twd_by_year']['2025']['profit_loss'])),
    lambda v:v['documents'][-1]['raw_receipt'].update(retrieved_at=time.time()+3600),
    lambda v:v['published_index_receipt'].update(raw_response_sha256='0'*64),
    lambda v:v['documents'][-1].update(provider='other'),
    lambda v:v['documents'][-1].update(url=v['documents'][-1]['url'].replace('report_id=A','report_id=C')),
])
def test_full_original_replay_rejects_scope_types_receipt_and_url_tampering(change):
    from data_fetch.annual_financial_source_provider import project_source_value
    result,_=fetch();value=deepcopy(result['value']);change(value)
    assert project_source_value(value,TICKER)is None


@pytest.mark.parametrize('change',[
    lambda d:d.update(stock_id='2647'),
    lambda d:d.update(company_identity={'ticker':'2647.TW'}),
    lambda d:d.update(company_identity={'quote_type':'ETF'}),
    lambda d:d.update(company_identity={'official_name':'另一家公司'}),
])
def test_explicit_context_identity_conflict_blocks_before_default_transport(monkeypatch,change):
    import asyncio
    import data_fetch.market_sources.ordinary_individual_annual as m
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest
    calls=[];monkeypatch.setattr(m,'IndividualMopsHttp',lambda:calls.append(1))
    data=context();change(data)
    with pytest.raises(ValueError):asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker(TICKER),'financial_statements',context={'data':data}))
    assert calls==[]


def test_default_service_actual_acquisition_refresh_chart_and_retention_contract(monkeypatch):
    import asyncio
    import data_fetch.market_sources.ordinary_individual_annual as m
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest
    from annual_financial_source_refresh import merge_annual_financial_source
    from reporting.html_chart_context import build_html_chart_context
    from report_annual_history_retention import retain_verified_annual_history
    http,calls=transport();monkeypatch.setattr(m,'IndividualMopsHttp',lambda:http)
    old={**context(),'current_price':20,'revenue_ttm_raw':999,'data_source_notes':[],'source_audit':[]}
    original=deepcopy(old)
    result=asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker(TICKER),'financial_statements',context={'data':old}))
    audit=result.data['source_audit'][0];value=result.data['financial_statements']
    assert audit['status']=='success'and audit['fetch_id']and audit['provider']=='TWSE MOPS issuer annual statements'
    assert len(calls)==6 and audit['http_request_count']==6 and audit['cache_hit']is False
    merged=merge_annual_financial_source(old,[],value,[audit],TICKER)
    assert old==original and merged['current_price']==20 and merged['revenue_ttm_raw']==999
    assert merged['ttm_vs_latest_annual_revenue_change']=='N/A'
    chart=build_html_chart_context(merged,{})
    assert '個別'in chart['financial_history_chart_title']and chart['chart_data']['netIncomeLabel']=='個別本期損益'
    incoming={**context(),'years':['2025'],'source_audit':[]}
    assert retain_verified_annual_history({'ticker':TICKER,'data':merged,'source_audit':[audit]},incoming,TICKER)==incoming


def test_normal_full_extractor_preserves_typed_basis_and_shared_cache_epoch(monkeypatch):
    import data_fetch.market_sources.ordinary_individual_annual as m
    from data_fetch.yfinance_extractors import extract_financial_histories
    http,calls=transport();monkeypatch.setattr(m,'IndividualMopsHttp',lambda:http)
    # Only the extractor's feature admission changes; MockTransport owns all
    # native requests and the wrapper continues blocking real network sockets.
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    notes=[]
    first=extract_financial_histories(object(),TICKER,notes,quote_type='EQUITY',industry_context='Airlines',finmind_use_cache=True)
    assert len(calls)==6 and first['financial_history_basis']['report_scope']=='individual'
    assert first['sector_specific_financials']['schema']=='ordinary_individual.v1'
    stamp=first['official_financial_audit']['fetched_at']
    second=extract_financial_histories(object(),TICKER,[],quote_type='EQUITY',industry_context='Airlines',finmind_use_cache=True)
    assert len(calls)==6 and second['official_financial_audit']['cache_hit']is True
    assert second['official_financial_audit']['fetched_at']==stamp
    assert second['financial_history_basis']==first['financial_history_basis']
    assert second['sector_specific_financials']==first['sector_specific_financials']


def test_complete_current_c_stays_consolidated_through_existing_collector():
    # Explicitly synthetic issuer adaptation; it proves dispatch, not a native
    # 2646 consolidated filing. Renderer bytes retain the real version contract.
    import base64
    from test_mops_public_annual_financial import FIXTURE
    from data_fetch.market_sources.ordinary_individual_annual import IndividualMopsHttp,fetch_annual_result
    from data_fetch.annual_financial_source_provider import project_source_value
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        if 'ajax_t203sb01'in request.url.path:return httpx.Response(200,content=index(c=range(2021,2026)),headers={'content-type':'text/html'})
        for v in FIXTURE['templates']:
            if str(request.url)==v['url']:return httpx.Response(200,content=base64.b64decode(v['body_b64']),headers={'content-type':'text/javascript'})
        payload=json.loads(request.content);assert payload['companyId']=='2646'
        v=next(v for v in FIXTURE['documents']if str(request.url)==v['url']and v['request_payload']['year']==payload['year'])
        body=json.loads(base64.b64decode(v['body_b64']));body['result']['companyAbbreviation']='星宇航空'
        for ref in body['result']['urlList']:ref['url']=ref['url'].replace('CO_ID=3443','CO_ID=2646')
        return httpx.Response(200,json=body)
    http=IndividualMopsHttp(client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(handler),**kw))
    result=fetch_annual_result(TICKER,transport=http)
    assert result['audit']['status']=='success'and len(calls)==19
    assert result['value']['schema']=='ordinary_consolidated_annual_history.v1'
    assert project_source_value(result['value'],TICKER)['report_scope']=='consolidated'
    assert all('report_id=A'not in u for u in calls)


def test_full_core_does_not_forward_individual_profit_to_pe_river(monkeypatch):
    from test_data_fetch_fixtures import _patch_common_fetch_dependencies,FakeProvider
    from data_fetch import yfinance_core_fetch as core
    import data_fetch.market_sources.ordinary_individual_annual as m
    _patch_common_fetch_dependencies(monkeypatch,resolved_ticker=TICKER)
    http,calls=transport();monkeypatch.setattr(m,'IndividualMopsHttp',lambda:http)
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(core,'fetch_monthly_revenue_records',lambda *a,**k:([],None))
    monkeypatch.setattr(core,'load_taiwan_stock_info_records',lambda:[])
    captured=[]
    def enrichment(**kwargs):
        captured.append(kwargs)
        return {'pe_river_chart':{'eps_twd':[999],'bands':{'15x':[999]},'source':'fixture'}}
    monkeypatch.setattr(core,'fetch_sync_enrichment_bundle',enrichment)
    data=core.fetch_stock_data(TICKER,skip_optional_http=True,market_data_provider=FakeProvider(TICKER))
    assert 'error'not in data, data.get('error')
    assert calls and captured
    assert captured[0]['net_income_history']==[], 'individual ProfitLoss cannot be group EPS'
    assert data['pe_river_chart']['bands']=={} and data['pe_river_chart']['eps_twd']==[]
    assert data['pe_river_chart']['fallback_reason']=='ordinary_individual_group_basis_unverified'
    assert data['ttm_vs_latest_annual_revenue_change']=='N/A'
    assert '個別'in data['equity_multiplier_note']and '母公司'not in data['dupont_identity_note']


def test_default_pe_provider_stops_before_individual_to_group_conversion(monkeypatch):
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.enrichment_providers import PeRiverChartProvider
    from data_fetch.types import FetchRequest
    import data_fetch.market_sources.valuation as valuation
    result,_=fetch();data={**context(),**project_source_value(result['value'],TICKER),'shares_raw':5e7}
    calls=[]
    monkeypatch.setattr(valuation,'build_pe_river_chart_data',lambda *args:(calls.append(args)or{'bands':{'15x':[1]},'eps_twd':[1]}))
    out=PeRiverChartProvider().fetch(FetchRequest.from_ticker(TICKER),{'data':data})
    assert calls==[],'the normal missing-core plan must not rebuild forbidden EPS bands'
    assert out.status=='unavailable'and out.audit['record_count']==0
    assert out.audit['http_request_sent']is False and out.audit['event_kind']=='local_block'


def test_default_stock_data_service_full_registry_keeps_individual_basis(monkeypatch):
    import asyncio
    from test_data_fetch_fixtures import _patch_common_fetch_dependencies,FakeProvider
    from data_fetch import yfinance_core_fetch as core,yfinance_snapshot as snapshot,workflow
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest
    import data_fetch.market_sources.ordinary_individual_annual as m
    _patch_common_fetch_dependencies(monkeypatch,resolved_ticker=TICKER)
    http,calls=transport();monkeypatch.setattr(m,'IndividualMopsHttp',lambda:http)
    monkeypatch.setattr(snapshot,'get_market_data_provider',lambda ticker:FakeProvider(ticker))
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(core,'fetch_monthly_revenue_records',lambda *a,**k:([],None))
    monkeypatch.setattr(core,'load_taiwan_stock_info_records',lambda:[])
    captured=[]
    monkeypatch.setattr(core,'fetch_sync_enrichment_bundle',lambda **kw:(captured.append(kw)or{}))
    # The normal registry and financial/PE-river consumers are real. Unrelated
    # optional source plans are outside this deterministic financial fixture.
    applies=workflow.source_is_applicable
    monkeypatch.setattr(workflow,'source_is_applicable',lambda source,data,ticker:
                        applies(source,data,ticker)if source in {'financial_statements','pe_river_chart'}else False)
    result=asyncio.run(StockDataService().fetch_async(FetchRequest.from_ticker(TICKER,skip_optional_http=True)))
    data=result.data
    assert 'error'not in data and len(calls)==6
    assert data['financial_history_basis']['statement_schema']=='ordinary_individual.v1'
    assert data['sector_specific_financials']['report_scope']=='individual'
    assert data['ttm_vs_latest_annual_revenue_change']=='N/A'and captured[0]['net_income_history']==[]
    assert data['pe_river_chart']['bands']=={}and data['pe_river_chart']['eps_twd']==[]
    annual=[a for a in data['source_audit']if a['source']=='financial_statements'and a['status']=='success'and a['provider']==m.PROVIDER]
    assert len(annual)==1 and annual[0]['record_count']==5 and annual[0]['fetch_id']
    blocked=[a for a in data['source_audit']if a.get('error_kind')=='ordinary_individual_group_basis_unverified']
    assert len(blocked)==1 and blocked[0]['http_request_sent']is False


@pytest.mark.parametrize('missing',[False,True])
def test_normal_payload_cannot_promote_individual_history_into_ttm(missing):
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.yfinance_core_context import build_yfinance_payload_vars,_PAYLOAD_KEYS,_QUALITY_INPUT_KEYS
    result,_=fetch();p=project_source_value(result['value'],TICKER)
    fields={k:None for k in (*_PAYLOAD_KEYS,*_QUALITY_INPUT_KEYS)}
    revenue=None if missing else 1e9;fcf=None if missing else 1e8
    fields.update(p,ticker=TICKER,info={},data_source_notes=[],current_price=20,market_cap=1e9,pe_ratio=10,
                  week_52_high=30,week_52_low=10,shares_outstanding=5e7,revenue_ttm=revenue,free_cash_flow=fcf,
                  trailing_eps=2,revenue_growth=.1,earnings_growth=.1,profit_margin=.1)
    payload,_=build_yfinance_payload_vars(fields)
    assert payload['revenue_ttm']==revenue and payload['free_cash_flow']==fcf
    assert payload['ttm_vs_latest_annual_revenue_change']is None
    assert payload['latest_annual_revenue_growth']is not None


def test_individual_equity_claim_must_not_be_relabelled_parent_equity():
    from data_fetch.annual_financial_source_provider import project_source_value
    from financial_money_claims import financial_money_claim_issues
    from data_fetch.market_sources.ordinary_individual_annual import IX
    bodies={}
    for year in range(2021,2026):
        root=ET.fromstring(synthetic_filing(year))
        for node in root.iter(IX+'nonFraction'):node.text=str(int(node.text)*1000)
        bodies[year]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    result,_=fetch(bodies=bodies);data={**context(),**project_source_value(result['value'],TICKER)}
    assert any('個別'in x for x in financial_money_claim_issues('2025年本公司母公司權益總額為30.30億元。',data))
    assert financial_money_claim_issues('2025年本公司個別權益總額為30.30億元。',data)==[]
    assert financial_money_claim_issues('2025年本公司個別本期損益為30.26億元。',data)==[]
    assert financial_money_claim_issues('2025年本公司個別權益總額為3030億元。',data)


def test_native_2025_profit_and_equity_money_claim_units():
    """Native 2025/2024 facts; other years are synthetic contract scaffolding."""
    from hashlib import sha256
    from data_fetch.annual_financial_source_provider import project_source_value
    from financial_money_claims import financial_money_claim_issues
    raw=(D/'2646-2025-research.body').read_bytes()
    assert sha256(raw).hexdigest()=='e4639afec6e44c15cfbab5cb89e89abf2f249cc803ee77ab3cf9acf606d4d1d7'
    result,_=fetch(bodies={2025:raw})
    data={**context(),**project_source_value(result['value'],TICKER)}
    assert result['value']['raw_twd_by_year']['2025']['profit_loss']==272608000
    assert result['value']['raw_twd_by_year']['2025']['equity']==31396288000
    assert result['value']['raw_twd_by_year']['2024']['profit_loss']==1324438000
    assert financial_money_claim_issues('2025年本公司個別本期損益為2.72608億元。',data)==[]
    assert financial_money_claim_issues('2025年本公司個別權益總額為313.96288億元。',data)==[]
    assert financial_money_claim_issues('2024年本公司個別本期損益為13.24438億元。',data)==[]
    assert financial_money_claim_issues('2025年本公司個別本期損益為272.608億元。',data)
    assert financial_money_claim_issues('2025年本公司個別權益總額為31396.288億元。',data)
