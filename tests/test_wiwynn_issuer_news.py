"""Actual complete Wiwynn originals, behind isolated public interfaces."""
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
F=Path(__file__).parent/'fixtures/source_acquisition/wiwynn_news_full_20261011';M=json.loads((F/'manifest.json').read_text())
MASTER=M['parts']['master']['url'];INDEX=M['parts']['index']['url'];ARTICLE=M['parts']['article']['url']
NOW=datetime(2026,10,11,10,30,tzinfo=timezone.utc)
DATA={'ticker':'6669.TW','company_name':'緯穎','instrument_type':'EQUITY','company_identity':{'ticker':'6669.TW','stock_id':'6669','official_name':'緯穎','legal_name':'緯穎科技服務股份有限公司','official_ubn':'53687704','allowed_aliases':['緯穎'],'forbidden_aliases':[]}}
class Http:
    def __init__(self,*,cached=False):
        self.contents={};self.epochs={};self.calls=[];self.components=[];self.http_request_count=0;self.cached=cached
        for p in M['parts'].values():
            raw=gzip.open(F/p['filename'],'rb').read();assert len(raw)==p['bytes']and sha256(raw).hexdigest()==p['sha256'];self.contents[p['url']]=raw;self.epochs[p['url']]=p['retrieved_at']
    def get(self,url):
        self.calls.append(url);self.http_request_count+=int(not self.cached);self.components.append({'url':url,'http_request_sent':not self.cached,'http_status':200,'cache_hit':self.cached,'fetched_at_epoch':self.epochs[url]});return self.contents[url]
def get(http=None):return fetch_recent_issuer_news('6669.TW',now=NOW,http=http or Http())
def test_new_exact_market_issuer_route_is_planned():
    r=ProviderRegistry()
    assert 'Verified issuer news'in r.provider_names(FetchRequest.from_ticker('6669.TW'),'recent_catalysts')
    assert 'Verified issuer news'not in r.provider_names(FetchRequest.from_ticker('6669.TWO'),'recent_catalysts')
def test_complete_actual_press_body_reaches_existing_company_selection():
    http=Http();records,audit=get(http)
    assert len(records)==1 and audit['status']=='success'
    selected,_=select_company_records(records,DATA,cutoff=NOW);assert len(selected)==1
    row=selected[0];assert row['date']=='2026-09-15T01:07:01+00:00'and 'September 14, 2026'in row['text']
    assert 'Wiwynn has invested more than US$1.6 billion'in row['text']and 'About Wiwynn'in row['text']
    assert '4 : 39'not in row['text']and 'Tweet'not in row['text']
    assert row['source_role']=='issuer_statement'and row['event_assessment']=='not_assessed'
    assert row['content_coverage']=='text_available'and row['content_truncated']is False
    assert audit['window_complete']is False and audit['http_request_count']==3
    assert http.calls==[MASTER,INDEX,ARTICLE]

def test_corrupt_compressed_original_is_rejected_without_raising(monkeypatch):
    import zlib
    from data_fetch.market_sources import wiwynn_issuer_news as source
    records,_=get()
    def unreadable(_):raise zlib.error('corrupt native deflate')
    monkeypatch.setattr(source,'read_response',unreadable)
    assert verified_issuer_news(records[0],DATA,today=NOW.date())is None

@pytest.mark.parametrize('field,value', [('公司名稱','別家公司股份有限公司'),('公司簡稱','其他公司'),('營利事業統一編號','99999999'),('英文簡稱','OtherCorp'),('網址','https://www.wiwynn.com.evil.test'),('出表日期','1150801'),('出表日期','1151012')])
def test_master_conflicts_stop_before_index_and_article(field,value):
    h=Http();rows=json.loads(h.contents[MASTER]);next(x for x in rows if x['公司代號']=='6669')[field]=value;h.contents[MASTER]=json.dumps(rows,ensure_ascii=False).encode()
    records,audit=get(h);assert not records and audit['status']=='error'and h.calls==[MASTER]

