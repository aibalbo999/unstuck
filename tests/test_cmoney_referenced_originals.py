"""Discover same-stock originals, never count a reshare or weaken original gates."""
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
import json
import pytest
from data_fetch.market_sources import cmoney_stock_posts as source
from test_cmoney_stock_posts import article,finance_listing,listing

NOW=datetime(2026,10,9,14,tzinfo=timezone.utc)
REF='https://www.cmoney.tw/forum/article/185141811'
PARENT='https://www.cmoney.tw/forum/article/185353826'


def test_real_referenced_original_is_discovered_and_parent_stays_rejected(monkeypatch):
    fixture=json.loads((Path(__file__).parent/'fixtures/source_acquisition/cmoney_6672_referenced_original_20261009.json').read_text())
    pages={p['url']:p['selected_html'].encode()for p in fixture['pages']};calls=[]
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(source,'_now',lambda:datetime.fromisoformat(fixture['reference_now']))
    monkeypatch.setattr(source,'_download',lambda url,**kwargs:calls.append(url) or pages.get(url,b''))
    assert source.parse_stock_article(pages[PARENT],'6672','騰輝電子-KY',(PARENT,None),now=source._now()) is None
    rows=source.fetch_cmoney_stock_posts('6672')
    assert [row['link']for row in rows]==[REF]
    assert rows[0]['response_sha256']==sha256(pages[REF]).hexdigest()
    assert rows[0]['discovered_from']==PARENT
    assert rows[0]['discovery_parent_response_sha256']==sha256(pages[PARENT]).hexdigest()
    assert rows[0]['source_discovery_kind']=='same_stock_original_reference'
    assert rows[0]['sentiment_assessment']=='not_assessed'
    assert PARENT not in [row['link']for row in rows]
    assert calls.count(REF)==1 and source.STOCK_URL.format(ticker='6672') not in calls


