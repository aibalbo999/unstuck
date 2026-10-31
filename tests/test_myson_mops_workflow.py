from pathlib import Path
from copy import deepcopy
import time,json,hashlib,asyncio,base64
import pytest
from test_mops_presentation import harness as common_harness
from test_myson_mops_qualification import context as valid_data
D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261031/myson-mops'
NOW=json.loads((D/'research-material.json').read_text())['receipt']['retrieved_at']+1

@pytest.fixture
def packet(common_harness,monkeypatch):
 from data_fetch.market_sources import mops_presentation as source
 from mops_material_transport import index_request
 bodies,calls=common_harness
 bodies['5314.TWO:material']=(D/'research-material.pdf').read_bytes()
 monkeypatch.setattr(time,'time',lambda:NOW)
 def master(self,url,diagnostic):
  assert url==source.OTC_MASTER
  raw=(D/'fixture-master.body').read_bytes();calls.append('otc-master');self.http_request_count+=1
  diagnostic.update(http_request_sent=True,http_status=200,response_bytes=len(raw),response_sha256=hashlib.sha256(raw).hexdigest())
  return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()}
 monkeypatch.setattr(source.OtcMasterHttp,'download_original',master)
 def index(ticker,year,deadline,diagnostics):
  assert ticker=='5314.TWO' and year==2026
  raw=(D/'fixture-index-2026.body').read_bytes();spec=index_request(ticker,year);calls.append(ticker+':index:2026')
  diagnostics.update(http_request_sent=True,http_request_count=1,http_status=200,response_complete=True,response_sha256=hashlib.sha256(raw).hexdigest(),response_metadata={'http_status':200,'effective_url':spec['url'],'num_redirects':0,'size_download':len(raw),'content_type':'text/html','content_length':len(raw),'method':'POST','proxy_used':0})
  return raw
 monkeypatch.setattr(source,'download_conference_index',index)
 return calls

def test_native_cold_warm_http_identity_and_role_whole_pages(packet,monkeypatch):
 from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
 from data_fetch.market_sources import mops_presentation as source
 from data_fetch.market_sources.myson_mops_qualification import ROLE_PAGES
 from conference_presentation_prompt import presentation_prompt_context
 diagnostic={};value=fetch_free_earnings_call_context('5314.TWO',diagnostics=diagnostic,force_refresh=False,use_cache=True)
 assert source.verify_context(value,'5314.TWO') and diagnostic['http_request_count']==3 and not diagnostic['cache_hit']
 assert packet==['otc-master','5314.TWO:index:2026','5314.TWO:material']
 doc=value['documents'][0]
 assert len(doc['pages'])==doc['page_count']==93 and doc['native_text_coverage']=='complete'
 assert not doc['full_content_coverage_verified'] and not doc['financial_statement_complete']
 assert doc['content_period']=='mixed' and doc['published_at'] is None and doc['presentation_cover_date'] is None
 for role,numbers in ROLE_PAGES.items():
  projected=presentation_prompt_context(value,role)['documents'][0]
  assert [p['page_number'] for p in projected['pages']]==list(numbers)
  assert all(p['content_truncated'] is False for p in projected['pages'])
  assert '臨床' in projected['period_scope_caution'] and '單位' in projected['period_scope_caution']
 packet.clear();warm={};again=fetch_free_earnings_call_context('5314.TWO',diagnostics=warm,force_refresh=False,use_cache=True)
 assert not packet and warm['cache_hit'] is True and warm['http_request_count']==0
 assert again['documents']==value['documents']
 monkeypatch.setattr(time,'time',lambda:NOW+1800)
 assert not source.verify_context(value,'5314.TWO')

@pytest.mark.parametrize('damage',['role_pages','nonrole_text','caution','coverage','scope','material_receipt'])
def test_unbound_or_forged_packet_not_promoted_to_role_content(packet,damage):
 from data_fetch.market_sources import mops_presentation as source
 from conference_presentation_prompt import presentation_prompt_context
 value=source.fetch_presentation_context('5314.TWO');doc=value['documents'][0]
 if damage=='role_pages':doc['role_page_allowlist']['5']=list(range(1,94))
 elif damage=='nonrole_text':doc['pages'][78]['text']='Audited TWD thousand financials'
 elif damage=='caution':doc['period_scope_caution']='All medical efficacy and current financial units are independently verified'
 elif damage=='coverage':doc['native_text_coverage']='partial'
 elif damage=='scope':doc['financial_statement_complete']=True
 else:value['mops_material_receipt']['material']['raw_response_sha256']='0'*64
 assert not source.verify_context(value,'5314.TWO')
 assert not presentation_prompt_context(value,5).get('documents')

