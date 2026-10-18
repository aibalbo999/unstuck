"""Five explicit fiscal periods may be reported in four published C filings."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import gzip,json,time
import httpx
import pytest

F=Path(__file__).parent/'fixtures/source_acquisition/greatek_comparative_start_full_20261011'
V=json.loads((F/'value.json').read_text());M=json.loads((F/'manifest.json').read_text())

def raw(receipt):
    p=M['full_parts'][receipt['raw_response_sha256']]
    body=gzip.open(F/p['filename'],'rb').read()
    assert len(body)==p['bytes'] and sha256(body).hexdigest()==p['sha256']
    return body

def captured():
    from official_response_evidence import archive_response
    value=deepcopy(V)
    def rebase(v):
        if isinstance(v,dict):
            if all(k in v for k in ('raw_response_sha256','raw_response_path','raw_response_bytes')):
                receipt=archive_response(raw(v),source_url=v['source_url'],retrieved_at=v['retrieved_at'])
                v.clear();v.update(receipt)
            else:
                for c in v.values():rebase(c)
        elif isinstance(v,list):
            for c in v:rebase(c)
    rebase(value);return value

def fixture_http(calls=None,change=None):
    from data_fetch.market_sources.mops_public_annual import template_url
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    def response(request):
        if calls is not None:calls.append(request)
        if change is not None:
            altered=change(request)
            if altered is not None:return altered
        url=str(request.url)
        if url==INDEX_URL:
            return httpx.Response(200,content=raw(V['documents'][0]['published_index_receipt']),headers={'Content-Type':'text/html'})
        for p in V['documents'][0]['components']:
            if url==template_url(p['statement']):
                return httpx.Response(200,content=raw(p['unit_template_receipt']),headers={'Content-Type':'text/javascript'})
        payload=json.loads(request.content)
        p=next(p for d in V['documents']for p in d['components']if p['url']==url and p['request']==payload)
        return httpx.Response(200,content=raw(p['raw_receipt']),headers={'Content-Type':'application/json'})
    return lambda **kwargs:httpx.Client(transport=httpx.MockTransport(response),**kwargs)

def test_complete_captured_first_comparative_is_admitted_as_five_periods_without_phantom_filing():
    from data_fetch.annual_financial_source_provider import project_source_value
    value=captured();result=project_source_value(value,'2441.TW')
    assert result is not None
    assert result['years']==['2021','2022','2023','2024','2025']
    assert [d['year']for d in result['documents']]==[2022,2023,2024,2025]
    assert result['raw_twd_by_year']['2021']['free_cash_flow']==1976784000
    assert result['documents'][0]['first_period_basis']['no_primary_filing_for_first_period_claimed'] is True

def test_cold_collection_uses_four_actual_filings_and_sixteen_http_operations():
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_annual_histories,project_public_history
    calls=[];value=fetch_public_annual_histories('2441.TW',transport=PublicMopsHttp(client_factory=fixture_http(calls)))
    assert len(calls)==16
    assert value['years']==V['years']and value['raw_twd_by_year']==V['raw_twd_by_year']
    assert [d['year']for d in value['documents']]==[2022,2023,2024,2025]
    assert project_public_history(value,'2441.TW') is not None
    requested=[json.loads(r.content)['year']for r in calls if '/api/'in str(r.url)]
    assert '110'not in requested and set(requested)=={'111','112','113','114'}

def test_source_only_merge_keeps_quote_and_exposes_comparative_origin():
    from annual_financial_source_refresh import merge_annual_financial_source
    value=captured();stamp=time.time()-3600
    old={'ticker':'2441.TW','instrument_type':'EQUITY','currency':'TWD','financial_currency':'TWD','data_source_notes':['保留來源說明'+str(i)for i in range(8)],
         'revenue_ttm_raw':1230000000,'current_price':75,'years':['2022','2023','2024','2025']}
    old_audits=[{'source':'market_data','status':'success','fetched_at_epoch':stamp},
                {'source':'financial_statements','provider':'cache','status':'skipped_fresh_cache','fetched_at_epoch':stamp}]
    audit={'source':'financial_statements','provider':'TWSE MOPS public annual JSON','status':'success','record_count':5,'cache_hit':False,'stale':False,
           'fetch_id':'fixture-first-comparative','fetched_at_epoch':time.time(),'documents':value['documents'],'source_url':value['source_url']}
    merged=merge_annual_financial_source(old,old_audits,value,[audit],'2441.TW')
    assert merged['current_price']==75 and merged['revenue_ttm_raw']==1230000000
    assert merged['years']==V['years']and merged['source_audit'][0]==old_audits[0]
    assert any('2021'in note and'2022'in note and'比較欄'in note and'四份'in note for note in merged['data_source_notes'])
    from prompt_builder import format_data_for_prompt
    assert '2021年度採2022年度官方合併財報明示的比較欄'in format_data_for_prompt(merged,compact=True)

def test_normal_annual_interface_keeps_five_periods_and_exposes_first_comparative_without_sdk(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    from data_fetch.yfinance_extractors import extract_financial_histories
    original=public.PublicMopsHttp;calls=[]
    monkeypatch.setattr(public,'PublicMopsHttp',lambda:original(client_factory=fixture_http(calls)))
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    class NoSDK:
        def __getattr__(self,name):raise AssertionError('SDK annual table must not be used: '+name)
    class NoFinMind:
        def __init__(self):raise AssertionError('FinMind must not replace complete official periods')
    notes=[];result=extract_financial_histories(NoSDK(),'2441.TW',notes,NoFinMind,quote_type='EQUITY',finmind_use_cache=True)
    assert result['years']==V['years']and result['fcf_history'][0]==1.976784
    assert result['official_financial_audit']['record_count']==5 and len(result['official_financial_audit']['documents'])==4
    assert len(calls)==16
    assert any('2021'in note and'2022'in note and'比較欄'in note and'四份'in note for note in notes)

@pytest.mark.parametrize('change',['remove_basis','remove_index','remove_both','basis_period','basis_filing','basis_period_float','basis_filing_float','basis_origin','basis_bool',
    'metadata_on_later_filing','extra_phantom_primary','drop_one_filing','unverified_index_url','unverified_index_hash','index_time_before_latest_close','index_time_future','first_period_value'])
def test_four_file_admission_never_downgrades_or_accepts_unverified_origin(change):
    from data_fetch.annual_financial_source_provider import project_source_value
    value=captured();doc=value['documents'][0]
    if change=='remove_basis':doc.pop('first_period_basis')
    elif change=='remove_index':doc.pop('published_index_receipt')
    elif change=='remove_both':doc.pop('first_period_basis');doc.pop('published_index_receipt')
    elif change=='basis_period':doc['first_period_basis']['period_year']=2020
    elif change=='basis_filing':doc['first_period_basis']['source_filing_year']=2023
    elif change=='basis_period_float':doc['first_period_basis']['period_year']=2021.0
    elif change=='basis_filing_float':doc['first_period_basis']['source_filing_year']=2022.0
    elif change=='basis_origin':doc['first_period_basis']['facts_origin']='primary_filing'
    elif change=='basis_bool':doc['first_period_basis']['no_primary_filing_for_first_period_claimed']=1
    elif change=='metadata_on_later_filing':value['documents'][1]['first_period_basis']=deepcopy(doc['first_period_basis'])
    elif change=='extra_phantom_primary':value['documents'].insert(0,{**deepcopy(doc),'year':2021})
    elif change=='drop_one_filing':value['documents'].pop()
    elif change=='unverified_index_url':doc['published_index_receipt']['source_url']='https://example.com/index'
    elif change=='unverified_index_hash':doc['published_index_receipt']['raw_response_sha256']='0'*64
    elif change=='index_time_before_latest_close':doc['published_index_receipt']['retrieved_at']=1700000000
    elif change=='index_time_future':doc['published_index_receipt']['retrieved_at']=time.time()+60
    else:value['raw_twd_by_year']['2021']['free_cash_flow']+=1000
    assert project_source_value(value,'2441.TW') is None
    if change in ('basis_period_float','basis_filing_float'):
        from data_fetch.market_sources.mops_public_annual import first_comparative_origin_note
        assert first_comparative_origin_note(value) is None

@pytest.mark.parametrize('change',['missing_first_intangible','first_intangible_dash','first_intangible_bool','first_operating_CF_missing'])
def test_first_prior_period_must_have_all_nine_explicit_facts(change):
    from data_fetch.market_sources.mops_public_annual import PublicMopsHttp,fetch_public_annual_histories
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    def mutate(request):
        if not str(request.url).endswith('/api/t164sb05')or json.loads(request.content)['year']!='111':return
        p=V['documents'][0]['components'][2];body=json.loads(raw(p['raw_receipt']));rows=body['result']['reportList'];item=next(r for r in rows if r[0].strip()=='取得無形資產')
        if change=='missing_first_intangible':rows.remove(item)
        elif change=='first_intangible_dash':item[2]='-'
        elif change=='first_intangible_bool':item[2]=False
        else:rows.remove(next(r for r in rows if r[0].strip()=='營業活動之淨現金流入（流出）'))
        return httpx.Response(200,json=body)
    with pytest.raises(FilingError):
        fetch_public_annual_histories('2441.TW',transport=PublicMopsHttp(client_factory=fixture_http(change=mutate)))
