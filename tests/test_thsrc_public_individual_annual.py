"""Real 2025 bodies, synthetic other years; neither is a new HTTP sample."""
from pathlib import Path
from copy import deepcopy
from contextlib import contextmanager
from hashlib import sha256
import json,time
import pytest
from test_public_annual_gap_cache import isolated_cache_and_provider

F=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261103/thsrc-individual-json'

def body(statement):return (F/({'IncomeStatement':'income'} .get(statement,statement)+'-2025.json')).read_bytes()
def template(statement):return (F/(statement+'-template.js')).read_bytes()

@pytest.mark.parametrize('statement',['BalanceSheet','IncomeStatement','CashflowStatement'])
def test_native_individual_rows_keep_scope_and_default_consolidated_path_rejects(statement):
    from data_fetch.market_sources.mops_public_annual import parse_statement,FilingError
    p=parse_statement(body(statement),'2633',2025,statement,template(statement),report_scope='individual')
    assert p['company_abbreviation']=='台灣高鐵'
    if statement=='IncomeStatement':
        assert p[2025]['ProfitLoss']==6580187000 and p[2024]['ProfitLoss']==6451428000
        assert 'ProfitLossAttributableToOwnersOfParent'not in p[2025]
    if statement=='BalanceSheet':assert p[2025]['Equity']==72772763000
    if statement=='CashflowStatement':assert p[2025]['PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities']==-9871968000
    with pytest.raises(FilingError):parse_statement(body(statement),'2633',2025,statement,template(statement))

@pytest.mark.parametrize('damage',['issuer','company','scope','year','quarter','unit','bool_code','selected_subsidiary','duplicate_fact','missing_profit','float_amount','template'])
def test_individual_json_rejects_unverified_identity_period_unit_and_amounts(damage):
    from data_fetch.market_sources.mops_public_annual import parse_statement,FilingError
    v=json.loads(body('IncomeStatement'));r=v['result'];t=template('IncomeStatement')
    if damage=='issuer':r['urlList'][0]['url']=r['urlList'][0]['url'].replace('CO_ID=2633','CO_ID=2330')
    elif damage=='company':r['companyAbbreviation']='台鐵'
    elif damage=='scope':r['reportType']='合併'
    elif damage=='year':r['year']='113'
    elif damage=='quarter':r['season']='3'
    elif damage=='unit':r['unit']='USD'
    elif damage=='bool_code':v['code']=True
    elif damage=='selected_subsidiary':r['subsidiaryCompanyId']='child'
    elif damage=='template':t+=b'changed'
    else:
        row=next(x for x in r['reportList']if x[0]=='本期淨利（淨損）')
        if damage=='duplicate_fact':r['reportList'].append(deepcopy(row))
        elif damage=='missing_profit':r['reportList'].remove(row)
        else:row[1]=6580187.0
    with pytest.raises(FilingError):parse_statement(json.dumps(v,ensure_ascii=False).encode(),'2633',2025,'IncomeStatement',t,report_scope='individual')

class Captured:
    """Native 2025 data recast to synthetic years only for pipeline contracts."""
    def __init__(self):self.deadline=time.monotonic()+45;self.components=[];self.calls=[]
    @contextmanager
    def batch(self):yield self
    def request(self,url,**kwargs):
        from data_fetch.market_sources.mops_public_annual import INDEX_URL,STATEMENTS,template_url,api_url
        from official_response_evidence import archive_response
        self.calls.append((url,kwargs))
        if url==INDEX_URL:raw=(F/'published-index.html').read_bytes()
        elif url in {template_url(s)for s in STATEMENTS}:raw=template(next(s for s in STATEMENTS if template_url(s)==url))
        else:
            s=next(s for s in STATEMENTS if api_url(s)==url);year=int(kwargs['json_body']['year'])+1911
            v=json.loads(body(s));r=v['result'];r['year']=str(year-1911)
            r['urlList'][0]['url']=r['urlList'][0]['url'].replace('SYEAR=2025','SYEAR='+str(year))
            r['titles'][1]['main']=r['titles'][1]['main'].replace('114',str(year-1911))
            r['titles'][2]['main']=r['titles'][2]['main'].replace('113',str(year-1912))
            raw=json.dumps(v,ensure_ascii=False).encode()
        self.components.append({'url':url,'http_request_sent':True,'http_status':200,'response_complete':True,
            'response_sha256':sha256(raw).hexdigest(),'response_bytes':len(raw),'status':'complete'})
        return raw,archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=200)

