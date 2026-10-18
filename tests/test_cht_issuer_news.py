"""Complete captured CHT press releases admitted through public interfaces."""
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
F=Path(__file__).parent/'fixtures/source_acquisition/cht_news_full_20261011'
M=json.loads((F/'manifest.json').read_text());MASTER=M['parts']['master']['url'];INDEX=M['parts']['index']['url']
NOW=datetime(2026,10,11,14,15,tzinfo=timezone.utc)
DATA={'ticker':'2412.TW','company_name':'中華電','instrument_type':'EQUITY','company_identity':{'ticker':'2412.TW','stock_id':'2412','official_name':'中華電','legal_name':'中華電信股份有限公司','official_ubn':'96979933','allowed_aliases':['中華電'],'forbidden_aliases':[]}}
class Http:
    def __init__(self,*,cached=False):
        self.contents={};self.epochs={};self.calls=[];self.components=[];self.http_request_count=0;self.cached=cached
        for p in M['parts'].values():
            raw=gzip.open(F/p['filename'],'rb').read();assert len(raw)==p['bytes']and sha256(raw).hexdigest()==p['sha256'];self.contents[p['url']]=raw;self.epochs[p['url']]=p['retrieved_at']
    def get(self,url):
        self.calls.append(url);self.http_request_count+=int(not self.cached);self.components.append({'url':url,'http_request_sent':not self.cached,'http_status':200,'cache_hit':self.cached,'fetched_at_epoch':self.epochs[url]});return self.contents[url]
def get(http=None):return fetch_recent_issuer_news('2412.TW',now=NOW,http=http or Http())
def test_new_exact_exchange_route_is_available():
    r=ProviderRegistry()
    assert 'Verified issuer news'in r.provider_names(FetchRequest.from_ticker('2412.TW'),'recent_catalysts')
    assert 'Verified issuer news'not in r.provider_names(FetchRequest.from_ticker('2412.TWO'),'recent_catalysts')

def test_current_published_index_route_without_locale_prefix_is_accepted():
    import gzip
    from data_fetch.market_sources.cht_issuer_news import parse_index
    fixture=Path(__file__).parent/'fixtures/source_acquisition/cht_news_index_route_20261017/index.html.gz'
    raw=gzip.open(fixture,'rb').read()
    rows=parse_index(raw)
    assert len(rows)==10
    assert rows[0]['date_original']=='2026/10/16'
    assert rows[0]['title'].startswith('中華電信宜蘭營運處推動數位賦能')
    assert rows[0]['url']=='https://www.cht.com.tw/home/cht/messages/2026/1016-1630?year=2026&month=10&category=86F3795F01B14D7FADFD148D9FC695EA&list=%7b8DAECF69-AEF0-4F1B-B066-3306E547C0CC%7d'
    assert rows[8]['tags']==['公司','ESG']
    from data_fetch.market_sources.cht_issuer_news import url_contract
    assert url_contract(rows[0]['url'])[0]==600_000

def test_article_roles_must_match_all_published_index_tags():
    from bs4 import BeautifulSoup
    from data_fetch.market_sources.cht_issuer_news import parse_article
    h=Http();url=M['parts']['article0']['url'];listed=__import__('data_fetch.market_sources.cht_issuer_news',fromlist=['parse_index']).parse_index(h.contents[INDEX])[0]
    listed['tags']=[listed['tag'],'ESG']
    soup=BeautifulSoup(h.contents[url],'html.parser')
    from data_fetch.market_sources.cht_issuer_news import TAGS
    extra=BeautifulSoup(f'<a data-article-hashtag-id="{TAGS["ESG"]}">#ESG</a>','html.parser').a
    soup.select_one('article .article-footer .related-tag').append(extra)
    title,body,dates=parse_article(str(soup).encode(),listed)
    assert title==listed['title'] and body and dates['date']==listed['date_original'].replace('/','-')

def test_locale_free_index_link_accepts_only_its_exact_locale_canonical_alias():
    from data_fetch.market_sources.cht_issuer_news import parse_article,parse_index
    h=Http();listed=parse_index(h.contents[INDEX])[0]
    listed['url']=listed['url'].replace('https://www.cht.com.tw/zh-tw/home/','https://www.cht.com.tw/home/')
    title,body,dates=parse_article(h.contents[M['parts']['article0']['url']],listed)
    assert title==listed['title'] and body and dates['date']==listed['date_original'].replace('/','-')
def test_five_complete_official_originals_reach_company_selection():
    h=Http();records,audit=get(h);assert len(records)==5 and audit['status']=='success'
    selected,_=select_company_records(records,DATA,cutoff=NOW);assert len(selected)==5
    assert {r['publisher']for r in selected}=={'CHT'}
    assert 'AI'in selected[0]['text']and '備註'in selected[0]['text']
    assert all(r['content_coverage']=='text_available'and r['content_truncated']is False and r['source_role']=='issuer_statement'and r['event_assessment']=='not_assessed'for r in selected)
    assert audit['window_complete']is False and audit['http_request_count']==7
    assert h.calls==[MASTER,INDEX]+[M['parts'][f'article{i}']['url']for i in range(5)]

