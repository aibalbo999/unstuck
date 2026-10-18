"""Actual complete E.SUN originals, parent attribution and indexed quote exclusion."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
import gzip,json
import pytest
from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news,verified_issuer_news
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from source_content_selection import select_company_records
F=Path(__file__).parent/'fixtures/source_acquisition/esun_news_full_20261012';M=json.loads((F/'manifest.json').read_text())
MASTER=M['parts']['master']['url'];INDEX=M['parts']['index']['url'];ARTICLES=[M['parts']['article'+str(i)]['url'] for i in range(3)];NOW=datetime(2026,10,11,16,30,tzinfo=timezone.utc)
DATA={'ticker':'2884.TW','company_name':'玉山金','instrument_type':'EQUITY','company_identity':{'ticker':'2884.TW','stock_id':'2884','official_name':'玉山金','legal_name':'玉山金融控股股份有限公司','official_ubn':'70796305','allowed_aliases':['玉山金','玉山金控'],'forbidden_aliases':[]}}
class Http:
 def __init__(self,*,cached=False):
  self.contents={};self.epochs={};self.calls=[];self.components=[];self.http_request_count=0;self.cached=cached
  for p in M['parts'].values():
   raw=gzip.open(F/p['filename'],'rb').read();assert sha256(raw).hexdigest()==p['sha256'] and len(raw)==p['bytes'];self.contents[p['url']]=raw;self.epochs[p['url']]=p['retrieved_at']
 def get(self,url):
  self.calls.append(url);self.http_request_count+=int(not self.cached);self.components.append({'url':url,'http_request_sent':not self.cached,'http_status':200,'cache_hit':self.cached,'fetched_at_epoch':self.epochs[url]});return self.contents[url]
def get(http=None):return fetch_recent_issuer_news('2884.TW',now=NOW,http=http or Http())
def test_new_exact_market_route_is_available():
 r=ProviderRegistry();assert 'Verified issuer news' in r.provider_names(FetchRequest.from_ticker('2884.TW'),'recent_catalysts')
 assert 'Verified issuer news' not in r.provider_names(FetchRequest.from_ticker('2884.TWO'),'recent_catalysts')
def test_three_native_complete_parent_news_are_selected_as_one_firstparty_publisher():
 h=Http();records,audit=get(h);assert len(records)==3 and audit['status']=='success',audit
 selected,_=select_company_records(records,DATA,cutoff=NOW);assert len(selected)==3 and {x['publisher'] for x in selected}=={'E.SUN FHC'}
 assert {r['source_document_url'] for r in records}==set(ARTICLES)
 assert all(r['text'].startswith('玉山金控') and r['source_role']=='issuer_statement' and r['event_assessment']=='not_assessed' and not r['content_truncated'] for r in records)
 assert audit['window_complete'] is False and audit['http_request_count']==5
 assert h.calls==[MASTER,INDEX,ARTICLES[0],ARTICLES[2],ARTICLES[1]]
 assert not any('返回列表' in r['text'] or '更多新聞' in r['text'] for r in records)
def quote_record(**changes):
 return {'title':'玉山金融控股 | 2884.TW 股價走勢與即時報價 - BigGo 財經','summary':'玉山金融控股報價','date':'2026-10-07T03:49:25+00:00','link':'https://news.google.com/rss/articles/captured','source':'BigGo 財經',**changes}
def test_observed_google_indexed_biggo_quote_is_not_current_news():
 records,audit=select_company_records([quote_record()],DATA,cutoff=NOW);assert records==[]
 assert audit['rejected_reason_counts']=={'indexed_non_article_unverified':1}
def test_legacy_freshness_retains_index_original_in_unverified_bucket():
 from news_freshness_policy import apply_news_only_freshness
 raw=quote_record();d={**deepcopy(DATA),'recent_catalysts':[deepcopy(raw)]};apply_news_only_freshness(d,cutoff=NOW)
 assert not d['recent_catalysts'] and len(d['unverified_catalysts'])==1 and d['unverified_catalysts'][0]['title']==raw['title']

@pytest.mark.parametrize('changes',[{'title':'玉山金控提升即時報價服務，營運成長 - BigGo 財經'},{'source':'經濟日報'},{'link':'https://publisher.test/original'}])
def test_quote_exclusion_does_not_generalize_to_editorial_or_direct_original(changes):
 from source_content_selection import _indexed_non_article_unverified
 r=quote_record(**changes);assert not _indexed_non_article_unverified(r,r['link'])

@pytest.mark.parametrize('field,value',[('公司名稱','別家公司股份有限公司'),('公司簡稱','玉山銀行'),('營利事業統一編號','99999999'),('英文簡稱','E.SUN BANK'),('網址','https://www.esunbank.com'),('出表日期','1150801'),('出表日期','1151013')])
def test_master_conflicts_stop_before_index(field,value):
 h=Http();rows=json.loads(h.contents[MASTER]);next(r for r in rows if r['公司代號']=='2884')[field]=value;h.contents[MASTER]=json.dumps(rows,ensure_ascii=False).encode()
 records,audit=get(h);assert not records and audit['status']=='error' and h.calls==[MASTER]

@pytest.mark.parametrize('change',['role','date','canonical','off_host','wrong_language','owner','duplicate_conflict'])
def test_index_roles_exact_published_routes_owner_and_dates_are_required(change):
 from bs4 import BeautifulSoup
 h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=next(n for n in s.select('div.newsList') if n.select_one('h3.title').get_text(strip=True).startswith('玉山金控攜手三商壽'))
 if change=='role':s.select_one('h1').string='投資人關係'
 elif change=='date':card.select_one('p.catalog span').string='2026/99/05'
 elif change=='canonical':s.select_one('link[rel=canonical]')['href']='https://other.example.test/'
 elif change=='off_host':card.select_one('.contentBox a')['href']='https://www.esunfhc.com.evil.test/story'
 elif change=='wrong_language':s.html['lang']='en'
 elif change=='owner':
  n=next(n for n in s.find_all(string=True) if n.strip()=='©E.SUN FHC');n.replace_with('©E.SUN BANK')
 else:
  n=deepcopy(card);n.select_one('h3.title').string='玉山金控不同新聞';card.parent.append(n)
 h.contents[INDEX]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error' and h.calls==[MASTER,INDEX]

@pytest.mark.parametrize('url',[INDEX+'?year=2026',ARTICLES[0]+'&token=x',ARTICLES[0]+'#body',ARTICLES[0].replace('https:','http:'),ARTICLES[0].replace('www.esunfhc.com','www.esunfhc.com.evil.test'),ARTICLES[0].replace('p=148DB1EBDC2B47629ED09DC9820A2155','p=00000000000000000000000000000000'),ARTICLES[0].replace('zh-tw','en'),'https://https://www.esunfhc.com/zh-tw/news-center/news-center/news'])
def test_transport_does_not_follow_or_repair_nonpublished_routes(url):
 from data_fetch.market_sources.esun_issuer_news import url_contract
 from search_provider_runtime import SourceResponseError
 with pytest.raises(SourceResponseError):url_contract(url)

@pytest.mark.parametrize('change',['title','date','repaired_canonical','different_og','back_role','back_title','script','child_only','body_drift','section','locale'])
def test_article_requires_native_published_title_date_full_parent_body_and_section(change):
 from bs4 import BeautifulSoup
 h=Http();s=BeautifulSoup(h.contents[ARTICLES[0]],'html.parser');root=s.select_one('section.l-news');body=root.select_one('.l-news__content')
 if change=='title':root.select_one('h1').string='玉山金控其他新聞'
 elif change=='date':root.select_one('.l-news__headRight p').string='2026/10/06'
 elif change=='repaired_canonical':s.select_one('link[rel=canonical]')['href']=ARTICLES[0]
 elif change=='different_og':s.select_one('meta[property="og:url"]')['content']='https://https://other.example.test/story'
 elif change=='back_role':root.select_one('a[news-gobak]')['href']='/zh-tw/about'
 elif change=='back_title':root.select_one('a[news-gobak]').string='返回產品'
 elif change=='script':body.append(BeautifulSoup('<script>invent facts</script>','html.parser'))
 elif change=='child_only':body.string='玉山銀行其他新聞'*50
 elif change=='body_drift':body.append('額外無來源聲明')
 elif change=='section':root['data-comp-name']='_advertisement'
 else:s.html['lang']='en'
 h.contents[ARTICLES[0]]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error' and h.calls==[MASTER,INDEX,ARTICLES[0]]

@pytest.mark.parametrize('change',['title','body','date','publisher','role','policy','truncated','receipt_hash','receipt_size','receipt_time','identity_ubn','forbidden_parent'])
def test_saved_article_replays_all_originals_and_explicit_parent_identity(change):
 records,_=get();r=deepcopy(records[0]);d=deepcopy(DATA)
 if change=='title':r['title']='玉山金控其他標題'
 elif change=='body':r['text']='玉山金控其他正文'*40
 elif change=='date':r['date']='2026-10-06'
 elif change=='publisher':r['publisher']='E.SUN BANK'
 elif change=='role':r['source_role']='independent_editorial'
 elif change=='policy':r['issuer_news_receipt']['policy']='generic-news'
 elif change=='truncated':r['content_truncated']=True
 elif change=='identity_ubn':d['company_identity']['official_ubn']='99999999'
 elif change=='forbidden_parent':d['company_identity']['forbidden_aliases']=['玉山金控']
 else:
  p=r['issuer_news_receipt']['source_record_archive']['article']
  if change=='receipt_hash':p['raw_response_sha256']='0'*64
  elif change=='receipt_size':p['raw_response_bytes']+=1
  else:p['retrieved_at']=float('nan')
 assert verified_issuer_news(r,d,today=NOW.date()) is None

def test_complete_cached_originals_keep_original_times_without_http():
 records,audit=get(Http(cached=True));assert len(records)==3 and audit['status']=='skipped_fresh_cache' and audit['http_request_count']==0
 assert audit['fetched_at_epoch']==min(p['retrieved_at'] for p in M['parts'].values())

def test_shared_master_status_is_not_invented_and_digest_epoch_are_replayed():
 class Shared(Http):
  def get(self,url):
   raw=super().get(url)
   if url==MASTER:
    self.http_request_count-=1;self.components[-1].update(http_request_sent=False,cache_hit=True,evidence_kind='cached_complete_source_payload_verified_by_digest',http_status=None,http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=MASTER,source_payload_sha256=sha256(raw).hexdigest(),source_payload_bytes=len(raw),stale=False)
   return raw
 records,audit=get(Shared());assert len(records)==3 and audit['http_request_count']==4
 p=records[0]['issuer_news_receipt']['source_record_archive']['master'];assert p['http_status'] is None and p['http_status_observed'] is False and p['retrieved_at']==M['parts']['master']['retrieved_at']
 r=deepcopy(records[0]);r['issuer_news_receipt']['source_record_archive']['master']['http_status']=200;assert verified_issuer_news(r,DATA,today=NOW.date()) is None

def test_body_only_child_and_missing_original_title_do_not_initiate_article_http():
 h=Http();records,audit=get(h);assert len(records)==3 and audit['excluded_reason_counts']=={'missing_original_title':1,'not_explicit_parent_body_lead':6}
 assert len(h.calls)==5

def test_whole_deadline_covers_full_original_parsing_and_replay(monkeypatch):
 import time
 from types import SimpleNamespace
 from data_fetch.market_sources import esun_issuer_news as source
 clock=[0.];original=source.parse_article;monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=time.time))
 def late(*a):r=original(*a);clock[0]=21.;return r
 monkeypatch.setattr(source,'parse_article',late);records,audit=get();assert not records and audit['status']=='error' and audit['error_kind']=='timeout'

@pytest.mark.parametrize('change',['future','historical'])
def test_outside_window_card_does_not_request_its_article(change):
 from bs4 import BeautifulSoup
 h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=next(n for n in s.select('div.newsList') if n.select_one('h3.title').get_text(strip=True).startswith('玉山金控攜手三商壽'))
 card.select_one('p.catalog span').string='2026/10/13' if change=='future' else '2026/09/08';h.contents[INDEX]=str(s).encode()
 records,audit=get(h);assert len(records)==2 and ARTICLES[0] not in h.calls and audit['excluded_reason_counts'][change]>0

def test_three_issuer_originals_alone_cannot_pass_eight_three_gate():
 from external_search_quality import search_quality_satisfied
 from external_search_types import SearchResult
 records,_=get();rs=[SearchResult(r['title'],r['text'],r['link'],r['publisher'],r['date']) for r in records]
 assert not search_quality_satisfied(rs,max_results=8,query='玉山金',require_recent=True,cutoff=NOW)

def test_source_only_preserves_all_nonnews_fields_audits_and_original_context(monkeypatch):
 import asyncio
 from data_fetch.service import StockDataService
 from data_fetch.market_sources import issuer_news
 from report_source_refresh import fetch_report_source_data
 real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda t:real(t,now=NOW,http=Http()))
 old=deepcopy(DATA);old.update(current_price=29.,financial_currency='TWD',revenue_ttm_raw=1234000000,years=['2021','2022','2023','2024','2025'],recent_catalysts=[],social_sentiment=[{'text':'old social'}])
 audits=[{'source':'market_data','provider':'saved quote','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1},{'source':'financial_statements','provider':'saved finance','status':'success','fetched_at_epoch':NOW.timestamp()-700,'record_count':5}]
 snap={'ticker':'2884.TW','data':old,'source_audit':audits};before=deepcopy(snap);merged=asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
 assert len(merged['recent_catalysts'])==3 and snap==before and merged['source_audit'][:2]==audits
 for k in ('company_identity','current_price','revenue_ttm_raw','financial_currency','years','social_sentiment'):assert merged[k]==old[k]

@pytest.mark.parametrize('changed',[{'instrument_type':'ETF'},{'instrument_type':False},{'instrument_type':'unknown'},{'quote_type':'ETF'},{'quote_type':'EQUITY','quoteType':'ETF'},{'quote_type':False}])
def test_conflicting_source_only_instrument_is_rejected_before_provider(monkeypatch,changed):
 import asyncio
 from fastapi import HTTPException
 from data_fetch.service import StockDataService
 from data_fetch.market_sources import esun_issuer_news as source
 from report_source_refresh import fetch_report_source_data
 def no_http(*a):raise AssertionError('must stop before provider')
 monkeypatch.setattr(source,'EsunHttp',no_http);snap={'ticker':'2884.TW','data':{**deepcopy(DATA),**changed},'source_audit':[{'source':'market_data','provider':'saved','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1}]}
 with pytest.raises(HTTPException) as e:asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
 assert e.value.status_code==400

def test_optional_workflow_keeps_core_and_parent_context(monkeypatch):
 import asyncio
 from data_fetch.issuer_news_provider import IssuerNewsProvider
 from data_fetch.enrichment_merge import _merge_optional_http_bundle
 from data_fetch.market_sources import issuer_news
 import data_fetch.workflow as workflow
 real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda t:real(t,now=NOW,http=Http()))
 monkeypatch.setattr(workflow,'cache_financial_payload',lambda *a:None);monkeypatch.setattr(workflow,'finalize_data_trust',lambda *a:None)
 monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda d,b,**k:_merge_optional_http_bundle(d,b))
 data=deepcopy(DATA);data['current_price']=29.;data['financial_currency']='TWD'
 result=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('2884.TW'),ProviderRegistry([IssuerNewsProvider()]),data,sources=('recent_catalysts',)))
 assert len(result['recent_catalysts'])==3 and result['company_identity']==DATA['company_identity'] and result['current_price']==29.
 assert any(a['provider']=='Verified issuer news' and a['record_count']==3 for a in result['source_audit'])
