"""Complete Acer newsroom originals must survive the ordinary source boundaries."""
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
F=Path(__file__).parent/'fixtures/source_acquisition/acer_news_full_20261011'
M=json.loads((F/'manifest.json').read_text());MASTER=M['parts']['master']['url'];INDEX=M['parts']['index']['url']
NOW=datetime(2026,10,11,15,30,tzinfo=timezone.utc)
DATA={'ticker':'2353.TW','company_name':'宏碁','instrument_type':'EQUITY','company_identity':{'ticker':'2353.TW','stock_id':'2353','official_name':'宏碁','legal_name':'宏碁股份有限公司','official_ubn':'20828393','allowed_aliases':['宏碁'],'forbidden_aliases':[]}}
@pytest.fixture(autouse=True)
def replay_wall_clock(monkeypatch):
    """Original receipts are replayed at their declared acquisition date."""
    import time
    monkeypatch.setattr(time, 'time', lambda: NOW.timestamp())

class Http:
    def __init__(self,*,cached=False):
        self.contents={};self.epochs={};self.calls=[];self.components=[];self.http_request_count=0;self.cached=cached
        for p in M['parts'].values():
            raw=gzip.open(F/p['filename'],'rb').read();assert len(raw)==p['bytes']and sha256(raw).hexdigest()==p['sha256'];self.contents[p['url']]=raw;self.epochs[p['url']]=p['retrieved_at']
    def get(self,url):
        self.calls.append(url);self.http_request_count+=int(not self.cached);self.components.append({'url':url,'http_request_sent':not self.cached,'http_status':200,'cache_hit':self.cached,'fetched_at_epoch':self.epochs[url]});return self.contents[url]
def get(http=None):return fetch_recent_issuer_news('2353.TW',now=NOW,http=http or Http())
def test_new_exact_market_route_is_available():
    r=ProviderRegistry()
    assert 'Verified issuer news'in r.provider_names(FetchRequest.from_ticker('2353.TW'),'recent_catalysts')
    assert 'Verified issuer news'not in r.provider_names(FetchRequest.from_ticker('2353.TWO'),'recent_catalysts')
def test_complete_native_originals_reach_selection_as_one_issuer_publisher():
    h=Http();records,audit=get(h);assert len(records)==5 and audit['status']=='success',audit
    selected,_=select_company_records(records,DATA,cutoff=NOW);assert len(selected)==5 and {r['publisher']for r in selected}=={'ACER'}
    assert '347.37'in selected[0]['text']and '宏碁公司'in selected[0]['text']and 'Googlebook'in selected[3]['text']
    assert all(r['content_coverage']=='text_available'and r['content_truncated']is False and r['source_role']=='issuer_statement'and r['event_assessment']=='not_assessed'for r in selected)
    assert all('press@acer.com'not in r['text']and '私隱要求'not in r['text']for r in selected)
    assert audit['window_complete']is False and audit['http_request_count']==7 and h.calls==[MASTER,INDEX,*[M['parts']['article'+str(i)]['url']for i in range(5)]]

@pytest.mark.parametrize('field,value',[('公司名稱','別家公司股份有限公司'),('公司簡稱','其他'),('營利事業統一編號','99999999'),('英文簡稱','OtherCorp'),('網址','http://www.acer.com.evil.test'),('出表日期','1150801'),('出表日期','1151012')])
def test_master_conflicts_stop_before_index(field,value):
    h=Http();rows=json.loads(h.contents[MASTER]);next(r for r in rows if r['公司代號']=='2353')[field]=value;h.contents[MASTER]=json.dumps(rows,ensure_ascii=False).encode()
    records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER]

@pytest.mark.parametrize('change',['title','date','canonical','off_host','wrong_language','duplicate_conflict','website_link','owner'])
def test_index_requires_the_actual_owner_cards_dates_and_routes(change):
    from bs4 import BeautifulSoup
    h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=s.select('div.StoryCard_container__MsB7x')[0]
    if change=='title':card.select_one('h2').string='另一家公司'
    elif change=='date':card.select_one('time')['datetime']='2026-99-08T08:52:00.000Z'
    elif change=='canonical':s.select_one('link[rel=canonical]')['href']=INDEX+'/other'
    elif change=='off_host':card.select_one('a.StoryCard_linkOverlay__9ats1')['href']='https://news.acer.com.evil.test/hong-qi-news'
    elif change=='wrong_language':s.html['lang']='en'
    elif change=='duplicate_conflict':
        other=deepcopy(card);other.select_one('h2').string='宏碁不同內容';other.select_one('a.StoryCard_linkOverlay__9ats1')['aria-label']='宏碁不同內容';card.parent.append(other)
    elif change=='website_link':
        for a in s.select('a[href]'):
            if 'www.acer.com'in a['href']:a['href']='https://www.acer.com.evil.test'
    else:
        n=s.select_one('script[type="application/ld+json"]');v=json.loads(n.get_text());v['name']='別家企業';n.string=json.dumps(v)
    h.contents[INDEX]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX]

