"""Portable complete GUC originals, with issuer/date/role public boundaries."""
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
F=Path(__file__).parent/'fixtures/source_acquisition/guc_news_full_20261011'
M=json.loads((F/'manifest.json').read_text());MASTER=M['parts']['master']['url'];INDEX=M['parts']['index']['url']
NOW=datetime(2026,10,11,14,45,tzinfo=timezone.utc)
DATA={'ticker':'3443.TW','company_name':'創意','instrument_type':'EQUITY','company_identity':{'ticker':'3443.TW','stock_id':'3443','official_name':'創意','legal_name':'創意電子股份有限公司','official_ubn':'16299879','allowed_aliases':['創意'],'forbidden_aliases':[]}}
class Http:
    def __init__(self,*,cached=False):
        self.contents={};self.epochs={};self.calls=[];self.components=[];self.http_request_count=0;self.cached=cached
        for p in M['parts'].values():
            raw=gzip.open(F/p['filename'],'rb').read();assert len(raw)==p['bytes']and sha256(raw).hexdigest()==p['sha256'];self.contents[p['url']]=raw;self.epochs[p['url']]=p['retrieved_at']
    def get(self,url):
        self.calls.append(url);self.http_request_count+=int(not self.cached);self.components.append({'url':url,'http_request_sent':not self.cached,'http_status':200,'cache_hit':self.cached,'fetched_at_epoch':self.epochs[url]});return self.contents[url]
def get(http=None):return fetch_recent_issuer_news('3443.TW',now=NOW,http=http or Http())
def test_new_exact_market_route_is_available():
    r=ProviderRegistry()
    assert 'Verified issuer news'in r.provider_names(FetchRequest.from_ticker('3443.TW'),'recent_catalysts')
    assert 'Verified issuer news'not in r.provider_names(FetchRequest.from_ticker('3443.TWO'),'recent_catalysts')
def test_complete_actual_originals_reach_selection_as_one_issuer_publisher():
    h=Http();records,audit=get(h);assert len(records)==2 and audit['status']=='success'
    selected,_=select_company_records(records,DATA,cutoff=NOW);assert len(selected)==2 and {r['publisher']for r in selected}=={'GUC'}
    assert '102.8%'in selected[0]['text']and 'HBM4E'in selected[1]['text']and 'Igor Elkanovich'in selected[1]['text']
    assert all(r['content_coverage']=='text_available'and r['content_truncated']is False and r['source_role']=='issuer_statement'and r['event_assessment']=='not_assessed'for r in selected)
    assert all('SHARE'not in r['text']and 'Cookie 政策'not in r['text']for r in selected)
    assert audit['window_complete']is False and audit['http_request_count']==4 and h.calls==[MASTER,INDEX,M['parts']['article0']['url'],M['parts']['article1']['url']]

@pytest.mark.parametrize('field,value',[('公司名稱','別家公司股份有限公司'),('公司簡稱','其他'),('營利事業統一編號','99999999'),('英文簡稱','OtherCorp'),('網址','www.guc-asic.com.evil.test'),('出表日期','1150801'),('出表日期','1151012')])
def test_master_conflicts_stop_before_index(field,value):
    h=Http();rows=json.loads(h.contents[MASTER]);next(r for r in rows if r['公司代號']=='3443')[field]=value;h.contents[MASTER]=json.dumps(rows,ensure_ascii=False).encode()
    records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER]

@pytest.mark.parametrize('change',['category','date','og_url','off_host','wrong_language','duplicate_conflict'])
def test_index_metadata_is_bound_to_full_published_cards(change):
    from bs4 import BeautifulSoup
    h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=s.select('main section.news a.news-item')[0]
    if change=='category':card.select_one('span.category').string='企業活動'
    elif change=='date':card.select_one('.date > p').string='99'
    elif change=='og_url':s.select_one('meta[property="og:url"]')['content']=INDEX+'/other'
    elif change=='off_host':card['href']=card['href'].replace('www.guc-asic.com','www.guc-asic.com.evil.test')
    elif change=='wrong_language':card['href']=card['href'].replace('/tw/','/en/')
    else:
        other=deepcopy(card);other.select_one('p.des').string='創意電子不同內容';card.parent.append(other)
    h.contents[INDEX]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX]

