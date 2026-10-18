"""A fetched PTT article must retain issuer evidence in its author body."""
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import news_fetchers
import pytest

from data_fetch.agent_context_providers import SocialSentimentProvider
from data_fetch.types import FetchRequest


NOW = datetime(2026, 10, 9, 12, tzinfo=news_fetchers.TAIPEI_TZ)
STAMP = NOW - timedelta(days=1)
LINK = f'https://www.ptt.cc/bbs/Stock/M.{int(STAMP.timestamp())}.A.ABC.html'
DATA = {'ticker': '2308.TW', 'company_name': '台達電',
        'company_identity': {'official_name': '台達電'}}


def article(body, *, author='writer', push=''):
    metadata = ''.join(
        '<div class="article-metaline"><span class="article-meta-tag">'
        + key + '</span><span class="article-meta-value">' + value + '</span></div>'
        for key, value in (('作者', author), ('標題', '[標的] 2308'),
                           ('時間', STAMP.strftime('%a %b %d %H:%M:%S %Y'))))
    return (f'<div id="main-content">{metadata}{body}\n--\n'
            f'※ 發信站: 批踢踢實業坊(ptt.cc), 來自: 127.0.0.1\n'
            f'※ 文章網址: {LINK}<div class="push">{push}</div></div>')


@pytest.fixture
def source_boundary(monkeypatch):
    events, calls = [], []
    monkeypatch.setattr(news_fetchers, '_current_taipei_datetime', lambda: NOW)
    monkeypatch.setattr(news_fetchers, 'cooldown_state', lambda _key: {})
    monkeypatch.setattr(news_fetchers, 'record_observation', lambda *a, **kw: events.append(kw))
    monkeypatch.setattr(news_fetchers, 'remember_failure', lambda *a, **kw: {})
    monkeypatch.setattr('news_freshness_policy.news_cutoff', lambda *a, **kw: NOW)
    monkeypatch.setattr('data_fetch.market_sources.cmoney_stock_posts.fetch_cmoney_stock_posts', lambda *a, **kw: [])
    monkeypatch.setattr('data_fetch.market_sources.yahoo_stock_comments.fetch_yahoo_stock_comments', lambda *a, **kw: [])

    def install(raw_article):
        search = (f'<div class="r-list-container"><div class="r-ent"><div class="title">'
                  f'<a href="{LINK}">[標的] 2308</a></div><div class="date">10/8</div></div></div>')
        responses = iter([search, raw_article])

        def get(url, **kwargs):
            calls.append(url)
            raw = next(responses).encode()
            return SimpleNamespace(status_code=200, content=raw, text=raw.decode())

        monkeypatch.setattr(news_fetchers, 'sync_get', get)

    return install, calls, events


def test_public_fetch_retains_author_text_and_original_response_hash(source_boundary):
    install, calls, _events = source_boundary
    raw = article('1. 標的：2308 台達電<br>正文：觀察公司營運與風險。', push='別人的留言')
    install(raw)
    rows = news_fetchers.fetch_ptt_stock_sentiment('2308', limit=5)
    assert len(rows) == 1 and len(calls) == 2
    assert '台達電' in rows[0].get('text', '')
    assert '別人的留言' not in rows[0]['text']
    assert '發信站' not in rows[0]['text']
    assert rows[0]['response_sha256'] == sha256(raw.encode()).hexdigest()
    assert rows[0]['text_truncated'] is False


def test_provider_keeps_body_only_issuer_match_without_relaxing_selector(source_boundary):
    install, _calls, _events = source_boundary
    raw = article('1. 標的：2308 台達電<br>正文：觀察公司營運與風險。')
    install(raw)
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('2308.TW'), {'data': DATA})
    assert result.audit['record_count'] == 1
    assert result.status == 'success'
    record = result.value['ptt_stock_direct'][0]
    assert record['issuer_match'] == '台達電'
    assert '台達電' in record['text']
    assert record['response_sha256'] == sha256(raw.encode()).hexdigest()
    assert result.value['sentiment_assessment'] == 'not_assessed'


