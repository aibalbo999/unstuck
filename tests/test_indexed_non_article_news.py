"""A search timestamp does not turn a stock page or indexed forum into news."""
from datetime import datetime,timezone
from pathlib import Path

import pytest

from external_search_payloads import parse_news_rss_payload
from external_search_types import SearchResult
from external_search_quality import select_quality_results,search_quality_satisfied
from source_content_selection import select_company_records

CONTEXT={'ticker':'8069.TWO','company_name':'元太','instrument_type':'EQUITY','company_identity':{'official_name':'元太'}}
CUTOFF=datetime(2026,10,11,7,23,10,tzinfo=timezone.utc)


def test_native_search_mix_cannot_fill_eight_news_gate_with_overview_and_forum_wrappers():
    raw=(Path(__file__).parent/'fixtures/source_acquisition/eink8069_news_with_indexed_forum_native_20261011.xml').read_text()
    parsed=parse_news_rss_payload(raw,provider='google_news_rss',fallback_source='Google News RSS')
    records=[{'title':v.title,'summary':v.snippet,'source':v.source,'link':v.link,'date':v.published_at,'source_type':'google_news_rss_search'}for v in parsed[:20]]
    assert len(records)==15
    selected,audit=select_company_records(records,CONTEXT,cutoff=CUTOFF)
    assert len(selected)==6
    assert audit['rejected_reason_counts']=={'indexed_non_article_unverified':8,'issuer_unverified':1}
    rejected=[v['record']for v in audit['source_record_archive']if v['reason']=='indexed_non_article_unverified']
    assert len(rejected)==8 and all(v in records for v in rejected)
    assert all('股市爆料同學會'not in v['title']and '個股概覽'not in v['title']for v in selected)
    typed=[SearchResult(v['title'],v['summary'],v['link'],v['source'],v['date'])for v in selected]
    chosen=select_quality_results(typed,limit=8,query='元太',require_recent=True,cutoff=CUTOFF)
    assert not search_quality_satisfied(chosen,max_results=8,query='元太',require_recent=True,cutoff=CUTOFF)


@pytest.mark.parametrize('title,source,link,accepted',[
    ('元太(8069) 個股概覽 | 個股 - 股市 - CMoney','CMoney','https://news.google.com/rss/articles/overview',False),
    ('8069 元太- 可以賭身家了 - 股市爆料同學會 - CMoney','CMoney','https://news.google.com/rss/articles/forum',False),
    ('8069 元太- 元太9月營收成長 - 股市爆料同學會 - CMoney','CMoney','https://news.google.com/rss/articles/repost',False),
    ('元太9月營收成長 - CMoney','CMoney','https://news.google.com/rss/articles/editorial',True),
    ('元太接受股市爆料同學會專訪 - CMoney','CMoney','https://news.google.com/rss/articles/interview',True),
    ('元太公布公司新聞 - UDN','UDN','https://news.google.com/rss/articles/news',True),
])
def test_fixed_publisher_role_formats_keep_editorial_controls(title,source,link,accepted):
    row={'title':title,'summary':'元太','source':source,'link':link,'date':'2026-10-08T10:00:00+08:00'}
    selected,audit=select_company_records([row],CONTEXT,cutoff=CUTOFF)
    assert bool(selected)==accepted
    if not accepted:assert audit['source_record_archive']==[{'reason':'indexed_non_article_unverified','record':row}]


def test_direct_social_samples_and_other_issuers_retain_their_channel_and_binding():
    social={'title':'元太(8069) 技術分析討論','text':'元太電子紙產品','link':'https://www.ptt.cc/bbs/Stock/M.1791446400.A.ABC.html','source':'PTT','date':'2026-10-08T10:00:00+08:00','social_channel':'ptt_stock_direct'}
    editorial={'title':'台泥營收創高 - CMoney','summary':'台泥公司營收','link':'https://news.google.com/rss/articles/tcc','source':'CMoney','date':'2026-10-08T10:00:00+08:00'}
    selected,audit=select_company_records([social,editorial],CONTEXT,cutoff=CUTOFF)
    assert selected[0]['social_channel']=='ptt_stock_direct'and len(selected)==1
    assert audit['rejected_reason_counts']=={'issuer_unverified':1}
