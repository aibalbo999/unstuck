"""An exact original stock tag is context, without changing an author's title."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest

from data_fetch.market_sources.cmoney_stock_posts import parse_stock_article
from source_content_selection import select_company_records, issuer_match, reselect_social_context

FIXTURE=json.loads((Path(__file__).parent/'fixtures/source_acquisition/cmoney_5314_context_selected_20261010.json').read_text())
NOW=datetime.fromisoformat(FIXTURE['reference_now'])
DATA={'ticker':'5314.TWO','company_name':'世紀*','company_identity':{'official_name':'世紀*','forbidden_aliases':[]}}

def record(*, code_title=False):
    from bs4 import BeautifulSoup
    raw=FIXTURE['selected_html'].encode()
    if code_title:
        soup=BeautifulSoup(raw,'html.parser');soup.select_one('meta[property="og:title"]')['content']='5314 世紀* 看多';raw=str(soup).encode()
    row=parse_stock_article(raw,'5314','世紀*',(FIXTURE['original_url'],None),now=NOW)
    assert row is not None
    return dict(row,social_channel='cmoney_stock_direct')

def test_original_single_stock_tag_recovers_issuer_without_inventing_a_title():
    row=record();assert row['title']=='世紀* 看多' and '5314' not in row['title']+row['text']
    accepted,selection=select_company_records([row],DATA,cutoff=NOW)
    assert len(accepted)==1 and selection['rejected_count']==0
    assert accepted[0]['title']==row['title'] and accepted[0]['text']==row['text']
    assert accepted[0]['issuer_match']=='世紀*'
    assert row['cmoney_stock_context']['policy']=='cmoney-single-stock-context-v1'
    assert row['sentiment_assessment']=='not_assessed'

def test_context_survives_real_social_snapshot_reselection():
    row=record();data={**deepcopy(DATA),'social_sentiment':{'cmoney_stock_direct':[row],'yahoo_stock_direct':[],'ptt_stock_direct':[]}}
    reselect_social_context(data,cutoff=NOW)
    assert data['social_sentiment']['sample_count']==1
    saved=deepcopy(data['social_sentiment']);reselect_social_context(data,cutoff=NOW)
    assert data['social_sentiment']['cmoney_stock_direct']==saved['cmoney_stock_direct']

@pytest.mark.parametrize('change',['body','title','date','link','source','source_tag','source_listing','parser_version','raw_hash','raw_bytes','receipt','channel'])
def test_mutated_receipt_never_falls_back_to_generic_stock_code(change):
    row=record(code_title=True)
    if change=='title':row['title']='5314 世紀* fabricated title'
    elif change=='body':row['text']='5314 世紀* fabricated text'
    elif change=='date':row['date']='2026-10-09T15:00:00+00:00'
    elif change=='link':row['link']='https://evil.test/story'
    elif change=='source':row['source']='independent publisher'
    elif change=='source_tag':row['source_tag']='5314另一家公司'
    elif change=='source_listing':row['source_listing']='https://www.cmoney.tw/finance/2330/f00025'
    elif change=='parser_version':row['parser_version']='unknown'
    elif change=='raw_hash':row['response_sha256']='broken'
    elif change=='raw_bytes':row['response_bytes']=True
    elif change=='receipt':row['cmoney_stock_context']=None
    elif change=='channel':row['social_channel']='yahoo_stock_direct'
    accepted,_=select_company_records([row],DATA,cutoff=NOW)
    assert accepted==[]

@pytest.mark.parametrize('ticker',['5314.TW','2330.TW','5314'])
def test_exact_receipt_cannot_be_used_for_another_market_or_ticker(ticker):
    row=record();accepted,_=select_company_records([row],{**DATA,'ticker':ticker},cutoff=NOW)
    assert accepted==[]

@pytest.mark.parametrize('name',['世紀','世紀民生','另一家公司'])
def test_canonical_company_name_must_match_exact_starred_issuer(name):
    row=record();data={**DATA,'company_identity':{'official_name':name}}
    accepted,_=select_company_records([row],data,cutoff=NOW);assert accepted==[]

@pytest.mark.parametrize('forbidden',['世紀','世紀*',' <b>世紀*</b> '])
def test_original_tag_does_not_override_forbidden_alias(forbidden):
    row=record();data={**DATA,'company_identity':{'official_name':'世紀*','forbidden_aliases':[forbidden]}}
    accepted,_=select_company_records([row],data,cutoff=NOW);assert accepted==[]

def test_a_plain_starred_company_name_stays_ambiguous_without_a_stock_context_receipt():
    row=record();row.pop('cmoney_stock_context',None)
    assert issuer_match(row,DATA) is None

def test_real_public_social_provider_adopts_verified_context_without_unneeded_fallback(monkeypatch):
    import news_fetchers
    import news_freshness_policy
    from data_fetch.agent_context_providers import SocialSentimentProvider
    from data_fetch.market_sources import cmoney_stock_posts as source
    from data_fetch.types import FetchRequest
    from test_cmoney_stock_posts import finance_listing
    from data_trust import build_data_snapshot
    pages={source.FINANCE_URL.format(ticker='5314'):finance_listing(ticker='5314',company='世紀*',article_id='185359540'),FIXTURE['original_url']:FIXTURE['selected_html'].encode()}
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(source,'_download',lambda url,**kwargs:pages[url])
    monkeypatch.setattr(source,'_now',lambda:NOW)
    monkeypatch.setattr(news_freshness_policy,'news_cutoff',lambda value=None:NOW)
    monkeypatch.setattr(news_fetchers,'fetch_ptt_stock_sentiment',lambda *a,**k:pytest.fail('unnecessary fallback'))
    from data_fetch.market_sources import yahoo_stock_comments
    monkeypatch.setattr(yahoo_stock_comments,'fetch_yahoo_stock_comments',lambda *a,**k:pytest.fail('unnecessary fallback'))
    result=SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('5314.TWO'),{'data':deepcopy(DATA)})
    assert result.status=='success' and result.audit['record_count']==1
    assert result.value['sentiment_assessment']=='not_assessed'
    data={**deepcopy(DATA),'social_sentiment':result.value}
    snapshot=build_data_snapshot({'ticker':'5314.TWO','company_name':'世紀*','pipeline_id':'v3','data':data},pipeline_id='v3',generated_at=NOW.isoformat())
    restored=json.loads(json.dumps(snapshot,ensure_ascii=False));saved=restored['data']['social_sentiment']['cmoney_stock_direct'][0]
    assert saved['cmoney_stock_context']==record()['cmoney_stock_context']
    assert saved['title']=='世紀* 看多' and saved['text']==record()['text']
    assert issuer_match(saved,restored['data'])=='世紀*'

def test_removing_receipt_from_new_context_sample_does_not_restore_generic_code_fallback():
    row=record(code_title=True);row.pop('cmoney_stock_context',None)
    selected,_=select_company_records([row],DATA,cutoff=NOW)
    assert selected==[]

@pytest.mark.parametrize('bad_identity',[[],False])
def test_explicitly_malformed_company_identity_is_not_treated_as_absent(bad_identity):
    selected,_=select_company_records([record()],{**DATA,'company_identity':bad_identity},cutoff=NOW)
    assert selected==[]

@pytest.mark.parametrize('field,value',[('official_name',False),('official_name',0),('stock_id',False),('stock_id',0)])
def test_explicit_false_or_zero_identity_fields_cannot_use_fallback(field,value):
    data=deepcopy(DATA);data['company_identity'][field]=value
    selected,_=select_company_records([record()],data,cutoff=NOW)
    assert selected==[]
