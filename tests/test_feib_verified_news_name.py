"""Captured issuer brands recover bank news without treating its FX column as news."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import gzip
import json
import pytest

F = Path(__file__).parent / 'fixtures/source_acquisition'


def captured(label='rss'):
    from external_search_payloads import parse_news_rss_payload
    meta = json.loads((F / 'feib_verified_news_native_20261011.json').read_text())
    proof = meta['receipts'][label]
    raw = gzip.decompress((F / proof['fixture']).read_bytes())
    assert sha256(raw).hexdigest() == proof['sha256'] and len(raw) == proof['bytes']
    rows = [{'title': x.title, 'summary': x.snippet, 'link': x.link,
             'date': x.published_at, 'source': x.source} for x in parse_news_rss_payload(
                 raw.decode('utf8'), provider='google_news_rss', fallback_source='Google News RSS')]
    return meta, rows[:20]


def test_captured_group_stock_website_and_brand_support_real_query_selection():
    from bs4 import BeautifulSoup
    from company_news_queries import company_news_query, company_search_name
    from source_content_selection import select_company_records
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    meta, rows = captured(); data = deepcopy(meta['data']); before = deepcopy(data)
    proof = meta['receipts']['group']; raw = gzip.decompress((F / proof['fixture']).read_bytes())
    assert sha256(raw).hexdigest() == proof['sha256']
    soup = BeautifulSoup(raw, 'html.parser'); text = soup.get_text(' ', strip=True)
    assert all(s in text for s in ['遠東國際商業銀行股份有限公司', '2845', '遠東商銀', '遠銀'])
    assert soup.find('a', href='https://www.feib.com.tw/')
    assert meta['roster']['營利事業統一編號'] == '86517096'
    assert company_search_name(data) == '遠東商銀'
    assert company_news_query(data) == '"遠銀" when:30d'
    cutoff = datetime.fromisoformat(meta['cutoff'])
    selected, _ = select_company_records(rows, data, cutoff=cutoff, lookback_days=30)
    assert len(selected) >= 8
    typed = [SearchResult(r['title'], r['summary'], r['link'], r['source'], r['date']) for r in selected]
    assert search_quality_satisfied(typed, max_results=8, query='遠東商銀', require_recent=True,
                                    lookback_days=30, cutoff=cutoff)
    assert data == before


@pytest.mark.parametrize('field,value', [
    ('ticker', '2845.TWO'), ('stock_id', '2883'), ('official_name', '另一家公司'),
    ('official_name', []), ('legal_name', '另一家股份有限公司'), ('legal_name', {}),
    ('official_ubn', '00000001'), ('official_ubn', []), ('instrument_type', 'ETF'),
    ('forbidden_aliases', ['遠銀']), ('forbidden_aliases', ['<b>遠東商銀</b>']),
    ('forbidden_aliases', ['* 遠銀 *']), ('forbidden_aliases', False),
    ('forbidden_aliases', [None]),
])
def test_conflict_forbidden_or_malformed_identity_keeps_new_bank_labels_unverified(field, value):
    from company_news_queries import company_news_query
    from source_content_selection import issuer_match
    meta, _ = captured(); data = deepcopy(meta['data']); data['company_identity'][field] = value
    assert company_news_query(data) != '"遠銀" when:30d'
    assert issuer_match({'title': '遠銀Bankee推出信貸服務'}, data) is None


def test_conflicting_root_instrument_or_stock_blocks_bank_alias():
    from company_news_queries import company_news_query
    meta, _ = captured()
    for field, value in [('instrument_type', 'ETF'), ('ticker', '2845.TWO')]:
        data = deepcopy(meta['data']); data[field] = value
        assert company_news_query(data) != '"遠銀" when:30d'


def test_captured_macro_author_credit_does_not_become_issuer_subject():
    from source_content_selection import select_company_records, issuer_match
    meta, rows = captured('commentary'); data = deepcopy(meta['data'])
    columns = [r for r in rows if r['title'].startswith('【遠東商銀】')]
    assert len(columns) == 11
    assert all(issuer_match(r, data) is None for r in columns)
    selected, audit = select_company_records(columns, data, cutoff=meta['cutoff'])
    assert selected == [] and audit['rejected_reason_counts'] == {'issuer_not_subject': 11}
    assert [x['record'] for x in audit['source_record_archive']] == columns


@pytest.mark.parametrize('title', [
    '【遠東商銀】營收成長帶動本行獲利創高 - 鉅亨網',
    '【遠東商銀】推出美元存款服務，分行新增客戶 - 鉅亨網',
    '遠東商銀主辦昇貿科技25億元聯貸 - 自由財經',
])
def test_bank_own_events_remain_eligible(title):
    from source_content_selection import issuer_match
    meta, _ = captured()
    assert issuer_match({'title': title, 'source': '鉅亨網'}, meta['data']) is not None


def test_invalid_typed_receipt_and_other_stock_do_not_gain_bank_brand():
    from source_content_selection import issuer_match
    meta, _ = captured(); row = {'title': '遠銀Bankee推出信貸', 'issuer_news_receipt': {}}
    assert issuer_match(row, meta['data']) is None
    other = deepcopy(meta['data']); other['ticker'] = '2883.TW'
    assert issuer_match({'title': '遠銀Bankee推出信貸'}, other) is None


def test_captured_legacy_identity_uses_root_equity_without_mutating_identity():
    from company_news_queries import company_news_query
    meta, _ = captured(); data = deepcopy(meta['data'])
    assert 'instrument_type' not in data['company_identity']
    assert data['instrument_type'] == 'EQUITY'
    before = deepcopy(data); assert company_news_query(data) == '"遠銀" when:30d'; assert data == before


def test_bounded_original_two_queries_stop_when_eight_are_available(monkeypatch):
    import asyncio
    import external_search_providers as search
    import data_fetch.market_sources.ltn_stock_news as ltn
    meta, rows = captured(); cutoff = datetime.fromisoformat(meta['cutoff'])
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cutoff.astimezone(tz) if tz else cutoff.replace(tzinfo=None)
    monkeypatch.setattr(search, 'datetime', Clock); calls = []
    async def acquire(query, **kw):
        calls.append(kw)
        assert kw['max_results'] == 8 and kw['lookback_days'] == 30
        assert kw['provider_allowlist'] == {'google_news_rss'}
        assert kw['provider_queries']['google_news_rss'].startswith('"遠銀" when:30d')
        take = rows[:1] if len(calls) == 1 else rows
        return [search.SearchResult(r['title'], r['summary'], r['link'], r['source'], r['date'],
                                    provider='google_news_rss') for r in take]
    monkeypatch.setattr(search, 'fetch_web_search_results_async', acquire)
    monkeypatch.setattr(ltn, 'fetch_ltn_stock_news', lambda *a, **k: pytest.fail('sufficient news stops fallback'))
    data = deepcopy(meta['data']); before = deepcopy(data)
    out = asyncio.run(search.fetch_alternative_search_catalysts_async(data['ticker'], data['company_name'],
        data['company_identity'], provider_allowlist={'google_news_rss'}))
    assert len(calls) == 2 and len(out) == 8
    assert calls[1]['provider_queries']['google_news_rss'] == '"遠銀" when:30d'
    assert data == before


@pytest.mark.parametrize('title', [
    '【遠東商銀】美元獲利了結，日圓走強 - 鉅亨網',
    '【遠東商銀】英鎊獲利回吐，美元反彈 - 鉅亨網',
])
def test_fx_profit_taking_or_retracement_is_not_the_banks_own_profit(title):
    from source_content_selection import issuer_match
    meta, _ = captured()
    assert issuer_match({'title': title, 'source': '鉅亨網'}, meta['data']) is None
