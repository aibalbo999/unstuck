"""Native MOPS workflow with archived public originals and isolated cache/SQL."""
from copy import deepcopy
from pathlib import Path
import asyncio,json
import pytest
from test_mops_presentation import harness as common_harness
from test_getac_conference import D as LEGACY,valid_data
CASE=Path(__file__).resolve().parents[1]

@pytest.fixture
def packet(common_harness):
 bodies,calls=common_harness
 bodies['3005.TW:index']=(CASE/'docs/evidence/source-acquisition/20261031/getac-mops/index.html').read_bytes()
 bodies['3005.TW:material']=(LEGACY/'getac-pdf.body').read_bytes()
 return calls

def test_normal_selection_is_independent_government_original_with_warm_truth(packet):
 from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
 from data_fetch.market_sources import mops_presentation as s
 from conference_presentation_prompt import presentation_prompt_context
 diagnostic={};v=fetch_free_earnings_call_context('3005.TW',diagnostics=diagnostic,force_refresh=False,use_cache=True)
 assert s.verify_context(v,'3005.TW') and diagnostic['http_request_count']==3
 assert packet==['master','3005.TW:index','3005.TW:material']
 assert v['documents'][0]['material_file_date']=='2026-08-13' and v['documents'][0]['presentation_cover_date']=='2026-08-14'
 assert 'getac_conference_receipt' not in v and v['source']=='MOPS published presentation'
 for role in (3,5,12):
  d=presentation_prompt_context(v,role)['documents'][0]
  assert [p['page_number'] for p in d['pages']]==[1,2,7,8]
  assert all(p['content_truncated'] is False for p in d['pages'])
  assert '35.37%' in d['period_scope_caution']
  assert d['presentation_cover_date']=='2026-08-14' and d['material_file_date']=='2026-08-13' and d['event_date']=='2026-08-14'
 warm={};again=fetch_free_earnings_call_context('3005.TW',diagnostics=warm,force_refresh=False,use_cache=True)
 assert again['documents']==v['documents'] and warm['cache_hit'] is True and warm['http_request_count']==0
 assert len(packet)==3

@pytest.mark.parametrize('damage',['missing_page','unit_caution','file_date','scope','receipt'])
def test_forged_packet_never_enters_roles(packet,damage):
 from data_fetch.market_sources import mops_presentation as s
 from conference_presentation_prompt import presentation_prompt_context
 v=s.fetch_presentation_context('3005.TW')
 if damage=='missing_page':v['documents'][0]['pages'].pop()
 elif damage=='unit_caution':v['documents'][0]['period_scope_caution']='Wholly owned3004 and independently verified40% market share'
 elif damage=='file_date':v['documents'][0]['material_file_date']='2026-08-14'
 elif damage=='scope':v['documents'][0]['financial_statement_complete']=True
 else:v.pop('mops_material_receipt')
 assert not s.verify_context(v,'3005.TW')
 for role in (3,5,12):assert not presentation_prompt_context(v,role).get('documents')

def test_provider_refresh_keeps_original_report_analysis_and_native_audit(packet,tmp_path):
 from data_fetch import enrichment_providers
 from data_fetch.provider_registry import ProviderRegistry
 from data_fetch.service import StockDataService
 from report_refresh_service import refresh_report_data_snapshot
 from report_analysis_evidence import capture_analysis_evidence
 from storage.report_storage import InMemoryStorage
 from test_report_refresh_acquisition_audit import init_db,events
 from test_unitech_tcfhc_source_integration import saved_target,assert_preserved
 init_db();storage=InMemoryStorage();filename,keys,before=saved_target(storage,'3005.TW','神基')
 before['data'].update(valid_data());before['analysis_evidence']=capture_analysis_evidence({'data':before['data']},generated_at=before['generated_at'])
 storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json')
 service=StockDataService(registry=ProviderRegistry([enrichment_providers.EarningsCallProvider()]))
 result=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='earnings_call',return_refreshed_data=True))
 after=json.loads(storage.get_report(keys.data_key).content)
 assert_preserved(storage,keys,before,after);assert result['analysis_text_stale'] is True
 assert after['data']['earnings_call']['documents'][0]['page_count']==21
 rows=events();assert len(rows)==1 and rows[0]['status']=='success' and rows[0]['record_count']==1
 details=json.loads(rows[0]['details_json']);assert details['http_request_sent'] is True and details['http_request_count']==3

 originals=details['original_http_receipts']
 assert len(originals)==3
 assert all(x['http_request_sent'] is True and x['cache_hit'] is False and x['http_status']==200 and x['response_bytes']>0 for x in originals)
 assert sorted(x['request_method'] for x in originals)==['GET','POST','POST']
 assert len({x['source_url_sha256'] for x in originals})==3
