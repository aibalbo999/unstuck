from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json,time
import pytest
from test_cht_careers_parser import NOW,index,listing,bodies
from test_shared_provider_cache import memory_cache
from data_fetch.market_sources import cht_careers as c


def issuer():
 from official_response_evidence import archive_response
 from data_fetch.market_sources.official_company_legal_name import parse_roster,select_legal_name,URLS
 rows=[{'公司代號':str(n),'公司名稱':f'測試{n}股份有限公司','公司簡稱':f'測{n}','出表日期':'1151030','營利事業統一編號':str(20000000+n),'網址':'https://example.com'}for n in range(1000,1800)]
 rows.append({'公司代號':'2412','公司名稱':c.LEGAL,'公司簡稱':c.SHORT,'出表日期':'1151030','營利事業統一編號':c.UBN,'網址':'http://www.cht.com.tw'})
 raw=json.dumps(rows,ensure_ascii=False).encode();archive_response(raw,source_url=URLS['.TW'],retrieved_at=NOW,http_status=200)
 anchor=select_legal_name(parse_roster(raw,'.TW'),c.TICKER,c.SHORT,today=datetime.fromtimestamp(NOW,c.TZ).date());return {**anchor,'fetched_at_epoch':NOW}


def receipts():
 from official_response_evidence import archive_response
 rows=[]
 for url,raw in [(c.INDEX_URL,index()),(c.LIST_URL,listing()),*bodies().items()]:
  rows.append({'schema':'cht-careers-http.v1','url':url,'method':'GET','encoding':'utf-8'if url==c.INDEX_URL else'cp950','fetched_at_epoch':NOW,
   'raw_receipt':archive_response(raw,source_url=url,retrieved_at=NOW,http_status=200)})
 return rows


def test_complete_original_chain_replays_three_exact_open_jobs_without_network(monkeypatch):
 monkeypatch.setattr(time,'time',lambda:NOW);a=issuer();v=c.parse_receipts(receipts(),now=NOW)
 assert c.verified_job_count(v,c.TICKER,c.LEGAL,c.UBN,a,now=NOW)==3
 assert v['current_open_job_count']is None and v['job_count']is None and not v['first_publication_verified']
 assert c.verified_job_count(v,c.TICKER,c.LEGAL,c.UBN,a,now=NOW+3600)==0

@pytest.mark.parametrize('change',[
 lambda v:v.update(current_open_job_count=11),lambda v:v.update(first_publication_verified=True),
 lambda v:v['job_postings'][0].update(employer='中華電信子公司'),lambda v:v['job_postings'][0].update(title='wrong'),
 lambda v:v['job_postings'][0].update(published_date='2026-10-16'),lambda v:v['source_record_archive']['receipts'][0].update(url=c.LIST_URL),
 lambda v:v['source_record_archive']['receipts'][0]['raw_receipt'].update(raw_response_sha256='0'*64),
 lambda v:v['source_record_archive']['receipts'].pop(),
 lambda v:v['source_record_archive']['receipts'].append(v['source_record_archive']['receipts'][-1])])
def test_counter_never_trusts_changed_display_fields_or_damaged_originals(monkeypatch,change):
 monkeypatch.setattr(time,'time',lambda:NOW);a=issuer();v=c.parse_receipts(receipts(),now=NOW);change(v)
 assert c.verified_job_count(v,c.TICKER,c.LEGAL,c.UBN,a,now=NOW)==0

@pytest.mark.parametrize('key,value',[('ticker','2330.TW'),('official_ubn','12345678'),('legal_name','中華電信子公司股份有限公司'),('official_short_name','中華電信'),('response_sha256','a'*64),('as_of','2025-10-30')])
def test_current_complete_issuer_original_must_match_metadata(monkeypatch,key,value):
 monkeypatch.setattr(time,'time',lambda:NOW);a=issuer();a[key]=value
 assert not c.verified_issuer(a,c.TICKER,c.SHORT,now=NOW)