@pytest.mark.parametrize('field,value',[('公司名稱','別家公司股份有限公司'),('公司簡稱','其他'),('營利事業統一編號','99999999'),('英文簡稱','OtherCorp'),('網址','https://www.cht.com.tw.evil.test'),('出表日期','1150801'),('出表日期','1151012')])
def test_master_conflicts_stop_before_article_requests(field,value):
    h=Http();rows=json.loads(h.contents[MASTER]);next(r for r in rows if r['公司代號']=='2412')[field]=value;h.contents[MASTER]=json.dumps(rows,ensure_ascii=False).encode()
    records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER]

@pytest.mark.parametrize('change',['active_category','query_category','query_year','query_month','tag_id','visible_date','duplicate_conflict','off_host'])
def test_list_role_route_date_and_duplicate_conflicts_stop_before_articles(change):
    from bs4 import BeautifulSoup
    h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=s.select('.list-item')[0];a=card.select_one('.list-item-head-link')
    if change=='active_category':s.select_one('button.active[data-category-id]').string='重要公告'
    elif change=='query_category':a['href']=a['href'].replace('86F3795F01B14D7FADFD148D9FC695EA','A2C3904030A3428BA9F609D225B8E85E')
    elif change=='query_year':a['href']=a['href'].replace('year=2026','year=2025')
    elif change=='query_month':a['href']=a['href'].replace('month=10','month=09')
    elif change=='tag_id':card.select_one('[messagedategroup-hashtag-id]')['messagedategroup-hashtag-id']='0'*32
    elif change=='visible_date':card.select_one('.list-item-date').string='2026/02/30'
    elif change=='duplicate_conflict':
        other=deepcopy(card);other.select_one('h3').string='中華電信不同內容';card.parent.append(other)
    else:a['href']=a['href'].replace('www.cht.com.tw','www.cht.com.tw.evil.test')
    h.contents[INDEX]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX]

@pytest.mark.parametrize('url',[INDEX+'?token=x',M['parts']['article0']['url']+'#body',M['parts']['article0']['url'].replace('https:','http:'),M['parts']['article0']['url'].replace('www.cht.com.tw','www.cht.com.tw.evil.test'),M['parts']['article0']['url'].split('?')[0],MASTER+'?key=x'])
def test_transport_only_accepts_bounded_published_paths(url):
    from data_fetch.market_sources.cht_issuer_news import url_contract
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):url_contract(url)

@pytest.mark.parametrize('change',['title','og_title','date','canonical','role','script','body_only_navigation'])
def test_article_must_agree_with_published_list_and_have_real_body(change):
    from bs4 import BeautifulSoup
    h=Http();u=M['parts']['article0']['url'];s=BeautifulSoup(h.contents[u],'html.parser')
    if change=='title':s.select_one('article h1').string='中華電信不同內容'
    elif change=='og_title':s.select_one('meta[property="og:title"]')['content']='中華電信不同內容'
    elif change=='date':s.select_one('article .article-meta > span').string='2026/10/07'
    elif change=='canonical':s.select_one('link[rel=canonical]')['href']=INDEX
    elif change=='role':s.select_one('article .related-tag > a').string='#重要公告'
    elif change=='script':s.select_one('article .article-content').append(BeautifulSoup('<script>invent facts</script>','html.parser'))
    else:s.select_one('article .article-content').string='中華電信 首頁 搜尋'
    h.contents[u]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX,u]

@pytest.mark.parametrize('change',['title','body','date','publisher','role','policy','truncated','receipt_hash','receipt_size','receipt_time','quote_type','quoteType','identity_ubn'])
def test_admission_replays_full_original_and_rejects_semantic_drift(change):
    records,_=get();row=deepcopy(records[0]);data=deepcopy(DATA)
    if change=='title':row['title']='中華電信虛構標題'
    elif change=='body':row['text']='中華電信虛構正文'*40
    elif change=='date':row['date']='2026-10-07'
    elif change=='publisher':row['publisher']='Independent News'
    elif change=='role':row['source_role']='independent_editorial'
    elif change=='policy':row['issuer_news_receipt']['policy']='generic-source'
    elif change=='truncated':row['content_truncated']=True
    elif change in {'quote_type','quoteType'}:data[change]='ETF'
    elif change=='identity_ubn':data['company_identity']['official_ubn']='99999999'
    else:
        p=row['issuer_news_receipt']['source_record_archive']['article']
        if change=='receipt_hash':p['raw_response_sha256']='0'*64
        elif change=='receipt_size':p['raw_response_bytes']+=1
        else:p['retrieved_at']=float('nan')
    assert verified_issuer_news(row,data,today=NOW.date())is None

