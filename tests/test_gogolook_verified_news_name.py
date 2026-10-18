"""The captured exchange label and native RSS stay bound to issuer 6902."""
from datetime import datetime, timezone
from pathlib import Path
import gzip
import json
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest


FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'


def captured():
    meta = json.loads((FIXTURES / 'gogolook_brand_query_native_20261011.json').read_text())
    raw = gzip.decompress((FIXTURES / 'gogolook_brand_query_native_20261011.xml.gz').read_bytes())
    records = [{'title': item.findtext('title'), 'summary': item.findtext('description'),
                'date': item.findtext('pubDate'), 'source': item.findtext('source'),
                'link': item.findtext('link')} for item in ET.fromstring(raw).findall('./channel/item')]
    return meta, records


def test_captured_issuer_brand_name_keeps_six_articles_and_excludes_indexed_pages():
    from hashlib import sha256
    from data_fetch.market_sources.official_company_legal_name import parse_roster
    from company_news_queries import company_news_query
    from source_content_selection import select_company_records
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    meta, records = captured()
    original = gzip.decompress((FIXTURES / 'gogolook_company_roster_native_20261011.json.gz').read_bytes())
    assert sha256(original).hexdigest() == meta['roster_sha256']
    assert parse_roster(original, '.TW')['entries']['6902'] == meta['captured_current_issuer']
    data = meta['company_data']
    assert company_news_query(data) == '"Gogolook" 6902 when:30d'
    cutoff = datetime.fromtimestamp(meta['rss_retrieved_at'], timezone.utc)
    selected, diagnostics = select_company_records(records, data, cutoff=cutoff, lookback_days=30)
    assert len(selected) == 6 and diagnostics['rejected_reason_counts'] == {
        'issuer_unverified': 1, 'indexed_non_article_unverified': 2}
    excluded = [v['record'] for v in diagnostics['source_record_archive']
                if v['reason'] == 'indexed_non_article_unverified']
    assert len(excluded) == 2
    assert any('股市爆料同學會' in r['title'] for r in excluded)
    assert any('股東人數' in r['title'] for r in excluded)
    typed = [SearchResult(r['title'], r['summary'], r['link'], r['source'], r['date']) for r in selected]
    assert not search_quality_satisfied(typed, max_results=8, query='Gogolook', lookback_days=30,
                                        require_recent=True, cutoff=cutoff)


@pytest.mark.parametrize('field,value', [
    ('ticker', '6902.TWO'), ('stock_id', '6924'), ('instrument_type', 'ETF'),
    ('official_name', '另一家公司'), ('legal_name', '另一家股份有限公司'),
    ('official_ubn', '00000001'), ('forbidden_aliases', ['Gogolook']),
    ('legal_name', []), ('official_name', {}), ('official_ubn', []),
])
def test_context_conflict_or_malformed_identity_never_adds_new_brand_alias(field, value):
    from company_news_queries import company_news_query
    from source_content_selection import issuer_match
    meta, _ = captured()
    data = deepcopy(meta['company_data'])
    data['company_identity'][field] = value
    assert not company_news_query(data).startswith('"Gogolook"')
    assert issuer_match({'title': 'Gogolook announces a new service'}, data) is None


def test_common_chinese_phrase_and_partial_english_word_are_not_new_company_evidence():
    from source_content_selection import issuer_match
    meta, _ = captured()
    assert issuer_match({'title': '我們走著瞧再說'}, meta['company_data']) is None
    assert issuer_match({'title': 'A pseudogogolooking term'}, meta['company_data']) is None


@pytest.mark.parametrize('forbidden', [False, 0, {}, '', ['<b>Gogolook</b>'],
                                     ['* Gogolook *'], ['Ｇｏｇｏｌｏｏｋ'], [None]])
def test_malformed_or_formatted_forbidden_name_never_enables_new_brand_query(forbidden):
    from company_news_queries import company_news_query
    from source_content_selection import issuer_match
    meta, _ = captured()
    data = deepcopy(meta['company_data'])
    data['company_identity']['forbidden_aliases'] = forbidden
    assert not company_news_query(data).startswith('"Gogolook"')
    assert issuer_match({'title': 'Gogolook announces a new service'}, data) is None


def test_public_search_uses_verified_brand_for_both_existing_queries_and_keeps_provider_budget(monkeypatch):
    import asyncio
    import external_search_providers as search
    from external_search_types import SearchResult
    import data_fetch.market_sources.ltn_stock_news as ltn
    meta, records = captured()
    cutoff = datetime.fromtimestamp(meta['rss_retrieved_at'], timezone.utc)
    class CapturedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cutoff.astimezone(tz) if tz else cutoff.replace(tzinfo=None)
    monkeypatch.setattr(search, 'datetime', CapturedClock)
    calls = []
    async def upstream(query, **kwargs):
        calls.append((query, kwargs))
        native_query = kwargs['provider_queries']['google_news_rss']
        assert (native_query.startswith('"Gogolook" 6902 when:30d') if len(calls) == 1
                else native_query == '"Gogolook" when:30d')
        assert kwargs['provider_allowlist'] == {'google_news_rss'}
        assert kwargs['max_results'] == 8 and kwargs['lookback_days'] == 30
        chosen = records[:1] if len(calls) == 1 else records
        return [SearchResult(r['title'], r['summary'], r['link'], r['source'], r['date'],
                             provider='google_news_rss') for r in chosen]
    monkeypatch.setattr(search, 'fetch_web_search_results_async', upstream)
    publisher_calls = []
    def publisher_originals(*a, **k):
        publisher_calls.append((a, k))
        return []
    monkeypatch.setattr(ltn, 'fetch_ltn_stock_news', publisher_originals)
    data = meta['company_data']
    result = asyncio.run(search.fetch_alternative_search_catalysts_async(
        data['ticker'], data['company_name'], data['company_identity'],
        company_context=data,
        provider_allowlist={'google_news_rss'}))
    assert len(calls) == 2 and len(result) == 6
    assert len(publisher_calls) == 1 and publisher_calls[0][1]['max_records'] == 2
    assert calls[1][1]['provider_queries']['google_news_rss'] == '"Gogolook" when:30d'
    assert data['company_identity']['official_name'] == 'GOGOLOOK-創'