@pytest.mark.parametrize('url',[INDEX+'?page=2',ARTICLE+'#body',ARTICLE+'?token=x',ARTICLE.replace('https:','http:'),ARTICLE.replace('www.wiwynn.com','www.wiwynn.com.evil.test'),'https://www.wiwynn.com/news/author/wiwynn','https://www.wiwynn.com/news/../private',MASTER+'?key=x'])
def test_only_bounded_public_routes_can_start_transport(url):
    from data_fetch.market_sources.wiwynn_issuer_news import url_contract
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):url_contract(url)

@pytest.mark.parametrize('change',['title','date','body','publisher','role','coverage','published_date','wrong_context','policy','receipt_time','receipt_size','receipt_hash'])
def test_semantic_admission_replays_full_originals(change):
    records,_=get();row=deepcopy(records[0]);data=deepcopy(DATA)
    if change=='title':row['title']='Wiwynn fabricated title'
    elif change=='date':row['date']='2026-09-14T01:07:01+00:00'
    elif change=='body':row['text']='Wiwynn invented facts '*40
    elif change=='publisher':row['publisher']='Independent News'
    elif change=='role':row['source_role']='independent_editorial'
    elif change=='coverage':row['content_truncated']=True
    elif change=='published_date':row['published_date']='2026-09-15T01:07:02+00:00'
    elif change=='wrong_context':data['instrument_type']='ETF'
    elif change=='policy':row['issuer_news_receipt']['policy']='generic-issuer'
    else:
        proof=row['issuer_news_receipt']['source_record_archive']['article']
        if change=='receipt_time':proof['retrieved_at']=float('nan')
        elif change=='receipt_size':proof['raw_response_bytes']+=1
        else:proof['raw_response_sha256']='0'*64
    assert verified_issuer_news(row,data,today=NOW.date())is None

@pytest.mark.parametrize('change',['title','canonical','visible_day','jsonld_day','jsonld_naive','jsonld_modified_only','publisher','author','role','script','wrong_market'])
def test_article_metadata_or_body_cannot_override_published_index(change):
    from bs4 import BeautifulSoup
    h=Http();soup=BeautifulSoup(h.contents[ARTICLE],'html.parser');node=soup.select_one('script[type="application/ld+json"]');ld=json.loads(node.get_text())
    if change=='title':soup.select_one('h1.blog-post__title').string='Wiwynn other news'
    elif change=='canonical':soup.select_one('link[rel=canonical]')['href']=INDEX
    elif change=='visible_day':soup.select_one('.blog-post__timestamp').string='September 14, 2026'
    elif change=='jsonld_day':ld['datePublished']='2026-09-14T01:07:01.000Z'
    elif change=='jsonld_naive':ld['datePublished']='2026-09-15T01:07:01'
    elif change=='jsonld_modified_only':ld.pop('datePublished')
    elif change=='publisher':ld['publisher']['name']='Other Publisher'
    elif change=='author':soup.select_one('.meta-author > a')['href']='https://www.wiwynn.com/news/author/guest'
    elif change=='role':soup.select_one('.blog-post__tag-link').string='In the News'
    elif change=='script':soup.select_one('#hs_cos_wrapper_post_body').append(BeautifulSoup('<script>invent facts</script>','html.parser'))
    else:soup.select_one('#hs_cos_wrapper_post_body').append('6669.TWO')
    node.string=json.dumps(ld);h.contents[ARTICLE]=str(soup).encode();records,audit=get(h)
    assert not records and audit['status']=='error'and h.calls==[MASTER,INDEX,ARTICLE]