@pytest.mark.parametrize('author,push', [('台達電分析家', ''), ('writer', '台達電')])
def test_author_handle_or_push_does_not_supply_body_issuer_evidence(source_boundary, author, push):
    install, _calls, _events = source_boundary
    install(article('只討論一般市場風險。', author=author, push=push))
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('2308.TW'), {'data': DATA})
    assert result.audit['record_count'] == 0
    assert result.status == 'degraded_enrichment'


def test_long_body_is_bounded_and_explicitly_marked_as_excerpt(source_boundary):
    install, _calls, _events = source_boundary
    install(article('台達電正文。' + '長文內容。' * 2000))
    rows = news_fetchers.fetch_ptt_stock_sentiment('2308', limit=5)
    assert len(rows) == 1
    assert 0 < len(rows[0].get('text', '')) <= 2000
    assert rows[0]['text_truncated'] is True
    assert rows[0]['body_text_chars'] > len(rows[0]['text'])
    assert len(rows[0]['body_text_sha256']) == 64


def test_captured_article_explicit_body_code_survives_missing_company_alias(source_boundary, monkeypatch):
    captured = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/ptt_2308_body_20261009.json').read_text())
    cutoff = datetime.fromisoformat(captured['replay_cutoff'])
    monkeypatch.setattr(news_fetchers, '_current_taipei_datetime', lambda: cutoff)
    monkeypatch.setattr('news_freshness_policy.news_cutoff', lambda *a, **kw: cutoff)
    search = ('<div class="r-list-container"><div class="r-ent"><div class="title">'
              f'<a href="{captured["source_url"]}">{captured["title"]}</a></div>'
              '<div class="date">9/9</div></div></div>')
    original = ('<div id="main-content"><div class="article-metaline">'
                '<span class="article-meta-tag">標題</span>'
                f'<span class="article-meta-value">{captured["title"]}</span></div>'
                '<div class="article-metaline"><span class="article-meta-tag">時間</span>'
                f'<span class="article-meta-value">{captured["timestamp_text"]}</span></div>'
                + captured['author_body_text'] + '</div>')
    responses = iter([search, original])
    monkeypatch.setattr(news_fetchers, 'sync_get', lambda *a, **kw: SimpleNamespace(
        status_code=200, text=(raw := next(responses)), content=raw.encode()))
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('2308.TW'),
        {'data': captured['replay_context']})
    assert result.audit['record_count'] == 1
    assert result.value['ptt_stock_direct'][0]['issuer_match'] == '2308'
    assert result.value['sentiment_assessment'] == 'not_assessed'


@pytest.mark.parametrize('prefix,gap', [('', ''), (': ', ''), ('> ', ' ')])
def test_quote_attribution_handle_is_not_company_body_evidence(source_boundary, prefix, gap):
    install, _calls, _events = source_boundary
    install(article(f'<span class="f2">{prefix}※ 引述{gap}《writer (台達電分析家)》之銘言：</span>'
                    '<br>只討論一般市場風險。'))
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('2308.TW'), {'data': DATA})
    assert result.audit['record_count'] == 0
    assert result.status == 'degraded_enrichment'


def test_quoted_station_footer_does_not_cut_following_author_body(source_boundary):
    install, _calls, _events = source_boundary
    install(article(': ※ 發信站: 批踢踢實業坊(ptt.cc), 來自: 127.0.0.2<br>'
                    ': ※ 文章網址: https://www.ptt.cc/bbs/Stock/M.1234567890.A.ABC.html<br>'
                    '我的正文是台達電營運與風險。'))
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('2308.TW'), {'data': DATA})
    assert result.audit['record_count'] == 1
    assert '我的正文是台達電營運與風險' in result.value['ptt_stock_direct'][0]['text']


def test_ordinary_f2_body_remains_evidence(source_boundary):
    install, _calls, _events = source_boundary
    install(article('<span class="f2">台達電營運與風險。</span>'))
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('2308.TW'), {'data': DATA})
    assert result.audit['record_count'] == 1