@pytest.mark.parametrize('url',[INDEX+'?token=x',M['parts']['article0']['url']+'#body',M['parts']['article0']['url'].replace('https:','http:'),M['parts']['article0']['url'].replace('news.acer.com','news.acer.com.evil.test'),'https://news.acer.com/zh/search','https://news.acer.com/zh/category/cai-wu-xiang-guan',MASTER+'?key=x'])
def test_transport_accepts_only_the_fixed_public_newsroom_routes(url):
    from data_fetch.market_sources.acer_issuer_news import url_contract
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):url_contract(url)

@pytest.mark.parametrize('change',['title','visible_date','date','modified','og_url','og_locale','json_title','json_date','json_modified','json_url','json_publisher','json_language','script','short_body','wrong_market'])
def test_article_metadata_and_body_cannot_override_the_full_index(change):
    from bs4 import BeautifulSoup
    h=Http();u=M['parts']['article0']['url'];s=BeautifulSoup(h.contents[u],'html.parser');article=s.select_one('article')
    if change=='title':article.select_one('h1').string='宏碁不同內容'
    elif change=='visible_date':article.select_one('time').string='10/09/2026'
    elif change=='date':article.select_one('time')['datetime']='2026-10-09T08:52:00.000Z'
    elif change=='modified':
        n=next(n for n in s.select('script[type="application/ld+json"]')if json.loads(n.get_text()).get('@type')=='NewsArticle');v=json.loads(n.get_text());v['dateModified']='2026-10-12T08:52:00+00:00';n.string=json.dumps(v)
    elif change=='og_url':s.select_one('meta[property="og:url"]')['content']=INDEX
    elif change=='og_locale':s.select_one('meta[property="og:locale"]')['content']='en_US'
    elif change.startswith('json_'):
        n=next(n for n in s.select('script[type="application/ld+json"]')if json.loads(n.get_text()).get('@type')=='NewsArticle');v=json.loads(n.get_text())
        if change=='json_title':v['headline']='宏碁不同內容'
        elif change=='json_date':v['datePublished']='2026-10-09T08:52:00+00:00'
        elif change=='json_modified':v['dateModified']='2026-10-07T08:52:00+00:00'
        elif change=='json_url':v['mainEntityOfPage']['@id']=INDEX
        elif change=='json_publisher':v['publisher']['name']='Independent News'
        else:v['inLanguage']='en'
        n.string=json.dumps(v)
    elif change=='script':article.select_one('.ContentRenderer_renderer__IBbst').append(BeautifulSoup('<script>invent facts</script>','html.parser'))
    elif change=='short_body':article.select_one('.ContentRenderer_renderer__IBbst').string='宏碁首頁'
    else:article.select_one('.ContentRenderer_renderer__IBbst').append('2353.TWO')
    h.contents[u]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX,u]

@pytest.mark.parametrize('change',['title','body','date','publisher','role','policy','truncated','receipt_hash','receipt_size','receipt_time','quote_type','quoteType','identity_ubn','forbidden_acer'])
def test_saved_record_admission_replays_the_original_bytes_and_context(change):
    records,_=get();row=deepcopy(records[0]);data=deepcopy(DATA)
    if change=='title':row['title']='宏碁虛構標題'
    elif change=='body':row['text']='宏碁虛構正文'*40
    elif change=='date':row['date']='2026-10-09'
    elif change=='publisher':row['publisher']='Independent News'
    elif change=='role':row['source_role']='independent_editorial'
    elif change=='policy':row['issuer_news_receipt']['policy']='generic-source'
    elif change=='truncated':row['content_truncated']=True
    elif change in {'quote_type','quoteType'}:data[change]='ETF'
    elif change=='identity_ubn':data['company_identity']['official_ubn']='99999999'
    elif change=='forbidden_acer':data['company_identity']['forbidden_aliases']=['ACER']
    else:
        p=row['issuer_news_receipt']['source_record_archive']['article']
        if change=='receipt_hash':p['raw_response_sha256']='0'*64
        elif change=='receipt_size':p['raw_response_bytes']+=1
        else:p['retrieved_at']=float('nan')
    assert verified_issuer_news(row,data,today=NOW.date())is None

def test_all_cached_originals_keep_their_real_epochs_without_http():
    records,audit=get(Http(cached=True));assert len(records)==5 and audit['status']=='skipped_fresh_cache'and audit['http_request_count']==0
    assert audit['fetched_at_epoch']==min(p['retrieved_at']for p in M['parts'].values())

