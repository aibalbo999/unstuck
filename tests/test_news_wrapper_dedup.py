"""A search wrapper and the matching publisher headline remain one article."""
from copy import deepcopy

import pytest

from news_freshness_policy import apply_news_only_freshness


TITLE = '《業績-電通》豐藝9月營收為25.56億元，年增6.41%'
WRAPPER = {'title': TITLE + ' - 富聯網', 'source': '富聯網',
           'link': 'https://news.google.com/rss/articles/example', 'date': '2026-10-08T06:18:00+00:00'}
DIRECT = {'title': TITLE, 'source': '富聯網',
          'link': 'https://ww2.money-link.com.tw/RealtimeNews/NewsContent.aspx?SN=6324383001',
          'date': '2026-10-09T00:39:23+00:00'}


def select(records):
    return apply_news_only_freshness({'ticker': '6189.TW', 'company_name': '豐藝'},
        records=records, cutoff='2026-10-16T00:40:00Z')


@pytest.mark.parametrize('records', [[WRAPPER, DIRECT], [DIRECT, WRAPPER]])
def test_same_headline_through_wrapper_and_original_counts_once(records):
    original = deepcopy(records)
    result = select(records)
    assert result['news_selection']['eligible_count'] == 1
    assert len(result['recent_catalysts']) == 1
    assert records == original
    assert result['recent_catalysts'][0]['title'] == records[0]['title']
    assert result['recent_catalysts'][0]['link'] == records[0]['link']
    again = apply_news_only_freshness(deepcopy(result), cutoff='2026-10-16T00:40:00Z')
    assert again == result


@pytest.mark.parametrize('changed', [
    {'title': TITLE + ' - 未核對媒體'},
    {'title': TITLE + ' - 富聯網', 'link': 'https://other.example/article'},
    {'title': TITLE + ' - 富聯網', 'source': 'Google News RSS'},
    {'title': TITLE + '，公司另公布展望 - 富聯網'},
])
def test_only_matching_publisher_suffix_on_google_wrapper_is_removed(changed):
    result = select([{**WRAPPER, **changed}, DIRECT])
    assert result['news_selection']['eligible_count'] == 2