def test_normal_provider_uses_official_jobs_and_skips_blocked_keyword_portals(monkeypatch):
 monkeypatch.setattr(time,'time',lambda:NOW);anchor=issuer();rs=receipts();calls=[]
 from data_fetch.market_sources import official_company_legal_name as master,cht_careers_transport as wire
 from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
 from data_fetch.types import FetchRequest
 from data_trust import source_record_count
 monkeypatch.setattr(master,'get_official_legal_name',lambda *a:anchor)
 def read(self,url):
  calls.append(url);self.http_request_count+=1;self.components.append({'source_url':url,'cache_hit':False,'http_request_sent':True,'http_request_count':1})
  return deepcopy(next(r for r in rs if r['url']==url))
 monkeypatch.setattr(wire.ChtCareersHttp,'read',read)
 def forbidden(*a,**kw):raise AssertionError('Legacy keyword sources must not run after exact official success')
 monkeypatch.setattr(AlternativeJobOpeningsProvider,'_fetch_uncached',forbidden)
 data={'ticker':c.TICKER,'company_name':c.SHORT,'quote_type':'EQUITY','company_identity':{'ticker':c.TICKER,'official_name':c.SHORT,'instrument_type':'EQUITY'}}
 provider=AlternativeJobOpeningsProvider();request=FetchRequest.from_ticker(c.TICKER)
 first=provider.fetch(request,{'data':data});second=provider.fetch(request,{'data':data})
 assert first.status=='success'and len(calls)==5
 assert source_record_count('alternative_data',{**data,'alternative_data':first.value})==3
 assert second.audit['cache_hit']is True and second.audit['http_request_count']==0 and second.audit['http_request_sent']is False
 assert second.audit['fetched_at_epoch']==first.audit['fetched_at_epoch']
 from alternative_source_refresh import guard_alternative_result
 assert guard_alternative_result(first,data).status=='success'
 assert guard_alternative_result(second,data).status=='success'

@pytest.mark.parametrize('change',[
 lambda d:d.update(quote_type='ETF'),lambda d:d.update(quoteType='ETF'),lambda d:d.update(instrument_type='ETF'),
 lambda d:d.update(ticker='2330.TW'),lambda d:d['company_identity'].update(ticker='2330.TW'),
 lambda d:d['company_identity'].update(official_name='中華電信'),lambda d:d['company_identity'].update(official_ubn='12345678'),
 lambda d:d['company_identity'].update(stock_id='2330'),lambda d:d['company_identity'].update(legal_name='中華電信子公司')])
def test_conflicting_identity_or_instrument_cannot_enter_official_provider(change):
 from data_fetch.cht_careers_provider import eligible
 from data_fetch.types import FetchRequest
 data={'ticker':c.TICKER,'quote_type':'EQUITY','company_identity':{'ticker':c.TICKER,'official_name':c.SHORT,'instrument_type':'EQUITY'}}
 change(data);assert not eligible(data,FetchRequest.from_ticker(c.TICKER))


def test_failed_official_attempt_remains_a_failure_when_legacy_fallback_runs(monkeypatch):
 from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
 from data_fetch.types import FetchRequest,ProviderResult
 from data_fetch import cht_careers_provider as provider
 from provider_acquisition import observation_kind
 error=ProviderResult('alternative_data','104 & 1111 job openings','unavailable',value={},audit={
  'source':'alternative_data','provider':'104 & 1111 job openings','actual_provider':c.PROVIDER,'status':'unavailable','record_count':0,
  'event_kind':'fetch','http_request_sent':True,'http_request_count':1,'http_status':503,'cache_hit':False})
 monkeypatch.setattr(provider,'cht_context_result',lambda *a:error)
 fallback=ProviderResult('alternative_data','104 & 1111 job openings','degraded_enrichment',value={'old':'preserved'},audit={'source':'alternative_data','provider':'104 & 1111 job openings','status':'degraded_enrichment','record_count':0})
 monkeypatch.setattr(AlternativeJobOpeningsProvider,'_fetch_uncached',lambda *a:fallback)
 result=AlternativeJobOpeningsProvider().fetch(FetchRequest.from_ticker(c.TICKER),{'data':{'ticker':c.TICKER}})
 child,=result.audit['related_entries'];assert child['provider']==c.PROVIDER and child['http_status']==503
 assert result.value['old']=='preserved' and result.value['cache_hit']is False
 assert observation_kind({**child,'message':'failure','details':child})=='failed_count'


