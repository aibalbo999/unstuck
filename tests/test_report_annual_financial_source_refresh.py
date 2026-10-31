"""Public saved-report annual-source repair preserves quotes and conclusions."""
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import json,time
import pytest
from fastapi import HTTPException
from data_fetch.service import StockDataService
from report_refresh_service import refresh_report_data_snapshot
from report_persistence import report_bundle_keys_for_filename
from report_analysis_evidence import capture_analysis_evidence
from storage.report_storage import InMemoryStorage
from test_report_refresh_acquisition_audit import init_db,events

FIXTURE=json.loads((Path(__file__).parent/'fixtures/annual_financial_source_2313_captured_20261011.json').read_text())

def report(ticker="2313.TW"):
    storage=InMemoryStorage();name=ticker.replace('.', '_')+'_v4_report_20261011_001000.html';keys=report_bundle_keys_for_filename(name);epoch=time.time()-3*86400
    audit={'ticker':ticker,'source':'market_data','provider':'original quote','status':'success','record_count':1,'fetched_at_epoch':epoch,'fetched_at':datetime.fromtimestamp(epoch,timezone.utc).isoformat(),'cache_hit':False,'stale':True,'fetch_id':'original'}
    financial={**audit,'source':'financial_statements','provider':'original four-year fallback','record_count':4,'status':'degraded_enrichment'}
    data={'ticker':ticker,'quote_type':'EQUITY','company_name':'台郡','company_identity':{'official_name':'台郡','legal_name':'台郡科技股份有限公司'},'financial_currency':'TWD','currency':'TWD','sector':'Technology','industry':'Electronic Components','current_price':100,'daily_market_data':{'original':True},'revenue_ttm_raw':80000000000,'free_cash_flow_raw':987654321,'operating_cash_flow_raw':1987654321,'wacc_capital_structure_note':'old market weights','recent_catalysts':[{'title':'original event'}],'earnings_call':{'original':True},'data_source_notes':[],'source_audit':[audit,financial],**{k:deepcopy(v[-4:])if isinstance(v,list)else deepcopy(v)for k,v in FIXTURE['history'].items()}}
    data.update(revenue_cagr_5yr='stale old CAGR',gross_margin_history=[1]*4,op_margin_history=[2]*4,net_margin_history=[3]*4,roe_history=[4]*4,latest_annual_revenue_growth='old',latest_annual_net_income_growth='old',revenue_growth='old',earnings_growth='old',dupont_identity_note='old annual statement',ttm_vs_latest_annual_revenue_change='old')
    old={'ticker':ticker,'pipeline':'v4','generated_at':datetime.fromtimestamp(epoch,timezone.utc).isoformat(),'data':data,'source_audit':deepcopy(data['source_audit'])}
    for gate in ['report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance']:old[gate]={'original':gate}
    old['analysis_evidence']=capture_analysis_evidence({'data':data},generated_at=old['generated_at'])
    for key,payload,ctype in [(keys.html_key,b'original conclusions','text/html'),(keys.md_key,b'original conclusions','text/markdown'),(keys.data_key,json.dumps(old).encode(),'application/json')]:storage.save_report(key,payload,content_type=ctype)
    return storage,name,keys,old

def acquire(monkeypatch,*,failed=False):
    import data_fetch.official_financial_gap_cache as boundary
    import data_fetch.market_sources.official_quarterly_financials as quarterly
    calls=[]
    def native(ticker,**kwargs):
        calls.append(ticker);epoch=time.time()
        audit={'source':'financial_statements','provider':'TWSE MOPS official consolidated iXBRL','status':'error'if failed else'success','record_count':0 if failed else 5,'fetched_at_epoch':epoch,'fetched_at':datetime.fromtimestamp(epoch,timezone.utc).isoformat(),'cache_hit':False,'stale':False,'error_kind':'FilingError'if failed else'','message':'annual XBRL facts are incomplete for2021'if failed else'captured native result fixture'}
        return {'value':None if failed else{**deepcopy(FIXTURE['history']),**deepcopy(FIXTURE['official'])},'audit':audit}
    monkeypatch.setattr(boundary,'fetch_official_financial_result',native)
    def no_quarterly(ticker,data):
        epoch=time.time()
        return {'value':None,'audit':{'source':'financial_statements','provider':quarterly.PROVIDER,
            'status':'error','record_count':0,'fetched_at_epoch':epoch,
            'fetched_at':datetime.fromtimestamp(epoch,timezone.utc).isoformat(),
            'cache_hit':False,'stale':False,'error_kind':'fixture_unavailable',
            'coverage_status':'latest_quarter_only','message':'offline test fixture'}}
    monkeypatch.setattr(quarterly,'fetch_latest_quarter_result',no_quarterly)
    return calls

