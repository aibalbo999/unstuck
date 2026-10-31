"""Public corporate/global combination, using saved original fixtures only."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import time
import pytest

from test_sym_issuer_news import harness, valid_data, NOW
from test_issuer_news import Http as LegacyHttp


def corporate_http(*, cached=False, body_cached=False):
 class OriginalHttp(LegacyHttp):
  def get(self,url):
   if cached or body_cached and '/busnessnews-page' in url:
    self.components.append({'url':url,'http_request_sent':False,'cache_hit':True,'fetched_at_epoch':NOW-300})
    return self.contents[url]
   raw=super().get(url);self.components[-1]['fetched_at_epoch']=NOW-300;return raw
 return OriginalHttp('2206.TW')


def test_public_bundle_keeps_corporate_and_adds_distinct_global_originals(harness):
 try:
  module=importlib.import_module('data_fetch.market_sources.sanyang_news_bundle')
 except ModuleNotFoundError as exc:
  assert exc.name=='data_fetch.market_sources.sanyang_news_bundle'
  from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news
  records,audit=fetch_recent_issuer_news('2206.TW',now=datetime.fromtimestamp(NOW,timezone.utc),http=corporate_http())
 else:
  records,audit=module.fetch_recent_sanyang_news(now=datetime.fromtimestamp(NOW,timezone.utc),corporate_http=corporate_http())
  assert audit['status']=='success' and audit['http_request_count']==10
  assert audit['fetched_at_epoch']==NOW-300
  assert audit['window_complete'] is False and audit['coverage_status']=='partial'
  assert module.guard_bundle(records,audit,valid_data())
 assert len(records)==3,'Existing corporate-only path loses the two qualified global articles'


def bundle(**kwargs):
 from data_fetch.market_sources.sanyang_news_bundle import fetch_recent_sanyang_news
 return fetch_recent_sanyang_news(now=datetime.fromtimestamp(NOW,timezone.utc),**kwargs)


def empty_global(monkeypatch, *, sent=False):
 from data_fetch.market_sources import sym_issuer_news as source
 def fetch(**kwargs):
  component={'url':source.CHAIN['index'],'http_request_sent':sent,'cache_hit':not sent,'fetched_at_epoch':NOW-100}
  return [],{'status':'unavailable','coverage_status':'partial','window_complete':False,'stale':False,
   'http_request_sent':sent,'http_request_count':int(sent),'cache_hit':not sent,'record_count':0,'usable_count':0,
   'fetched_at_epoch':NOW-100,'component_receipts':[component]}
 monkeypatch.setattr(source,'fetch_recent_news',fetch)


@pytest.mark.parametrize('sent,status',[(False,'skipped_fresh_cache'),(True,'degraded_enrichment')])
def test_warm_body_never_becomes_fresh_success_from_empty_new_branch(harness,monkeypatch,sent,status):
 from data_fetch.market_sources import sanyang_news_bundle as module
 empty_global(monkeypatch,sent=sent)
 records,audit=bundle(corporate_http=corporate_http(cached=True))
 assert len(records)==1 and audit['status']==status
 assert audit['cache_hit'] is True and audit['http_request_count']==int(sent)
 assert audit['fetched_at_epoch']==NOW-300 and module.guard_bundle(records,audit,valid_data())


def test_new_corporate_metadata_with_warm_body_is_not_a_new_body(harness,monkeypatch):
 from data_fetch.market_sources import sanyang_news_bundle as module
 empty_global(monkeypatch)
 records,audit=bundle(corporate_http=corporate_http(body_cached=True))
 assert len(records)==1 and audit['status']=='degraded_enrichment' and audit['http_request_count']==2
 assert audit['cache_hit'] is True and module.guard_bundle(records,audit,valid_data())


def partial_global(monkeypatch):
 from data_fetch.market_sources.sym_issuer_news_transport import SymNewsHttp,ARTICLES
 from search_provider_runtime import SourceResponseError
 original=SymNewsHttp.download_original
 def download(self,url,diagnostic):
  if url==ARTICLES[1]:
   self.http_request_count+=1;diagnostic.update(http_request_sent=True,error_kind='timeout')
   raise SourceResponseError('timeout')
  return original(self,url,diagnostic)
 monkeypatch.setattr(SymNewsHttp,'download_original',download)


def test_later_global_timeout_keeps_both_completed_articles_and_child_diagnostics(harness,monkeypatch):
 from data_fetch.market_sources import sanyang_news_bundle as module
 partial_global(monkeypatch)
 records,audit=bundle(corporate_http=corporate_http())
 assert len(records)==2 and audit['status']=='degraded_enrichment'
 assert audit['component_audits']['global']['status']=='degraded_enrichment'
 assert audit['component_audits']['global']['error_kind']=='timeout' and audit['http_request_count']==10
 assert module.guard_bundle(records,audit,valid_data())


def test_corporate_timeout_does_not_discard_valid_global_articles(harness):
 from data_fetch.market_sources import sanyang_news_bundle as module
 from search_provider_runtime import SourceResponseError
 http=corporate_http()
 def failure(url):
  http.http_request_count+=1;http.components.append({'url':url,'http_request_sent':True,'error_kind':'timeout'})
  raise SourceResponseError('timeout')
 http.get=failure
 records,audit=bundle(corporate_http=http)
 assert len(records)==2 and audit['status']=='degraded_enrichment' and audit['http_request_count']==8
 assert audit['component_audits']['corporate']['error_kind']=='timeout'
 assert module.guard_bundle(records,audit,valid_data())


def test_parent_deadline_prevents_starting_global_and_keeps_valid_corporate(harness,monkeypatch):
 from data_fetch.market_sources import sanyang_news_bundle as module,issuer_news,sym_issuer_news
 clock=[500.];monkeypatch.setattr(time,'monotonic',lambda:clock[0])
 original=issuer_news.fetch_recent_issuer_news
 def corporate(*args,**kwargs):
  result=original(*args,**kwargs);clock[0]+=26;return result
 monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',corporate)
 monkeypatch.setattr(sym_issuer_news,'fetch_recent_news',lambda **kwargs:pytest.fail('started after parent deadline'))
 records,audit=bundle(corporate_http=corporate_http())
 assert len(records)==1 and audit['status']=='degraded_enrichment'
 assert audit['bundle_error_kind']=='timeout' and audit['http_request_count']==3
 assert module.guard_bundle(records,audit,valid_data())


def test_global_receives_only_remaining_capacity_and_common_deadline(harness,monkeypatch):
 from data_fetch.market_sources import sym_issuer_news
 original=sym_issuer_news.fetch_recent_news;observed=[]
 def fetch(**kwargs):
  observed.append(kwargs);return original(**kwargs)
 monkeypatch.setattr(sym_issuer_news,'fetch_recent_news',fetch)
 http=corporate_http();http.deadline=time.monotonic()+100
 records,audit=bundle(corporate_http=http)
 assert len(records)==3 and observed[0]['limit']==4
 assert 0 < observed[0]['deadline']-http.deadline <= 5


@pytest.mark.parametrize('change',['status','count','http','epoch','future','body','child_status','component_receipts','component_records','unknown','identity','cache_claim'])
def test_guard_rejects_false_bundle_projections(harness,monkeypatch,change):
 from data_fetch.market_sources import sanyang_news_bundle as module
 partial_global(monkeypatch)
 records,audit=bundle(corporate_http=corporate_http());data=valid_data()
 assert module.guard_bundle(records,audit,data)
 if change=='status':audit['status']='success'
 elif change=='count':audit['record_count']+=1
 elif change=='http':audit['http_request_count']-=1
 elif change=='epoch':audit['fetched_at_epoch']=NOW
 elif change=='future':audit['component_audits']['corporate']['component_receipts'][0]['fetched_at_epoch']=NOW+1
 elif change=='body':records[0]['text']+=' fabricated'
 elif change=='child_status':
  audit['component_audits']['global']['status']='success';audit['component_audits']['global'].pop('error_kind',None);audit['component_audits']['global'].pop('error_message',None)
  audit['status']='success';audit['bundle_error_kind']=''
 elif change=='component_receipts':audit['component_receipts'].pop()
 elif change=='component_records':audit['component_records']['corporate']=[]
 elif change=='unknown':audit['component_audits']['global']['status']='unknown'
 elif change=='identity':data['company_identity']['stock_id']='2207'
 else:audit.update(status='skipped_fresh_cache',http_request_sent=False,http_request_count=0,cache_hit=True,event_kind='cache_hit')
 assert not module.guard_bundle(records,audit,data)


def test_guard_rechecks_oldest_original_after_last_record_replay(harness,monkeypatch):
 from data_fetch.market_sources import sanyang_news_bundle as module
 records,audit=bundle(corporate_http=corporate_http())
 real=module._verified;clock=[NOW];monkeypatch.setattr(time,'time',lambda:clock[0])
 def verified(record,name,data,today):
  result=real(record,name,data,today)
  if record['source_document_url']==records[-1]['source_document_url']:clock[0]=NOW+1501
  return result
 monkeypatch.setattr(module,'_verified',verified)
 assert not module.guard_bundle(records,audit,valid_data())


def test_guard_rejects_unknown_component_url_even_with_consistent_totals(harness,monkeypatch):
 from data_fetch.market_sources import sanyang_news_bundle as module
 empty_global(monkeypatch,sent=True)
 records,audit=bundle(corporate_http=corporate_http(cached=True))
 audit['component_audits']['global']['component_receipts'][0]['url']='https://unrelated.invalid/index'
 audit['component_receipts'][-1]['url']='https://unrelated.invalid/index'
 assert not module.guard_bundle(records,audit,valid_data())


def test_five_corporate_slots_skip_global_without_mutating_records(harness,monkeypatch):
 from bs4 import BeautifulSoup
 from data_fetch.market_sources import issuer_news,sym_issuer_news,sanyang_news_bundle as module
 http=corporate_http();soup=BeautifulSoup(http.contents[issuer_news.SANYANG_INDEX],'html.parser')
 anchor=soup.select_one('h4.blog_title a[href]');card=anchor.parent.parent;parent=card.parent
 raw=http.contents[anchor['href']]
 for number in range(694,698):
  clone=deepcopy(card);clone.select_one('h4.blog_title a')['href']='https://www.sanyang.com.tw/busnessnews-page'+str(number)
  parent.append(clone);http.contents[clone.select_one('h4.blog_title a')['href']]=raw
 http.contents[issuer_news.SANYANG_INDEX]=str(soup).encode()
 expected,_=issuer_news.fetch_recent_issuer_news('2206.TW',now=datetime.fromtimestamp(NOW,timezone.utc),http=http)
 assert len(expected)==5
 http.components=[];http.http_request_count=0;http.calls=[]
 monkeypatch.setattr(sym_issuer_news,'fetch_recent_news',lambda **kw:pytest.fail('capacity already full'))
 result,audit=bundle(corporate_http=http)
 assert result==expected and len(result)==5 and audit['http_request_count']==7
 assert audit['component_audits']['global']['not_attempted_reason']=='incoming_limit'
 assert audit['status']=='success' and module.guard_bundle(result,audit,valid_data())
 result[0]['text']='caller change'
 assert audit['component_records']['corporate']==expected


def test_empty_windows_are_unavailable_and_never_cache_success(harness,monkeypatch):
 from data_fetch.market_sources import issuer_news,sanyang_news_bundle as module
 empty_global(monkeypatch)
 http=corporate_http();raw=http.contents[issuer_news.SANYANG_INDEX]
 # Older published entries remain excluded; no empty list is promoted to success.
 changed=raw.replace(b'Oct 02 2026',b'Sep 02 2026');assert changed!=raw
 http.contents[issuer_news.SANYANG_INDEX]=changed
 records,audit=bundle(corporate_http=http)
 assert records==[] and audit['status']=='unavailable' and audit['http_request_count']==2
 assert not module.guard_bundle(records,audit,valid_data())


@pytest.mark.parametrize('supplied',[False,True])
def test_corporate_preserves_its_twenty_second_native_budget(harness,monkeypatch,supplied):
 from data_fetch.market_sources import issuer_news,sym_issuer_news
 clock=[500.];monkeypatch.setattr(time,'monotonic',lambda:clock[0])
 http=corporate_http();http.deadline=600.
 original=issuer_news.fetch_recent_issuer_news;seen=[]
 def corporate(*args,**kwargs):
  seen.append(kwargs['http'].deadline)
  return original(*args,**kwargs)
 monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',corporate)
 monkeypatch.setattr(issuer_news,'IssuerNewsHttp',lambda deadline:http)
 original_global=sym_issuer_news.fetch_recent_news;global_deadlines=[]
 def global_fetch(**kwargs):
  global_deadlines.append(kwargs['deadline']);return original_global(**kwargs)
 monkeypatch.setattr(sym_issuer_news,'fetch_recent_news',global_fetch)
 result,audit=bundle(**({'corporate_http':http} if supplied else {}))
 assert len(result)==3 and audit['status']=='success'
 assert seen==[520.] and global_deadlines==[525.]
