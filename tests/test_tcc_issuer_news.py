"""Native observed TCC article sections exercise the public provider and selector."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest

from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news
from data_fetch.market_sources.issuer_news_transport import ROSTER_URL, url_contract
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from source_content_selection import select_company_records

FIXTURE = json.loads((Path(__file__).parent/'fixtures/source_acquisition/tcc_issuer_news_selected_20261010.json').read_text())
NOW = datetime(2026,10,10,0,tzinfo=timezone.utc)
INDEX = 'https://www.tccgroupholdings.com/news'
DATA = {'ticker':'1101.TW','company_name':'台泥','company_identity':{'official_name':'台泥','allowed_aliases':['台泥'],'forbidden_aliases':[]}}

class Http:
    def __init__(self, *, cached=False):
        self.contents={ROSTER_URL:json.dumps([FIXTURE['roster']],ensure_ascii=False).encode(),INDEX:FIXTURE['index_html'].encode(),**{url:raw.encode() for url,raw in FIXTURE['articles'].items()}}
        self.calls=[];self.components=[];self.http_request_count=0;self.cached=cached
    def get(self,url):
        self.calls.append(url);self.http_request_count+=int(not self.cached)
        self.components.append({'url':url,'cache_hit':self.cached,'http_request_sent':not self.cached,'fetched_at_epoch':NOW.timestamp()-300})
        return self.contents[url]

def get(http=None):
    return fetch_recent_issuer_news('1101.TW',now=NOW,http=http or Http())

def test_tcc_is_in_exact_public_provider_plan_and_other_market_is_excluded():
    registry=ProviderRegistry()
    assert 'Verified issuer news' in registry.provider_names(FetchRequest.from_ticker('1101.TW'),'recent_catalysts')
    assert 'Verified issuer news' not in registry.provider_names(FetchRequest.from_ticker('1101.TWO'),'recent_catalysts')

def test_native_observed_articles_reach_company_time_selection():
    rows,audit=get()
    assert audit['status']=='success' and len(rows)==3
    accepted,_=select_company_records(rows,DATA,cutoff=NOW)
    assert len(accepted)==3
    assert [r['date'] for r in accepted]==['2026-10-01','2026-09-23','2026-09-21']
    assert all(r['source_role']=='issuer_statement' and r['event_assessment']=='not_assessed' for r in accepted)
    assert all(r['content_truncated'] is False and r['publication_date_precision']=='day' for r in accepted)
    assert all('related title' not in r['text'] for r in accepted)
    assert len({r['issuer_news_receipt']['index_response_sha256'] for r in accepted})==1
    assert audit['window_complete'] is False and audit['http_request_count']==5

def test_tcc_has_its_own_size_cap_and_fixed_public_destination():
    assert url_contract(INDEX)[0]==600000
    assert url_contract(next(iter(FIXTURE['articles'])))[0]==600000
    assert url_contract('https://www.sanyang.com.tw/newslist')[0]==150000

@pytest.mark.parametrize('field,value',[('公司名稱','另一家公司股份有限公司'),('英文簡稱','OTHER'),('網址','https://www.tccgroupholdings.com/elsewhere/'),('網址','https://www.tccgroupholdings.com.evil.test/tw/'),('出表日期','1150801')])
def test_wrong_current_issuer_binding_stops_after_roster(field,value):
    http=Http();rows=json.loads(http.contents[ROSTER_URL]);rows[0][field]=value;http.contents[ROSTER_URL]=json.dumps(rows,ensure_ascii=False).encode()
    records,audit=get(http)
    assert records==[] and http.calls==[ROSTER_URL]
    assert audit['status']=='error'

def test_wholly_cached_originals_preserve_acquisition_epoch_and_are_not_new_fetches():
    rows,audit=get(Http(cached=True))
    assert len(rows)==3 and audit['status']=='skipped_fresh_cache'
    assert audit['http_request_count']==0 and audit['http_request_sent'] is False
    assert audit['fetched_at_epoch']==NOW.timestamp()-300

@pytest.mark.parametrize('change',['title','date','body','url','source_type','index_hash'])
def test_saved_receipt_mutations_fail_closed(change):
    rows,_=get();assert rows
    record=rows[0]
    if change=='title':record['title']='台泥 fabricated title'
    elif change=='date':record['date']='2026-10-09'
    elif change=='body':record['text']='台泥 fabricated body'*20
    elif change=='url':record['link']='https://evil.test/news/private'
    elif change=='source_type':record.pop('source_type')
    else:record['issuer_news_receipt']['index_response_sha256']='not-a-hash'
    accepted,_=select_company_records([record],DATA,cutoff=NOW)
    assert accepted==[]

def test_listing_and_original_dates_must_match_and_related_dates_cannot_supply_them():
    http=Http();url=next(iter(FIXTURE['articles']));http.contents[url]=http.contents[url].replace(b'2026.10.01',b'2026.09.30')
    rows,audit=get(http)
    assert rows==[] and audit['status']=='error'
    assert len(http.calls)==3

def test_first_party_receipt_cannot_fall_back_to_aliases_without_source_type():
    from test_issuer_news import Http as SinbonHttp, NOW as SINBON_NOW
    rows,_=fetch_recent_issuer_news('3023.TW',now=SINBON_NOW,http=SinbonHttp())
    assert rows
    row=rows[0];row.pop('source_type');row['issuer_news_receipt']['article_response_sha256']='broken'
    accepted,_=select_company_records([row],{'ticker':'3023.TW','company_name':'SINBON'},cutoff=SINBON_NOW)
    assert accepted==[]

@pytest.mark.parametrize('url',[INDEX+'?token=x','https://www.tccgroupholdings.com/news/../private','https://www.tccgroupholdings.com/news/story/private','https://www.tccgroupholdings.com.evil.test/news/story','http://www.tccgroupholdings.com/news/story'])
def test_unsupported_tcc_urls_never_start_transport(url):
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):url_contract(url)

def test_unknown_and_historical_index_dates_skip_original_http():
    http=Http();http.contents[INDEX]=http.contents[INDEX].replace(b'2026.10.01',b'unknown').replace(b'2026.09.23',b'2026.08.23').replace(b'2026.09.21',b'2026.11.21')
    rows,audit=get(http)
    assert rows==[] and audit['status']=='unavailable'
    assert http.calls==[ROSTER_URL,INDEX]

def test_partial_original_failure_retains_completed_original_with_failure():
    http=Http();second=list(FIXTURE['articles'])[1];http.contents[second]=http.contents[second].replace(b'2026.09.23',b'2026.09.22')
    rows,audit=get(http)
    assert len(rows)==1 and rows[0]['date']=='2026-10-01'
    assert audit['status']=='degraded_enrichment' and audit['error_kind']=='parse_error'
    assert http.calls[-1]==second and len(http.calls)==4

def test_records_survive_public_optional_provider_bundle_without_alias_expansion(monkeypatch):
    import asyncio
    from unittest.mock import patch
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources import issuer_news
    import data_fetch.workflow as workflow
    real=issuer_news.fetch_recent_issuer_news
    monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=NOW,http=Http()))
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *a:None)
    monkeypatch.setattr(workflow,'finalize_data_trust',lambda *a:None)
    monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda data,bundle,**kwargs:_merge_optional_http_bundle(data,bundle))
    before=deepcopy(DATA['company_identity']);data=deepcopy(DATA)
    with patch('news_freshness_policy.news_cutoff',return_value=NOW):
        out=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('1101.TW'),ProviderRegistry([IssuerNewsProvider()]),data,sources=('recent_catalysts',)))
    assert len(out['recent_catalysts'])==3 and out['company_identity']==before
    assert any(a['provider']=='Verified issuer news' and a['record_count']==3 for a in out['source_audit'])
    assert not ProviderRegistry().provider_names(FetchRequest.from_ticker('9103.TW'),'recent_catalysts').count('Verified issuer news')

@pytest.mark.parametrize('location',['article','featured_index','card_index'])
def test_nested_related_date_cannot_replace_direct_publication_date(location):
    from bs4 import BeautifulSoup
    http=Http();url=next(iter(FIXTURE['articles']))
    if location=='article':
        soup=BeautifulSoup(http.contents[url],'html.parser');header=soup.find('h2').parent
        direct=header.find('p',class_='font-arial',recursive=False);stamp=direct.get_text(' ',strip=True);direct.decompose()
        header.append(BeautifulSoup('<aside class="related-news"><p class="font-arial">'+stamp+'</p></aside>','html.parser'))
        http.contents[url]=str(soup).encode()
    else:
        soup=BeautifulSoup(http.contents[INDEX],'html.parser')
        if location=='featured_index':section=soup.select_one('a.m-btn--fill').parent;direct=section.find('p',class_='font-arial',recursive=False)
        else:section=soup.select_one('a.group.block');direct=section.find('div',class_='font-arial',recursive=False)
        stamp=direct.get_text(' ',strip=True);direct.decompose()
        section.append(BeautifulSoup('<aside class="related-news"><p class="font-arial">'+stamp+'</p></aside>','html.parser'))
        http.contents[INDEX]=str(soup).encode()
    rows,audit=get(http)
    assert rows==[] and audit['status']=='error'
