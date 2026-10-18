"""A captured 2254 issuer alias recovers evidence with original search gates."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import gzip
import json

import pytest

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'


def captured():
    from external_search_payloads import parse_news_rss_payload
    meta = json.loads((FIXTURES / 'coplus_verified_local_name_native_20261011.json').read_text())
    raw = gzip.decompress((FIXTURES / 'coplus_verified_local_name_native_20261011.xml.gz').read_bytes())
    assert sha256(raw).hexdigest() == meta['RSS_sha256']
    records = [{'title': r.title, 'summary': r.snippet, 'date': r.published_at,
                'link': r.link, 'source': r.source} for r in parse_news_rss_payload(
                    raw.decode('utf8'), provider='google_news_rss', fallback_source='Google News RSS')]
    return meta, records


def test_public_query_and_captured_selection_recover_eight_with_original_code_time_and_quality():
    from company_news_queries import company_news_query
    from source_content_selection import select_company_records
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    meta, records = captured()
    master = gzip.decompress((FIXTURES / 'coplus_company_roster_native_20261011.json.gz').read_bytes())
    assert sha256(master).hexdigest() == meta['roster_sha256']
    row = next(v for v in json.loads(master) if v.get('公司代號') == '2254')
    assert {k: row[k] for k in meta['captured_current_issuer']} == meta['captured_current_issuer']
    data = deepcopy(meta['company_data']); before = deepcopy(data)
    assert company_news_query(data) == '"巨鎧精密" 2254 when:30d'
    cutoff = datetime.fromtimestamp(meta['RSS_retrieved_at'], timezone.utc)
    selected, diagnostics = select_company_records(records, data, cutoff=cutoff, lookback_days=30)
    assert len(selected) == 8 and diagnostics['rejected_count'] == 0
    typed = [SearchResult(r['title'], r['summary'], r['link'], r['source'], r['date']) for r in selected]
    assert search_quality_satisfied(typed, max_results=8, query='巨鎧精密',
                                    lookback_days=30, require_recent=True, cutoff=cutoff)
    assert data == before


@pytest.mark.parametrize('field,value', [
    ('ticker', '2254.TWO'), ('stock_id', '6924'), ('instrument_type', 'ETF'),
    ('official_name', '另一家公司'), ('legal_name', '另一家股份有限公司'),
    ('official_ubn', '00000001'), ('legal_name', []), ('official_name', {}),
    ('official_ubn', []), ('forbidden_aliases', ['巨鎧精密']),
    ('forbidden_aliases', ['<b>巨鎧精密</b>']), ('forbidden_aliases', ['* 巨鎧精密 *']),
    ('forbidden_aliases', False), ('forbidden_aliases', {}), ('forbidden_aliases', [None]),
])
def test_conflict_malformed_or_forbidden_identity_does_not_add_the_local_alias(field, value):
    from company_news_queries import company_news_query
    from source_content_selection import issuer_match
    meta, _ = captured(); data = deepcopy(meta['company_data'])
    data['company_identity'][field] = value
    assert not company_news_query(data).startswith('"巨鎧精密"')
    assert issuer_match({'title': '熱門股－巨鎧精密 成功收復周線'}, data) is None


def test_other_innovation_board_name_without_verified_scope_is_not_stripped():
    from company_news_queries import company_news_query
    from source_content_selection import issuer_match
    data = {'ticker': '6924.TW', 'company_name': '榮惠-KY創',
            'company_identity': {'ticker': '6924.TW', 'stock_id': '6924',
                                 'official_name': '榮惠-KY創', 'allowed_aliases': ['榮惠-KY創']}}
    assert company_news_query(data) == '"榮惠-KY創" 6924 when:30d'
    assert issuer_match({'title': '榮惠-KY 營收消息'}, data) is None


def test_two_original_search_queries_use_the_same_bound_alias_and_stop_at_original_budget(monkeypatch):
    import asyncio
    import external_search_providers as search
    from external_search_types import SearchResult
    import data_fetch.market_sources.ltn_stock_news as ltn
    meta, records = captured(); cutoff = datetime.fromtimestamp(meta['RSS_retrieved_at'], timezone.utc)
    class CapturedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cutoff.astimezone(tz) if tz else cutoff.replace(tzinfo=None)
    monkeypatch.setattr(search, 'datetime', CapturedClock)
    calls = []
    async def upstream(query, **kwargs):
        calls.append((query, kwargs))
        native_query = kwargs['provider_queries']['google_news_rss']
        assert (native_query.startswith('"巨鎧精密" 2254 when:30d') if len(calls) == 1
                else native_query == '"巨鎧精密" when:30d')
        assert kwargs['max_results'] == 8 and kwargs['lookback_days'] == 30
        assert kwargs['provider_allowlist'] == {'google_news_rss'}
        chosen = records[:1] if len(calls) == 1 else records
        return [SearchResult(r['title'], r['summary'], r['link'], r['source'], r['date'],
                             provider='google_news_rss') for r in chosen]
    monkeypatch.setattr(search, 'fetch_web_search_results_async', upstream)
    monkeypatch.setattr(ltn, 'fetch_ltn_stock_news', lambda *a, **k: pytest.fail('sufficient candidates stop publisher fallback'))
    data = meta['company_data']; before = deepcopy(data)
    result = asyncio.run(search.fetch_alternative_search_catalysts_async(
        data['ticker'], data['company_name'], data['company_identity'], company_context=data,
        provider_allowlist={'google_news_rss'}))
    assert len(calls) == 2 and len(result) == 8 and data == before
    assert calls[1][1]['provider_queries']['google_news_rss'] == '"巨鎧精密" when:30d'
