"""A brokerage research author is not the subject of another stock's news."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import gzip
import json

import pytest

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'


def captured():
    from external_search_payloads import parse_news_rss_payload
    meta = json.loads((FIXTURES / 'psc_broker_subject_role_native_20261011.json').read_text())
    records = []
    for receipt in meta['raw_RSS']:
        raw = gzip.decompress((FIXTURES / receipt['file']).read_bytes())
        assert len(raw) == receipt['bytes'] and sha256(raw).hexdigest() == receipt['sha256']
        records += [{'title': r.title, 'summary': r.snippet, 'link': r.link,
                     'source': r.source, 'date': r.published_at}
                    for r in parse_news_rss_payload(raw.decode('utf8'), provider='google_news_rss',
                                                     fallback_source='Google News RSS')]
    return meta, records


def test_captured_two_queries_do_not_turn_four_other_subject_research_rows_into_broker_catalysts():
    from source_content_selection import select_company_records
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    meta, records = captured(); before = deepcopy(records); data = deepcopy(meta['company_data'])
    original = deepcopy(data); cutoff = datetime.fromisoformat(meta['cutoff'])
    selected, audit = select_company_records(records, data, cutoff=cutoff, lookback_days=30)
    assert len(selected) == 3
    # The formerly fourth row is an indexed forum repost, not an original article.
    non_articles = [r['record'] for r in audit['source_record_archive']
                    if r['reason'] == 'indexed_non_article_unverified']
    assert len(non_articles) == 1 and '股市爆料同學會' in non_articles[0]['title']
    excluded = [r['record'] for r in audit['source_record_archive'] if r['reason'] == 'issuer_not_subject']
    assert len(excluded) == 4
    assert sum('2330 台積電' in r['title'] for r in excluded) == 3
    assert sum('圓祥生技(6945)' in r['title'] for r in excluded) == 1
    typed = [SearchResult(r['title'], r['summary'], r['link'], r['source'], r['date']) for r in selected]
    assert not search_quality_satisfied(typed, max_results=8, query='統一證',
                                        require_recent=True, lookback_days=30, cutoff=cutoff)
    assert records == before and data == original


@pytest.mark.parametrize('title', [
    '2330 台積電 - 統一證券：台股整體技術面強勢- 股市爆料同學會 - CMoney',
    '２３３０ 台積電 - 統一證券：台股整體技術面強勢- 股市爆料同學會 - CMoney',
    '統一證券剛剛發布了一份圓祥生技(6945)的券商報告，目標價為205.00',
    '統一綜合證券發布了一份圓祥生技（6945）的券商報告',
])
def test_public_match_does_not_match_author_to_other_explicit_subject(title):
    from source_content_selection import issuer_match
    meta, _ = captured()
    assert issuer_match({'title': title, 'source': 'CMoney'}, meta['company_data']) is None


@pytest.mark.parametrize('title', [
    '統一證股價劍指新高- 日報 - 工商時報',
    '券商大賺！統一證前3季EPS創新高8.112元 大展證2.63元 - 品觀點',
    '統一證券：今年獲利創新高，介紹(6945)為客戶',
    '統一證券(2855)發布第三季財報，EPS創新高；圓祥生技(6945)券商報告僅為附件',
    '統一證券發布（2855）年度財報，自身獲利創高，並附台積電(2330)券商報告摘要',
    '2026 年統一證券(2855)年度獲利展望 - 股市爆料同學會 - CMoney',
    '2330 台積電 - 統一證券前3季EPS創新高 - 股市爆料同學會 - CMoney',
    '2855 統一證 - 統一證券年度獲利報告- 股市爆料同學會 - CMoney',
    '２８５５ 統一證 - 統一證券年度獲利報告- 股市爆料同學會 - CMoney',
])
def test_own_issuer_news_and_same_subject_stock_label_are_retained(title):
    from source_content_selection import issuer_match
    meta, _ = captured()
    assert issuer_match({'title': title, 'source': 'CMoney'}, meta['company_data']) is not None


def test_other_stock_keeps_research_about_its_own_explicit_subject():
    from source_content_selection import issuer_match
    data = {'ticker': '2330.TW', 'company_name': '台積電',
            'company_identity': {'ticker': '2330.TW', 'stock_id': '2330',
                                 'official_name': '台積電', 'allowed_aliases': ['台積電']}}
    record = {'title': '2330 台積電 - 統一證券：台積電技術面強勢- 股市爆料同學會 - CMoney',
              'source': 'CMoney'}
    assert issuer_match(record, data) is not None
