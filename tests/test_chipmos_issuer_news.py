"""Complete ChipMOS originals with exact issuer, published URL and date boundaries."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
import json,gzip
import pytest
from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news,verified_issuer_news
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from source_content_selection import select_company_records
F=Path(__file__).parent/'fixtures/source_acquisition/chipmos_news_full_20261011';M=json.loads((F/'manifest.json').read_text())
MASTER=M['parts']['master']['url'];INDEX=M['parts']['index']['url'];ARTICLE=M['parts']['article0']['url'];NOW=datetime(2026,10,11,15,55,tzinfo=timezone.utc)
DATA={'ticker':'8150.TW','company_name':'南茂','instrument_type':'EQUITY','company_identity':{'ticker':'8150.TW','stock_id':'8150','official_name':'南茂','legal_name':'南茂科技股份有限公司','official_ubn':'16130042','allowed_aliases':['南茂'],'forbidden_aliases':[]}}
class Http:
    def __init__(self,*,cached=False):
        self.contents={};self.epochs={};self.calls=[];self.components=[];self.http_request_count=0;self.cached=cached
        for part in M['parts'].values():
            raw=gzip.open(F/part['filename'],'rb').read();assert sha256(raw).hexdigest()==part['sha256']and len(raw)==part['bytes'];self.contents[part['url']]=raw;self.epochs[part['url']]=part['retrieved_at']
    def get(self,url):
        self.calls.append(url);self.http_request_count+=int(not self.cached);self.components.append({'url':url,'http_request_sent':not self.cached,'http_status':200,'cache_hit':self.cached,'fetched_at_epoch':self.epochs[url]});return self.contents[url]
def get(http=None):return fetch_recent_issuer_news('8150.TW',now=NOW,http=http or Http())
def test_new_exact_market_route_is_available():
    r=ProviderRegistry();assert 'Verified issuer news'in r.provider_names(FetchRequest.from_ticker('8150.TW'),'recent_catalysts')
    assert 'Verified issuer news'not in r.provider_names(FetchRequest.from_ticker('8150.TWO'),'recent_catalysts')
def test_actual_body_tables_and_cautions_reach_selection_as_one_firstparty_publisher():
    h=Http();records,audit=get(h);assert len(records)==1 and audit['status']=='success',audit
    selected,_=select_company_records(records,DATA,cutoff=NOW);assert len(selected)==1 and selected[0]['publisher']=='ChipMOS';row=selected[0]
    assert '8,400.8'in row['text']and '8150'in row['text']and 'Forward-Looking Statements:'in row['text']and 'Unaudited'in row['text']
    assert row['source_document_url']==ARTICLE and row['source_role']=='issuer_statement'and row['event_assessment']=='not_assessed'and row['content_truncated']is False
    assert '回列表頁'not in row['text']and 'Cookie'not in row['text']
    assert audit['window_complete']is False and audit['http_request_count']==3 and h.calls==[MASTER,INDEX,ARTICLE]

@pytest.mark.parametrize('field,value',[('公司名稱','別家公司股份有限公司'),('公司簡稱','其他'),('營利事業統一編號','99999999'),('英文簡稱','OtherCorp'),('網址','www.chipmos.com.evil.test'),('出表日期','1150801'),('出表日期','1151013')])
def test_master_conflicts_stop_before_index(field,value):
    h=Http();rows=json.loads(h.contents[MASTER]);next(r for r in rows if r['公司代號']=='8150')[field]=value;h.contents[MASTER]=json.dumps(rows,ensure_ascii=False).encode()
    records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER]

@pytest.mark.parametrize('change',['role','date','canonical','off_host','wrong_language','duplicate_conflict'])
def test_index_role_dates_and_exact_published_links_are_required(change):
    from bs4 import BeautifulSoup
    h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=s.select('ul.ir-table2.csr-news:not(.table2-header)')[0]
    if change=='role':s.select_one('div.iryearbox h4').string='ESG訊息'
    elif change=='date':card.select_one('li').string='2026-99-08'
    elif change=='canonical':s.select_one('link[rel=canonical]')['href']='https://other.example.test/'
    elif change=='off_host':card.select_one('a')['href']='https://www.chipmos.com.evil.test/chinese/news/news-detail.aspx?NID=271'
    elif change=='wrong_language':s.html['lang']='en'
    else:
        duplicate=deepcopy(card);duplicate.select_one('a').string='南茂科技不同新聞';card.parent.append(duplicate)
    h.contents[INDEX]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX]

@pytest.mark.parametrize('url',[INDEX+'&YEAR=2026',ARTICLE+'&token=x',ARTICLE+'#body',ARTICLE.replace('https:','http:'),ARTICLE.replace('www.chipmos.com','www.chipmos.com.evil.test'),ARTICLE.replace('NID=271','NID=0271'),ARTICLE.replace('/chinese/','/english/'),'https://www.chipmos.com/chinese/news/news-list.aspx?MID=3'])
def test_transport_is_limited_to_known_public_news_routes(url):
    from data_fetch.market_sources.chipmos_issuer_news import url_contract
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):url_contract(url)

@pytest.mark.parametrize('change',['title','date','press_date','canonical','og_type','back_role','back_title','script','short_body','wrong_exchange','wrong_market','no_issuer','nav_only'])
def test_full_article_identity_date_and_body_cannot_override_index(change):
    from bs4 import BeautifulSoup
    h=Http();s=BeautifulSoup(h.contents[ARTICLE],'html.parser');root=s.select_one('div.page-content');block=root.select_one(':scope > div.editbox')
    if change=='title':root.select_one('h4').string='南茂科技另一篇新聞'
    elif change=='date':root.select_one('p.fc-main').string='2026-10-09'
    elif change=='press_date':
        node=next(n for n in block.select('p')if 'HSINCHU' in n.get_text());node.string=node.get_text().replace('Oct. 8, 2026','Oct. 9, 2026')
    elif change=='canonical':s.select_one('link[rel=canonical]')['href']=ARTICLE
    elif change=='og_type':s.select_one('meta[property="og:type"]')['content']='article'
    elif change=='back_role':root.select_one('p.textC a.btn')['href']='news-list.aspx?MID=3'
    elif change=='back_title':root.select_one('p.textC a.btn').string='公司產品'
    elif change=='script':block.append(BeautifulSoup('<script>invent facts</script>','html.parser'))
    elif change=='short_body':block.string='南茂科技首頁'
    elif change=='wrong_market':block.append('8150.TWO')
    elif change=='wrong_exchange':
        for n in block.select('p'):
            if 'Taiwan Stock Exchange: 8150'in n.get_text():n.string=n.get_text().replace('Taiwan Stock Exchange: 8150','Taiwan Stock Exchange: 2330')
    elif change=='no_issuer':
        for n in block.select('p'):
            if 'ChipMOS TECHNOLOGIES INC.'in n.get_text():n.string=n.get_text().replace('ChipMOS TECHNOLOGIES INC.','Other TECH INC.')
    else:root.select_one(':scope > div.editbox').decompose()
    h.contents[ARTICLE]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX,ARTICLE]

@pytest.mark.parametrize('change',['title','body','date','publisher','role','policy','truncated','receipt_hash','receipt_size','receipt_time','identity_ubn','forbidden_chipmos'])
def test_saved_record_admission_replays_originals_and_issuer_context(change):
    records,_=get();row=deepcopy(records[0]);data=deepcopy(DATA)
    if change=='title':row['title']='南茂科技虛構標題'
    elif change=='body':row['text']='南茂科技虛構正文'*40
    elif change=='date':row['date']='2026-10-09'
    elif change=='publisher':row['publisher']='PRNewswire'
    elif change=='role':row['source_role']='independent_editorial'
    elif change=='policy':row['issuer_news_receipt']['policy']='generic-source'
    elif change=='truncated':row['content_truncated']=True
    elif change=='identity_ubn':data['company_identity']['official_ubn']='99999999'
    elif change=='forbidden_chipmos':data['company_identity']['forbidden_aliases']=['ChipMOS']
    else:
        p=row['issuer_news_receipt']['source_record_archive']['article']
        if change=='receipt_hash':p['raw_response_sha256']='0'*64
        elif change=='receipt_size':p['raw_response_bytes']+=1
        else:p['retrieved_at']=float('nan')
    assert verified_issuer_news(row,data,today=NOW.date())is None

def test_cached_originals_keep_real_times_with_no_http():
    records,audit=get(Http(cached=True));assert len(records)==1 and audit['status']=='skipped_fresh_cache'and audit['http_request_count']==0
    assert audit['fetched_at_epoch']==min(p['retrieved_at']for p in M['parts'].values())

def test_shared_roster_unknown_http_status_and_original_digest_are_honest():
    class Shared(Http):
        def get(self,url):
            raw=super().get(url)
            if url==MASTER:
                self.http_request_count-=1;self.components[-1].update(http_request_sent=False,cache_hit=True,evidence_kind='cached_complete_source_payload_verified_by_digest',http_status=None,http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=MASTER,source_payload_sha256=sha256(raw).hexdigest(),source_payload_bytes=len(raw),stale=False)
            return raw
    records,audit=get(Shared());assert len(records)==1 and audit['http_request_count']==2
    p=records[0]['issuer_news_receipt']['source_record_archive']['master'];assert p['http_status']is None and p['http_status_observed']is False and p['retrieved_at']==M['parts']['master']['retrieved_at']
    row=deepcopy(records[0]);row['issuer_news_receipt']['source_record_archive']['master']['http_status']=200
    assert verified_issuer_news(row,DATA,today=NOW.date())is None

def test_whole_deadline_covers_parsing_and_full_original_admission(monkeypatch):
    import time
    from types import SimpleNamespace
    from data_fetch.market_sources import chipmos_issuer_news as source
    clock=[0.];original=source.parse_article;monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=time.time))
    def late(*args):value=original(*args);clock[0]=21.;return value
    monkeypatch.setattr(source,'parse_article',late);records,audit=get();assert not records and audit['status']=='error'and audit['error_kind']=='timeout'

@pytest.mark.parametrize('change',['future','historical'])
def test_outside_window_first_card_never_requests_its_article(change):
    from bs4 import BeautifulSoup
    h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=s.select('ul.ir-table2.csr-news:not(.table2-header)')[0]
    card.select_one('li').string='2026-10-13'if change=='future'else'2026-09-08'
    h.contents[INDEX]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='unavailable'and ARTICLE not in h.calls and audit['excluded_reason_counts'][change]>0

def test_one_firstparty_original_does_not_satisfy_eight_three_gate():
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    records,_=get();rs=[SearchResult(r['title'],r['text'],r['link'],r['publisher'],r['date'])for r in records]
    assert not search_quality_satisfied(rs,max_results=8,query='南茂',require_recent=True,cutoff=NOW)

def test_source_only_preserves_quote_finance_social_and_original_audits(monkeypatch):
    import asyncio
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import issuer_news
    from report_source_refresh import fetch_report_source_data
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    old=deepcopy(DATA);old.update(current_price=75.,financial_currency='TWD',revenue_ttm_raw=1234000000,years=['2021','2022','2023','2024','2025'],recent_catalysts=[],social_sentiment=[{'text':'old social'}])
    audits=[{'source':'market_data','provider':'saved quote','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1},{'source':'financial_statements','provider':'saved finance','status':'success','fetched_at_epoch':NOW.timestamp()-700,'record_count':5}]
    snap={'ticker':'8150.TW','data':old,'source_audit':audits};before=deepcopy(snap);merged=asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert len(merged['recent_catalysts'])==1 and snap==before and merged['source_audit'][:2]==audits
    for k in ('company_identity','current_price','revenue_ttm_raw','financial_currency','years','social_sentiment'):assert merged[k]==old[k]

@pytest.mark.parametrize('changed',[{'instrument_type':'ETF'},{'instrument_type':False},{'instrument_type':'unknown'},{'quote_type':'ETF'},{'quote_type':'EQUITY','quoteType':'ETF'},{'quote_type':False}])
def test_inconsistent_source_only_instrument_stops_before_provider(monkeypatch,changed):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import chipmos_issuer_news as source
    from report_source_refresh import fetch_report_source_data
    def no_http(*args):raise AssertionError('preflight must stop before provider')
    monkeypatch.setattr(source,'ChipmosHttp',no_http);snap={'ticker':'8150.TW','data':{**deepcopy(DATA),**changed},'source_audit':[{'source':'market_data','provider':'saved','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1}]}
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert exc.value.status_code==400

def test_normal_optional_workflow_admits_original_and_preserves_core(monkeypatch):
    import asyncio
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources import issuer_news
    import data_fetch.workflow as workflow
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *args:None);monkeypatch.setattr(workflow,'finalize_data_trust',lambda *args:None)
    monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda data,bundle,**kwargs:_merge_optional_http_bundle(data,bundle))
    data=deepcopy(DATA);data['current_price']=75.;data['financial_currency']='TWD'
    result=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('8150.TW'),ProviderRegistry([IssuerNewsProvider()]),data,sources=('recent_catalysts',)))
    assert len(result['recent_catalysts'])==1 and result['company_identity']==DATA['company_identity']and result['current_price']==75.
    assert any(a['provider']=='Verified issuer news'and a['record_count']==1 for a in result['source_audit'])
