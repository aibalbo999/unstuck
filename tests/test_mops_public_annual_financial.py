"""Public MOPS JSON replaces incomplete annual sources without losing evidence."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64,json,time
import httpx
import pytest

FIXTURE=json.loads((Path(__file__).parent/'fixtures/source_acquisition/mops_public_3443_20261011.json').read_text())
PUBLIC='TWSE MOPS public annual JSON'
PAGE='https://mops.twse.com.tw/mops/#/web/t164sb03'

@pytest.fixture(autouse=True)
def restore_fixture_provider_guard():
    # The individual-report adapter subclasses this transport at import time;
    # load it before tests replace the public factory with a fixture callable.
    import data_fetch.market_sources.ordinary_individual_annual
    from provider_resilience import clear_provider_circuits
    from provider_throttle import clear_provider_throttles
    clear_provider_circuits(PUBLIC);clear_provider_throttles(PUBLIC)
    yield
    clear_provider_circuits(PUBLIC);clear_provider_throttles(PUBLIC)

def captured_value():
    from official_response_evidence import archive_response
    templates={v['url']:archive_response(base64.b64decode(v['body_b64']),source_url=v['url'],retrieved_at=time.time())for v in FIXTURE['templates']}
    docs=[]
    for year in range(2021,2026):
        parts=[]
        for v in FIXTURE['documents']:
            if v['year']!=year:continue
            raw=base64.b64decode(v['body_b64']);url=v['url'];template=url.replace('/api/','/assets/')+'.js'
            parts.append({'year':year,'period_end':f'{year}-12-31','statement':v['statement'],'provider':PUBLIC,'url':url,'request':deepcopy(v['request_payload']),'sha256':v['sha256'],'raw_receipt':archive_response(raw,source_url=url,retrieved_at=time.time()),'unit_template_receipt':templates[template]})
        docs.append({'year':year,'period_end':f'{year}-12-31','provider':PUBLIC,'url':parts[0]['url'],'sha256':sha256(';'.join(p['sha256']for p in parts).encode()).hexdigest(),'components':parts})
    return {**deepcopy(FIXTURE['candidate_series']),'ticker':'3443.TW','currency':'TWD','report_scope':'consolidated','schema':'ordinary_consolidated_annual_history.v1','source_url':PAGE,'documents':docs,'comparative_revisions':[]}

def test_real_captured_public_five_year_receipts_can_project_including_negative_fcf():
    from data_fetch.annual_financial_source_provider import ordinary_projection
    value=captured_value();projected=ordinary_projection(value,'3443.TW')
    assert projected is not None
    assert projected['years']==['2021','2022','2023','2024','2025']
    assert projected['raw_twd_by_year']['2025']['free_cash_flow']==-2313966000
    assert projected['fcf_history'][-1]==-2.313966

def fixture_http(*,mutate=None,calls=None):
    def respond(request):
        if calls is not None:calls.append(request)
        if mutate is not None:
            changed=mutate(request)
            if changed is not None:return changed
        if str(request.url).endswith('ajax_t203sb01'):
            raw=' '.join('/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=3443&year='+str(y)+'&season=4&report_id=C'for y in range(2021,2026)).encode()
            return httpx.Response(200,content=raw,headers={'Content-Type':'text/html'})
        for v in FIXTURE['templates']:
            if str(request.url)==v['url']:return httpx.Response(200,content=base64.b64decode(v['body_b64']),headers={'Content-Type':'text/javascript'})
        payload=json.loads(request.content)
        match=next(v for v in FIXTURE['documents']if v['url']==str(request.url)and v['request_payload']==payload)
        return httpx.Response(200,content=base64.b64decode(match['body_b64']),headers={'Content-Type':'application/json'})
    return lambda **kw:httpx.Client(transport=httpx.MockTransport(respond),**kw)

def test_default_ordinary_source_uses_named_public_entry_and_full_original_receipts(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    from data_fetch.official_financial_gap_cache import fetch_official_financial_result
    original=public.PublicMopsHttp
    monkeypatch.setattr(public,'PublicMopsHttp',lambda:original(client_factory=fixture_http()))
    result=fetch_official_financial_result('3443.TW')
    assert result['audit']['provider']==PUBLIC
    assert result['audit']['status']=='success'and result['audit']['record_count']==5
    assert result['audit']['http_request_count']==19
    assert public.project_public_history(result['value'],'3443.TW')is not None

@pytest.mark.parametrize('change',['issuer','blank_duplicate_query','year','individual','quarter','fiscal_year','missing','duplicate','blank','null','bool','dash','positive_purchase','column_order','unit_field','code_bool','json_duplicate_key','subsidiary_shape','selected_subsidiary'])
def test_statement_rejects_unverified_metadata_missing_and_ambiguous_amounts(change):
    from data_fetch.market_sources.mops_public_annual import parse_statement
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    v=next(v for v in FIXTURE['documents']if v['statement']=='CashflowStatement'and v['year']==2024)
    body=json.loads(base64.b64decode(v['body_b64']));r=body['result'];row=next(x for x in r['reportList']if x[0].strip()=='取得無形資產')
    if change=='issuer':r['urlList'][0]['url']=r['urlList'][0]['url'].replace('CO_ID=3443','CO_ID=2330')
    elif change=='blank_duplicate_query':r['urlList'][0]['url']+='&CO_ID='
    elif change=='year':r['year']='112'
    elif change=='individual':r['reportType']='個別'
    elif change=='quarter':r['season']='3'
    elif change=='fiscal_year':r['fiscalYear']='4'
    elif change=='missing':r['reportList'].remove(row)
    elif change=='duplicate':r['reportList'].append(deepcopy(row))
    elif change=='blank':row[1]=''
    elif change=='null':row[1]=None
    elif change=='bool':row[1]=False
    elif change=='dash':row[1]='-'
    elif change=='positive_purchase':row[1]='361,731'
    elif change=='column_order':r['titles'][1],r['titles'][2]=r['titles'][2],r['titles'][1]
    elif change=='unit_field':r['currency']='USD'
    elif change=='code_bool':body['code']=True
    elif change=='subsidiary_shape':r['subsidiary']='not-a-list'
    elif change=='selected_subsidiary':r['subsidiaryCompanyId']='child'
    raw=json.dumps(body,ensure_ascii=False).encode()
    if change=='json_duplicate_key':raw=raw.replace(b'"code": 200',b'"code": 200, "code": 200')
    template=base64.b64decode(next(v['body_b64']for v in FIXTURE['templates']if v['url'].endswith('/t164sb05.js')))
    with pytest.raises(FilingError):parse_statement(raw,'3443',2024,'CashflowStatement',template)

def test_missing_purchase_row_is_inferred_zero_only_when_investing_section_reconciles():
    from data_fetch.market_sources.mops_public_annual import parse_statement
    v=next(v for v in FIXTURE['documents']if v['statement']=='CashflowStatement'and v['year']==2024)
    body=json.loads(base64.b64decode(v['body_b64']));rows=body['result']['reportList']
    rows.remove(next(row for row in rows if row[0].strip()=='取得無形資產'))
    total=next(row for row in rows if row[0].strip().startswith('投資活動之淨現金流'))
    total[1:3]=['-1,159,984','-366,712']
    raw=json.dumps(body,ensure_ascii=False).encode()
    template=base64.b64decode(next(v['body_b64']for v in FIXTURE['templates']if v['url'].endswith('/t164sb05.js')))
    parsed=parse_statement(raw,'3443',2024,'CashflowStatement',template,include_prior=True,
                           allow_reconciled_missing_purchases=True)
    assert parsed[2024]['PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities']==0
    assert parsed[2023]['PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities']==0
    assert parsed['inferred_zero_facts']==[
        {'period_year':2023,'fact':'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities','value_twd':0,
         'filing_year':2024,'proof':'investment_cashflows_reconcile_to_reported_net_with_nonpositive_purchases'},
        {'period_year':2024,'fact':'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities','value_twd':0,
         'filing_year':2024,'proof':'investment_cashflows_reconcile_to_reported_net_with_nonpositive_purchases'},
    ]

def test_two_missing_purchase_rows_are_both_inferred_only_when_both_periods_reconcile():
    from data_fetch.market_sources.mops_public_annual import parse_statement
    v=next(v for v in FIXTURE['documents']if v['statement']=='CashflowStatement'and v['year']==2024)
    body=json.loads(base64.b64decode(v['body_b64']));rows=body['result']['reportList']
    for label in ('取得不動產、廠房及設備','取得無形資產'):
        rows.remove(next(row for row in rows if row[0].strip()==label))
    total_index=next(i for i,row in enumerate(rows)if row[0].strip()=='投資活動之淨現金流入（流出）')
    start=next(i for i,row in enumerate(rows)if row[0].strip()=='投資活動之現金流量')
    for column in (1,2):
        rows[total_index][column]=f'{sum(int(row[column].replace(",",""))for row in rows[start+1:total_index]):,}'
    raw=json.dumps(body,ensure_ascii=False).encode()
    template=base64.b64decode(next(v['body_b64']for v in FIXTURE['templates']if v['url'].endswith('/t164sb05.js')))
    parsed=parse_statement(raw,'3443',2024,'CashflowStatement',template,include_prior=True,
                           allow_reconciled_missing_purchases=True)
    for period in (2023,2024):
        assert parsed[period]['PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities']==0
        assert parsed[period]['PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities']==0
    assert {(item['period_year'],item['fact'])for item in parsed['inferred_zero_facts']}=={
        (2023,'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'),
        (2023,'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'),
        (2024,'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'),
        (2024,'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'),
    }

@pytest.mark.parametrize('change',['total_mismatch','malformed_detail','second_missing_purchase','detail_after_total','both_missing_total_mismatch'])
def test_missing_purchase_zero_inference_fails_closed_when_investing_section_is_not_provable(change):
    from data_fetch.market_sources.mops_public_annual import parse_statement
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    v=next(v for v in FIXTURE['documents']if v['statement']=='CashflowStatement'and v['year']==2024)
    body=json.loads(base64.b64decode(v['body_b64']));rows=body['result']['reportList']
    rows.remove(next(row for row in rows if row[0].strip()=='取得無形資產'))
    total=next(row for row in rows if row[0].strip()=='投資活動之淨現金流入（流出）')
    total[1:3]=['-1,159,984','-366,712']
    if change=='total_mismatch':total[1]='-1,159,983'
    elif change=='malformed_detail':
        detail=next(row for row in rows if row[0].strip()=='取得不動產、廠房及設備');detail[1]='-'
    elif change=='second_missing_purchase':
        rows.remove(next(row for row in rows if row[0].strip()=='取得不動產、廠房及設備'))
    elif change=='both_missing_total_mismatch':
        rows.remove(next(row for row in rows if row[0].strip()=='取得不動產、廠房及設備'))
        total[1]='-1,159,983'
    else:
        total_index=rows.index(total)
        rows.insert(total_index+1,['未辨識之投資項目','0','0'])
    raw=json.dumps(body,ensure_ascii=False).encode()
    template=base64.b64decode(next(v['body_b64']for v in FIXTURE['templates']if v['url'].endswith('/t164sb05.js')))
    with pytest.raises(FilingError):
        parse_statement(raw,'3443',2024,'CashflowStatement',template,include_prior=True,
                        allow_reconciled_missing_purchases=True)

@pytest.mark.parametrize('change',['fact_value','bool_zero','issuer_request','raw_hash','raw_source','raw_http','raw_bytes','future_receipt','template_hash','template_source','scope','currency','revision','inferred_zero_facts'])
def test_admission_reextracts_originals_and_rejects_tampered_fact_and_receipt(change):
    from data_fetch.annual_financial_source_provider import ordinary_projection
    value=captured_value();part=value['documents'][0]['components'][0]
    if change=='fact_value':value['raw_twd_by_year']['2021']['free_cash_flow']+=1000
    elif change=='bool_zero':value['raw_twd_by_year']['2021']['property_purchase']=False
    elif change=='issuer_request':part['request']['companyId']='2330'
    elif change=='raw_hash':part['sha256']='0'*64
    elif change=='raw_source':part['raw_receipt']['source_url']=part['url']+'?issuer=2330'
    elif change=='raw_http':part['raw_receipt']['http_status']=503
    elif change=='raw_bytes':part['raw_receipt']['raw_response_bytes']=True
    elif change=='future_receipt':part['raw_receipt']['retrieved_at']=time.time()+600
    elif change=='template_hash':part['unit_template_receipt']['raw_response_sha256']='0'*64
    elif change=='template_source':part['unit_template_receipt']['source_url']=part['url']
    elif change=='scope':value['report_scope']='standalone'
    elif change=='currency':value['currency']='USD'
    elif change=='revision':value['comparative_revisions']=[{'fact':'Revenue','revised_twd':0}]
    else:value['inferred_zero_facts']=[{'period_year':2021,'fact':'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities','value_twd':0,'filing_year':2021,'proof':'investment_cashflows_reconcile_to_reported_net_with_nonpositive_purchases'}]
    assert ordinary_projection(value,'3443.TW')is None

def test_newer_complete_comparative_revisions_keep_original_and_revised_fact_provenance():
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_annual_histories
    def change(request):
        if str(request.url).endswith('/api/t164sb04')and json.loads(request.content)['year']=='111':
            v=next(v for v in FIXTURE['documents']if v['statement']=='IncomeStatement'and v['year']==2022)
            body=json.loads(base64.b64decode(v['body_b64']));row=next(r for r in body['result']['reportList']if r[0].strip()=='營業收入合計');row[3]='15,107,916'
            return httpx.Response(200,json=body)
    value=fetch_public_annual_histories('3443.TW',transport=PublicMopsHttp(client_factory=fixture_http(mutate=change)))
    assert value['raw_twd_by_year']['2021']['revenue_history']==15107916000
    assert value['comparative_revisions']==[{'year':2021,'fact':'Revenue','original_twd':15107915000,'revised_twd':15107916000,'original_filing_year':2021,'comparative_filing_year':2022,'kind':'restatement'}]

@pytest.mark.parametrize('comparative_value,expected_twd',[('0',0),('-1,234',-1234000)])
def test_missing_intangible_row_can_only_be_recovered_from_explicit_next_annual_comparative(comparative_value,expected_twd):
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_annual_histories,project_public_history
    tag='PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'
    def change(request):
        if not str(request.url).endswith('/api/t164sb05'):return
        year=int(json.loads(request.content)['year'])+1911
        if year not in {2024,2025}:return
        v=next(v for v in FIXTURE['documents']if v['statement']=='CashflowStatement'and v['year']==year)
        body=json.loads(base64.b64decode(v['body_b64']));rows=body['result']['reportList'];row=next(r for r in rows if r[0].strip()=='取得無形資產')
        if year==2024:rows.remove(row)
        else:row[2]=comparative_value
        return httpx.Response(200,json=body)
    value=fetch_public_annual_histories('3443.TW',transport=PublicMopsHttp(client_factory=fixture_http(mutate=change)))
    assert value['raw_twd_by_year']['2024']['intangible_purchase']==expected_twd
    assert value['comparative_revisions']==[{'year':2024,'fact':tag,'original_twd':None,'revised_twd':expected_twd,'original_filing_year':2024,'comparative_filing_year':2025,'kind':'missing_fact_fill'}]
    assert value['raw_twd_by_year']['2023']['intangible_purchase']==FIXTURE['candidate_series']['raw_twd_by_year']['2023']['intangible_purchase']
    coverage=next(v for v in value['comparative_coverage']if v['year']==2023)
    assert coverage['status']=='partial_nonconflicting'and coverage['missing_facts']==[tag]and coverage['retained_primary_facts']==[tag]
    assert project_public_history(value,'3443.TW')is not None
    tampered=deepcopy(value);next(v for v in tampered['comparative_coverage']if v['year']==2023)['status']='complete'
    assert project_public_history(tampered,'3443.TW')is None

@pytest.mark.parametrize('case',['latest_missing','consecutive_missing','conflicting_partial','duplicate','dash','bool','other_fact_missing'])
def test_missing_row_continuation_never_accepts_unresolved_or_ambiguous_annual_evidence(case):
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_annual_histories
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    def change(request):
        if not str(request.url).endswith('/api/t164sb05'):return
        year=int(json.loads(request.content)['year'])+1911
        affected={2025}if case=='latest_missing'else{2023,2024}if case=='consecutive_missing'else{2024}
        if year not in affected:return
        v=next(v for v in FIXTURE['documents']if v['statement']=='CashflowStatement'and v['year']==year)
        body=json.loads(base64.b64decode(v['body_b64']));rows=body['result']['reportList'];row=next(r for r in rows if r[0].strip()=='取得無形資產')
        if case=='duplicate':rows.append(deepcopy(row))
        elif case=='dash':row[1]='-'
        elif case=='bool':row[1]=False
        elif case=='other_fact_missing':rows.remove(next(r for r in rows if r[0].strip()=='營業活動之淨現金流入（流出）'))
        else:
            rows.remove(row)
            if case=='conflicting_partial':next(r for r in rows if r[0].strip()=='取得不動產、廠房及設備')[2]='-2'
        return httpx.Response(200,json=body)
    with pytest.raises(FilingError):
        fetch_public_annual_histories('3443.TW',transport=PublicMopsHttp(client_factory=fixture_http(mutate=change)))

def test_actual_auo_originals_recover_explicit_2024_comparative_without_claiming_complete_2023_comparison(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    capture=json.loads((Path(__file__).parent/'fixtures/source_acquisition/mops_public_2409_comparative_20261011.json').read_text())
    calls=[]
    def respond(request):
        calls.append(request)
        if str(request.url).endswith('ajax_t203sb01'):
            return httpx.Response(200,content=base64.b64decode(capture['index_body_b64']),headers={'Content-Type':'text/html'})
        for v in capture['templates']:
            if str(request.url)==v['url']:return httpx.Response(200,content=base64.b64decode(v['body_b64']),headers={'Content-Type':'text/javascript'})
        query=json.loads(request.content)
        v=next(v for v in capture['documents']if v['url']==str(request.url)and v['request_payload']==query)
        return httpx.Response(200,content=base64.b64decode(v['body_b64']),headers={'Content-Type':'application/json'})
    original=public.PublicMopsHttp
    monkeypatch.setattr(public,'PublicMopsHttp',lambda:original(client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(respond),**kw)))
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    from provider_correlation import correlation_scope
    request=FetchRequest(ticker='2409.TW')
    with correlation_scope(replace=True,ticker='2409.TW',fetch_id='isolated-public-auo-fetch'):
        result=AnnualFinancialSourceProvider().fetch(request,{'data':{'ticker':'2409.TW','quote_type':'EQUITY','currency':'TWD','financial_currency':'TWD'}})
    assert result.status=='success',result.audit
    assert result.value['years']==['2021','2022','2023','2024','2025']and len(calls)==19
    assert result.value['raw_twd_by_year']['2024']['intangible_purchase']==0
    assert result.value['raw_twd_by_year']['2023']['intangible_purchase']==0
    assert result.value['comparative_revisions']==capture['expected_revisions'][:2]
    assert result.value['inferred_zero_facts']==[
        {'period_year':2023,'fact':'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities','value_twd':0,
         'filing_year':2024,'proof':'investment_cashflows_reconcile_to_reported_net_with_nonpositive_purchases'},
        {'period_year':2024,'fact':'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities','value_twd':0,
         'filing_year':2024,'proof':'investment_cashflows_reconcile_to_reported_net_with_nonpositive_purchases'},
    ]
    assert result.audit['inferred_zero_facts']==result.value['inferred_zero_facts']
    coverage=next(v for v in result.audit['comparative_coverage']if v['year']==2023)
    assert coverage['status']=='complete'and len(coverage['available_facts'])==9
    assert coverage['inferred_zero_facts']==['PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities']
    assert result.audit['coverage_status']=='complete'and result.audit['record_count']==5
    assert public.project_public_history(result.value,'2409.TW')is not None

def test_429_stops_remaining_requests_and_honors_retry_after_before_next_index():
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_financial_result
    cache_store.set_cache_backend(InMemoryCache());calls=[]
    def refused(request):
        if str(request.url).endswith('/assets/t164sb03.js'):return httpx.Response(429,headers={'Retry-After':'600'})
    try:
        factory=fixture_http(mutate=refused,calls=calls)
        first=fetch_public_financial_result('3443.TW',transport=PublicMopsHttp(client_factory=factory))
        assert first['value']is None and first['audit']['error_kind']=='rate_limited'and len(calls)==2
        second=fetch_public_financial_result('3443.TW',transport=PublicMopsHttp(client_factory=factory))
        assert second['value']is None and second['audit']['error_kind']in {'cooldown','ProviderRateLimitOpenError'}and second['audit']['http_request_sent']is False
        assert len(calls)==2
        from provider_throttle import clear_provider_throttles
        clear_provider_throttles(PUBLIC) # Only the isolated macro fixture, not the endpoint cooldown.
        third=fetch_public_financial_result('3443.TW',transport=PublicMopsHttp(client_factory=factory))
        assert third['audit']['error_kind']=='cooldown'and len(calls)==2
    finally:cache_store.reset_cache_store_for_tests()

def test_formal_saved_report_source_boundary_preserves_quotes_body_and_all_quality_gates(tmp_path,monkeypatch):
    import asyncio
    from report_refresh_service import refresh_report_data_snapshot
    from data_fetch.service import StockDataService
    from test_report_annual_financial_source_refresh import report
    from test_report_refresh_acquisition_audit import init_db,events
    import data_fetch.market_sources.mops_public_annual as public
    init_db();storage,name,keys,before=report('3443.TW')
    original=public.PublicMopsHttp;monkeypatch.setattr(public,'PublicMopsHttp',lambda:original(client_factory=fixture_http()))
    result=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    after=json.loads(storage.get_report(keys.data_key).content)
    assert result['analysis_text_stale']is True
    assert after['data']['years']==['2021','2022','2023','2024','2025']and after['data']['fcf_history'][-1]==-2.313966
    for field in ('current_price','daily_market_data','revenue_ttm_raw','free_cash_flow_raw','operating_cash_flow_raw'):assert after['data'][field]==before['data'][field]
    assert after['analysis_evidence']==before['analysis_evidence']
    for gate in ('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert after[gate]==before[gate]
    assert storage.get_report(keys.html_key).content==storage.get_report(keys.md_key).content==b'original conclusions'
    rows=events();assert len(rows)==1 and rows[0]['provider']==PUBLIC and rows[0]['status']=='success'and rows[0]['record_count']==5

def test_normal_uncached_annual_flow_uses_public_source_before_SDK_and_names_unit_origin(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    from data_fetch.yfinance_extractors import _extract_financial_histories_uncached
    original=public.PublicMopsHttp;monkeypatch.setattr(public,'PublicMopsHttp',lambda:original(client_factory=fixture_http()))
    # Permit this mocked official seam; the boundary still denies all sockets.
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    class NoSDK:
        def __getattr__(self,name):pytest.fail('complete official source must not query SDK: '+name)
    notes=[];result=_extract_financial_histories_uncached(NoSDK(),'3443.TW',notes,quote_type='EQUITY',industry_context='Semiconductors')
    assert result['official_financial_audit']['provider']==PUBLIC and result['official_financial_audit']['record_count']==5
    assert result['fcf_history'][-1]==-2.313966 and result['primary_financial_audit']is None
    assert any('JSON'in n and '新台幣仟元'in n for n in notes)

@pytest.mark.parametrize('shape',[None,False,'not-a-part'])
def test_malformed_component_receipt_fails_closed(shape):
    from data_fetch.annual_financial_source_provider import ordinary_projection
    value=captured_value();value['documents'][0]['components'][0]=shape
    assert ordinary_projection(value,'3443.TW')is None

def test_filing_received_before_its_fiscal_year_closed_cannot_project():
    from data_fetch.annual_financial_source_provider import ordinary_projection
    value=captured_value();value['documents'][-1]['components'][0]['raw_receipt']['retrieved_at']=1577836800.0
    assert ordinary_projection(value,'3443.TW')is None

def test_final_original_readback_expiry_must_not_return_new_source_success(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    real=time.monotonic;clock={'elapsed':0.0};calls=[];reads={'count':0}
    monkeypatch.setattr(public.time,'monotonic',lambda:real()+clock['elapsed'])
    original_read=public.read_response
    def readback(proof):
        raw=original_read(proof);reads['count']+=1
        if reads['count']>19:clock['elapsed']=46.0
        return raw
    monkeypatch.setattr(public,'read_response',readback)
    result=public.fetch_public_financial_result('3443.TW',transport=public.PublicMopsHttp(client_factory=fixture_http(calls=calls)))
    assert len(calls)==19 and reads['count']>19
    assert result['value']is None and result['audit']['status']!='success'and result['audit']['record_count']==0

def test_contradictory_issuer_abbreviation_cannot_establish_complete_company_series():
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_financial_result
    def mutate(request):
        if str(request.url).endswith('/api/t164sb03')and json.loads(request.content)['year']=='114':
            v=next(v for v in FIXTURE['documents']if v['statement']=='BalanceSheet'and v['year']==2025)
            body=json.loads(base64.b64decode(v['body_b64']));body['result']['companyAbbreviation']='台積電'
            return httpx.Response(200,json=body)
    result=fetch_public_financial_result('3443.TW',transport=PublicMopsHttp(client_factory=fixture_http(mutate=mutate)))
    assert result['value']is None and result['audit']['record_count']==0

def test_subsidiary_options_do_not_change_explicit_parent_scope():
    from data_fetch.market_sources.mops_public_annual import parse_statement
    v=next(v for v in FIXTURE['documents']if v['statement']=='CashflowStatement'and v['year']==2024)
    body=json.loads(base64.b64decode(v['body_b64']));body['result']['subsidiary']=[{'value':'child','label':'child option'}]
    template=base64.b64decode(next(v['body_b64']for v in FIXTURE['templates']if v['url'].endswith('/t164sb05.js')))
    facts=parse_statement(json.dumps(body,ensure_ascii=False).encode(),'3443',2024,'CashflowStatement',template)
    assert facts[2024]['CashFlowsFromUsedInOperatingActivities']==6242286000

def test_corrupt_deflate_original_fails_closed_and_is_restored():
    from data_fetch.annual_financial_source_provider import ordinary_projection
    value=captured_value();path=Path(value['documents'][0]['components'][0]['raw_receipt']['raw_response_path'])
    original=path.read_bytes();corrupt=bytearray(original);corrupt[10]=255
    try:
        path.write_bytes(corrupt)
        assert ordinary_projection(value,'3443.TW')is None
    finally:path.write_bytes(original)

def test_archive_zlib_failure_stops_without_implicit_multi_year_retry(monkeypatch):
    import zlib
    import data_fetch.market_sources.mops_public_annual as public
    calls=[]
    def unavailable(*a,**kw):raise zlib.error('isolated archive fixture')
    monkeypatch.setattr(public,'archive_response',unavailable)
    result=public.fetch_public_financial_result('3443.TW',transport=public.PublicMopsHttp(client_factory=fixture_http(calls=calls)))
    assert result['value']is None and result['audit']['record_count']==0
    assert len(calls)==1 and result['audit']['http_request_count']==1

def test_complete_annual_operation_reuses_one_anonymous_client_and_closes_it():
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_annual_histories
    calls=[];created=[];fixture_factory=fixture_http(calls=calls)
    def factory(**kwargs):
        client=fixture_factory(**kwargs);created.append(client);return client
    value=fetch_public_annual_histories('3443.TW',transport=PublicMopsHttp(client_factory=factory))
    assert value['years']==['2021','2022','2023','2024','2025']
    assert len(calls)==19
    assert len(created)==1, 'One complete query must not recreate nineteen TCP/TLS pools'
    assert all(client.is_closed for client in created)
    assert all('cookie'not in request.headers and 'authorization'not in request.headers for request in calls)

def test_pooled_response_cookies_never_become_next_query_credentials():
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_annual_histories
    calls=[];created=[]
    def set_cookie(request):
        if str(request.url).endswith('/assets/t164sb03.js'):
            template=next(v for v in FIXTURE['templates']if v['url']==str(request.url))
            return httpx.Response(200,content=base64.b64decode(template['body_b64']),headers={
                'Content-Type':'text/javascript','Set-Cookie':'application_session=isolated_fixture; Domain=mops.twse.com.tw; Path=/; Secure'})
    fixture_factory=fixture_http(mutate=set_cookie,calls=calls)
    def factory(**kwargs):
        client=fixture_factory(**kwargs);created.append(client);return client
    value=fetch_public_annual_histories('3443.TW',transport=PublicMopsHttp(client_factory=factory))
    assert len(value['years'])==5 and len(calls)==19 and len(created)==1
    assert all('cookie'not in request.headers and 'authorization'not in request.headers for request in calls)
    assert created[0].is_closed and not list(created[0].cookies.jar)

@pytest.mark.parametrize('failure,expected_calls',[('403',2),('429',2),('503',2),('connect_error',2),('bad_unit',4),('bad_json',5)])
def test_pooled_operation_rejections_close_without_retry(failure,expected_calls):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_financial_result
    calls=[];created=[]
    def reject(request):
        if failure=='bad_json'and str(request.url).endswith('/api/t164sb03'):
            return httpx.Response(200,content=b'not-json',headers={'Content-Type':'application/json'})
        if not str(request.url).endswith('/assets/t164sb03.js'):return
        if failure.isdigit():return httpx.Response(int(failure),headers={'Retry-After':'600'})
        if failure=='connect_error':raise httpx.ConnectError('isolated connection fixture',request=request)
        if failure=='bad_unit':return httpx.Response(200,content=b'changed unit renderer',headers={'Content-Type':'text/javascript'})
    fixture_factory=fixture_http(mutate=reject,calls=calls)
    def factory(**kwargs):
        client=fixture_factory(**kwargs);created.append(client);return client
    cache_store.set_cache_backend(InMemoryCache())
    try:
        result=fetch_public_financial_result('3443.TW',transport=PublicMopsHttp(client_factory=factory))
        assert result['value']is None and result['audit']['status']!='success'and result['audit']['record_count']==0
        assert len(calls)==expected_calls and len(created)==1
        assert created[0].is_closed and not list(created[0].cookies.jar)
    finally:cache_store.reset_cache_store_for_tests()

def test_pooled_each_request_uses_remaining_original_deadline(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    base=time.monotonic();clock={'elapsed':0.0};calls=[];created=[]
    monkeypatch.setattr(public.time,'monotonic',lambda:base+clock['elapsed'])
    def elapse(request):clock['elapsed']+=3
    fixture_factory=fixture_http(mutate=elapse,calls=calls)
    def factory(**kwargs):
        client=fixture_factory(**kwargs);created.append(client);return client
    result=public.fetch_public_financial_result('3443.TW',transport=public.PublicMopsHttp(client_factory=factory,seconds=8))
    assert result['value']is None and result['audit']['error_kind']=='timeout'
    assert len(calls)==3 and len(created)==1 and created[0].is_closed
    assert [r.extensions['timeout']['read']for r in calls]==[5.,5.,2.]
    assert [r.extensions['timeout']['connect']for r in calls]==[2.,2.,2.]

def test_standalone_requests_and_separate_annual_operations_do_not_share_client_lifetime():
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_annual_histories,template_url
    created=[];fixture_factory=fixture_http()
    def factory(**kwargs):
        client=fixture_factory(**kwargs);created.append(client);return client
    transport=PublicMopsHttp(client_factory=factory)
    transport.request(template_url('BalanceSheet'));transport.request(template_url('BalanceSheet'))
    assert len(created)==2 and all(c.is_closed for c in created)
    fetch_public_annual_histories('3443.TW',transport=transport)
    fetch_public_annual_histories('3443.TW',transport=transport)
    assert len(created)==4 and all(c.is_closed for c in created)

def test_client_cleanup_expiry_cannot_promote_complete_bodies_to_source_success(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    base=time.monotonic();clock={'elapsed':0.0};calls=[];created=[]
    monkeypatch.setattr(public.time,'monotonic',lambda:base+clock['elapsed'])
    fixture_factory=fixture_http(calls=calls)
    def factory(**kwargs):
        client=fixture_factory(**kwargs);created.append(client);close=client.close
        def finish():
            close();clock['elapsed']=46.
        client.close=finish
        return client
    result=public.fetch_public_financial_result('3443.TW',transport=public.PublicMopsHttp(client_factory=factory))
    assert len(calls)==19 and len(created)==1 and created[0].is_closed
    assert result['value']is None and result['audit']['record_count']==0 and result['audit']['error_kind']=='timeout'

def test_transient_public_json_document_failure_falls_back_to_audited_official_xbrl(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    import data_fetch.market_sources.official_xbrl_financial as xbrl
    from search_provider_runtime import SourceResponseError
    http=public.PublicMopsHttp()
    http.components.extend([
        {'url':xbrl.INDEX_URL,'http_request_sent':True,'http_status':200,'status':'complete'},
        {'url':public.api_url('BalanceSheet'),'http_request_sent':True,'http_status':None,'error_kind':'timeout'},
    ])
    def unavailable(_ticker,*,transport=None):raise SourceResponseError('timeout')
    monkeypatch.setattr(public,'fetch_public_annual_histories',unavailable)
    value=captured_value();value.update(ticker='2367.TW',source_url=xbrl.INDEX_URL)
    value['documents']=[{'year':int(year),'period_end':year+'-12-31','url':xbrl.BASE+'/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=2367&year='+year+'&season=4&report_id=C','sha256':('a' if i%2==0 else 'b')*64}for i,year in enumerate(value['years'])]
    def fallback(ticker,*,request_observer=None):
        assert ticker=='2367.TW'
        for index in range(6):request_observer({'url':xbrl.INDEX_URL if index==0 else value['documents'][index-1]['url'],'http_request_sent':True,'http_status':200})
        return deepcopy(value)
    monkeypatch.setattr(xbrl,'fetch_official_annual_histories',fallback)
    result=public._fetch_public_financial_result_uncached('2367.TW',transport=http)
    audit=result['audit']
    assert result['value']['source_url']==xbrl.INDEX_URL
    assert audit['status']=='success'and audit['record_count']==5
    assert audit['source_mix']=='official_xbrl_after_public_json_transport_failure'
    assert audit['actual_provider']==xbrl.PROVIDER
    assert audit['http_request_count']==8 and audit['http_request_sent']is True
    assert len(audit['component_statuses']['xbrl_fallback'])==6
    from data_fetch.annual_financial_source_provider import ordinary_projection
    assert ordinary_projection(result['value'],'2367.TW')is not None

def test_annual_source_provider_admits_verified_xbrl_fallback_as_actual_provider(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    import data_fetch.market_sources.official_xbrl_financial as xbrl
    import data_fetch.official_financial_gap_cache as gap_cache
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    from provider_correlation import correlation_scope
    from search_provider_runtime import SourceResponseError
    http=public.PublicMopsHttp()
    http.components.extend([
        {'url':xbrl.INDEX_URL,'http_request_sent':True,'http_status':200,'status':'complete'},
        {'url':public.api_url('BalanceSheet'),'http_request_sent':True,'http_status':None,'error_kind':'transport_error'},
    ])
    def unavailable(_ticker,*,transport=None):raise SourceResponseError('transport_error')
    monkeypatch.setattr(public,'fetch_public_annual_histories',unavailable)
    monkeypatch.setattr(gap_cache,'fetch_official_financial_result',lambda ticker:public._fetch_public_financial_result_uncached(ticker,transport=http))
    value=captured_value();value.update(ticker='2367.TW',source_url=xbrl.INDEX_URL)
    value['documents']=[{'year':int(year),'period_end':year+'-12-31','url':xbrl.BASE+'/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=2367&year='+year+'&season=4&report_id=C','sha256':('a' if i%2==0 else'b')*64}for i,year in enumerate(value['years'])]
    def fallback(_ticker,*,request_observer=None):
        for index in range(6):request_observer({'url':xbrl.INDEX_URL if index==0 else value['documents'][index-1]['url'],'http_request_sent':True,'http_status':200})
        return deepcopy(value)
    monkeypatch.setattr(xbrl,'fetch_official_annual_histories',fallback)
    context={'data':{'ticker':'2367.TW','quote_type':'EQUITY','currency':'TWD','financial_currency':'TWD'}}
    with correlation_scope(replace=True,ticker='2367.TW',fetch_id='isolated-xbrl-fallback-fetch'):
        raw=public._fetch_public_financial_result_uncached('2367.TW',transport=http)
        from data_fetch.annual_financial_source_provider import ordinary_projection,_valid_observation
        projected=ordinary_projection(raw['value'],'2367.TW')
        assert projected is not None
        assert _valid_observation(raw['audit'],'2367.TW',xbrl.PROVIDER,projected['years'][-1]),raw['audit']
        monkeypatch.setattr(gap_cache,'fetch_official_financial_result',lambda _ticker:raw)
        result=AnnualFinancialSourceProvider().fetch(FetchRequest(ticker='2367.TW'),context)
    assert result.status=='success',result.audit
    assert result.value['years']==['2021','2022','2023','2024','2025']
    assert result.audit['provider']==xbrl.PROVIDER and result.audit['status']=='success'
    assert result.audit['source_mix']=='official_xbrl_after_public_json_transport_failure'
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    from data_fetch.yfinance_extractors import _extract_financial_histories_uncached
    class NoSDK:
        def __getattr__(self,name):pytest.fail('verified official annual fallback must not query SDK: '+name)
    notes=[]
    extracted=_extract_financial_histories_uncached(NoSDK(),'2367.TW',notes,quote_type='EQUITY',industry_context='Semiconductors')
    assert extracted['official_financial_audit']['source_mix']=='official_xbrl_after_public_json_transport_failure'
    assert 'xbrl_fallback'in extracted['official_financial_audit']['component_statuses']
    assert any('JSON 文件發生暫時傳輸錯誤' in note for note in notes)

@pytest.mark.parametrize('error_kind,status_code,expected_fallback',[
    ('timeout',None,True),('transport_error',None,True),
    ('server_error',500,True),('server_error',503,True),('server_error',504,True),
    ('timeout',403,False),('access_denied',403,False),('rate_limited',429,False),
    ('http_error',404,False),('parse_error',None,False)])
def test_public_json_fallback_covers_transport_and_retryable_server_failures_only(monkeypatch,error_kind,status_code,expected_fallback):
    import data_fetch.market_sources.mops_public_annual as public
    import data_fetch.market_sources.official_xbrl_financial as xbrl
    from search_provider_runtime import SourceResponseError
    http=public.PublicMopsHttp()
    http.components.extend([
        {'url':xbrl.INDEX_URL,'http_request_sent':True,'http_status':200},
        {'url':public.api_url('BalanceSheet'),'http_request_sent':True,'http_status':status_code,'error_kind':error_kind},
    ])
    def unavailable(_ticker,*,transport=None):raise SourceResponseError(error_kind,status_code=status_code)
    monkeypatch.setattr(public,'fetch_public_annual_histories',unavailable)
    called=[]
    monkeypatch.setattr(xbrl,'fetch_official_annual_histories',lambda *_a,**_k:called.append(True))
    result=public._fetch_public_financial_result_uncached('2367.TW',transport=http)
    assert called==([True]if expected_fallback else[])
    assert result['value']is None and result['audit']['status']!='success'

@pytest.mark.parametrize('failure_kind',["index_transport_error","index_server_error","missing_required_fact"])
def test_public_json_fallback_requires_a_received_index_and_never_repairs_missing_facts(monkeypatch,failure_kind):
    import data_fetch.market_sources.mops_public_annual as public
    import data_fetch.market_sources.official_xbrl_financial as xbrl
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    from search_provider_runtime import SourceResponseError
    http=public.PublicMopsHttp()
    if failure_kind=='index_transport_error':
        http.components.append({'url':xbrl.INDEX_URL,'http_request_sent':True,'http_status':None,'error_kind':'transport_error'})
        error=SourceResponseError('transport_error')
    elif failure_kind=='index_server_error':
        http.components.append({'url':xbrl.INDEX_URL,'http_request_sent':True,'http_status':503,'error_kind':'server_error'})
        error=SourceResponseError('server_error',status_code=503)
    else:
        http.components.extend([
            {'url':xbrl.INDEX_URL,'http_request_sent':True,'http_status':200},
            {'url':public.api_url('CashflowStatement'),'http_request_sent':True,'http_status':200,'status':'complete'},
        ])
        error=FilingError('missing required public annual fact')
    monkeypatch.setattr(public,'fetch_public_annual_histories',lambda *_a,**_k:(_ for _ in()).throw(error))
    called=[];monkeypatch.setattr(xbrl,'fetch_official_annual_histories',lambda *_a,**_k:called.append(True))
    result=public._fetch_public_financial_result_uncached('2367.TW',transport=http)
    assert called==[]
    assert result['value']is None and result['audit']['status']!='success'
