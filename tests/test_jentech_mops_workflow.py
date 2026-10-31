from pathlib import Path
from copy import deepcopy
import time,json,hashlib,asyncio
import pytest
from test_mops_presentation import harness as common_harness
D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261031/jentech-mops'
NOW=json.loads((D/'research-material.json').read_text())['receipt']['retrieved_at']+1

def valid_data():
 return {'ticker':'3653.TW','instrument_type':'EQUITY','company_name':'健策 / Jentech Precision Industrial Co., Ltd','raw_company_name':'Jentech Precision Industrial Co., Ltd','company_identity':{'ticker':'3653.TW','stock_id':'3653','official_name':'健策','legal_name':'健策精密工業股份有限公司','official_ubn':'22415854','instrument_type':'EQUITY','display_name':'健策 / Jentech Precision Industrial Co., Ltd','english_names':['Jentech Precision Industrial Co., Ltd','JENTECH PRECISION INDUSTRIAL CO'],'allowed_aliases':['健策','3653.TW','3653','Jentech Precision Industrial Co., Ltd','JENTECH PRECISION INDUSTRIAL CO'],'forbidden_aliases':[]}}

@pytest.fixture
def packet(common_harness,monkeypatch):
 from data_fetch.market_sources import mops_presentation as m
 from mops_material_transport import index_request
 bodies,calls=common_harness;bodies['master']=(D/'fixture-master.body').read_bytes();bodies['3653.TW:material']=(D/'research-material.pdf').read_bytes()
 monkeypatch.setattr(time,'time',lambda:NOW)
 def index(ticker,year,deadline,diagnostics):
  assert ticker=='3653.TW' and year in (2026,2025)
  raw=(D/('fixture-index-'+str(year)+'.body')).read_bytes();spec=index_request(ticker,year);calls.append(ticker+':index:'+str(year))
  diagnostics.update(http_request_sent=True,http_request_count=1,http_status=200,response_complete=True,response_sha256=hashlib.sha256(raw).hexdigest(),response_metadata={'http_status':200,'effective_url':spec['url'],'num_redirects':0,'size_download':len(raw),'content_type':'text/html','content_length':len(raw),'method':'POST','proxy_used':0})
  return raw
 monkeypatch.setattr(m,'download_conference_index',index)
 return calls

def test_native_cold_warm_prior_year_chain_preserves_all_pages_and_role_limits(packet,monkeypatch):
 from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
 from data_fetch.market_sources import mops_presentation as m
 from conference_presentation_prompt import presentation_prompt_context
 diagnostic={};value=fetch_free_earnings_call_context('3653.TW',diagnostics=diagnostic,force_refresh=False,use_cache=True)
 assert m.verify_context(value,'3653.TW') and diagnostic['http_request_count']==4 and not diagnostic['cache_hit']
 assert packet==['master','3653.TW:index:2026','3653.TW:index:2025','3653.TW:material']
 doc=value['documents'][0];assert doc['page_count']==24 and len(doc['pages'])==24 and doc['native_text_coverage']=='partial'
 assert doc['garbled_pages']==[2,3,4,14,15,16,17] and not doc['full_content_coverage_verified'] and not doc['financial_statement_complete']
 assert value['mops_material_receipt']['absence_current_request']['year']==2026 and value['mops_material_receipt']['index_request']['year']==2025
 for role in (3,5,12):
  v=presentation_prompt_context(value,role)['documents'][0]
  assert [p['page_number']for p in v['pages']]==[1,5,6,7,8,11,21] and all(p['content_truncated']is False for p in v['pages'])
  assert 'Basic EPS' in v['period_scope_caution'] and '未經查核' in v['period_scope_caution']
 packet.clear();warm={};again=fetch_free_earnings_call_context('3653.TW',diagnostics=warm,force_refresh=False,use_cache=True)
 assert not packet and warm['cache_hit']is True and warm['http_request_count']==0
 assert again['documents']==value['documents']
 monkeypatch.setattr(time,'time',lambda:NOW+1800);assert not m.verify_context(value,'3653.TW')

@pytest.mark.parametrize('damage',['role_whitelist','nonrole_text','unit_caution','garbled_status','scope','absence_receipt'])
def test_forged_or_unbounded_packet_never_enters_roles(packet,damage):
 from data_fetch.market_sources import mops_presentation as m
 from conference_presentation_prompt import presentation_prompt_context
 v=m.fetch_presentation_context('3653.TW');doc=v['documents'][0]
 if damage=='role_whitelist':doc['role_page_allowlist']['5']=list(range(1,25))
 elif damage=='nonrole_text':doc['pages'][1]['text']='independently audited current results'
 elif damage=='unit_caution':doc['period_scope_caution']='EPS thousand TWD; expansion completed in2026'
 elif damage=='garbled_status':doc['garbled_pages']=[]
 elif damage=='scope':doc['financial_statement_complete']=True
 else:v['mops_material_receipt'].pop('absence_current_index')
 assert not m.verify_context(v,'3653.TW')
 assert not presentation_prompt_context(v,5).get('documents')

@pytest.mark.parametrize('damage',['ticker','ubn','instrument'])
def test_provider_context_denial_sends_no_request(monkeypatch,damage):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 from data_fetch.market_sources import mops_presentation as m,jentech_conference as j
 d=valid_data()
 if damage=='ticker':d['ticker']='2330.TW'
 elif damage=='ubn':d['company_identity']['official_ubn']='11111111'
 else:d['instrument_type']='ETF'
 monkeypatch.setattr(m,'fetch_presentation_context',lambda *a,**kw:pytest.fail('Invalid context sent MOPS'))
 monkeypatch.setattr(j,'fetch_jentech_context',lambda *a,**kw:pytest.fail('Invalid context sent issuer'))
 r=EarningsCallProvider().fetch(FetchRequest.from_ticker('3653.TW'),{'data':d})
 assert r.audit['error_kind']=='context_unverified' and r.audit['http_request_sent']is False


def test_source_refresh_preserves_original_analysis_and_records_single_real_acquisition(packet,tmp_path):
 from data_fetch import enrichment_providers
 from data_fetch.provider_registry import ProviderRegistry
 from data_fetch.service import StockDataService
 from report_refresh_service import refresh_report_data_snapshot
 from report_analysis_evidence import capture_analysis_evidence
 from storage.report_storage import InMemoryStorage
 from test_report_refresh_acquisition_audit import init_db,events
 from test_unitech_tcfhc_source_integration import saved_target,assert_preserved
 init_db();storage=InMemoryStorage();filename,keys,before=saved_target(storage,'3653.TW','健策');before['data'].update(valid_data());before['analysis_evidence']=capture_analysis_evidence({'data':before['data']},generated_at=before['generated_at']);storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json')
 service=StockDataService(registry=ProviderRegistry([enrichment_providers.EarningsCallProvider()]));r=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='earnings_call',return_refreshed_data=True));after=json.loads(storage.get_report(keys.data_key).content)
 assert_preserved(storage,keys,before,after);assert r['analysis_text_stale']is True
 assert len(after['data']['earnings_call']['documents'][0]['pages'])==24
 audit=events();assert len(audit)==1 and audit[0]['status']=='success' and audit[0]['record_count']==1
 details=json.loads(audit[0]['details_json']);assert details['http_request_sent']is True and details['http_request_count']==4
 assert len(details['original_http_receipts'])==4