def pages_for_parent(parent,child=None):
    return {source.FINANCE_URL.format(ticker='6672'):finance_listing(ticker='6672',company='騰輝電子-KY',article_id='185353826'),
            PARENT:parent,REF:child or article(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',body='原文觀察仍維持風險控管。',published='2026-10-8T10:1:1+08:00'),
            source.STOCK_URL.format(ticker='6672'):b''}


def run_pages(monkeypatch,pages):
    calls=[];monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0');monkeypatch.setattr(source,'_now',lambda:NOW)
    monkeypatch.setattr(source,'_download',lambda url,**kwargs:calls.append(url) or pages.get(url,b''))
    return source.fetch_cmoney_stock_posts('6672'),calls


@pytest.mark.parametrize('invalid',['wrong_tag','mixed_tags','historical','future','external','shortener','self','multiple','no_comment','private','query','heading','unknown_date'])
def test_ineligible_parent_does_not_trigger_reference_network(monkeypatch,invalid):
    kwargs=dict(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',published='2026-10-9T10:1:1+08:00',body='值得持續觀察風險 '+REF)
    if invalid=='wrong_tag':kwargs['tags']=('2236百達-KY',)
    elif invalid=='mixed_tags':kwargs['tags']=('6672騰輝電子-KY','2236百達-KY')
    elif invalid=='historical':kwargs['published']='2026-08-9T10:1:1+08:00'
    elif invalid=='future':kwargs['published']='2026-10-10T10:1:1+08:00'
    elif invalid=='external':kwargs['body']='值得持續觀察風險 https://example.com/forum/article/185141811'
    elif invalid=='shortener':kwargs['body']='值得持續觀察風險 https://www.cmoney.tw/r/57/abc'
    elif invalid=='self':kwargs['body']='值得持續觀察風險 '+PARENT
    elif invalid=='multiple':kwargs['body']='值得持續觀察風險 '+REF+' https://example.com/'
    elif invalid=='no_comment':kwargs['body']=REF
    elif invalid=='private':kwargs['body']='值得持續觀察風險 https://www.cmoney.tw/private/article/185141811'
    elif invalid=='query':kwargs['body']='值得持續觀察風險 '+REF+'?session=not-a-real-secret'
    elif invalid=='heading':kwargs['heading']='其他股票看多'
    else:kwargs['published']='unknown'
    _,calls=run_pages(monkeypatch,pages_for_parent(article(**kwargs)))
    assert REF not in calls


@pytest.mark.parametrize('invalid',['wrong_stock','historical','future','external_body','recursive'])
def test_child_still_uses_existing_full_original_gate_and_never_recurses(monkeypatch,invalid):
    parent=article(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',published='2026-10-9T10:1:1+08:00',body='值得持續觀察風險 '+REF)
    kwargs=dict(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',published='2026-10-8T10:1:1+08:00',body='原文觀察仍維持風險控管。')
    if invalid=='wrong_stock':kwargs['tags']=('2236百達-KY',)
    elif invalid=='historical':kwargs['published']='2026-08-8T10:1:1+08:00'
    elif invalid=='future':kwargs['published']='2026-10-10T10:1:1+08:00'
    else:kwargs['body']='值得持續觀察風險 https://www.cmoney.tw/forum/article/185111111' if invalid=='recursive' else '原文 https://example.com/'
    rows,calls=run_pages(monkeypatch,pages_for_parent(parent,article(**kwargs)))
    assert calls.count(REF)==1
    assert rows==[] and 'https://www.cmoney.tw/forum/article/185111111' not in calls


def test_only_one_reference_attempt_is_added_to_bounded_acquisition(monkeypatch):
    second_parent='https://www.cmoney.tw/forum/article/185353828'
    second_ref='https://www.cmoney.tw/forum/article/185141813'
    finance=finance_listing(ticker='6672',company='騰輝電子-KY',article_id='185353826')
    finance=finance.replace(b'</ul>',b'<li grp="articleBlock" articleId="185353828"><a href="/forum/article/185353828">original</a></li></ul>')
    parent=lambda url:article(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',published='2026-10-9T10:1:1+08:00',body='值得持續觀察風險 '+url)
    pages=pages_for_parent(parent(REF),article(tags=('2236百達-KY',)))
    pages.update({source.FINANCE_URL.format(ticker='6672'):finance,second_parent:parent(second_ref),second_ref:article(tags=('6672騰輝電子-KY',))})
    _,calls=run_pages(monkeypatch,pages)
    assert calls.count(REF)==1 and second_ref not in calls


def test_reference_also_in_index_is_not_downloaded_or_counted_twice(monkeypatch):
    parent=article(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',published='2026-10-9T10:1:1+08:00',body='值得持續觀察風險 '+REF)
    pages=pages_for_parent(parent)
    pages[source.FINANCE_URL.format(ticker='6672')]=pages[source.FINANCE_URL.format(ticker='6672')].replace(b'</ul>',b'<li grp="articleBlock" articleId="185141811"><a href="/forum/article/185141811">original</a></li></ul>')
    rows,calls=run_pages(monkeypatch,pages)
    assert [row['link']for row in rows]==[REF] and calls.count(REF)==1


def test_nearly_exhausted_source_deadline_never_starts_reference(monkeypatch):
    parent=article(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',published='2026-10-9T10:1:1+08:00',body='值得持續觀察風險 '+REF)
    monkeypatch.setattr(source,'ACQUISITION_SECONDS',0.05)
    rows,calls=run_pages(monkeypatch,pages_for_parent(parent))
    assert rows==[] and REF not in calls


def test_rejected_reference_also_in_direct_index_reuses_raw_bytes(monkeypatch):
    parent=article(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',published='2026-10-9T10:1:1+08:00',body='值得持續觀察風險 '+REF)
    pages=pages_for_parent(parent,article(tags=('2236百達-KY',)))
    pages[source.FINANCE_URL.format(ticker='6672')]=pages[source.FINANCE_URL.format(ticker='6672')].replace(b'</ul>',b'<li grp="articleBlock" articleId="185141811"><a href="/forum/article/185141811">original</a></li></ul>')
    rows,calls=run_pages(monkeypatch,pages)
    assert rows==[] and calls.count(REF)==1


@pytest.mark.parametrize('extra',[' www.example.com/',' <a href="https://example.com/private">另一個入口</a>',
                                  ' <a href="https://example.com/private">'+REF+'</a>'])
def test_unverified_other_body_links_never_trigger_reference(monkeypatch,extra):
    parent=article(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',published='2026-10-9T10:1:1+08:00',body='值得持續觀察風險 '+(extra if REF in extra else REF+extra))
    _,calls=run_pages(monkeypatch,pages_for_parent(parent))
    assert REF not in calls


@pytest.mark.parametrize('stamp,expected',[('2026-10-08T02:01:01+00:00',1),('2026-10-07T02:01:01+00:00',0)])
def test_reused_original_still_uses_each_listing_company_and_timestamp(monkeypatch,stamp,expected):
    pages={source.FINANCE_URL.format(ticker='6672'):finance_listing(ticker='6672',company='騰輝電子',article_id='185141811'),
           REF:article(tags=('6672騰輝電子-KY',),heading='騰輝電子-KY 看多',body='原文觀察仍維持風險控管。',published='2026-10-8T10:1:1+08:00'),
           source.STOCK_URL.format(ticker='6672'):listing(ticker='6672',company='騰輝電子-KY',article='185141811',stamp=stamp)}
    rows,calls=run_pages(monkeypatch,pages)
    assert len(rows)==expected and calls.count(REF)==1