@pytest.mark.parametrize('url',[INDEX+'?token=x',M['parts']['article0']['url']+'#body',M['parts']['article0']['url'].replace('https:','http:'),M['parts']['article0']['url'].replace('www.guc-asic.com','www.guc-asic.com.evil.test'),M['parts']['article0']['url'].replace('/tw/','/en/'),'https://www.guc-asic.com/download/signed?open=1',MASTER+'?key=x'])
def test_transport_only_accepts_bounded_observed_public_routes(url):
    from data_fetch.market_sources.guc_issuer_news import url_contract
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):url_contract(url)

@pytest.mark.parametrize('change',['title','date','og_url','og_locale','role','role_link','script','short_body','wrong_market'])
def test_article_identity_date_role_and_body_cannot_override_the_published_index(change):
    from bs4 import BeautifulSoup
    h=Http();u=M['parts']['article0']['url'];s=BeautifulSoup(h.contents[u],'html.parser')
    if change=='title':s.select_one('main h2.article-title').string='創意電子不同內容'
    elif change=='date':s.select_one('main .date-circle > p').string='06'
    elif change=='og_url':s.select_one('meta[property="og:url"]')['content']=INDEX
    elif change=='og_locale':s.select_one('meta[property="og:locale"]')['content']='en_US'
    elif change=='role':s.select_one('main a.category').string='企業活動'
    elif change=='role_link':s.select_one('main a.category')['href']=INDEX+'/news/Events'
    elif change=='script':s.select_one('main ._articleBlock').append(BeautifulSoup('<script>invent facts</script>','html.parser'))
    elif change=='short_body':s.select_one('main ._articleBlock').string='創意電子首頁'
    else:s.select_one('main ._articleBlock').append('3443.TWO')
    h.contents[u]=str(s).encode();records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX,u]

@pytest.mark.parametrize('change',['title','body','date','publisher','role','policy','truncated','receipt_hash','receipt_size','receipt_time','quote_type','quoteType','identity_ubn','forbidden_guc'])
def test_full_original_admission_rejects_semantic_drift(change):
    records,_=get();row=deepcopy(records[0]);data=deepcopy(DATA)
    if change=='title':row['title']='創意電子虛構標題'
    elif change=='body':row['text']='創意電子虛構正文'*40
    elif change=='date':row['date']='2026-10-06'
    elif change=='publisher':row['publisher']='Independent News'
    elif change=='role':row['source_role']='independent_editorial'
    elif change=='policy':row['issuer_news_receipt']['policy']='generic-source'
    elif change=='truncated':row['content_truncated']=True
    elif change in {'quote_type','quoteType'}:data[change]='ETF'
    elif change=='identity_ubn':data['company_identity']['official_ubn']='99999999'
    elif change=='forbidden_guc':data['company_identity']['forbidden_aliases']=['GUC']
    else:
        p=row['issuer_news_receipt']['source_record_archive']['article']
        if change=='receipt_hash':p['raw_response_sha256']='0'*64
        elif change=='receipt_size':p['raw_response_bytes']+=1
        else:p['retrieved_at']=float('nan')
    assert verified_issuer_news(row,data,today=NOW.date())is None

def test_all_cached_originals_preserve_real_epochs_and_send_zero_http():
    records,audit=get(Http(cached=True));assert len(records)==2 and audit['status']=='skipped_fresh_cache'and audit['http_request_count']==0
    assert audit['fetched_at_epoch']==min(p['retrieved_at']for p in M['parts'].values())

def test_shared_roster_saves_unknown_http_status_and_original_payload_digest():
    class Shared(Http):
        def get(self,url):
            raw=super().get(url)
            if url==MASTER:
                self.http_request_count-=1;self.components[-1].update(http_request_sent=False,cache_hit=True,evidence_kind='cached_complete_source_payload_verified_by_digest',http_status=None,http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=MASTER,source_payload_sha256=sha256(raw).hexdigest(),source_payload_bytes=len(raw),stale=False)
            return raw
    records,audit=get(Shared());assert len(records)==2 and audit['http_request_count']==3
    p=records[0]['issuer_news_receipt']['source_record_archive']['master'];assert p['http_status']is None and p['http_status_observed']is False and p['retrieved_at']==M['parts']['master']['retrieved_at']
    row=deepcopy(records[0]);row['issuer_news_receipt']['source_record_archive']['master']['http_status']=200
    assert verified_issuer_news(row,DATA,today=NOW.date())is None

