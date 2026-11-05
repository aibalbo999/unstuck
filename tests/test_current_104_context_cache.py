"""Optional context cache preserves the earlier original deadline and IDs."""
import time,json
from dataclasses import replace
import pytest
from test_current_104_transport import setup,DATA,ISSUER
from data_fetch.market_sources import current_104_evidence as e,current_104_transport as t
from data_fetch.context_provider_cache import cached_context_result
from data_fetch.types import FetchRequest
from provider_correlation import correlation_scope,source_operation

class Provider:
 source='alternative_data';name=e.PROVIDER


def test_outer_cache_prevents_new_api_calls_and_preserves_original_time(monkeypatch):
 from data_fetch import context_provider_cache as cache
 from cache_store import get_cache_json
 calls=setup(monkeypatch);acquisitions=[];request=FetchRequest.from_ticker(ISSUER['ticker'])
 def acquire(req,ctx):
  acquisitions.append(1)
  return t.fetch_current_advertisements(req,DATA,ISSUER,primary={'status':'unavailable'})
 with correlation_scope(replace=True,ticker=ISSUER['ticker'],fetch_id='f'),source_operation('alternative_data',e.PROVIDER):
  first=cached_context_result(Provider(),request,{'data':DATA},acquire)
 before=get_cache_json(e.cache_key(ISSUER));stamp=first.audit['fetched_at_epoch']
 assert first.status=='success'
 with correlation_scope(replace=True,ticker=ISSUER['ticker'],fetch_id='another'),source_operation('alternative_data',e.PROVIDER):
  second=cached_context_result(Provider(),request,{'data':DATA},acquire)
 assert second.status=='success'and second.audit['cache_hit']is True
 assert second.audit['http_request_sent']is False and second.audit['http_request_count']==0
 assert second.audit['fetched_at_epoch']==stamp and len(acquisitions)==1 and len(calls)==2
 assert get_cache_json(e.cache_key(ISSUER))==before
 monkeypatch.setattr(e,'verified_issuer',lambda *a,**k:False)
 with correlation_scope(replace=True,ticker=ISSUER['ticker'],fetch_id='third'),source_operation('alternative_data',e.PROVIDER):
  third=cached_context_result(Provider(),request,{'data':DATA},acquire)
 assert third.status=='unavailable'and third.audit['record_count']==0 and len(calls)==2


def test_provider_preserves_primary_recent_success_without_new_fallback(monkeypatch):
 import alternative_data_fetcher as old
 from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
 monkeypatch.setattr(old,'fetch_104_company_jobs',lambda *a,**k:{'status':'success','evidence_kind':'company_job_postings','job_count':None,'job_postings':[{'title':'工程師','url':'https://www.104.com.tw/job/abc'}]})
 monkeypatch.setattr(old,'fetch_1111_job_openings_count',lambda *a,**k:{'status':'unavailable','job_count':None})
 monkeypatch.setattr(t,'fetch_current_advertisements',lambda *a,**k:pytest.fail('primary success must not call modern fallback'))
 data={**DATA,'company_identity':{**DATA['company_identity'],'legal_name':ISSUER['legal_name']}}
 result=AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker(ISSUER['ticker']),{'data':data})
 assert result.value['job_openings_104']['status']=='success'


def test_untrusted_candidate_cannot_bypass_source_operation_or_original_count(monkeypatch):
 calls=setup(monkeypatch)
 from prompt_evidence import prompt_evidence_copy
 from test_current_104_postings import packets,raw,NOW,JOB
 from data_fetch.market_sources.current_104_postings import parse_snapshot
 a,b=packets();p=parse_snapshot(raw(a),{JOB:raw(b)},issuer=ISSUER,observed_at=NOW,now=NOW).public_value()
 p.update(source_record_archive={'manifest':{'raw_response_path':'/private/contact.json'}})
 projected=prompt_evidence_copy({'alternative_data':{'job_openings_104_current':p}})
 assert 'raw_response_path'not in json.dumps(projected)and '/private/contact.json'not in json.dumps(projected)


def test_provider_uses_one_modern_batch_after_empty_recent_sample(monkeypatch):
 import alternative_data_fetcher as old
 from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
 from data_fetch.market_sources import official_company_legal_name as legal
 calls=setup(monkeypatch)
 monkeypatch.setattr(legal,'get_official_legal_name',lambda *a,**k:ISSUER)
 monkeypatch.setattr(legal,'verified_legal_name_from_evidence',lambda *a,**k:ISSUER['legal_name'])
 monkeypatch.setattr(legal,'verified_official_ubn_from_evidence',lambda *a,**k:ISSUER['official_ubn'])
 monkeypatch.setattr(old,'fetch_104_company_jobs',lambda *a,**k:{'status':'unavailable','reason_code':'no_verified_postings','job_count':None})
 monkeypatch.setattr(old,'fetch_104_company_jobs_by_ubn',lambda *a,**k:pytest.fail('legacy duplicate chain'))
 monkeypatch.setattr(old,'fetch_104_job_openings_count',lambda *a,**k:pytest.fail('unneeded keyword search'))
 monkeypatch.setattr(old,'fetch_1111_job_openings_count',lambda *a,**k:pytest.fail('unneeded keyword search'))
 with correlation_scope(replace=True,ticker=ISSUER['ticker'],fetch_id='f'),source_operation('alternative_data',e.PROVIDER):
  result=AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker(ISSUER['ticker']),{'data':DATA})
 assert result.status=='success'and len(calls)==2
 assert result.value['job_openings_104_current']['observed_sample_posting_count']==1
 assert result.audit['record_count']==1 and result.value['recent_company_job_count_104']is None


def test_outer_cache_rechecks_payload_identity_and_rejects_forged_boolean_count(monkeypatch):
 from data_fetch.types import ProviderResult
 from data_fetch import context_provider_cache as cache
 calls=setup(monkeypatch);request=FetchRequest.from_ticker(ISSUER['ticker'])
 with correlation_scope(replace=True,ticker=ISSUER['ticker'],fetch_id='f'),source_operation('alternative_data',e.PROVIDER):
  native=t.fetch_current_advertisements(request,DATA,ISSUER)
 from dataclasses import asdict
 forged=asdict(native);forged['audit']['record_count']=True
 monkeypatch.setattr(__import__('shared_provider_cache'),'shared_fetch',lambda *a,**k:(forged,{'cache_hit':True,'stale':False,'fetched_at_epoch':time.time()}))
 result=cached_context_result(Provider(),request,{'data':DATA},lambda *a:pytest.fail('no acquire'))
 assert result.status=='unavailable'and result.audit['record_count']==0