def test_shared_roster_retains_unknown_http_status_and_original_payload_digest():
    class Shared(Http):
        def get(self,url):
            raw=super().get(url)
            if url==MASTER:
                self.http_request_count-=1;self.components[-1].update(http_request_sent=False,cache_hit=True,evidence_kind='cached_complete_source_payload_verified_by_digest',http_status=None,http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=MASTER,source_payload_sha256=sha256(raw).hexdigest(),source_payload_bytes=len(raw),stale=False)
            return raw
    records,audit=get(Shared());assert len(records)==5 and audit['http_request_count']==6
    p=records[0]['issuer_news_receipt']['source_record_archive']['master'];assert p['http_status']is None and p['http_status_observed']is False and p['retrieved_at']==M['parts']['master']['retrieved_at']
    row=deepcopy(records[0]);row['issuer_news_receipt']['source_record_archive']['master']['http_status']=200
    assert verified_issuer_news(row,DATA,today=NOW.date())is None

def test_whole_deadline_includes_parsing_and_full_original_replay(monkeypatch):
    import time
    from types import SimpleNamespace
    from data_fetch.market_sources import acer_issuer_news as source
    clock=[0.];original=source.parse_article;monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=time.time))
    def late(*args):value=original(*args);clock[0]=21.;return value
    monkeypatch.setattr(source,'parse_article',late);records,audit=get();assert not records and audit['status']=='error'and audit['error_kind']=='timeout'

@pytest.mark.parametrize('change',['future','historical'])
def test_outside_window_card_never_starts_its_article_request(change):
    from bs4 import BeautifulSoup
    h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=s.select('div.StoryCard_container__MsB7x')[0];n=card.select_one('time')
    n['datetime']='2026-10-12T08:52:00.000Z'if change=='future'else'2026-09-08T08:52:00.000Z';n.string='10/12/2026'if change=='future'else'09/08/2026'
    h.contents[INDEX]=str(s).encode();records,audit=get(h)
    assert len(records)==4 and audit['status']=='success'and M['parts']['article0']['url']not in h.calls and audit['excluded_reason_counts'][change]>0

def test_five_same_publisher_articles_cannot_satisfy_eight_three_gate():
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    records,_=get();rs=[SearchResult(r['title'],r['text'],r['link'],r['publisher'],r['date'])for r in records]
    assert not search_quality_satisfied(rs,max_results=8,query='宏碁',require_recent=True,cutoff=NOW)

def test_source_only_preserves_original_quote_finance_and_social(monkeypatch):
    import asyncio
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import issuer_news
    from report_source_refresh import fetch_report_source_data
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    old=deepcopy(DATA);old.update(current_price=27.,financial_currency='TWD',revenue_ttm_raw=1234000000,years=['2021','2022','2023','2024','2025'],recent_catalysts=[],social_sentiment=[{'text':'old social'}])
    audits=[{'source':'market_data','provider':'saved quote','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1},{'source':'financial_statements','provider':'saved finance','status':'success','fetched_at_epoch':NOW.timestamp()-700,'record_count':5}]
    snap={'ticker':'2353.TW','data':old,'source_audit':audits};before=deepcopy(snap);merged=asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert len(merged['recent_catalysts'])==5 and snap==before and merged['source_audit'][:2]==audits
    for k in ('company_identity','current_price','revenue_ttm_raw','financial_currency','years','social_sentiment'):assert merged[k]==old[k]

@pytest.mark.parametrize('changed',[{'instrument_type':'ETF'},{'instrument_type':False},{'instrument_type':'unknown'},{'quote_type':'ETF'},{'quote_type':'EQUITY','quoteType':'ETF'},{'quote_type':False}])
def test_conflicting_source_only_instrument_stops_before_any_provider(monkeypatch,changed):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import acer_issuer_news as source
    from report_source_refresh import fetch_report_source_data
    def no_http(*args):raise AssertionError('preflight must stop before provider')
    monkeypatch.setattr(source,'AcerHttp',no_http);snap={'ticker':'2353.TW','data':{**deepcopy(DATA),**changed},'source_audit':[{'source':'market_data','provider':'saved','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1}]}
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert exc.value.status_code==400

def test_normal_optional_workflow_admits_originals_and_keeps_core(monkeypatch):
    import asyncio
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources import issuer_news
    import data_fetch.workflow as workflow
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *args:None);monkeypatch.setattr(workflow,'finalize_data_trust',lambda *args:None)
    monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda data,bundle,**kwargs:_merge_optional_http_bundle(data,bundle))
    data=deepcopy(DATA);data['current_price']=27.;data['financial_currency']='TWD'
    result=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('2353.TW'),ProviderRegistry([IssuerNewsProvider()]),data,sources=('recent_catalysts',)))
    assert len(result['recent_catalysts'])==5 and result['company_identity']==DATA['company_identity']and result['current_price']==27.
    assert any(a['provider']=='Verified issuer news'and a['record_count']==5 for a in result['source_audit'])