def test_whole_shared_deadline_includes_body_parsing_and_replay(monkeypatch):
    import time
    from types import SimpleNamespace
    from data_fetch.market_sources import guc_issuer_news as source
    clock=[0.];original=source.parse_article;monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=time.time))
    def late(*args):value=original(*args);clock[0]=21.;return value
    monkeypatch.setattr(source,'parse_article',late);records,audit=get();assert not records and audit['status']=='error'and audit['error_kind']=='timeout'

@pytest.mark.parametrize('change',['future','historical'])
def test_outside_window_card_does_not_start_its_article_request(change):
    from bs4 import BeautifulSoup
    h=Http();s=BeautifulSoup(h.contents[INDEX],'html.parser');card=s.select('main section.news a.news-item')[0]
    if change=='future':card.select_one('.date > p').string='12'
    else:card.select_one('.month').string='SEP'
    h.contents[INDEX]=str(s).encode();records,audit=get(h)
    assert len(records)==1 and audit['status']=='success'and M['parts']['article0']['url']not in h.calls and audit['excluded_reason_counts'][change]>0

def test_two_same_publisher_originals_do_not_satisfy_original_eight_three_gate():
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    records,_=get();rs=[SearchResult(r['title'],r['text'],r['link'],r['publisher'],r['date'])for r in records]
    assert not search_quality_satisfied(rs,max_results=8,query='創意',require_recent=True,cutoff=NOW)

def test_source_only_preserves_quote_finance_and_social_data(monkeypatch):
    import asyncio
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import issuer_news
    from report_source_refresh import fetch_report_source_data
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    old=deepcopy(DATA);old.update(current_price=1500.,financial_currency='TWD',revenue_ttm_raw=1234000000,years=['2021','2022','2023','2024','2025'],recent_catalysts=[],social_sentiment=[{'text':'old social'}])
    audits=[{'source':'market_data','provider':'saved quote','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1},{'source':'financial_statements','provider':'saved finance','status':'success','fetched_at_epoch':NOW.timestamp()-700,'record_count':5}]
    snap={'ticker':'3443.TW','data':old,'source_audit':audits};before=deepcopy(snap);merged=asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert len(merged['recent_catalysts'])==2 and snap==before and merged['source_audit'][:2]==audits
    for k in ('company_identity','current_price','revenue_ttm_raw','financial_currency','years','social_sentiment'):assert merged[k]==old[k]

@pytest.mark.parametrize('changed',[{'instrument_type':'ETF'},{'instrument_type':False},{'instrument_type':'unknown'},{'quote_type':'ETF'},{'quote_type':'EQUITY','quoteType':'ETF'},{'quote_type':False}])
def test_conflicting_source_only_instrument_stops_before_provider(monkeypatch,changed):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import guc_issuer_news as source
    from report_source_refresh import fetch_report_source_data
    def no_http(*args):raise AssertionError('preflight must stop before provider')
    monkeypatch.setattr(source,'GucHttp',no_http);snap={'ticker':'3443.TW','data':{**deepcopy(DATA),**changed},'source_audit':[{'source':'market_data','provider':'saved','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1}]}
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert exc.value.status_code==400

def test_normal_optional_workflow_admits_full_originals_and_keeps_core(monkeypatch):
    import asyncio
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources import issuer_news
    import data_fetch.workflow as workflow
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *args:None);monkeypatch.setattr(workflow,'finalize_data_trust',lambda *args:None)
    monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda data,bundle,**kwargs:_merge_optional_http_bundle(data,bundle))
    data=deepcopy(DATA);data['current_price']=1500.;data['financial_currency']='TWD'
    result=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('3443.TW'),ProviderRegistry([IssuerNewsProvider()]),data,sources=('recent_catalysts',)))
    assert len(result['recent_catalysts'])==2 and result['company_identity']==DATA['company_identity']and result['current_price']==1500.
    assert any(a['provider']=='Verified issuer news'and a['record_count']==2 for a in result['source_audit'])