def test_cached_originals_keep_real_epochs_and_send_no_http():
    records,audit=get(Http(cached=True));assert len(records)==5 and audit['status']=='skipped_fresh_cache'and audit['http_request_count']==0
    assert audit['fetched_at_epoch']==min(p['retrieved_at']for p in M['parts'].values())

def test_shared_roster_is_payload_evidence_with_unknown_http_status():
    class Shared(Http):
        def get(self,url):
            raw=super().get(url)
            if url==MASTER:
                self.http_request_count-=1;self.components[-1].update(http_request_sent=False,cache_hit=True,evidence_kind='cached_complete_source_payload_verified_by_digest',http_status=None,http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=MASTER,source_payload_sha256=sha256(raw).hexdigest(),source_payload_bytes=len(raw),stale=False)
            return raw
    records,audit=get(Shared());assert len(records)==5 and audit['http_request_count']==6
    proof=records[0]['issuer_news_receipt']['source_record_archive']['master'];assert proof['http_status']is None and proof['http_status_observed']is False and proof['retrieved_at']==M['parts']['master']['retrieved_at']
    assert verified_issuer_news(records[0],DATA,today=NOW.date())=='CHT'
    row=deepcopy(records[0]);row['issuer_news_receipt']['source_record_archive']['master']['http_status']=200
    assert verified_issuer_news(row,DATA,today=NOW.date())is None

def test_shared_deadline_includes_body_parsing_and_original_replay(monkeypatch):
    import time
    from types import SimpleNamespace
    from data_fetch.market_sources import cht_issuer_news as source
    clock=[0.];original=source.parse_article;monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=time.time))
    def late(*args):value=original(*args);clock[0]=21.;return value
    monkeypatch.setattr(source,'parse_article',late);records,audit=get();assert not records and audit['status']=='error'and audit['error_kind']=='timeout'

def test_one_publisher_five_originals_do_not_satisfy_unchanged_search_gate():
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    records,_=get();results=[SearchResult(r['title'],r['text'],r['link'],r['publisher'],r['date'])for r in records]
    assert not search_quality_satisfied(results,max_results=8,query='中華電',require_recent=True,cutoff=NOW)

def test_source_only_merge_retains_core_and_social_data(monkeypatch):
    import asyncio
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import issuer_news
    from report_source_refresh import fetch_report_source_data
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    old=deepcopy(DATA);old.update(current_price=130.,financial_currency='TWD',revenue_ttm_raw=1234000000,years=['2021','2022','2023','2024','2025'],recent_catalysts=[],social_sentiment=[{'text':'old social'}])
    audits=[{'source':'market_data','provider':'saved quote','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1},{'source':'financial_statements','provider':'saved finance','status':'success','fetched_at_epoch':NOW.timestamp()-700,'record_count':5}]
    snap={'ticker':'2412.TW','data':old,'source_audit':audits};before=deepcopy(snap);merged=asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert len(merged['recent_catalysts'])==5 and snap==before and merged['source_audit'][:2]==audits
    for k in ('company_identity','current_price','revenue_ttm_raw','financial_currency','years','social_sentiment'):assert merged[k]==old[k]

@pytest.mark.parametrize('changed',[{'instrument_type':'ETF'},{'instrument_type':False},{'instrument_type':'unknown'},{'quote_type':'ETF'},{'quote_type':'EQUITY','quoteType':'ETF'},{'quote_type':False}])
def test_conflicting_source_only_instrument_stops_before_http(monkeypatch,changed):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import cht_issuer_news as source
    from report_source_refresh import fetch_report_source_data
    def no_http(*args):raise AssertionError('preflight must stop before HTTP')
    monkeypatch.setattr(source,'ChtHttp',no_http);snap={'ticker':'2412.TW','data':{**deepcopy(DATA),**changed},'source_audit':[{'source':'market_data','provider':'saved','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1}]}
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert exc.value.status_code==400

def test_normal_optional_provider_preserves_core_and_merges_full_originals(monkeypatch):
    import asyncio
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources import issuer_news
    import data_fetch.workflow as workflow
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *args:None);monkeypatch.setattr(workflow,'finalize_data_trust',lambda *args:None)
    monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda data,bundle,**kwargs:_merge_optional_http_bundle(data,bundle))
    data=deepcopy(DATA);data['current_price']=130.;data['financial_currency']='TWD'
    result=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('2412.TW'),ProviderRegistry([IssuerNewsProvider()]),data,sources=('recent_catalysts',)))
    assert len(result['recent_catalysts'])==5 and result['company_identity']==DATA['company_identity']and result['current_price']==130.
    assert any(a['provider']=='Verified issuer news'and a['record_count']==5 for a in result['source_audit'])
