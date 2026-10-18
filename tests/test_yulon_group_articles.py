"""Actual group originals must stay issuer-specific, dated and unendorsed."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import gzip,time
import pytest
from data_fetch.issuer_news_provider import IssuerNewsProvider
from data_fetch.market_sources.registered_issuer_articles import CSV_MASTER_URL, ArticlesHttp
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
from source_content_selection import select_company_records

F=Path(__file__).parent/'fixtures/source_acquisition'
NOW=datetime(2026,10,16,3,30,tzinfo=timezone.utc).timestamp()
INDEX='https://www.yulon-group.com/news-list/35e09dd589fa639ffe18507f70fecbd0'
DIRECTORY='https://www.yulon-group.com/smart-transportation'
ARTICLES={'https://www.yulon-group.com/news-list/view/4bc4C96FeF33':'yulon-yuanli',
          'https://www.yulon-group.com/news-list/view/a1E55710b3e2':'yulon-woodcarving'}

def setup(monkeypatch, *, warm=False):
 source={CSV_MASTER_URL:gzip.decompress((F/'listed_company_complete_20261012.csv.gz').read_bytes())}
 for url,name in {INDEX:'yulon-community-index',DIRECTORY:'yulon-group-identity',**ARTICLES}.items():
  source[url]=gzip.decompress((F/(name+'_20261016.html.gz')).read_bytes())
 calls=[]
 def get(http,url):
  calls.append(url);raw=source[url]
  http.components.append({'url':url,'fetched_at_epoch':NOW-10,'cache_hit':warm,'http_request_sent':not warm,'stale':False,'http_status':200})
  http.http_request_count+=int(not warm)
  return raw
 class FrozenDateTime(datetime):
  @classmethod
  def now(cls,tz=None):return cls.fromtimestamp(NOW,tz)
 from data_fetch.market_sources import issuer_news
 monkeypatch.setattr(issuer_news,'datetime',FrozenDateTime)
 monkeypatch.setattr(time,'time',lambda:NOW)
 monkeypatch.setattr(ArticlesHttp,'get',get)
 return SimpleNamespace(source=source,calls=calls,data={'ticker':'2201.TW','instrument_type':'EQUITY','company_name':'裕隆 / Yulon Motor Company Ltd.','ttm_revenue':3,'fcf_history':[1,2]})

def test_normal_provider_recovers_two_actual_group_articles(monkeypatch):
 h=setup(monkeypatch);p=IssuerNewsProvider();req=SimpleNamespace(ticker='2201.TW')
 assert p.supports(req)
 result=p.fetch(req,{'data':h.data})
 assert result.status=='success',result.audit
 selected,_=select_company_records(result.value,h.data,cutoff=NOW)
 assert len(selected)==2
 assert {r['date']for r in selected}=={'2026-10-02','2026-10-12'}
 assert {r['link']for r in selected}==set(ARTICLES)
 assert len(h.calls)==5 and h.calls[:3]==[CSV_MASTER_URL,DIRECTORY,INDEX]
 assert all(r['publisher']=='Yulon Group' and r['source_role']=='related_group_statement' for r in selected)
 assert all(r['source_type']=='group_published_issuer_news' and r['publication_date_basis']=='group_page_displayed_day' for r in selected)
 assert all(len(r['text'])>500 and r['financial_assurance']=='not_verified_as_audited'for r in selected)
 assert all(r['publication_date_original']['original_issuer_publication_date_verified'] is False for r in selected)

@pytest.mark.parametrize('kind',['directory_missing','directory_link','directory_name','wrong_title','wrong_date','wrong_body','unknown_block'])
def test_publisher_subject_and_article_conflicts_do_not_become_news(monkeypatch,kind):
 h=setup(monkeypatch)
 if kind=='directory_missing':h.source[DIRECTORY]=h.source[DIRECTORY].replace(b'wisdom-link',b'not-member')
 elif kind=='directory_link':h.source[DIRECTORY]=h.source[DIRECTORY].replace(b'https://www.yulon-motor.com.tw/',b'https://wrong.example/')
 elif kind=='directory_name':h.source[DIRECTORY]=h.source[DIRECTORY].replace('裕隆汽車'.encode(),'裕融企業'.encode())
 else:
  url=next(u for u,n in ARTICLES.items()if n=='yulon-woodcarving')
  if kind=='wrong_title':h.source[url]=h.source[url].replace('裕隆深耕三義'.encode(),'裕隆另一活動'.encode())
  elif kind=='wrong_date':h.source[url]=h.source[url].replace(b'2026 Oct. 12',b'2026 Oct. 13')
  elif kind=='wrong_body':h.source[url]=h.source[url].replace('裕隆汽車'.encode(),'另一家公司'.encode())
  else:h.source[url]=h.source[url].replace(b'<div class="editor-block">',b'<div class="editor-block"><iframe src="https://example.com/"></iframe>')
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2201.TW'),{'data':h.data})
 assert r.status=='error' and not r.value
 assert not any(u in ARTICLES for u in h.calls) if kind.startswith('directory') else len([u for u in h.calls if u in ARTICLES])==1

@pytest.mark.parametrize('kind',['receipt_removed','directory_removed','group_owner_changed','publisher','role','date','original_date_claim','archive_hash','financial_claim'])
def test_saved_news_cannot_bypass_original_replay(monkeypatch,kind):
 h=setup(monkeypatch);rows=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2201.TW'),{'data':h.data}).value
 r=deepcopy(rows[0])
 if kind=='receipt_removed':r.pop('issuer_news_receipt')
 elif kind=='directory_removed':r['issuer_news_receipt']['source_record_archive'].pop('directory')
 elif kind=='group_owner_changed':r['issuer_news_receipt']['website_host']='www.yulon-group.com'
 elif kind=='original_date_claim':r['publication_date_original']['original_issuer_publication_date_verified']=True
 elif kind=='archive_hash':r['issuer_news_receipt']['source_record_archive']['article']['raw_response_sha256']='0'*64
 elif kind=='financial_claim':r['financial_assurance']='audited'
 else:r[{'role':'source_role'}.get(kind,kind)]='changed'
 selected,_=select_company_records([r],h.data,cutoff=NOW)
 assert not selected

@pytest.mark.parametrize('ticker,data',[('2201.TW',{'ticker':'2227.TW','instrument_type':'EQUITY'}),('2227.TW',{'ticker':'2201.TW','instrument_type':'EQUITY'}),('2201.TW',{'ticker':'2201.TW','instrument_type':'ETF'}),('2201.TW',{'ticker':'2201.TW','instrument_type':'EQUITY','company_name':'裕融企業'})])
def test_conflicting_request_context_stops_before_http(monkeypatch,ticker,data):
 h=setup(monkeypatch);r=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':data})
 assert r.status=='error' and not r.value and not h.calls

def test_warm_replay_has_zero_new_http_and_original_epoch(monkeypatch):
 h=setup(monkeypatch,warm=True);r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2201.TW'),{'data':h.data})
 assert r.status=='skipped_fresh_cache' and len(r.value)==2 and r.audit['http_request_count']==0
 assert r.audit['fetched_at_epoch']==NOW-10

def test_expired_window_has_no_article_http(monkeypatch):
 from data_fetch.market_sources import registered_issuer_articles as m
 h=setup(monkeypatch);h.source[INDEX]=h.source[INDEX].replace(b'2026 Oct.',b'2026 Aug.')
 r,audit=m.fetch_recent_news('2201.TW',now=datetime.fromtimestamp(NOW,timezone.utc))
 assert not r and not any(u in ARTICLES for u in h.calls)

def test_final_replay_timeout_never_returns_success(monkeypatch):
 from data_fetch.market_sources import registered_issuer_articles as m
 h=setup(monkeypatch,warm=True);clock=[0.];real=m.verified_record
 monkeypatch.setattr(m.time,'monotonic',lambda:clock[0])
 def late(*a,**k):
  result=real(*a,**k);clock[0]=21.;return result
 monkeypatch.setattr(m,'verified_record',late)
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2201.TW'),{'data':h.data})
 assert r.status=='error'and not r.value and r.audit['error_kind']=='timeout'

def test_pure_transport_contract_rejects_other_group_urls():
 from data_fetch.market_sources.registered_issuer_articles import url_contract
 from search_provider_runtime import SourceResponseError
 for url in [DIRECTORY,INDEX,*ARTICLES]:assert url_contract(url)[0]<=500000
 for url in [INDEX+'?next=2','http://www.yulon-group.com/smart-transportation','https://evil.example/news-list/view/4bc4C96FeF33',DIRECTORY+'@evil.example',INDEX+'#fragment']:
  with pytest.raises(SourceResponseError):url_contract(url)

def test_prompt_projection_drops_original_receipts_and_keeps_group_limits(monkeypatch):
 from prompt_evidence import prompt_evidence_copy
 h=setup(monkeypatch);r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2201.TW'),{'data':h.data})
 visible=prompt_evidence_copy({'recent_catalysts':r.value})
 import json
 text=json.dumps(visible,ensure_ascii=False)
 assert 'source_record_archive'not in text and 'archive_locator'not in text
 assert 'related_group_statement'in text and '不是獨立報導'in text

def test_source_only_service_preserves_existing_report_and_other_sources(monkeypatch,tmp_path):
 # Reuse the existing full refresh preservation assertions with this actual
 # publisher's native fixture and request, rather than a parser-only check.
 import test_registered_issuer_articles as existing
 h=setup(monkeypatch)
 h.article=next(iter(ARTICLES))
 h.index=INDEX
 monkeypatch.setattr(existing,'setup',lambda *a,**k:h)
 existing.test_actual_source_only_service_saves_originals_without_changing_analysis(monkeypatch,'2201.TW',tmp_path)

def test_no_store_group_pages_always_use_native_transport(monkeypatch):
 import json
 from data_fetch.market_sources import issuer_news_transport as wire
 from cache_store import get_cache_json
 raw=gzip.decompress((F/'yulon-community-index_20261016.html.gz').read_bytes())
 calls=[]
 def collect(argv,deadline,**kwargs):
  calls.append(argv[-1])
  metadata={'http_code':200,'url_effective':INDEX,'num_redirects':0}
  return {'body':raw,'headers':b'HTTP/2 200\r\nContent-Type: text/html\r\nCache-Control: no-store, no-cache, must-revalidate\r\n\r\n','metadata':json.dumps(metadata).encode(),'process_started':True},0,None
 monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
 monkeypatch.setattr(wire,'collect_capped_process',collect)
 for _ in range(2):
  http=ArticlesHttp(time.monotonic()+20)
  assert http.get(INDEX)==raw
  assert http.http_request_count==1 and http.components[-1]['cache_hit']is False
 assert calls==[INDEX,INDEX]
 for prefix in ('issuer-news-raw:v1:','yulon-news-no-store:v1:'):
  assert get_cache_json('shared_provider:v1:'+sha256((prefix+INDEX).encode()).hexdigest())is None

def test_master_expiry_during_final_article_validation_discards_result(monkeypatch):
 from data_fetch.market_sources import registered_issuer_articles as m
 h=setup(monkeypatch);clock=[NOW];real_get=ArticlesHttp.get;real_verify=m.verified_record
 monkeypatch.setattr(time,'time',lambda:clock[0])
 def get(http,url):
  raw=real_get(http,url)
  if url==CSV_MASTER_URL:http.components[-1]['fetched_at_epoch']=NOW-1799
  return raw
 def verify(*a,**k):
  result=real_verify(*a,**k);clock[0]+=1
  return result
 monkeypatch.setattr(ArticlesHttp,'get',get);monkeypatch.setattr(m,'verified_record',verify)
 result=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2201.TW'),{'data':h.data})
 assert result.status=='error'and not result.value and result.audit['error_kind']=='original_expired'

def test_normal_source_service_rejects_conflicting_original_company_context(monkeypatch):
 import asyncio
 from data_fetch import FetchRequest,ProviderRegistry,StockDataService
 h=setup(monkeypatch);h.data['company_name']='裕融企業'
 service=StockDataService(registry=ProviderRegistry([IssuerNewsProvider()]))
 r=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('2201.TW'),'issuer_news',context={'data':h.data}))
 assert not r.data.get('recent_catalysts') and not h.calls
