"""A delivered stock overview must not end bounded editorial discovery."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import json
import pytest
from test_finmind_news_daily_recovery import isolated,install_http,ROW
from data_fetch.types import FetchRequest


def observed():
    return json.loads((Path(__file__).parent/'fixtures/source_acquisition/finmind-stock-overview-1623-20261014.json').read_text())['observed_record']


def api_row(day):
    row=observed()
    return {**row,'stock_id':'1623','date':day+' 00:00:00'}


def test_overview_only_first_day_continues_to_actual_editorial(monkeypatch,isolated):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    from official_response_evidence import read_response
    isolated[0]=datetime(2026,10,13,tzinfo=timezone.utc).timestamp()
    overview=api_row('2026-10-12')
    editorial={**ROW,'stock_id':'1623','date':'2026-10-11 05:36:00','title':'大東電(1623)宣布營收'}
    calls=install_http(monkeypatch,{'2026-10-12':[overview],'2026-10-11':[editorial]})
    result=fetch_finmind_news_result(FetchRequest.from_ticker('1623.TW'))
    assert [r['link']for r in result.value]==[editorial['link']]
    assert [c['query']['start_date'][0]for c in calls]==['2026-10-12','2026-10-11']
    assert result.audit['rejected_reason_counts']=={'stock_overview_is_not_news':1}
    assert result.status=='success'
    assert result.audit['quality_status']=='partial'
    assert json.loads(read_response(result.audit['components'][0]['raw_http_receipt']))['data']==[overview]


def test_only_overviews_exhaust_existing_three_dates_without_false_success(monkeypatch,isolated):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    isolated[0]=datetime(2026,10,13,tzinfo=timezone.utc).timestamp()
    days=['2026-10-12','2026-10-11','2026-10-05']
    calls=install_http(monkeypatch,{d:[api_row(d)]for d in days})
    result=fetch_finmind_news_result(FetchRequest.from_ticker('1623.TW'))
    assert result.value==[] and result.status!='success'
    assert result.audit['rejected_reason_counts']=={'stock_overview_is_not_news':3}
    assert len(calls)==result.audit['http_request_count']==3


@pytest.mark.parametrize('publisher',['CMoney','unknown publisher'])
def test_actual_saved_overview_is_excluded_by_url_role_not_label(publisher):
    from source_content_selection import select_company_records
    record={**observed(),'publisher':publisher,'source':publisher}
    accepted,audit=select_company_records([record],{'ticker':'1623.TW','company_name':'大東電'},cutoff='2026-10-13T00:00:00+00:00')
    assert not accepted
    assert audit['rejected_reason_counts']=={'stock_overview_is_not_news':1}
    assert audit['source_record_archive'][0]['record']==record


def test_saved_projection_preserves_original_but_does_not_promote_to_eighth():
    from news_freshness_policy import apply_news_only_freshness
    records=[{'title':f'大東電(1623)營運消息 {i}','date':'2026-10-11','link':f'https://p{i%3}.example/news/{i}','source':f'p{i%3}'}for i in range(7)]
    data={'ticker':'1623.TW','company_name':'大東電','recent_catalysts':records,'unverified_catalysts':[observed()],'social_sentiment':{'unchanged':True}}
    apply_news_only_freshness(data,cutoff='2026-10-13T00:00:00+00:00')
    assert data['news_selection']['eligible_count']==7
    assert data['news_selection']['source_role_unverified_count']==1
    row=data['unverified_catalysts'][0]
    assert row['link']==observed()['link'] and row['source_role_status']=='stock_overview_is_not_news'
    assert row['publication_date_original']==observed()['publication_date_original']
    assert data['social_sentiment']=={'unchanged':True}
    once=deepcopy(data);apply_news_only_freshness(data,cutoff='2026-10-13T00:00:00+00:00');assert data==once


def test_editorial_foreign_host_and_separate_direct_social_are_unchanged():
    from source_content_selection import select_company_records
    original=observed()
    records=[{**original,'link':'https://www.cmoney.tw/notes/note-detail.aspx?nid=12345','title':'大東電(1623)營收新聞'},
             {**original,'link':'https://publisher.example/finance/1623/f00025','title':'大東電(1623)新聞'},
             {**original,'source_type':'forum_cmoney','social_channel':'cmoney_stock_direct','link':'https://www.cmoney.tw/forum/article/123456','title':'大東電(1623)討論'}]
    accepted,audit=select_company_records(records,{'ticker':'1623.TW','company_name':'大東電'},cutoff='2026-10-13T00:00:00+00:00')
    assert len(accepted)==3 and audit['rejected_count']==0
