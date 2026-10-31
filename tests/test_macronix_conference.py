"""Published dynamic index must select a past original, not a future empty row."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import base64, importlib, json, time
import pytest

R=Path(__file__).resolve().parents[1]
D=R/'docs/evidence/source-acquisition/20261015'
NOW=1792016200.

def source():
    return importlib.import_module('data_fetch.market_sources.macronix_conference')

def identity():
    return json.loads((D/'macronix-conference-integration/identity-input.json').read_text())

def test_published_original_has_a_real_collector():
    try:s=source()
    except ModuleNotFoundError as e:
        if e.name!='data_fetch.market_sources.macronix_conference':raise
        pytest.fail('Verified Macronix public original still has no collector')
    selected=s.select_presentation((D/'macronix-dynamic-originals/results.body').read_bytes(),NOW,as_of_epoch=NOW)
    assert selected['event_date']=='2026-07-28' and selected['period_label']=='2026Q2'
    assert '656/2026q2%20webcast_ppt_en.pdf' in selected['pdf_url']
    assert s.validate_context(identity(),s.TICKER)

@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    s=source();t=importlib.import_module('data_fetch.market_sources.macronix_conference_transport')
    cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={t.YEARS_URL:(D/'macronix-dynamic-originals/years.body').read_bytes(),t.MASTER_URL:(D.parent/'20261013/delta-transcript-integration/master.body').read_bytes(),
            t.INDEX_URL:(D/'macronix-dynamic-originals/results.body').read_bytes(),
            t.PDF_URL:(D/'macronix-dynamic-originals/presentation.body').read_bytes()}
    calls=[]
    def download(self,url,diagnostic):
        raw=bodies[url];calls.append(url);self.http_request_count+=1
        meta={'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(raw),'content_type':'text/csv' if url==t.MASTER_URL else 'application/pdf' if url==t.PDF_URL else 'text/html','content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'private, no-store, no-cache'}
        if url==t.MASTER_URL:
            from data_fetch.market_sources import official_issuer_master
            meta=official_issuer_master.master_metadata(meta,raw,{})
        else:meta.update(pragma='',expires='',age=None,cf_cache_status='')
        diagnostic.update(http_request_sent=True,http_status=200,response_metadata=meta)
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),**t.request_spec(url),'response_metadata':meta}
    monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
    yield s,bodies,calls
    cache_store.reset_cache_store_for_tests()

def test_original_and_whole_qualified_pages_replay(harness):
    from conference_presentation_prompt import presentation_prompt_context
    s,_,calls=harness;diag={};v=s.fetch_macronix_context(s.TICKER,diagnostics=diag)
    assert len(calls)==diag['http_request_count']==4
    assert s.verify_context(v,s.TICKER,max_age=1800)
    doc=v['documents'][0]
    assert doc['page_count']==len(doc['pages'])==23 and doc['native_text_coverage']=='partial'
    assert doc['garbled_pages']==[13,16,17,18,20]
    assert doc['coverage_status']=='partial' and doc['financial_statement_complete'] is False
    for role in (3,5,12):
        shown=presentation_prompt_context(v,role)['documents'][0]
        assert [p['page_number'] for p in shown['pages']]==[1,2,7,8,12]
        for p in shown['pages']:
            assert p['text']==doc['pages'][p['page_number']-1]['text'] and not p['content_truncated']
        assert shown['content_period']=='2026Q2' and shown['financial_statement_complete'] is False

@pytest.mark.parametrize('edit',['new_body','new_date','duplicate','year','filename','extra','truncate','duplicate_key'])
def test_changed_or_ambiguous_index_is_not_silently_accepted(edit):
    s=source();raw=(D/'macronix-dynamic-originals/results.body').read_bytes();v=json.loads(raw)
    if edit=='new_body':v[2]['webcast_PPT']='2026q3 webcast_ppt_en.pdf'
    elif edit=='new_date':v[1]['AnnounceDate']='2026/10/27'
    elif edit=='duplicate':v.append(deepcopy(v[1]))
    elif edit=='year':v[1]['Year']='2025'
    elif edit=='filename':v[1]['webcast_PPT']='../foreign.pdf'
    elif edit=='extra':v[1]['claims']='extra'
    raw=json.dumps(v).encode()
    if edit=='truncate':raw=raw[:-1]
    if edit=='duplicate_key':raw=raw.replace(b'"Id": "656"',b'"Id": "656", "Id": "656"')
    with pytest.raises(ValueError):s.select_presentation(raw,NOW,as_of_epoch=NOW)

@pytest.mark.parametrize('edit',['epoch','page','scope','future','identity','missing','role'])
def test_saved_evidence_cannot_be_relabelled(harness,edit):
    s,_,_=harness;v=s.fetch_macronix_context(s.TICKER);doc=v['documents'][0]
    if edit=='epoch':v['macronix_conference_receipt']['pdf']['retrieved_at']+=1
    elif edit=='page':doc['pages'][6]['text']='invented result'
    elif edit=='scope':doc['coverage_status']='complete'
    elif edit=='future':doc['event_date']='2026-10-27'
    elif edit=='identity':v['ticker']='2330.TW'
    elif edit=='missing':doc['pages'].pop()
    else:doc['role_page_allowlist'].append(13)
    assert not s.verify_context(v,s.TICKER,max_age=1800)

def test_header_policy_preserves_all_cache_restrictions():
    t=importlib.import_module('data_fetch.market_sources.macronix_conference_transport')
    raw=(D/'macronix-dynamic-originals/results.headers').read_bytes()
    code,headers=t._headers(raw)
    assert code==200 and headers['cache-control']=='private, no-store, no-cache'
    assert t.validation_ttl({'cache_control':headers['cache-control'],'age':None})==1800
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):t._headers(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 3\r\n\r\n')

def test_no_success_cache_reuse(harness):
    s,_,calls=harness;s.fetch_macronix_context(s.TICKER);s.fetch_macronix_context(s.TICKER)
    assert calls.count(s.INDEX_URL)==calls.count(s.PDF_URL)==2

@pytest.mark.parametrize('tamper',[None,'fact','missing_page','receipt'])
def test_actual_source_only_refresh_and_later_historical_retention(harness,tmp_path,monkeypatch,tamper):
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
 init_db();s=source();storage=InMemoryStorage();filename,keys,before=saved_target(storage,s.TICKER,s.LEGAL)
 before['data'].update(identity());before['analysis_evidence']=capture_analysis_evidence({'data':before['data']},generated_at=before['generated_at'])
 storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json');original=storage.get_report(keys.data_key).content
 if tamper:
  real=e.fetch_free_earnings_call_context
  def edited(*args,**kwargs):
   v=real(*args,**kwargs)
   if tamper=='missing_page':v['documents'][0]['pages'].pop()
   elif tamper=='fact':v['documents'][0]['pages'][12]['text']='Completed customer contracts'
   else:v.pop('macronix_conference_receipt')
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
   retained=retain_verified_conference(after,failed_data(after,'macronix',now=future),s.TICKER)
   assert retained['earnings_call']==after['data']['earnings_call']and retained['conference_retention']['new_acquisition']is False
   reused=retained['source_audit'][0]
   row=project_acquisition_events([{**reused,'created_at':future,'details_json':json.dumps(reused)}],window='last_24h',now=future)['sources'][0]
   assert row['fetch_attempts']==row['fetched_count']==0 and row['stale_cache_count']==1
 assert len(events())==1 and len(harness[2])==4


@pytest.mark.parametrize('marker_kind',['receipt','provider','policy','url'])
def test_private_original_is_never_reusable_financial_cache(monkeypatch,marker_kind):
 from data_fetch import cache_helpers
 from prompt_evidence import prompt_evidence_copy
 s=source();marker={'receipt':{'macronix_conference_receipt':None},'provider':{'source':s.PROVIDER},'policy':{'projection_policy':s.PROJECTION_POLICY},'url':{'url':s.PDF_URL}}[marker_kind]
 calls=[];monkeypatch.setattr(cache_helpers,'set_cache_json',lambda *a,**kw:calls.append(a))
 value={'ticker':s.TICKER,'earnings_call':{'documents':[marker]}};before=deepcopy(value)
 cache_helpers._cache_financial_data(value,s.TICKER);assert not calls and value==before
 assert prompt_evidence_copy({'macronix_conference_receipt':{'private':'archive'},'text':'正文'})=={'text':'正文'}

@pytest.mark.parametrize('failure',[None,'timeout','cooldown','single_flight_busy','guard_storage_unavailable'])
def test_public_dispatch_honors_source_policy(monkeypatch,failure):
 from data_fetch import earnings_call_fetcher as e
 from search_provider_runtime import SourceResponseError
 s=source();calls=[];expected={'source':s.PROVIDER,'documents':[{'page_count':s.PAGE_COUNT}]}
 def fake(ticker,**kw):
  calls.append((ticker,kw))
  if failure:raise SourceResponseError(failure)
  return expected
 monkeypatch.setattr(s,'fetch_macronix_context',fake)
 if failure:
  with pytest.raises(SourceResponseError)as caught:e.fetch_free_earnings_call_context(s.TICKER)
  assert caught.value.error_kind==failure
 else:assert e.fetch_free_earnings_call_context(s.TICKER)==expected
 assert len(calls)==1

def test_context_conflict_local_block_and_single_success_count(monkeypatch):
 from data_fetch import enrichment_providers as e
 from data_fetch.types import FetchRequest
 from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
 s=source()
 monkeypatch.setattr(e,'fetch_free_earnings_call_context',lambda *a,**k:pytest.fail('invalid identity reached HTTP'))
 result=e.EarningsCallProvider().fetch(FetchRequest.from_ticker(s.TICKER),{'data':{'ticker':s.TICKER,'quote_type':'ETF'}})
 assert result.provider==s.PROVIDER and result.audit['event_kind']=='local_block'and result.audit['http_request_count']==0
 result={'value':{'source':s.PROVIDER,'documents':[{'page_count':s.PAGE_COUNT}]},'audit':{'status':'success','record_count':12}}
 apply_earnings_call_audit(result,{'macronix_presentation_workflow':True,'macronix_originals_verified':True,'actual_provider':s.PROVIDER,'http_request_count':3,'http_request_sent':True,'cache_hit':False})
 assert result['audit']['record_count']==1 and result['audit']['http_request_count']==3