def test_source_only_path_preserves_child_failure_without_changing_one_row_contract(monkeypatch):
 import asyncio
 from data_fetch.service import StockDataService
 from data_fetch.provider_registry import ProviderRegistry
 from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
 from data_fetch.types import FetchRequest,FetchOptions,ProviderResult
 import provider_sla
 rows=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rs:rows.extend(deepcopy(rs)))
 child={'source':'alternative_data','provider':c.PROVIDER,'status':'unavailable','record_count':0,'http_request_sent':True,'http_request_count':1,'http_status':503}
 result=ProviderResult('alternative_data','104 & 1111 job openings','unavailable',value={},audit={'source':'alternative_data','provider':'104 & 1111 job openings','status':'unavailable','record_count':0,'related_entries':[child]})
 monkeypatch.setattr(AlternativeJobOpeningsProvider,'fetch',lambda *a:deepcopy(result))
 data={'ticker':c.TICKER,'company_name':c.SHORT,'quote_type':'EQUITY','company_identity':{'ticker':c.TICKER,'official_name':c.SHORT,'instrument_type':'EQUITY'}}
 service=StockDataService(registry=ProviderRegistry([AlternativeJobOpeningsProvider()]))
 fetched=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker(c.TICKER),'alternative_data',context={'data':data}))
 assert len(fetched.source_audit)==1 and rows==[child]
 rows.clear();request=FetchRequest.from_ticker(c.TICKER,record_provider_sla=False)
 asyncio.run(service.fetch_source_async(request,'alternative_data',context={'data':data}));assert not rows


@pytest.mark.parametrize('patch',[
 {'legal_name':{}},{'english_names':'Chunghwa Telecom Co., Ltd.'},
 {'english_names':[{}]},{'legal_name':['中華電信股份有限公司']}])
def test_malformed_identity_values_fail_closed(patch):
 data={'ticker':c.TICKER,'company_name':c.SHORT,'quote_type':'EQUITY',
       'company_identity':{'ticker':c.TICKER,'official_name':c.SHORT,'instrument_type':'EQUITY',**patch}}
 assert not c.valid_context(data)


def test_future_at_acquisition_cannot_become_current_by_replaying_later(monkeypatch):
 from official_response_evidence import archive_response
 monkeypatch.setattr(time,'time',lambda:NOW);rs=receipts()
 for r in rs[:2]:
  encoding=r['encoding'];raw=c.receipt_body(r,r['url'],NOW).decode(encoding)
  raw=raw.replace('2026/10/16 12:00','2026/10/30 13:00').encode(encoding)
  r['raw_receipt']=archive_response(raw,source_url=r['url'],retrieved_at=NOW-1,http_status=200)
 for r in rs:
  r['fetched_at_epoch']=NOW-1;r['raw_receipt']['retrieved_at']=NOW-1
 with pytest.raises(ValueError):c.parse_receipts(rs,now=NOW+1)


@pytest.mark.parametrize('archive_fails',[False,True])
def test_roster_archival_is_supplemental_and_preserves_existing_metadata(monkeypatch,archive_fails):
 import httpx
 from official_response_evidence import read_response
 from data_fetch.market_sources import official_company_legal_name as master
 import official_response_evidence as archive
 rows=[{'公司代號':'2412','公司名稱':c.LEGAL,'公司簡稱':c.SHORT,'出表日期':'1151030','營利事業統一編號':c.UBN,'網址':'https://www.cht.com.tw'}]
 raw=json.dumps(rows,ensure_ascii=False).encode();response=httpx.Response(200,content=raw,request=httpx.Request('GET',master.URLS['.TW']))
 monkeypatch.setattr(master,'sync_get',lambda *a,**kw:response)
 calls=[];original=archive.archive_response
 def save(*a,**kw):
  calls.append((a,kw))
  if archive_fails:raise OSError('isolated archive unavailable')
  return original(*a,**kw)
 monkeypatch.setattr(archive,'archive_response',save)
 assert master._fetch_roster(master.URLS['.TW'],'.TW')==master.parse_roster(raw,'.TW')
 assert len(calls)==1