def test_second_precision_future_publication_on_same_calendar_day_is_excluded():
    from bs4 import BeautifulSoup
    h=Http();soup=BeautifulSoup(h.contents[INDEX],'html.parser');soup.select_one('.hhs-post-meta > p').string='Oct 11, 2026';h.contents[INDEX]=str(soup).encode()
    soup=BeautifulSoup(h.contents[ARTICLE],'html.parser');soup.select_one('.blog-post__timestamp').string='October 11, 2026';node=soup.select_one('script[type="application/ld+json"]');ld=json.loads(node.get_text());ld['datePublished']='2026-10-11T14:07:01.000Z';node.string=json.dumps(ld);h.contents[ARTICLE]=str(soup).encode()
    records,audit=get(h);assert not records and audit['status']=='unavailable'and audit['excluded_reason_counts']['future']==1

def test_cached_originals_keep_acquisition_epoch_and_send_zero_http():
    records,audit=get(Http(cached=True));assert len(records)==1 and audit['status']=='skipped_fresh_cache'and audit['http_request_count']==0
    assert audit['fetched_at_epoch']==min(p['retrieved_at']for p in M['parts'].values())

def test_shared_deadline_after_parsing_cannot_admit_late_record(monkeypatch):
    import time
    from types import SimpleNamespace
    from data_fetch.market_sources import wiwynn_issuer_news as source
    clock=[0.];original=source.parse_article;monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=time.time))
    def late(*args):value=original(*args);clock[0]=21.;return value
    monkeypatch.setattr(source,'parse_article',late);records,audit=get();assert not records and audit['status']=='error'and audit['error_kind']=='timeout'

def test_source_only_refresh_preserves_other_data_and_one_article_does_not_satisfy_search_gate(monkeypatch):
    import asyncio
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import issuer_news
    from report_source_refresh import fetch_report_source_data
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    old=deepcopy(DATA);old.update(current_price=800.,financial_currency='TWD',revenue_ttm_raw=1234000000,years=['2021','2022','2023','2024','2025'],recent_catalysts=[],social_sentiment=[{'text':'old social'}])
    audits=[{'source':'market_data','provider':'saved quote','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1},{'source':'financial_statements','provider':'saved finance','status':'success','fetched_at_epoch':NOW.timestamp()-700,'record_count':5}]
    snap={'ticker':'6669.TW','data':old,'source_audit':audits};before=deepcopy(snap);merged=asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert len(merged['recent_catalysts'])==1 and snap==before and merged['source_audit'][:2]==audits
    for k in ('company_identity','current_price','revenue_ttm_raw','financial_currency','years','social_sentiment'):assert merged[k]==old[k]
    row=merged['recent_catalysts'][0];assert verified_issuer_news(row,DATA,today=NOW.date())
    assert not search_quality_satisfied([SearchResult(row['title'],row['text'],row['link'],row['publisher'],row['date'])],max_results=8,query='緯穎',require_recent=True,cutoff=NOW)

@pytest.mark.parametrize('changed',[{'instrument_type':'ETF'},{'instrument_type':False},{'instrument_type':'unknown'},{'quote_type':'ETF'}])
def test_conflicting_source_only_instrument_stops_before_provider_or_audit(monkeypatch,changed):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import wiwynn_issuer_news as source
    from report_source_refresh import fetch_report_source_data
    def no_http(*args):raise AssertionError('Preflight must stop before HTTP')
    monkeypatch.setattr(source,'WiwynnHttp',no_http);data={**deepcopy(DATA),**changed};snap={'ticker':'6669.TW','data':data,'source_audit':[{'source':'market_data','provider':'saved','status':'success','fetched_at_epoch':NOW.timestamp()-600,'record_count':1}]}
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(snap,'issuer_news',StockDataService()))
    assert exc.value.status_code==400

def test_normal_optional_provider_plan_keeps_core_data_and_real_full_article(monkeypatch):
    import asyncio
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources import issuer_news
    import data_fetch.workflow as workflow
    real=issuer_news.fetch_recent_issuer_news;monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *args:None);monkeypatch.setattr(workflow,'finalize_data_trust',lambda *args:None)
    monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda data,bundle,**kwargs:_merge_optional_http_bundle(data,bundle))
    data=deepcopy(DATA);data['current_price']=800.;data['financial_currency']='TWD'
    result=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('6669.TW'),ProviderRegistry([IssuerNewsProvider()]),data,sources=('recent_catalysts',)))
    assert len(result['recent_catalysts'])==1 and 'US$1.6 billion'in result['recent_catalysts'][0]['text']
    assert result['company_identity']==DATA['company_identity']and result['current_price']==800. and result['financial_currency']=='TWD'
    assert any(a['provider']=='Verified issuer news'and a['record_count']==1 for a in result['source_audit'])