def test_annual_source_repairs_five_year_history_and_derived_values_without_touching_quote(tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report();calls=acquire(monkeypatch)
    response=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements',return_refreshed_data=True))
    saved=json.loads(storage.get_report(keys.data_key).content);data=saved['data']
    assert calls==['2313.TW'] and response['refresh_sources']==['financial_statements']
    for key,value in FIXTURE['history'].items():assert data[key]==value
    for key,value in FIXTURE['golden_annual_derived'].items():assert data[key]==value
    for key in ['ticker','quote_type','financial_currency','current_price','daily_market_data','revenue_ttm_raw','free_cash_flow_raw','operating_cash_flow_raw','recent_catalysts','earnings_call','wacc_capital_structure_note']:assert data[key]==old['data'][key]
    assert data['ttm_vs_latest_annual_revenue_change']!='old' and data['dupont_identity_note']!='old annual statement'
    assert next(a for a in saved['source_audit']if a['source']=='market_data')==old['source_audit'][0]
    assert 'market_data'in saved['data_trust']['stale_sources'] and saved['data_trust']['status']!='fresh'
    assert saved['analysis_evidence']==old['analysis_evidence']
    for gate in ['report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance']:assert saved[gate]==old[gate]
    assert storage.get_report(keys.html_key).content==storage.get_report(keys.md_key).content==b'original conclusions'
    assert response['analysis_text_stale']is True
    rows=events();assert len(rows)==1 and rows[0]['source']=='financial_statements' and rows[0]['record_count']==5
    assert json.loads(rows[0]['details_json'])['fetch_id']

def test_failed_annual_source_keeps_snapshot_and_records_the_real_failure_once(tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report();before=storage.get_report(keys.data_key).content;calls=acquire(monkeypatch,failed=True)
    with pytest.raises(HTTPException)as raised:asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    assert raised.value.status_code==502 and calls==['2313.TW']
    assert storage.get_report(keys.data_key).content==before
    rows=events();assert len(rows)==2 and [row['status'] for row in rows]==['error','error']
    assert all(row['record_count']==0 for row in rows)

@pytest.mark.parametrize('field,value',[('quote_type','ETF'),('quote_type','unknown'),('financial_currency','USD')])
def test_unverified_annual_source_context_is_rejected_before_acquisition(tmp_path,monkeypatch,field,value):
    init_db();storage,name,keys,old=report();old['data'][field]=value;payload=json.dumps(old).encode();storage.save_report(keys.data_key,payload,content_type='application/json');calls=acquire(monkeypatch)
    with pytest.raises(HTTPException)as raised:asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    assert raised.value.status_code==400 and calls==[] and storage.get_report(keys.data_key).content==payload

@pytest.mark.parametrize('override',[{'record_count':True},{'ticker':'2454.TW'}])
def test_invalid_successful_native_observation_is_not_published_as_acquisition_success(tmp_path,monkeypatch,override):
    init_db();storage,name,keys,_=report();before=storage.get_report(keys.data_key).content;calls=acquire(monkeypatch)
    import data_fetch.official_financial_gap_cache as boundary
    original=boundary.fetch_official_financial_result
    def malformed(ticker,**kwargs):
        result=original(ticker,**kwargs);result['audit'].update(override);return result
    monkeypatch.setattr(boundary,'fetch_official_financial_result',malformed)
    with pytest.raises(HTTPException)as raised:asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    assert raised.value.status_code==502 and calls==['2313.TW']
    assert storage.get_report(keys.data_key).content==before
    observed=events();assert len(observed)==2 and observed[0]['status']=='degraded_enrichment'
    assert observed[0]['record_count']==observed[1]['record_count']==0


def test_foreign_quote_currency_is_rejected_before_annual_source_work(tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report();old['data']['currency']='USD';payload=json.dumps(old).encode();storage.save_report(keys.data_key,payload,content_type='application/json');calls=acquire(monkeypatch)
    with pytest.raises(HTTPException)as raised:asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    assert raised.value.status_code==400 and calls==[]and storage.get_report(keys.data_key).content==payload

@pytest.mark.parametrize('change',['missing_intangible','wrong_document_issuer','individual_document','wrong_currency','wrong_history','missing_hash'])
def test_incomplete_or_mixed_native_financial_receipt_keeps_report_unchanged(tmp_path,monkeypatch,change):
    init_db();storage,name,keys,_=report();before=storage.get_report(keys.data_key).content;calls=acquire(monkeypatch)
    import data_fetch.official_financial_gap_cache as boundary
    original=boundary.fetch_official_financial_result
    def changed(ticker,**kwargs):
        result=original(ticker,**kwargs);value=result['value']
        if change=='missing_intangible':value['raw_twd_by_year']['2021'].pop('intangible_purchase')
        elif change=='wrong_document_issuer':value['documents'][0]['url']=value['documents'][0]['url'].replace('co_id=2313','co_id=2454')
        elif change=='individual_document':value['documents'][0]['url']=value['documents'][0]['url'].replace('report_id=C','report_id=A')
        elif change=='wrong_currency':value['currency']='USD'
        elif change=='wrong_history':value['fcf_history'][0]+=1
        elif change=='missing_hash':value['documents'][0].pop('sha256')
        return result
    monkeypatch.setattr(boundary,'fetch_official_financial_result',changed)
    with pytest.raises(HTTPException)as raised:asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    assert raised.value.status_code==502 and calls==['2313.TW']and storage.get_report(keys.data_key).content==before
    observed=events();assert len(observed)==2 and observed[0]['status']=='degraded_enrichment'
    assert observed[0]['record_count']==observed[1]['record_count']==0


def test_financial_institution_annual_source_keeps_net_revenue_separate_and_avoids_industrial_fetch(tmp_path,monkeypatch):
    init_db();ticker='2891.TW';storage,name,keys,old=report(ticker);old['data'].update(company_name='中信金',company_identity={'official_name':'中信金','legal_name':'中國信託金融控股股份有限公司'},sector='Financial Services',industry='Financial Conglomerates')
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    raw=json.loads((Path(__file__).parent/'fixtures/source_acquisition/financial_institution_2891_20261009.json').read_text());calls=[]
    import data_fetch.market_sources.financial_institution_xbrl as native
    import data_fetch.official_financial_gap_cache as ordinary
    def acquire_bank(symbol):calls.append(symbol);return deepcopy(raw)
    monkeypatch.setattr(native,'fetch_financial_institution_histories',acquire_bank)
    monkeypatch.setattr(ordinary,'fetch_official_financial_result',lambda *a,**kw:pytest.fail('financial institution must not use industrial facts'))
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    saved=json.loads(storage.get_report(keys.data_key).content);data=saved['data']
    assert calls==[ticker]and data['years']==['2021','2022','2023','2024','2025']
    assert data['net_revenue_history'][-1]==244.894671 and data['net_income_history'][-1]==80.619233
    assert data['revenue_history']==data['gross_profit_history']==data['operating_income_history']==[None]*5
    assert data['financial_history_basis']['statement_schema']=='financial_institution_consolidated.v1'
    assert data['free_cash_flow_raw']==old['data']['free_cash_flow_raw']and data['current_price']==old['data']['current_price']
    assert 'market_data'in saved['data_trust']['stale_sources']
    observed=events();assert len(observed)==1 and observed[0]['record_count']==5


def test_retained_quote_with_different_issuer_is_rejected_before_new_financial_work(tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report();old['source_audit'][0]['ticker']='2454.TW';payload=json.dumps(old).encode();storage.save_report(keys.data_key,payload,content_type='application/json');calls=acquire(monkeypatch)
    with pytest.raises(HTTPException)as raised:asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    assert raised.value.status_code==400 and calls==[]and storage.get_report(keys.data_key).content==payload


def call(storage,name,tmp_path):
    return asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))

@pytest.mark.parametrize('bad',['duplicate_blank_issuer','http503','zero_http','before_latest_period','cache_origin','local_block'])
def test_malformed_native_origin_must_not_become_valid_annual_acquisition(tmp_path,monkeypatch,bad):
    init_db();storage,name,keys,_=report();before=storage.get_report(keys.data_key).content;acquire(monkeypatch)
    import data_fetch.official_financial_gap_cache as boundary
    original=boundary.fetch_official_financial_result
    def malformed(ticker,**kw):
        result=original(ticker,**kw)
        if bad=='duplicate_blank_issuer':result['value']['documents'][0]['url']+='&co_id='
        elif bad=='http503':result['audit']['http_status']=503
        elif bad=='zero_http':result['audit']['http_request_sent']=False
        elif bad=='cache_origin':result['audit']['event_kind']='cache_hit'
        elif bad=='local_block':result['audit']['event_kind']='local_block'
        else:
            epoch=datetime(2020,1,1,tzinfo=timezone.utc).timestamp()
            result['audit'].update(fetched_at_epoch=epoch,fetched_at=datetime.fromtimestamp(epoch,timezone.utc).isoformat())
        return result
    monkeypatch.setattr(boundary,'fetch_official_financial_result',malformed)
    with pytest.raises(HTTPException)as raised:call(storage,name,tmp_path)
    assert raised.value.status_code==502 and storage.get_report(keys.data_key).content==before
    observed=events();assert len(observed)==2 and observed[0]['status']!='success'
    assert observed[0]['record_count']==observed[1]['record_count']==0


def test_old_overflowing_ttm_does_not_discard_complete_new_annual_history(tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report();old['data']['revenue_ttm_raw']=10**400
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');acquire(monkeypatch)
    call(storage,name,tmp_path)
    data=json.loads(storage.get_report(keys.data_key).content)['data']
    assert data['revenue_ttm_raw']==10**400 and data['ttm_vs_latest_annual_revenue_change']=='N/A'
    assert len(data['years'])==5


def test_declared_foreign_sector_receipt_cannot_be_cast_as_twd(tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report('2891.TW')
    old['data'].update(company_name='中信金',sector='Financial Services',industry='Financial Conglomerates')
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');before=storage.get_report(keys.data_key).content
    raw=json.loads((Path(__file__).parent/'fixtures/source_acquisition/financial_institution_2891_20261009.json').read_text());raw['currency']='USD'
    import data_fetch.market_sources.financial_institution_xbrl as native
    monkeypatch.setattr(native,'fetch_financial_institution_histories',lambda symbol:deepcopy(raw))
    with pytest.raises(HTTPException)as raised:call(storage,name,tmp_path)
    assert raised.value.status_code==502 and storage.get_report(keys.data_key).content==before
    observed=events();assert len(observed)==2 and observed[0]['status']!='success'
    assert observed[0]['record_count']==observed[1]['record_count']==0


def test_old_ttm_origin_remains_visible_when_only_annual_facts_become_current(tmp_path,monkeypatch):
    import time
    from prompt_builder import format_data_for_prompt
    init_db();storage,name,keys,old=report()
    old_finance=deepcopy(old['source_audit'][1]);now=time.time()-60
    for audits in (old['source_audit'],old['data']['source_audit']):
        audits[0].update(fetched_at_epoch=now,fetched_at=datetime.fromtimestamp(now,timezone.utc).isoformat(),stale=False)
    old['data']['source_freshness']={'market_data':deepcopy(old['source_audit'][0]),'financial_statements':deepcopy(old_finance)}
    assert old_finance['fetched_at'] in format_data_for_prompt(old['data'])
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');acquire(monkeypatch)
    call(storage,name,tmp_path)
    data=json.loads(storage.get_report(keys.data_key).content)['data']
    assert data['revenue_ttm_raw']==old['data']['revenue_ttm_raw']
    rendered=format_data_for_prompt(data)
    assert (old_finance['fetched_at'] in rendered
            or data['source_freshness']['financial_statements']['fetched_at_epoch']<=old_finance['fetched_at_epoch']),data['data_trust']
    assert old_finance['fetched_at']in format_data_for_prompt(data,compact=True)
    # Another annual refresh still has not reacquired the retained TTM values.
    call(storage,name,tmp_path)
    again=json.loads(storage.get_report(keys.data_key).content)['data']
    assert old_finance['fetched_at']in format_data_for_prompt(again,compact=True)
    assert again['revenue_ttm_raw']==old['data']['revenue_ttm_raw']


def test_overflowing_old_degraded_financial_epoch_becomes_unknown_not_a_refresh_crash(tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report()
    for audits in (old['source_audit'],old['data']['source_audit']):
        audits[1]['fetched_at_epoch']=10**400
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    calls=acquire(monkeypatch)
    call(storage,name,tmp_path)
    data=json.loads(storage.get_report(keys.data_key).content)['data']
    assert calls==['2313.TW'] and len(data['years'])==5
    assert '原財務來源取得時間未確認' in data['data_source_notes'][0]


def test_quarterly_supplement_adds_current_statement_without_refreshing_annual_values(monkeypatch):
    from annual_financial_source_refresh import merge_latest_quarter_financial_source
    from data_fetch.market_sources import official_quarterly_financials as quarterly

    _,_,_,saved=report();old=deepcopy(saved['data'])
    old['source_freshness']={'financial_statements':{'fetched_at_epoch':1234567890,'stale':True}}
    now=time.time();iso=datetime.fromtimestamp(now,timezone.utc).isoformat()
    value={'schema':'mops_latest_quarter_financials.v1','coverage_status':'latest_quarter_only',
           'ticker':'2313.TW','period':{'year':2026,'quarter':2,'period_end':'2026-06-30'}}
    monkeypatch.setattr(quarterly,'project_latest_quarter',lambda candidate,ticker:value if candidate is value and ticker=='2313.TW' else None)
    failed={'source':'financial_statements','provider':'official annual failure','status':'error',
            'record_count':0,'fetch_id':'fetch-q','message':'annual primary source timeout'}
    supplemental={'source':'financial_statements','provider':quarterly.PROVIDER,'status':'success',
                  'coverage_status':'latest_quarter_only','record_count':1,'fetch_id':'fetch-q',
                  'fetched_at_epoch':now,'fetched_at':iso,'related_entries':[failed]}
    merged=merge_latest_quarter_financial_source(old,[*old['source_audit']],value,[supplemental,failed],'2313.TW')

    for field in ('years','revenue_history','net_income_history','fcf_history','total_assets_history','total_equity_history',
                  'revenue_ttm_raw','free_cash_flow_raw','operating_cash_flow_raw','current_price','ttm_vs_latest_annual_revenue_change'):
        assert merged[field]==old[field]
    assert merged['latest_quarter_financials']==value
    assert merged['source_freshness']==old['source_freshness']
    assert merged['source_audit'][-2:]==[supplemental,failed]
    assert 'not a five-year' not in merged['data_source_notes'][0]
    assert '不代表五年年度序列' in merged['data_source_notes'][0]


def test_failed_annual_fetch_falls_back_to_quarterly_snapshot_and_preserves_failure(tmp_path,monkeypatch):
    import data_fetch.market_sources.official_quarterly_financials as quarterly

    init_db();storage,name,keys,old=report();calls=acquire(monkeypatch,failed=True)
    old['data']['source_freshness']={'financial_statements':{'fetched_at_epoch':old['source_audit'][1]['fetched_at_epoch'],'stale':True}}
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    now=time.time();iso=datetime.fromtimestamp(now,timezone.utc).isoformat()
    value={'schema':'mops_latest_quarter_financials.v1','coverage_status':'latest_quarter_only',
        'ticker':'2313.TW','issuer_code':'2313','issuer_name':'台郡','market_code':'L','sector_code':'ci',
        'period':{'year':2026,'quarter':2,'period_end':'2026-06-30'},'currency':'TWD','filed_unit':'thousands',
        'income_period_basis':'year_to_date_cumulative','balance_period_basis':'quarter_end_instant',
        'scope':'as_published_scope_not_independently_verified','cash_flow_statement_available':False,
        'tables':{'balance_sheet':{},'income_statement_ytd':{}}}
    monkeypatch.setattr(quarterly,'project_latest_quarter',lambda candidate,ticker:value if candidate is value and ticker=='2313.TW' else None)
    def latest(ticker,data):
        return {'value':value,'audit':{'source':'financial_statements','provider':quarterly.PROVIDER,
            'status':'success','coverage_status':'latest_quarter_only','record_count':1,'ticker':ticker,
            'fetched_at_epoch':now,'fetched_at':iso,'cache_hit':False,'stale':False,
            'message':'latest quarterly fixture'}}
    monkeypatch.setattr(quarterly,'fetch_latest_quarter_result',latest)

    response=call(storage,name,tmp_path)
    saved=json.loads(storage.get_report(keys.data_key).content);data=saved['data']
    assert calls==['2313.TW'] and response['analysis_text_stale'] is True
    assert data['latest_quarter_financials']==value
    assert data['years']==old['data']['years'] and data['revenue_ttm_raw']==old['data']['revenue_ttm_raw']
    assert data['free_cash_flow_raw']==old['data']['free_cash_flow_raw']
    assert data['source_freshness']==old['data']['source_freshness']
    assert [entry['status'] for entry in saved['source_audit'][-2:]]==['success','error']
    assert '不代表五年年度序列' in data['data_source_notes'][0]
    rows=events();assert len(rows)==2 and [row['status'] for row in rows]==['success','error']
