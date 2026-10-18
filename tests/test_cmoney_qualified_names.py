"""Recognize actual exchange affixes while keeping issuer/date/body checks."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from data_fetch.market_sources.cmoney_stock_posts import (
    fetch_cmoney_stock_posts, parse_finance_listing, parse_stock_listing, parse_stock_article,
)
from test_cmoney_stock_posts import listing, article, finance_listing


NOW = datetime(2026, 10, 9, 14, tzinfo=timezone.utc)


@pytest.mark.parametrize('ticker,company', [('6672', '騰輝電子-KY'), ('2236', '百達-KY'), ('9103', '美德醫療-DR')])
def test_qualified_name_survives_both_indexes_and_exact_original_tag(ticker, company):
    url = 'https://www.cmoney.tw/forum/article/185356984'
    name, finance = parse_finance_listing(finance_listing(ticker=ticker, company=company,
        article_id='185356984'), ticker)
    assert name == company and finance == [(url, None)]
    name, stock = parse_stock_listing(listing(ticker=ticker, company=company,
        article='185356984', stamp='2026-10-08T02:01:01+00:00'), ticker, now=NOW)
    assert name == company and len(stock) == 1
    raw = article(tags=(ticker+company,), heading=company+' 看多', published='2026-10-8T10:1:1+08:00',
                  body='觀察股價與風險，沒有交易結論。')
    record = parse_stock_article(raw, ticker, company, stock[0], now=NOW)
    assert record is not None and record['source_tag'] == ticker+company
    assert record['response_sha256'] == sha256(raw).hexdigest()
    assert record['response_bytes'] == len(raw)
    assert record['parser_version'] == 'cmoney-stock-posts-v2'


@pytest.mark.parametrize('company', ['騰輝電子-ABC', '騰輝電子-KYABC', '騰輝電子-KY-DR', '騰輝電子-Ky'])
def test_unrecognized_or_combined_affix_stays_rejected(company):
    assert parse_finance_listing(finance_listing(ticker='6672', company=company), '6672') == ('', [])
    assert parse_stock_listing(listing(ticker='6672', company=company), '6672', now=NOW) == ('', [])


@pytest.mark.parametrize('change', ['wrong_ticker','wrong_name','historical','link','mixed_issuer'])
def test_market_affix_does_not_remove_existing_original_admission_checks(change):
    ticker,company='9103','美德醫療-DR'
    kwargs=dict(tags=(ticker+company,), heading=company+' 看多', published='2026-10-8T10:1:1+08:00',
                body='觀察股價與風險，沒有交易結論。')
    if change=='wrong_ticker':kwargs['tags']=('6672騰輝電子-KY',)
    elif change=='wrong_name':kwargs['tags']=('9103百達-KY',)
    elif change=='historical':kwargs['published']='2026-08-8T10:1:1+08:00'
    elif change=='link':kwargs['body']='轉貼 https://example.com/新聞'
    else:kwargs.update(tags=('9103美德醫療-DR','6672騰輝電子-KY'),body='美德醫療-DR與騰輝電子-KY都有機會')
    assert parse_stock_article(article(**kwargs),ticker,company,
        ('https://www.cmoney.tw/forum/article/185356984',None),now=NOW) is None


@pytest.mark.parametrize('ticker,company', [('2308', '台達電'), ('9103', '美德醫療-DR')])
@pytest.mark.parametrize('peer_tag,peer_core', [('6672騰輝電子-KY', '騰輝電子'), ('9105泰金寶-DR', '泰金寶')])
def test_other_tagged_issuer_without_market_affix_is_still_mixed_content(ticker, company, peer_tag, peer_core):
    raw = article(tags=(ticker + company, peer_tag), heading=company + ' 看多',
                  published='2026-10-8T10:1:1+08:00', body=company + '與' + peer_core + '都有機會。')
    assert parse_stock_article(raw, ticker, company,
        ('https://www.cmoney.tw/forum/article/185356984', None), now=NOW) is None


@pytest.mark.parametrize('ticker,company', [('2308', '台達電'), ('9103', '美德醫療-DR')])
@pytest.mark.parametrize('peer_tag', ['6672騰輝電子-KY', '9105泰金寶-DR'])
def test_affixed_peer_tag_without_peer_in_body_keeps_explicit_target_sample(ticker, company, peer_tag):
    raw = article(tags=(ticker + company, peer_tag), heading=company + ' 看多',
                  published='2026-10-8T10:1:1+08:00', body=company + '值得繼續觀察風險。')
    record = parse_stock_article(raw, ticker, company,
        ('https://www.cmoney.tw/forum/article/185356984', None), now=NOW)
    assert record is not None and record['evidence_kind'] == 'explicit_target_multitag_forum_post'


def test_captured_dr_post_reaches_public_provider_without_new_http(monkeypatch):
    from data_fetch.market_sources import cmoney_stock_posts as source
    fixture=json.loads((Path(__file__).parent/'fixtures/source_acquisition/cmoney_9103_qualified_name_20261009.json').read_text())
    pages={entry['url']:entry['selected_html'].encode() for entry in fixture['pages']}
    calls=[]
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(source,'_now',lambda:datetime.fromisoformat(fixture['reference_now']))
    monkeypatch.setattr(source,'_download',lambda url,**kw:calls.append(url) or pages[url])
    records=fetch_cmoney_stock_posts('9103')
    assert len(records)==3
    assert all(r['source_tag']=='9103美德醫療-DR' and r['sentiment_assessment']=='not_assessed' for r in records)
    assert all(r['response_sha256'] for r in records)
    assert source.STOCK_URL.format(ticker='9103') not in calls


def test_captured_dr_posts_keep_hashes_after_real_company_selection(monkeypatch):
    from data_fetch.market_sources import cmoney_stock_posts as source
    from data_fetch.agent_context_providers import SocialSentimentProvider
    from data_fetch.types import FetchRequest
    import news_freshness_policy

    fixture = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/cmoney_9103_qualified_name_20261009.json').read_text())
    pages = {entry['url']: entry['selected_html'].encode() for entry in fixture['pages']}
    reference = datetime.fromisoformat(fixture['reference_now'])
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    monkeypatch.setattr(source, '_now', lambda: reference)
    monkeypatch.setattr(source, '_download', lambda url, **kwargs: pages[url])
    monkeypatch.setattr(news_freshness_policy, 'news_cutoff', lambda value=None: reference)
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('9103.TW'),
        {'data': {'ticker': '9103.TW', 'company_name': '美德醫療-DR / Medtecs International Corporation Limited'}})
    assert result.status == 'success' and result.audit['record_count'] == 3
    rows = result.value['cmoney_stock_direct']
    assert all(row['issuer_match'] == '美德醫療-dr' for row in rows)
    assert all(row['response_sha256'] == sha256(pages[row['link']]).hexdigest() for row in rows)
    assert result.value['yahoo_stock_direct'] == result.value['ptt_stock_direct'] == []
    assert result.value['sentiment_assessment'] == 'not_assessed'
