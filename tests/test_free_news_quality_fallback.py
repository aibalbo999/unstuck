"""Normal news acquisition expands only when usable company evidence is short."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from data_fetch.enrichment_providers import FreeNewsWaterfallProvider
from data_fetch.types import FetchRequest
from external_data_client import ExternalDataClient


def news(index, *, name='豐藝', days=1, publisher=None):
    publisher = publisher or f'publisher{index % 3}'
    return {'title': f'{name} 營運消息 {index}', 'summary': f'{name} 營收及產品展望',
            'published_date': (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(),
            'source': publisher, 'link': f'https://{publisher}.example/news/{index}'}


def fetch(monkeypatch, google, fallback):
    import external_data_client
    calls = []
    def ddg(*args, **kwargs):
        calls.append(kwargs)
        if isinstance(fallback, Exception):
            raise fallback
        return deepcopy(fallback)
    client = ExternalDataClient(google_news=lambda *a, **k: deepcopy(google), ddg_news=ddg)
    monkeypatch.setattr(external_data_client, 'ExternalDataClient', lambda: client)
    context = {'data': {'ticker': '6189.TW', 'company_name': '豐藝',
                        'company_identity': {'official_name': '豐藝電子股份有限公司'}}}
    before = deepcopy(context)
    result = FreeNewsWaterfallProvider().fetch(FetchRequest.from_ticker('6189.TW'), context)
    assert context == before
    return result, calls


@pytest.mark.parametrize('google', [
    [news(0)],
    [news(i, days=100) for i in range(20)],
    [news(i, name='其他公司') for i in range(20)],
    [news(i, publisher='same') for i in range(8)],
])
def test_insufficient_usable_google_results_expand_once(monkeypatch, google):
    result, calls = fetch(monkeypatch, google, [news(i) for i in range(30, 38)])
    assert len(calls) == 1, 'Nonempty raw Google results must not suppress free fallback'
    assert calls[0]['limit'] == 20
    assert len(result.value) == 8
    assert result.audit['news_selection']['publisher_count'] >= 3
    assert [x['provider'] for x in result.audit['related_entries']] == ['Google News RSS', 'DuckDuckGo News']
    if len(google) == 20:
        assert result.audit['rejected_count'] == 20
        assert len(result.audit['source_record_archive']) == 20


def test_sufficient_google_does_not_fetch_fallback(monkeypatch):
    result, calls = fetch(monkeypatch, [news(i) for i in range(8)], [news(30)])
    assert len(result.value) == 8
    assert calls == []


@pytest.mark.parametrize('fallback', [[], TimeoutError('upstream timeout')])
def test_failed_fallback_preserves_google_and_does_not_retry(monkeypatch, fallback):
    first = news(0)
    result, calls = fetch(monkeypatch, [first], fallback)
    assert len(calls) == 1
    assert [r['link'] for r in result.value] == [first['link']]
    assert result.audit['related_entries'][-1]['status'] == ('error' if isinstance(fallback, Exception) else 'unavailable')


def test_duplicate_news_from_fallback_does_not_inflate_count(monkeypatch):
    result, calls = fetch(monkeypatch, [news(0)], [news(0), news(1)])
    assert len(calls) == 1
    assert len(result.value) == 2


@pytest.mark.parametrize('link,reason', [
    ('https://www.cmoney.tw/forum/article/166736289', 'forum_post_is_not_news'),
    ('https://www.cmoney.tw/finance/6189/f00025', 'stock_overview_is_not_news'),
])
def test_free_search_direct_non_news_cannot_fill_last_slot(monkeypatch, link, reason):
    candidate = news(30, publisher='CMoney')
    candidate['link'] = link
    result, calls = fetch(monkeypatch, [news(i) for i in range(7)], [candidate])
    assert len(calls) == 1
    assert len(result.value) == 7
    assert result.audit['rejected_reason_counts'] == {reason: 1}


@pytest.mark.parametrize('link', [
    'https://news.google.com/rss/articles/wiki-example',
    'https://www.moneydj.com/KMDJ/wiki/wikiviewer.aspx?keyid=dad7457e-7057-46e1-bb4a-17874cead4ac',
])
def test_moneydj_company_encyclopedia_is_not_recent_news_and_stays_archived(link):
    from source_content_selection import select_company_records
    from news_freshness_policy import apply_news_only_freshness
    company = {'ticker': '6189.TW', 'company_name': '豐藝'}
    row = news(0, publisher='MoneyDJ')
    row.update(title='豐藝電子股份有限公司 - MoneyDJ', link=link)
    rows, audit = select_company_records([row], company)
    assert rows == [], 'A company encyclopedia update is not a recent catalyst'
    assert audit['rejected_reason_counts'] == {'indexed_non_article_unverified': 1}
    assert audit['source_record_archive'][0]['record'] == row
    saved = {**company, 'recent_catalysts': [row]}
    apply_news_only_freshness(saved)
    assert saved['recent_catalysts'] == []
    assert saved['unverified_catalysts'][0]['source_role_status'] == 'indexed_non_article_unverified'


@pytest.mark.parametrize('title,publisher', [
    ('豐藝電子股份有限公司公布營收成長 - MoneyDJ', 'MoneyDJ'),
    ('豐藝電子股份有限公司 - Other News', 'Other News'),
])
def test_editorial_news_is_not_rejected_as_company_encyclopedia(title, publisher):
    from source_content_selection import select_company_records
    row = news(0, publisher=publisher)
    row.update(title=title, link='https://news.google.com/rss/articles/editorial-example')
    rows, audit = select_company_records([row], {'ticker': '6189.TW', 'company_name': '豐藝'})
    assert len(rows) == 1 and not audit['rejected_count']


@pytest.mark.parametrize('days,period', [(1, 'd'), (7, 'w'), (30, 'm'), (90, 'y')])
def test_ddg_translates_google_recency_operator_to_native_search(monkeypatch, days, period):
    import news_fetchers
    calls = []
    class Client:
        def news(self, **kwargs):
            calls.append(kwargs)
            return []
    monkeypatch.setattr(news_fetchers, 'DDGS', Client)
    news_fetchers.fetch_duckduckgo_news(f'"豐藝" 6189 when:{days}d', limit=20)
    assert calls == [{'query': '"豐藝" 6189', 'max_results': 20,
                      'timelimit': period, 'region': 'tw-tzh'}]


def test_ddg_us_query_keeps_region_default_and_plain_query_unchanged(monkeypatch):
    import news_fetchers
    calls = []
    class Client:
        def news(self, **kwargs):
            calls.append(kwargs)
            return []
    monkeypatch.setattr(news_fetchers, 'DDGS', Client)
    news_fetchers.fetch_duckduckgo_news('"Apple" AAPL when:30d')
    news_fetchers.fetch_duckduckgo_news('TSMC')
    assert calls == [{'query': '"Apple" AAPL', 'max_results': 10, 'timelimit': 'm'},
                     {'query': 'TSMC', 'max_results': 10}]
