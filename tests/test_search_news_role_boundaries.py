"""Search delivery must not turn known forums/overviews into news evidence."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html import escape
from urllib.parse import quote
import pytest

@pytest.mark.parametrize('url,title', [
 ('https://www.cmoney.tw/forum/article/166736289', '台積電(2330)最新討論 - 股市爆料同學會'),
 ('https://www.cmoney.tw/finance/2330/f00025', '台積電(2330) 個股概覽 | 個股 - 股市'),
])
def test_bing_known_non_news_must_not_complete_eighth_slot(monkeypatch, url, title):
    import external_search_providers as search
    from external_search_payloads import parse_news_rss_payload
    stamp = format_datetime(datetime.now(timezone.utc) - timedelta(hours=1))
    items = []
    for i in range(7):
        items.append((f'https://publisher{i%2}.example/news/{i}', f'台積電營收展望新聞 {i}', f'publisher{i%2}'))
    items.append((url,title,'CMoney'))
    rss = '<rss xmlns:news="https://www.bing.com/news/search"><channel>' + ''.join(
        '<item><title>'+escape(t)+'</title><description>台積電近期營運資料</description><pubDate>'+stamp+'</pubDate><link>'+escape('https://www.bing.com/news/apiclick.aspx?url='+quote(u,safe=''))+'</link><news:Source>'+s+'</news:Source></item>' for u,t,s in items) + '</channel></rss>'
    observed = parse_news_rss_payload(rss, provider='bing_news_rss', fallback_source='Bing News RSS')
    @asynccontextmanager
    async def client(): yield object()
    async def upstream(*a,**k): return observed
    monkeypatch.setattr(search,'async_client',client)
    monkeypatch.setattr(search,'_provider_order',lambda:['bing_news_rss'])
    monkeypatch.setattr(search,'_fetch_provider_results',upstream)
    diagnostics = {}
    rows = asyncio.run(search.fetch_alternative_search_catalysts_async('2330.TW','台積電',{'official_name':'台積電'}, diagnostics=diagnostics, provider_allowlist={'bing_news_rss'}))
    assert not any(r['link']==url for r in rows), 'Known non-news URL retained as eighth news and publisher'
    assert diagnostics['quality_status'] == 'insufficient_candidates'


@pytest.mark.parametrize('source_type', ['bing_news_rss_search', 'google_news_rss_search', 'tavily_search', 'yahoo_rss_search', 'finmind_news'])
@pytest.mark.parametrize('url,reason', [
    ('https://www.cmoney.tw/forum/article/166736289', 'forum_post_is_not_news'),
    ('https://www.cmoney.tw/finance/2330/f00025', 'stock_overview_is_not_news'),
])
def test_saved_search_non_news_stays_unverified_and_keeps_social(source_type, url, reason):
    from copy import deepcopy
    from news_freshness_policy import apply_news_only_freshness
    record = {'title': '台積電(2330) 資料', 'date': '2026-10-15T01:00:00+00:00',
              'link': url, 'source': 'CMoney', 'source_type': source_type}
    social = {'separate_original': True}
    data = {'ticker': '2330.TW', 'company_name': '台積電', 'recent_catalysts': [record],
            'social_sentiment': deepcopy(social)}
    apply_news_only_freshness(data, cutoff='2026-10-15T02:00:00+00:00')
    assert data['recent_catalysts'] == []
    assert data['news_selection']['eligible_count'] == 0
    assert data['unverified_catalysts'][0]['source_role_status'] == reason
    assert data['unverified_catalysts'][0]['link'] == url
    assert data['social_sentiment'] == social
    once = deepcopy(data)
    apply_news_only_freshness(data, cutoff='2026-10-15T02:00:00+00:00')
    assert data == once