def test_full_json_protocol_projects_individual_basis_and_rejects_manifest_relabeling():
    from data_fetch.market_sources.ordinary_individual_annual import fetch_annual_result
    from data_fetch.annual_financial_source_provider import project_source_value
    http=Captured();out=fetch_annual_result('2633.TW',transport=http)
    assert out['audit']['status']=='success'and len(http.calls)==19
    value=out['value'];p=project_source_value(value,'2633.TW')
    assert p and p['financial_history_basis']['report_scope']=='individual'
    assert p['financial_history_basis']['field_sources']['net_income_history']['fact']=='mops-public-individual-row:本期淨利（淨損）'
    wrong=deepcopy(value);wrong['report_scope']='consolidated';assert project_source_value(wrong,'2633.TW')is None
    wrong=deepcopy(value);wrong['raw_twd_by_year']['2025']['profit_loss']=True;assert project_source_value(wrong,'2633.TW')is None
    wrong=deepcopy(value);wrong['documents'][0]['components'][0]['request']['companyId']='2330';assert project_source_value(wrong,'2633.TW')is None

class FiveYearOriginals(Captured):
    """Replay all 19 complete research originals; never a fresh HTTP sample."""
    def request(self,url,**kwargs):
        from data_fetch.market_sources.mops_public_annual import INDEX_URL,STATEMENTS,template_url,api_url
        from official_response_evidence import archive_response
        self.calls.append((url,kwargs));saved=F/'full-five-years'
        if url==INDEX_URL:raw=(saved/'current-index.body').read_bytes()
        elif url in {template_url(s)for s in STATEMENTS}:
            raw=(saved/(next(s for s in STATEMENTS if template_url(s)==url)+'-template.js')).read_bytes()
        else:
            s=next(s for s in STATEMENTS if api_url(s)==url);year=int(kwargs['json_body']['year'])+1911
            raw=(saved/(str(year)+'-'+s+'.json')).read_bytes()
        return raw,archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=200)

def test_all_five_actual_years_replay_and_money_claims_keep_individual_twd():
    from data_fetch.market_sources.ordinary_individual_annual import fetch_annual_result
    from data_fetch.annual_financial_source_provider import project_source_value
    from financial_money_claims import financial_money_claim_issues
    from data_fetch.financial_history_basis import is_ordinary_individual_basis,prompt_history_basis
    http=FiveYearOriginals();result=fetch_annual_result('2633.TW',transport=http)
    value=result['value'];assert value is not None and len(http.calls)==19
    data={'ticker':'2633.TW','financial_currency':'TWD',**project_source_value(value,'2633.TW')}
    assert value['years']==['2021','2022','2023','2024','2025']
    assert value['raw_twd_by_year']['2025']['free_cash_flow']==20691035000-75652000-9871968000==10743415000
    assert is_ordinary_individual_basis(data)
    assert prompt_history_basis(data)['report_scope']=='individual'
    from quant_input_contract import read_quant_inputs
    assert 'ordinary_individual_group_basis_unverified'in read_quant_inputs(data)[2]['dcf']
    for text in ['2025年本公司個別本期損益為65.80187億元。','2024年本公司個別本期損益為64.51428億元。','2025年本公司個別權益總額為727.72763億元。']:
        assert financial_money_claim_issues(text,data)==[],text
    assert any('金額單位紅線'in x for x in financial_money_claim_issues('2025年本公司個別本期損益為65801.87億元。',data))
    assert any('個別財報範圍紅線'in x for x in financial_money_claim_issues('2025年本公司合併淨利為65.80187億元。',data))
    wrong=deepcopy(value);wrong['documents'][0]['components'][0]['raw_receipt']['http_status']=True
    assert project_source_value(wrong,'2633.TW')is None