@pytest.mark.parametrize('damage',['ticker','ubn','instrument','foreign_alias'])
def test_provider_context_denial_precedes_any_http(monkeypatch,damage):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 from data_fetch.market_sources import mops_presentation as source
 data=valid_data()
 if damage=='ticker':data['ticker']='2330.TW'
 elif damage=='ubn':data['company_identity']['official_ubn']='00000000'
 elif damage=='instrument':data['quote_type']='ETF'
 else:data['company_identity']['allowed_aliases'].append('台積電')
 monkeypatch.setattr(source,'fetch_presentation_context',lambda *a,**k:pytest.fail('Unbound identity sent request'))
 result=EarningsCallProvider().fetch(FetchRequest.from_ticker('5314.TWO'),{'data':data})
 assert result.audit['error_kind']=='context_unverified' and result.audit['http_request_sent'] is False

@pytest.mark.parametrize('kind,status',[('timeout',None),('rate_limited',429),('lease_lost',None)])
def test_no_legacy_retry_after_new_primary_refusal(monkeypatch,kind,status):
 from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
 from data_fetch.market_sources import mops_presentation as source
 from search_provider_runtime import SourceResponseError
 import company_conference_content as legacy
 def fail(*a,**k):raise SourceResponseError(kind,status_code=status)
 monkeypatch.setattr(source,'fetch_presentation_context',fail)
 monkeypatch.setattr(legacy,'fetch_company_conference',lambda *a,**k:pytest.fail('Legacy retry bypassed primary refusal'))
 with pytest.raises(SourceResponseError):fetch_free_earnings_call_context('5314.TWO',force_refresh=False)

def test_provider_success_audit_is_not_mistagged_legacy_aggregate(packet):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 from data_fetch.market_sources.mops_presentation import PROVIDER
 from provider_acquisition import observation_kind
 provider=EarningsCallProvider()
 cold=provider.fetch(FetchRequest.from_ticker('5314.TWO'),{'data':valid_data()})
 assert cold.status=='success' and cold.audit['provider']==PROVIDER
 assert cold.audit['record_count']==1 and cold.audit['http_request_sent'] is True and cold.audit['http_request_count']==3
 assert not cold.audit['message'].startswith('optional 外部來源')
 assert observation_kind({**cold.audit,'details':cold.audit})=='fetched_count'
 packet.clear();warm=provider.fetch(FetchRequest.from_ticker('5314.TWO'),{'data':valid_data()})
 assert not packet and warm.audit['cache_hit'] is True and warm.audit['http_request_count']==0
 assert observation_kind({**warm.audit,'details':warm.audit})=='fresh_cache_count'

def test_new_primary_does_not_change_or_expire_valid_legacy_cache(packet):
 import cache_store
 from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
 key='shared_provider:v1:'+hashlib.sha256(b'myson-conference-content-v2:5314').hexdigest()
 old={'fetched_at_epoch':NOW-100,'fresh_until_epoch':NOW+10000,'retained_until_epoch':NOW+10000,'value':{'context':{'legacy':'original'}}}
 cache_store.set_cache_json(key,old,ttl_seconds=10000)
 before=deepcopy(cache_store.get_cache_json(key))
 value=fetch_free_earnings_call_context('5314.TWO',force_refresh=False)
 assert value['source']=='MOPS published presentation'
 assert cache_store.get_cache_json(key)==before

def test_source_refresh_preserves_original_analysis_and_single_acquisition(packet,tmp_path):
 from data_fetch import enrichment_providers
 from data_fetch.provider_registry import ProviderRegistry
 from data_fetch.service import StockDataService
 from report_refresh_service import refresh_report_data_snapshot
 from report_analysis_evidence import capture_analysis_evidence
 from storage.report_storage import InMemoryStorage
 from test_report_refresh_acquisition_audit import init_db,events
 from test_unitech_tcfhc_source_integration import saved_target,assert_preserved
 init_db();storage=InMemoryStorage();filename,keys,before=saved_target(storage,'5314.TWO','世紀*')
 before['data'].update(valid_data());before['analysis_evidence']=capture_analysis_evidence({'data':before['data']},generated_at=before['generated_at'])
 storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json')
 service=StockDataService(registry=ProviderRegistry([enrichment_providers.EarningsCallProvider()]))
 result=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='earnings_call',return_refreshed_data=True))
 after=json.loads(storage.get_report(keys.data_key).content)
 assert_preserved(storage,keys,before,after)
 assert result['analysis_text_stale'] is True and len(after['data']['earnings_call']['documents'][0]['pages'])==93
 audit=events();assert len(audit)==1 and audit[0]['status']=='success' and audit[0]['record_count']==1
 details=json.loads(audit[0]['details_json'])
 assert details['http_request_sent'] is True and details['http_request_count']==3
 assert len(details['original_http_receipts'])==3