def test_prompt_keeps_original_records_and_hides_archival_filesystem_paths():
    from prompt_builder import format_data_for_prompt
    records,_=get();original=deepcopy(records);prompt=format_data_for_prompt({**deepcopy(DATA),'recent_catalysts':records})
    assert records==original and records[0]['title']in prompt
    assert 'official-response-evidence'not in prompt and 'raw_response_path'not in prompt

def test_shared_master_original_keeps_unknown_http_status_and_cached_payload_kind():
    class Shared(Http):
        def get(self,url):
            raw=super().get(url)
            if url==MASTER:
                self.http_request_count-=1
                self.components[-1].update(http_request_sent=False,cache_hit=True,evidence_kind='cached_complete_source_payload_verified_by_digest',http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=MASTER,source_payload_sha256=sha256(raw).hexdigest(),source_payload_bytes=len(raw),stale=False)
                self.components[-1].pop('http_status',None)
            return raw
    records,audit=get(Shared());assert len(records)==1 and audit['http_request_count']==2
    proof=records[0]['issuer_news_receipt']['source_record_archive']['master']
    assert proof['evidence_kind']=='cached_complete_source_payload_verified_by_digest'
    assert proof['http_status']is None and proof['http_status_observed']is False
    assert proof['retrieved_at']==M['parts']['master']['retrieved_at']
    assert verified_issuer_news(records[0],DATA,today=NOW.date())

@pytest.mark.parametrize('change',['cached_master_claims_HTTP200','article_claims_shared_master_kind'])
def test_cached_payload_provenance_never_claims_native_http_or_other_document(change):
    records,_=get();row=deepcopy(records[0]);proof=row['issuer_news_receipt']['source_record_archive']['master'if change=='cached_master_claims_HTTP200'else'article']
    proof.update(evidence_kind='cached_complete_source_payload_verified_by_digest',http_status=200 if change=='cached_master_claims_HTTP200'else None,http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_payload_sha256=proof['raw_response_sha256'],source_payload_bytes=proof['raw_response_bytes'])
    assert verified_issuer_news(row,DATA,today=NOW.date())is None

def test_native_kind_cannot_hide_explicit_shared_cache_only_provenance():
    records,_=get();row=deepcopy(records[0]);proof=row['issuer_news_receipt']['source_record_archive']['master'];proof.update(http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_payload_sha256=proof['raw_response_sha256'],source_payload_bytes=proof['raw_response_bytes'])
    assert verified_issuer_news(row,DATA,today=NOW.date())is None

@pytest.mark.parametrize('change',['cached_HTTP200','cache_markers_native_kind'])
def test_collector_rejects_contradictory_cached_master_metadata(change):
    class Contradictory(Http):
        def get(self,url):
            raw=super().get(url)
            if url==MASTER:
                self.http_request_count-=1;self.components[-1].update(http_request_sent=False,cache_hit=True,evidence_kind='cached_complete_source_payload_verified_by_digest'if change=='cached_HTTP200'else'raw_http_response_bytes',http_status=200,http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=MASTER,source_payload_sha256=sha256(raw).hexdigest(),source_payload_bytes=len(raw),stale=False)
            return raw
    records,audit=get(Contradictory());assert not records and audit['status']=='error'


@pytest.fixture(autouse=True)
def replay_wall_clock(monkeypatch):
    import time
    monkeypatch.setattr(time, 'time', lambda: NOW.timestamp())
