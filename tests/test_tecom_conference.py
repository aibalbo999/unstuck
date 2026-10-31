"""Tecom complete original with explicitly partial native text."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import base64, importlib, json, time
import pytest
R=Path(__file__).resolve().parents[1]
D=R/'docs/evidence/source-acquisition/20261015'
NOW=1792009000.
PROFILES={'tecom':{'ticker':'2321.TW','folder':'new-free-originals/tecom','pages':21,'date':'2025-12-17','document_date':'2025-12-17','cover':'2025-12','roles':[1,2,16,18,19]}}

def module(name):return importlib.import_module('data_fetch.market_sources.'+name+'_conference')
def identity(name):
 return json.loads((D/'tecom-conference-integration/current-targets.json').read_text())['targets'][PROFILES[name]['ticker']]['identity_input']
@pytest.fixture(params=PROFILES)
def profile(request):return request.param
@pytest.fixture
def harness(profile,monkeypatch):
 import cache_store
 from cache_backends import InMemoryCache
 t=importlib.import_module('data_fetch.market_sources.'+profile+'_conference_transport')
 cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
 bodies={t.MASTER_URL:(D.parent/'20261013/delta-transcript-integration/master.body').read_bytes(),t.INDEX_URL:(D/PROFILES[profile]['folder']/'index.body').read_bytes(),t.PDF_URL:(D/PROFILES[profile]['folder']/'presentation.body').read_bytes()};calls=[]
 def download(self,url,diagnostic):
  raw=bodies[url];calls.append(url);self.http_request_count+=1
  meta={'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(raw),'content_type':'text/csv'if url==t.MASTER_URL else'application/pdf'if url==t.PDF_URL else'text/html','content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'no-cache'}
  if url==t.MASTER_URL:
   from data_fetch.market_sources import official_issuer_master
   meta=official_issuer_master.master_metadata(meta,raw,{})
  else:meta.update(pragma='',expires='',age=None,cf_cache_status='')
  diagnostic.update(http_request_sent=True,http_status=200,response_metadata=meta)
  return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),'request_method':'GET','request_body':None,'response_metadata':meta}
 monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
 yield bodies,calls
 cache_store.reset_cache_store_for_tests()
def acquire(name,**kwargs):return getattr(module(name),'fetch_'+name+'_context')(PROFILES[name]['ticker'],**kwargs)
def test_qualified_missing_original_is_available(profile,request):
 try:s=module(profile)
 except ModuleNotFoundError as e:
  if e.name!='data_fetch.market_sources.'+profile+'_conference':raise
  value={}
 else:
  _,calls=request.getfixturevalue('harness');diag={};value=acquire(profile,diagnostics=diag)
  assert len(calls)==diag['http_request_count']==3
  assert s.validate_context(identity(profile),s.TICKER)and s.verify_context(value,s.TICKER,max_age=1800)
 assert len(value.get('documents',[]))==1,'Qualified native original has no source collector'
 d=value['documents'][0];p=PROFILES[profile]
 assert d['page_count']==len(d['pages'])==p['pages']and d['native_text_coverage']=='partial'
 assert d['event_date']==p['date']and d['material_file_date']==p['document_date']and d['presentation_cover_month']==p['cover']
 assert d['coverage_status']=='partial'and d['financial_statement_complete']is False and d['published_at']is None
 assert d['q_and_a_transcript_available']is False and value['transcript_available']is False
 assert d['role_page_allowlist']==p['roles']and 'symbol_mapping_evidence'not in d

@pytest.mark.parametrize('change',['epoch','expiry','manifest','page','coverage','financial','boolean','role','period','document_date','extra_field','missing_parser'])
def test_saved_proof_rejects_retiming_and_scope_edits(harness,profile,change):
 s=module(profile);v=acquire(profile);r=v[profile+'_conference_receipt']['pdf'];d=v['documents'][0]
 if change=='epoch':r['retrieved_at']+=1
 elif change=='expiry':r['fresh_until_epoch']-=1
 elif change=='manifest':r['acquisition_manifest']['raw_response_sha256']='0'*64
 elif change=='page':d['pages'][6]['text']='invented financial fact'
 elif change=='coverage':v['coverage_status']='complete'
 elif change=='financial':d['financial_statement_complete']=True
 elif change=='boolean':d['binary_complete']=1
 elif change=='role':d['role_page_allowlist'].append(9)
 elif change=='period':d['content_period']='2026Q3'
 elif change=='document_date':d['material_file_date']='2026-10-12'
 elif change=='extra_field':d['unqualified_claim']='extra fact'
 else:d.pop('parser_version')
 assert not s.verify_context(v,s.TICKER,max_age=1800)

@pytest.mark.parametrize('change',['name','ubn','alias','forbidden','quote','ticker','other_nanya'])
def test_context_does_not_mix_related_companies(profile,change):
 s=module(profile);d=identity(profile)
 if change=='name':d['raw_company_name']='Other issuer'
 elif change=='ubn':d['company_identity']['official_ubn']='00000000'
 elif change=='alias':d['company_identity']['allowed_aliases'].append('Different company')
 elif change=='forbidden':d['company_identity']['forbidden_aliases']=[s.LEGAL]
 elif change=='quote':d['quote_type']='ETF'
 elif change=='other_nanya':d['raw_company_name']='南亞科技股份有限公司'
 else:d['ticker']=s.TICKER.replace('.TW','.TWO')
 assert not s.validate_context(d,s.TICKER)

@pytest.mark.parametrize('options',[{}, {'force_refresh':True},{'use_cache':False}])
def test_success_does_not_reuse_old_index_or_pdf(harness,profile,options):
 s=module(profile);_,calls=harness;acquire(profile);acquire(profile,**options)
 assert calls.count(s.INDEX_URL)==calls.count(s.PDF_URL)==2

@pytest.mark.parametrize('role',[3,5,12])
def test_qualified_roles_keep_every_date_and_caution(harness,profile,role):
 from conference_presentation_prompt import presentation_prompt_context,without_presentation_documents
 v=acquire(profile);before=deepcopy(v);p=presentation_prompt_context(v,role);d=p['documents'][0]
 assert [x['page_number']for x in d['pages']]==PROFILES[profile]['roles']
 assert all(x['content_truncated']is False for x in d['pages'])
 for x in d['pages']:assert x['text']==before['documents'][0]['pages'][x['page_number']-1]['text']
 for key in ('native_editorial_caution','index_reuse_caution','unit_scope_caution','financial_scope_caution','forward_looking_caution','period_scope_caution','material_file_date','presentation_cover_month'):assert d[key]==v['documents'][0][key]
 assert 'symbol_mapping_evidence'not in d and 'documents'not in without_presentation_documents(v)and v==before

@pytest.mark.parametrize('change',['page','missing','boolean','event','role','scope','title','caution','extra_field','missing_parser'])
def test_roles_reject_modified_original(profile,harness,change):
 from conference_presentation_prompt import presentation_prompt_context
 v=acquire(profile);d=v['documents'][0]
 if change=='page':d['pages'][3]['text']='Unverified claim'
 elif change=='missing':d['pages'].pop()
 elif change=='boolean':d['pages'][0]['page_number']=True
 elif change=='event':d['event_date']=None
 elif change=='role':d['role_page_allowlist'].append(14)
 elif change=='scope':d['financial_statement_complete']=True
 elif change=='title':d['title']='Current audited results'
 elif change=='caution':d['forward_looking_caution']='Completed'
 elif change=='extra_field':d['unqualified_claim']='extra fact'
 else:d.pop('parser_version')
 for role in (3,5,12):assert not presentation_prompt_context(v,role).get('documents')

@pytest.mark.parametrize('marker_kind',['receipt','provider','policy','url'])
def test_private_original_is_never_reusable_financial_cache(profile,monkeypatch,marker_kind):
 from data_fetch import cache_helpers
 from prompt_evidence import prompt_evidence_copy
 s=module(profile);marker={'receipt':{profile+'_conference_receipt':None},'provider':{'source':s.PROVIDER},'policy':{'projection_policy':s.PROJECTION_POLICY},'url':{'url':s.PDF_URL}}[marker_kind]
 calls=[];monkeypatch.setattr(cache_helpers,'set_cache_json',lambda *a,**kw:calls.append(a))
 value={'ticker':s.TICKER,'earnings_call':{'documents':[marker]}};before=deepcopy(value)
 cache_helpers._cache_financial_data(value,s.TICKER);assert not calls and value==before
 assert prompt_evidence_copy({profile+'_conference_receipt':{'private':'archive'},'text':'正文'})=={'text':'正文'}

@pytest.mark.parametrize('failure',[None,'timeout','cooldown','single_flight_busy','guard_storage_unavailable'])
def test_public_dispatch_honors_source_policy(profile,monkeypatch,failure):
 from data_fetch import earnings_call_fetcher as e
 from search_provider_runtime import SourceResponseError
 s=module(profile);calls=[];expected={'source':s.PROVIDER,'documents':[{'page_count':s.PAGE_COUNT}]}
 def fake(ticker,**kw):
  calls.append((ticker,kw))
  if failure:raise SourceResponseError(failure)
  return expected
 monkeypatch.setattr(s,'fetch_'+profile+'_context',fake)
 if failure:
  with pytest.raises(SourceResponseError)as caught:e.fetch_free_earnings_call_context(s.TICKER)
  assert caught.value.error_kind==failure
 else:assert e.fetch_free_earnings_call_context(s.TICKER)==expected
 assert len(calls)==1

def test_context_conflict_local_block_and_single_success_count(profile,monkeypatch):
 from data_fetch import enrichment_providers as e
 from data_fetch.types import FetchRequest
 from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
 s=module(profile)
 monkeypatch.setattr(e,'fetch_free_earnings_call_context',lambda *a,**k:pytest.fail('invalid identity reached HTTP'))
 result=e.EarningsCallProvider().fetch(FetchRequest.from_ticker(s.TICKER),{'data':{'ticker':s.TICKER,'quote_type':'ETF'}})
 assert result.provider==s.PROVIDER and result.audit['event_kind']=='local_block'and result.audit['http_request_count']==0
 result={'value':{'source':s.PROVIDER,'documents':[{'page_count':s.PAGE_COUNT}]},'audit':{'status':'success','record_count':12}}
 apply_earnings_call_audit(result,{profile+'_presentation_workflow':True,profile+'_originals_verified':True,'actual_provider':s.PROVIDER,'http_request_count':3,'http_request_sent':True,'cache_hit':False})
 assert result['audit']['record_count']==1 and result['audit']['http_request_count']==3

@pytest.mark.parametrize('tamper',[None,'fact','missing_page','receipt'])
def test_actual_source_only_refresh_and_later_historical_retention(profile,harness,tmp_path,monkeypatch,tamper):
 import asyncio
 from fastapi import HTTPException
 from data_fetch import enrichment_providers as e
 from data_fetch.provider_registry import ProviderRegistry
 from data_fetch.service import StockDataService
 from report_refresh_service import refresh_report_data_snapshot
 from report_analysis_evidence import capture_analysis_evidence
 from storage.report_storage import InMemoryStorage
 from test_report_refresh_acquisition_audit import init_db,events
 from test_unitech_tcfhc_source_integration import saved_target,assert_preserved
 init_db();s=module(profile);storage=InMemoryStorage();filename,keys,before=saved_target(storage,s.TICKER,s.LEGAL)
 before['data'].update(identity(profile));before['analysis_evidence']=capture_analysis_evidence({'data':before['data']},generated_at=before['generated_at'])
 storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json');original=storage.get_report(keys.data_key).content
 if tamper:
  real=e.fetch_free_earnings_call_context
  def edited(*args,**kwargs):
   v=real(*args,**kwargs)
   if tamper=='missing_page':v['documents'][0]['pages'].pop()
   elif tamper=='fact':v['documents'][0]['pages'][12]['text']='Completed customer contracts'
   else:v.pop(profile+'_conference_receipt')
   return v
  monkeypatch.setattr(e,'fetch_free_earnings_call_context',edited)
 service=StockDataService(registry=ProviderRegistry([e.EarningsCallProvider()]))
 call=refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='earnings_call',return_refreshed_data=True)
 if tamper:
  with pytest.raises(HTTPException)as caught:asyncio.run(call)
  assert caught.value.status_code==502 and storage.get_report(keys.data_key).content==original
 else:
  result=asyncio.run(call);after=json.loads(storage.get_report(keys.data_key).content)
  assert after['data']['earnings_call']['documents'][0]['page_count']==s.PAGE_COUNT
  assert result['analysis_text_stale']is True;assert_preserved(storage,keys,before,after)
  from report_conference_retention import retain_verified_conference
  from test_conference_retention_new_profiles import failed_data
  from provider_acquisition import project_acquisition_events
  for future in (NOW,NOW+400*86400):
   monkeypatch.setattr(time,'time',lambda:future)
   if future>NOW:assert not s.verify_context(after['data']['earnings_call'],s.TICKER,max_age=1800)
   retained=retain_verified_conference(after,failed_data(after,profile,now=future),s.TICKER)
   assert retained['earnings_call']==after['data']['earnings_call']and retained['conference_retention']['new_acquisition']is False
   reused=retained['source_audit'][0]
   row=project_acquisition_events([{**reused,'created_at':future,'details_json':json.dumps(reused)}],window='last_24h',now=future)['sources'][0]
   assert row['fetch_attempts']==row['fetched_count']==0 and row['stale_cache_count']==1
 assert len(events())==1 and len(harness[1])==3


@pytest.mark.parametrize('change',['date','pdf','new_card','duplicate','truncated','trailer','canonical','owner','onclick','root'])
def test_changed_current_card_or_document_stops_before_pdf(profile,harness,change):
 from bs4 import BeautifulSoup
 from search_provider_runtime import SourceResponseError
 s=module(profile);bodies,calls=harness;raw=bodies[s.INDEX_URL];soup=BeautifulSoup(raw,'html.parser')
 root=soup.select('[data-elementor-type="wp-page"]')[0]
 card=root.select('div.elementor-inner-column')[0]
 if change=='date':
  for n in card.find_all(string=lambda x:x and '2025/12/17'in x):n.replace_with(str(n).replace('2025/12/17','2026/10/15'))
 elif change=='pdf':card.select('a[href]')[1]['href']='https://example.invalid/new.pdf'
 elif change in ('new_card','duplicate'):
  new=deepcopy(card)
  if change=='new_card':new['data-id']='new-event'
  card.insert_before(new)
 elif change=='truncated':raw=raw[:raw.rindex(b'</html>')]
 elif change=='trailer':raw+=b'<p>new event</p>'
 elif change=='canonical':soup.select('link[rel="canonical"]')[0]['href']='https://other.invalid/'
 elif change=='owner':soup.title.string='Different publisher'
 elif change=='onclick':card.select('a[href]')[1]['onclick']='alternateAction()'
 else:root['data-elementor-id']='different'
 if change not in ('truncated','trailer'):raw=str(soup).encode()
 assert raw!=bodies[s.INDEX_URL];bodies[s.INDEX_URL]=raw
 with pytest.raises(SourceResponseError):acquire(profile)
 assert calls==[s.MASTER_URL,s.INDEX_URL]

def test_partial_native_bytes_and_project_estimates_are_never_promoted(profile,harness):
 from conference_presentation_prompt import presentation_prompt_context
 s=module(profile);v=acquire(profile);d=v['documents'][0]
 assert d['garbled_pages']==[3,12] and d['text_extraction_complete']is False
 assert any('\ue000'<=c<='\uf8ff'for c in d['pages'][2]['text'])
 for role in (3,5,12):
  p=presentation_prompt_context(v,role)['documents'][0]
  assert p['native_text_coverage']=='partial'
  assert p['publisher_notice']==d['publisher_notice']
  assert [x['page_number']for x in p['pages']]==[1,2,16,18,19]
  assert '預計0.59年'in p['pages'][-1]['text']
  assert all('TECOM PROPRIETARY AND CONFIDENTIAL'in x['text']for x in p['pages'][1:])
  assert p['period_scope_caution']==d['period_scope_caution']
