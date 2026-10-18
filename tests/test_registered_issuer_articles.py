"""Full exchange-bound originals for Mirle and Mega, never another audited fact."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
from copy import deepcopy
from hashlib import sha256
import gzip,time
import pytest
from data_fetch.issuer_news_provider import IssuerNewsProvider
from data_fetch.market_sources.issuer_news_transport import ROSTER_URL
from data_fetch.market_sources.registered_issuer_articles import CSV_MASTER_URL,ArticlesHttp
from source_content_selection import select_company_records

F=Path(__file__).parent/'fixtures/source_acquisition'
NOW=datetime(2026,10,12,6,45,tzinfo=timezone.utc).timestamp()
PROFILES={
 '2464.TW':('mirle2464','https://www.mirle.com.tw/news/?index_m_year=2026','https://www.mirle.com.tw/news-detail/671/','盟立 / Mirle Automation Corporation','2026-09-15'),
 '2886.TW':('mega2886','https://www.megaholdings.com.tw/tc/news.aspx','https://www.megaholdings.com.tw/tc/news_in.aspx?id=6639&cid=0&chk=9591bef5-2f9d-4206-b242-1080bc6e3861&param=pn%3d1','兆豐金 / Mega Financial Holding Co., Ltd.','2026-09-21'),
}

def setup(monkeypatch,ticker,*,warm=False):
 tag,index,article,name,_=PROFILES[ticker];source={ROSTER_URL:gzip.decompress((F/'nanya2408_complete_roster_20261011.json.gz').read_bytes()),index:gzip.decompress((F/(tag+'_complete_news_index_20261012.html.gz')).read_bytes()),article:gzip.decompress((F/(tag+'_complete_news_article_20261012.html.gz')).read_bytes())};calls=[]
 source[CSV_MASTER_URL]=gzip.decompress((F/'listed_company_complete_20261012.csv.gz').read_bytes())
 if ticker=='2886.TW':
  from bs4 import BeautifulSoup
  from urllib.parse import urljoin,parse_qs,urlsplit
  for a in BeautifulSoup(source[index],'html.parser').select('a.item[href]'):
   id=parse_qs(urlsplit(a['href']).query).get('id',[''])[0]
   if id in {'6640','6638'}:source[urljoin(index,a['href'])]=gzip.decompress((F/('mega2886_complete_parent_article'+id+'_20261012.html.gz')).read_bytes())
 def get(http,url):
  calls.append(url);body=source[url];cached=url==ROSTER_URL or warm
  c={'url':url,'fetched_at_epoch':NOW-10,'cache_hit':cached,'http_request_sent':not cached,'stale':False}
  if url==ROSTER_URL:c.update(fetched_at_epoch=NOW-1000,evidence_kind='cached_complete_source_payload_verified_by_digest',http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=url,source_payload_sha256=sha256(body).hexdigest(),source_payload_bytes=len(body))
  else:c.update(http_status=200);http.http_request_count+=int(not cached)
  if url==CSV_MASTER_URL:c['fetched_at_epoch']=NOW-1000
  http.components.append(c);return body
 class FrozenDateTime(datetime):
  @classmethod
  def now(cls,tz=None):return cls.fromtimestamp(NOW,tz)
 from data_fetch.market_sources import issuer_news
 monkeypatch.setattr(issuer_news,'datetime',FrozenDateTime)
 monkeypatch.setattr(time,'time',lambda:NOW);monkeypatch.setattr(ArticlesHttp,'get',get)
 data={'ticker':ticker,'instrument_type':'EQUITY','quote_type':'EQUITY','quoteType':'EQUITY','company_name':name,'fcf_history':[1,2],'ttm_revenue':3}
 return SimpleNamespace(source=source,calls=calls,data=data,index=index,article=article)

@pytest.mark.parametrize('ticker',PROFILES)
def test_public_provider_recovers_complete_dated_parent_article(monkeypatch,ticker):
 h=setup(monkeypatch,ticker);p=IssuerNewsProvider();req=SimpleNamespace(ticker=ticker);before=deepcopy(h.data)
 assert p.supports(req)
 result=p.fetch(req,{'data':h.data})
 assert result.status=='success' and result.audit['record_count']>=1 and h.data==before,(result.audit.get('error_kind'),result.audit.get('error_message'),h.calls)
 selected,_=select_company_records(result.value,h.data,cutoff=NOW)
 assert selected and PROFILES[ticker][4]in{r['date']for r in selected}
 assert all(r['source_role']=='issuer_statement'and r['event_assessment']=='not_assessed'and r['financial_assurance']=='not_verified_as_audited'for r in selected)
 assert any(len(r['text'])>600 for r in selected)

@pytest.mark.parametrize('ticker',PROFILES)
@pytest.mark.parametrize('field',['title','text','date','publisher','financial_assurance','basis','image_claim','hash','bool_epoch','future_epoch','fake_master_HTTP'])
def test_saved_original_or_date_semantics_tampering_is_not_admitted(monkeypatch,ticker,field):
 from data_fetch.market_sources import registered_issuer_articles as m
 h=setup(monkeypatch,ticker);rows,_=m.fetch_recent_news(ticker,now=datetime.fromtimestamp(NOW,timezone.utc));r=deepcopy(rows[0]);proof=r['issuer_news_receipt']['source_record_archive']
 if field in {'title','text','date','publisher','financial_assurance'}:r[field]='changed'
 elif field=='basis':r['publication_date_basis']='independently_confirmed'
 elif field=='image_claim':r['publication_date_original']['images_independently_verified']=True
 elif field=='hash':proof['article']['raw_response_sha256']='0'*64
 elif field=='bool_epoch':proof['article']['retrieved_at']=True
 elif field=='future_epoch':proof['article']['retrieved_at']=NOW+1
 else:proof['master']['http_status']=None
 assert m.verified_record(r,h.data,today=datetime.fromtimestamp(NOW,timezone.utc).date())is None
 selected,_=select_company_records([r],h.data,cutoff=NOW);assert not selected

@pytest.mark.parametrize('ticker',PROFILES)
@pytest.mark.parametrize('field',['instrument_type','quote_type','quoteType','company_name'])
def test_explicit_instrument_conflict_refuses_before_any_provider_work(monkeypatch,ticker,field):
 h=setup(monkeypatch,ticker);h.data[field]='ETF';result=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':h.data})
 assert result.status=='error'and result.audit['http_request_count']==0 and h.calls==[]

@pytest.mark.parametrize('ticker',PROFILES)
def test_actual_source_only_service_saves_originals_without_changing_analysis(monkeypatch,ticker,tmp_path):
 import asyncio,json
 from test_report_source_refresh import saved_report
 from storage.report_storage import InMemoryStorage
 from report_persistence import report_bundle_keys_for_filename
 from report_analysis_evidence import capture_analysis_evidence
 from report_refresh_service import refresh_report_data_snapshot
 from data_fetch.service import StockDataService
 from data_fetch.provider_registry import ProviderRegistry
 h=setup(monkeypatch,ticker);storage=InMemoryStorage();_,oldkeys,before=saved_report(storage);filename=ticker.replace('.','_')+'_v4_report_20261010_100000.html';keys=report_bundle_keys_for_filename(filename)
 before['ticker']=ticker;before['data'].update(h.data);before['data']['company_identity']={'ticker':ticker,'instrument_type':'EQUITY'};before['data']['recent_catalysts']=[{'title':h.data['company_name']+'原有新聞','text':h.data['company_name']+'原有事實','date':'2026-10-10','link':'https://example.com/original','source':'original publisher'}]
 before['analysis_evidence']=capture_analysis_evidence({'data':before['data']},generated_at=before['generated_at'])
 for k,old,mime in ((keys.html_key,oldkeys.html_key,'text/html'),(keys.md_key,oldkeys.md_key,'text/markdown')):storage.save_report(k,storage.get_report(old).content,content_type=mime)
 storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json')
 response=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(registry=ProviderRegistry([IssuerNewsProvider()])),source='issuer_news',return_refreshed_data=True))
 after=json.loads(storage.get_report(keys.data_key).content)
 assert response['analysis_text_stale']is True and response['refresh_sources']==['recent_catalysts']
 assert any(r['link']==h.article for r in after['data']['recent_catalysts'])and any(r['link']=='https://example.com/original'for r in after['data']['recent_catalysts'])
 assert after['analysis_evidence']==before['analysis_evidence']
 for k in ('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert after[k]==before[k]
 for k in ('current_price','ttm_revenue','fcf_history','revenue_history','years','earnings_call','company_identity'):assert after['data'][k]==before['data'][k]
 assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'and storage.get_report(keys.md_key).content==b'original conclusions'

@pytest.mark.parametrize('ticker',PROFILES)
def test_wrong_request_subject_does_not_use_context_as_another_issuer(monkeypatch,ticker):
 h=setup(monkeypatch,ticker);req='2886.TW'if ticker=='2464.TW'else'2464.TW';r=IssuerNewsProvider().fetch(SimpleNamespace(ticker=req),{'data':h.data});assert r.status=='error'and h.calls==[]

@pytest.mark.parametrize('request_ticker',['2464.TW','2886.TW'])
def test_new_request_cannot_be_replaced_by_existing_other_issuer_context(monkeypatch,request_ticker):
 from test_txc_issuer_news import setup_http,bodies
 calls=[];setup_http(monkeypatch,bodies(),calls,[False])
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker=request_ticker),{'data':{'ticker':'3042.TW','instrument_type':'EQUITY','company_name':'晶技 / TXC Corporation'}})
 assert r.status=='error'and r.value==[]and calls==[],(r.status,[x.get('ticker')for x in r.value],calls)

@pytest.mark.parametrize('ticker',PROFILES)
def test_warm_success_keeps_old_originals_and_zero_current_HTTP(monkeypatch,ticker):
 h=setup(monkeypatch,ticker);cold=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':h.data});h=setup(monkeypatch,ticker,warm=True);warm=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':h.data})
 assert warm.value==cold.value and warm.status=='skipped_fresh_cache'and warm.audit['http_request_count']==0
 assert warm.audit['fetched_at_epoch']==NOW-1000

def test_mirle_second_responsive_text_disagreement_refuses_the_article(monkeypatch):
 h=setup(monkeypatch,'2464.TW');marker='專注智能自動化系統整合'.encode();assert h.source[h.article].count(marker)>=2
 head,last=h.source[h.article].rsplit(marker,1);h.source[h.article]=head+'另篇不符'.encode()+last
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2464.TW'),{'data':h.data});assert r.status=='error'and r.value==[]

def test_mega_first_native_ROC_day_mismatch_is_not_replaced_by_index_date(monkeypatch):
 h=setup(monkeypatch,'2886.TW');latest=next(k for k in h.source if'id=6640&'in k);h.source[latest]=h.source[latest].replace('115年9月23日'.encode(),'115年9月24日'.encode(),1)
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2886.TW'),{'data':h.data});assert r.status=='error'and r.value==[]

@pytest.mark.parametrize('ticker',PROFILES)
def test_invalid_full_native_UTF8_is_not_repaired(monkeypatch,ticker):
 h=setup(monkeypatch,ticker);h.source[h.index]+=b'\xe8\xa8'
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':h.data});assert r.status=='error'and h.calls==[CSV_MASTER_URL,h.index]

@pytest.mark.parametrize('ticker',PROFILES)
def test_final_replay_deadline_failure_cannot_be_successful_cache_skip(monkeypatch,ticker):
 from data_fetch.market_sources import registered_issuer_articles as m
 h=setup(monkeypatch,ticker,warm=True);clock=[0.];real=m.verified_record
 monkeypatch.setattr(m.time,'monotonic',lambda:clock[0])
 def late(*a,**k):
  result=real(*a,**k);clock[0]=21.;return result
 monkeypatch.setattr(m,'verified_record',late)
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':h.data});assert r.status=='error'and r.audit['error_kind']=='timeout'and r.audit['http_request_count']==0

@pytest.mark.parametrize('ticker',PROFILES)
def test_prompt_copy_strips_internal_original_paths(monkeypatch,ticker):
 from prompt_evidence import prompt_evidence_copy
 h=setup(monkeypatch,ticker);r=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':h.data});view=prompt_evidence_copy({'recent_catalysts':r.value});assert 'source_record_archive'not in str(view)and'raw_response_path'not in str(view)

@pytest.mark.parametrize('url',['https://www.mirle.com.tw/news-detail/671/?x=1','http://www.mirle.com.tw/news-detail/671/','https://www.megaholdings.com.tw/tc/news_in.aspx?id=6639&cid=0&chk=x&param=pn%3d1','https://www.megaholdings.com.tw/tc/news_in.aspx?id=6639&id=6640&cid=0&chk=9591bef5-2f9d-4206-b242-1080bc6e3861&param=pn%3d1'])
def test_unpublished_ambiguous_transport_aliases_are_refused(url):
 from data_fetch.market_sources.registered_issuer_articles import url_contract
 from search_provider_runtime import SourceResponseError
 with pytest.raises(SourceResponseError):url_contract(url)

@pytest.mark.parametrize('ticker',PROFILES)
def test_new_public_route_uses_complete_official_CSV_without_retrying_failed_JSON_master(monkeypatch,ticker):
 h=setup(monkeypatch,ticker)
 from data_fetch.market_sources.registered_issuer_articles import ArticlesHttp
 from search_provider_runtime import SourceResponseError
 csv_url='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv';h.source[csv_url]=gzip.decompress((F/'listed_company_complete_20261012.csv.gz').read_bytes());old_get=ArticlesHttp.get
 def get(http,url):
  if url==ROSTER_URL:h.calls.append(url);raise SourceResponseError('timeout')
  return old_get(http,url)
 monkeypatch.setattr(ArticlesHttp,'get',get)
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':h.data})
 assert r.status=='success'and ROSTER_URL not in h.calls and h.calls[0]==csv_url,(r.status,r.audit,h.calls)
 assert all(x['issuer_news_receipt']['master_source_url']==csv_url and x['issuer_news_receipt']['source_record_archive']['master']['source_url']==csv_url for x in r.value)

@pytest.mark.parametrize('mutation',['duplicate_header','missing_cell','invalid_UTF8','HTML','wrong_UBN','wrong_website','future_date','broken_quote'])
def test_complete_CSV_failure_does_not_take_JSON_identity_or_continue_to_articles(monkeypatch,mutation):
 import csv,io
 h=setup(monkeypatch,'2464.TW');raw=h.source[CSV_MASTER_URL]
 if mutation=='invalid_UTF8':raw+=b'\xe8\xa8'
 elif mutation=='HTML':raw=b'<html>not the published dataset</html>'
 elif mutation=='broken_quote':raw+=b'\n"unterminated'
 else:
  reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''));rows=list(reader);head=rows[0];row=next(r for r in rows[1:]if r[head.index('公司代號')]=='2464')
  if mutation=='duplicate_header':head[-1]=head[0]
  elif mutation=='missing_cell':row.pop()
  elif mutation=='wrong_UBN':row[head.index('營利事業統一編號')]='11111111'
  elif mutation=='wrong_website':row[head.index('網址')]='https://other.example'
  else:row[head.index('出表日期')]='1151013'
  stream=io.StringIO(newline='');csv.writer(stream).writerows(rows);raw=stream.getvalue().encode()
 h.source[CSV_MASTER_URL]=raw
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2464.TW'),{'data':h.data})
 assert r.status=='error'and r.value==[]and h.calls==[CSV_MASTER_URL]

def test_native_CSV_cannot_be_relabelled_as_unknown_HTTP_cached_JSON_master(monkeypatch):
 from data_fetch.market_sources.registered_issuer_articles import verified_record,CACHED_MASTER_KIND
 h=setup(monkeypatch,'2464.TW');r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2464.TW'),{'data':h.data});row=deepcopy(r.value[0]);proof=row['issuer_news_receipt']['source_record_archive']['master'];proof.update(http_status=None,http_status_observed=False,evidence_kind=CACHED_MASTER_KIND,cache_source='official-company-roster:v2:.TW',source_payload_sha256=proof['raw_response_sha256'],source_payload_bytes=proof['raw_response_bytes'])
 assert verified_record(row,h.data,today=datetime.fromtimestamp(NOW,timezone.utc).date())is None

@pytest.mark.parametrize('ticker',PROFILES)
def test_previous_complete_JSON_master_receipt_remains_replayable_without_renewing_it(monkeypatch,ticker):
 from data_fetch.market_sources.registered_issuer_articles import _identity,_build_record,parse_index,parse_article,verified_record
 from official_response_evidence import archive_response
 h=setup(monkeypatch,ticker);stamp=NOW-1000
 master=archive_response(h.source[ROSTER_URL],source_url=ROSTER_URL,retrieved_at=stamp,http_status=None,evidence_kind='cached_complete_source_payload_verified_by_digest');master.update(http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_payload_sha256=sha256(h.source[ROSTER_URL]).hexdigest(),source_payload_bytes=len(h.source[ROSTER_URL]))
 identity=_identity(h.source[ROSTER_URL],ticker,datetime.fromtimestamp(NOW,timezone.utc).date(),stamp);listed=next(r for r in parse_index(h.source[h.index],ticker)if r['url']==h.article);title,body,dates=parse_article(h.source[h.article],listed,ticker)
 proofs={'master':master,'index':archive_response(h.source[h.index],source_url=h.index,retrieved_at=NOW-10,http_status=200),'article':archive_response(h.source[h.article],source_url=h.article,retrieved_at=NOW-10,http_status=200)}
 record=_build_record(ticker,identity,listed,title,body,dates,proofs);before=deepcopy(proofs)
 assert verified_record(record,h.data,today=datetime.fromtimestamp(NOW,timezone.utc).date())and proofs==before

@pytest.mark.parametrize('ticker',PROFILES)
def test_explicit_complete_master_original_reuse_preserves_epoch_and_HTTP_error_cache(monkeypatch,ticker):
 from data_fetch.market_sources import registered_issuer_articles as m
 from cache_backends import InMemoryCache
 import cache_store
 from official_response_evidence import archive_response
 from search_provider_runtime import SourceResponseError
 h=setup(monkeypatch,ticker);cache_store.set_cache_backend(InMemoryCache());stamp=NOW-1000
 receipt=archive_response(h.source[CSV_MASTER_URL],source_url=CSV_MASTER_URL,retrieved_at=stamp,http_status=200);old=deepcopy(receipt);key='shared_provider:v1:'+sha256(('issuer-news-raw:v1:'+CSV_MASTER_URL).encode()).hexdigest();error={'error_kind':'SourceResponseError','retry_after_epoch':NOW+60,'fresh_until_epoch':NOW};cache_store.set_cache_json(key,error,ttl_seconds=60)
 result=m.retain_qualified_master_original(receipt);assert result['new_HTTP_or_acquisition_successes']==0
 real=ArticlesHttp.get
 def get(http,url):
  if url==CSV_MASTER_URL:raise SourceResponseError('timeout')
  return real(http,url)
 monkeypatch.setattr(ArticlesHttp,'get',get)
 r=IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker),{'data':h.data})
 assert r.status=='success'and CSV_MASTER_URL not in h.calls and r.audit['http_request_count']==(2 if ticker=='2464.TW'else 4)and r.audit['fetched_at_epoch']==stamp
 assert cache_store.get_cache_json(key)==error and receipt==old
 assert all(x['issuer_news_receipt']['source_record_archive']['master']==receipt for x in r.value)
 cache_store.reset_cache_store_for_tests()

@pytest.mark.parametrize('field',['expired','unknown_HTTP','future','bool_epoch','hash'])
def test_explicit_master_adoption_refuses_invalid_or_expired_original(monkeypatch,field):
 from data_fetch.market_sources import registered_issuer_articles as m
 from official_response_evidence import archive_response
 h=setup(monkeypatch,'2464.TW');receipt=archive_response(h.source[CSV_MASTER_URL],source_url=CSV_MASTER_URL,retrieved_at=NOW-10,http_status=200)
 if field=='expired':receipt['retrieved_at']=NOW-1801
 elif field=='unknown_HTTP':receipt['http_status']=None
 elif field=='future':receipt['retrieved_at']=NOW+1
 elif field=='bool_epoch':receipt['retrieved_at']=True
 else:receipt['raw_response_sha256']='0'*64
 with pytest.raises((ValueError,OSError)):m.retain_qualified_master_original(receipt)

def test_retained_master_expiring_during_articles_cannot_be_success_or_cache_skip(monkeypatch):
 from data_fetch.market_sources import registered_issuer_articles as m
 from official_response_evidence import archive_response
 from cache_backends import InMemoryCache
 import cache_store
 h=setup(monkeypatch,'2464.TW',warm=True);cache_store.set_cache_backend(InMemoryCache());receipt=archive_response(h.source[CSV_MASTER_URL],source_url=CSV_MASTER_URL,retrieved_at=NOW-1790,http_status=200);m.retain_qualified_master_original(receipt);real=ArticlesHttp.get
 def get(http,url):
  raw=real(http,url)
  if url==h.article:monkeypatch.setattr(time,'time',lambda:NOW+11)
  return raw
 monkeypatch.setattr(ArticlesHttp,'get',get);r=IssuerNewsProvider().fetch(SimpleNamespace(ticker='2464.TW'),{'data':h.data});assert r.status not in{'success','skipped_fresh_cache'}
 cache_store.reset_cache_store_for_tests()
