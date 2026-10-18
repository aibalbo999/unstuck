"""Complete archived issuer bytes, replayed without production or network I/O."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
import gzip
import json

import pytest
from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news, verified_issuer_news
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from source_content_selection import select_company_records

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition/eink_issuer_news_full_20261011'
MANIFEST = json.loads((FIXTURES / 'manifest.json').read_text())
MASTER = MANIFEST['parts']['otc_master']['url']
LOCALE = MANIFEST['parts']['locale_anchor']['url']
INDEX = MANIFEST['parts']['zh_index']['url']
ARTICLES = [MANIFEST['parts'][key]['url'] for key in ('zh_article_1', 'zh_article_2')]
NOW = datetime(2026, 10, 11, 8, 30, tzinfo=timezone.utc)
DATA = {'ticker': '8069.TWO', 'company_name': '元太', 'instrument_type': 'EQUITY',
        'company_identity': {'ticker': '8069.TWO', 'stock_id': '8069', 'official_name': '元太',
            'legal_name': '元太科技工業股份有限公司', 'official_ubn': '22099890',
            'allowed_aliases': ['元太'], 'forbidden_aliases': []}}


class Http:
    def __init__(self, *, cached=False):
        self.contents = {}
        for part in MANIFEST['parts'].values():
            raw = gzip.open(FIXTURES / part['filename'], 'rb').read()
            assert len(raw) == part['bytes'] and sha256(raw).hexdigest() == part['sha256']
            self.contents[part['url']] = raw
        self.calls, self.components = [], []
        self.http_request_count = 0
        self.cached = cached

    def get(self, url):
        self.calls.append(url)
        self.http_request_count += int(not self.cached)
        self.components.append({'url': url, 'http_request_sent': not self.cached,
                                'cache_hit': self.cached, 'fetched_at_epoch': NOW.timestamp() - 300})
        return self.contents[url]


def get(http=None):
    return fetch_recent_issuer_news('8069.TWO', now=NOW, http=http or Http())


def test_eink_otc_originals_enter_existing_provider_plan_only_on_exact_market():
    registry = ProviderRegistry()
    assert 'Verified issuer news' in registry.provider_names(FetchRequest.from_ticker('8069.TWO'), 'recent_catalysts')
    assert 'Verified issuer news' not in registry.provider_names(FetchRequest.from_ticker('8069.TW'), 'recent_catalysts')


def test_two_complete_press_originals_reach_public_company_selection():
    http = Http()
    records, audit = get(http)
    assert len(records) == 2 and audit['status'] == 'success'
    chosen, _ = select_company_records(records, DATA, cutoff=NOW)
    assert len(chosen) == 2
    assert [row['date'] for row in chosen] == ['2026-10-01', '2026-09-30']
    assert all(row['content_truncated'] is False and row['content_coverage'] == 'text_available' for row in chosen)
    assert all(row['source_role'] == 'issuer_statement' and row['event_assessment'] == 'not_assessed' for row in chosen)
    assert '2027' in chosen[0]['text'] and '股市爆料' not in chosen[0]['text']
    assert audit['window_complete'] is False
    assert audit['http_request_count'] == 5
    assert http.calls == [MASTER, LOCALE, INDEX, *ARTICLES]
    assert DATA['company_identity']['allowed_aliases'] == ['元太']


@pytest.mark.parametrize('field,value', [
    ('CompanyName', '另一家公司股份有限公司'), ('CompanyAbbreviation', '他家公司'),
    ('UnifiedBusinessNo.', '99999999'), ('WebAddress', 'www.eink.com.evil.test'),
    ('WebAddress', 'tw.eink.com'), ('Date', '1150801'), ('Date', '1151012')])
def test_invalid_otc_issuer_anchor_stops_before_any_article(field, value):
    http = Http()
    roster = json.loads(http.contents[MASTER])
    next(row for row in roster if row['SecuritiesCompanyCode'] == '8069')[field] = value
    http.contents[MASTER] = json.dumps(roster, ensure_ascii=False).encode()
    records, audit = get(http)
    assert records == [] and audit['status'] == 'error'
    assert http.calls == [MASTER]


def test_partial_or_duplicate_master_cannot_claim_complete_otc_identity():
    for duplicate in (False, True):
        http = Http()
        roster = json.loads(http.contents[MASTER])
        row = next(item for item in roster if item['SecuritiesCompanyCode'] == '8069')
        http.contents[MASTER] = json.dumps(roster + [row] if duplicate else [row], ensure_ascii=False).encode()
        records, _ = get(http)
        assert records == [] and http.calls == [MASTER]


def test_locale_host_must_be_explicitly_linked_by_the_bound_official_site():
    http = Http()
    http.contents[LOCALE] = http.contents[LOCALE].replace(INDEX.encode(), b'https://evil.test/news')
    records, audit = get(http)
    assert records == [] and audit['status'] == 'error'
    assert http.calls == [MASTER, LOCALE]


@pytest.mark.parametrize('url', [
    INDEX + '?page=2', ARTICLES[0] + '?token=x', ARTICLES[0] + '#article',
    ARTICLES[0].replace('https:', 'http:'), ARTICLES[0].replace('tw.eink.com', 'tw.eink.com.evil.test'),
    'https://www.eink.com/news/detail/eiInk-names-flint-paper-battery-qinner-of-2026-mit-solve-award',
    'https://tw.eink.com/news/detail/../private', 'https://tw.eink.com/investor', MASTER + '?key=x'])
def test_other_language_pagination_private_or_ambiguous_routes_cannot_start_transport(url):
    from data_fetch.market_sources.eink_issuer_news import url_contract
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):
        url_contract(url)


@pytest.mark.parametrize('context', [False, 'not a company', {'ticker': '8069.TW'},
    {'stock_id': '2330'}, {'official_name': '他家公司'}, {'legal_name': '他家公司股份有限公司'},
    {'official_ubn': '99999999'}, {'instrument_type': 'ETF'}, {'forbidden_aliases': False},
    {'forbidden_aliases': ['元太']}, {'forbidden_aliases': ['E INK']}])
def test_original_receipt_cannot_override_malformed_or_conflicting_company_context(context):
    records, _ = get()
    chosen, _ = select_company_records(records, {**DATA, 'company_identity': context}, cutoff=NOW)
    assert chosen == []


@pytest.mark.parametrize('change', ['title', 'body', 'date', 'role', 'publisher', 'coverage',
    'source_type', 'url', 'market', 'policy', 'master_hash', 'article_hash', 'locale_missing',
    'archive_url', 'archive_size', 'archive_path', 'archive_nan', 'archive_future', 'master_older_than_publication'])
def test_complete_originals_are_replayed_before_semantic_admission(change):
    records, _ = get()
    row = deepcopy(records[0])
    receipt = row['issuer_news_receipt']
    if change == 'title': row['title'] = '元太虛構新聞'
    elif change == 'body': row['text'] = '元太虛構資料' * 30
    elif change == 'date': row['date'] = '2026-10-02'
    elif change == 'role': row['source_role'] = 'independent_editorial'
    elif change == 'publisher': row['publisher'] = 'Independent newspaper'
    elif change == 'coverage': row['content_truncated'] = True
    elif change == 'source_type': row.pop('source_type')
    elif change == 'url': row['link'] = 'https://evil.test/news'
    elif change == 'market': receipt['market'] = 'TWSE'
    elif change == 'policy': receipt['policy'] = 'generic-firstparty'
    elif change == 'master_hash': receipt['master_response_sha256'] = '0' * 64
    elif change == 'article_hash': receipt['article_response_sha256'] = '0' * 64
    elif change == 'locale_missing': receipt['source_record_archive'].pop('locale')
    elif change == 'master_older_than_publication': receipt['source_record_archive']['master']['retrieved_at'] = NOW.timestamp() - 5 * 86400
    else:
        proof = receipt['source_record_archive']['article']
        if change == 'archive_url': proof['source_url'] = INDEX
        elif change == 'archive_size': proof['raw_response_bytes'] += 1
        elif change == 'archive_path': proof['raw_response_path'] = '/tmp/not-an-original.gz'
        elif change == 'archive_nan': proof['retrieved_at'] = float('nan')
        else: proof['retrieved_at'] = 9e15
    chosen, _ = select_company_records([row], DATA, cutoff=NOW)
    assert chosen == []


@pytest.mark.parametrize('change', ['title', 'date', 'role', 'body_issuer', 'wrong_market', 'script'])
def test_detail_title_publication_body_and_market_must_match_its_own_index(change):
    from bs4 import BeautifulSoup
    http = Http()
    soup = BeautifulSoup(http.contents[ARTICLES[0]], 'html.parser')
    outline = soup.select_one('div.outline')
    if change == 'title': outline.find('h1', recursive=False).string = '另一則元太新聞'
    elif change == 'date': outline.select_one('.date').clear()
    elif change == 'role': outline.select_one('.tag').string = '部落格'
    else:
        body = soup.select_one('div._articleBlock')
        if change == 'body_issuer': body.clear(); body.string = '另一家公司' * 40
        elif change == 'wrong_market': body.append(BeautifulSoup('<p>8069.TW</p>', 'html.parser'))
        else: body.append(BeautifulSoup('<script>document.write("元太科技")</script>', 'html.parser'))
    http.contents[ARTICLES[0]] = str(soup).encode()
    records, audit = get(http)
    assert records == [] and audit['status'] == 'error'
    assert http.calls == [MASTER, LOCALE, INDEX, ARTICLES[0]]


def test_all_originals_from_fresh_cache_keep_epoch_and_http_zero():
    records, audit = get(Http(cached=True))
    assert len(records) == 2 and audit['status'] == 'skipped_fresh_cache'
    assert audit['http_request_sent'] is False and audit['http_request_count'] == 0
    assert audit['fetched_at_epoch'] == NOW.timestamp() - 300


def test_processing_after_shared_deadline_cannot_admit_the_late_body(monkeypatch):
    import time
    from types import SimpleNamespace
    from data_fetch.market_sources import eink_issuer_news as parser
    clock = [0.]
    original = parser.parse_article
    monkeypatch.setattr(parser, 'time', SimpleNamespace(monotonic=lambda: clock[0], time=time.time))
    def late(*args):
        value = original(*args); clock[0] = 21.; return value
    monkeypatch.setattr(parser, 'parse_article', late)
    records, audit = get()
    assert records == [] and audit['status'] == 'error' and audit['error_kind'] == 'timeout'


def test_complete_firstparty_source_merges_only_news_and_does_not_satisfy_eight_record_search_gate(monkeypatch):
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources import issuer_news
    import data_fetch.workflow as workflow
    import asyncio
    real = issuer_news.fetch_recent_issuer_news
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news', lambda ticker: real(ticker, now=NOW, http=Http()))
    monkeypatch.setattr(workflow, 'cache_financial_payload', lambda *a: None)
    monkeypatch.setattr(workflow, 'finalize_data_trust', lambda *a: None)
    monkeypatch.setattr(workflow, '_merge_optional_http_bundle', lambda data, bundle, **kw: _merge_optional_http_bundle(data, bundle))
    data = deepcopy(DATA)
    data['current_price'] = 123.; data['financial_currency'] = 'TWD'
    result = asyncio.run(workflow._run_optional_provider_plan(
        FetchRequest.from_ticker('8069.TWO'), ProviderRegistry([IssuerNewsProvider()]), data, sources=('recent_catalysts',)))
    assert len(result['recent_catalysts']) == 2
    assert result['company_identity'] == DATA['company_identity'] and result['current_price'] == 123.
    assert result['financial_currency'] == 'TWD'
    assert any(a['provider'] == 'Verified issuer news' and a['record_count'] == 2 for a in result['source_audit'])
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    news = [SearchResult(r['title'], r['text'], r['link'], r['publisher'], r['date']) for r in result['recent_catalysts']]
    assert not search_quality_satisfied(news, max_results=8, query='元太', require_recent=True, cutoff=NOW)


def test_original_archive_paths_stay_out_of_prompts_and_whole_records_are_preserved():
    from prompt_builder import format_data_for_prompt
    records, _ = get()
    before = deepcopy(records)
    prompt = format_data_for_prompt({**deepcopy(DATA), 'recent_catalysts': records})
    assert 'official-response-evidence' not in prompt and 'raw_response_path' not in prompt
    assert records[0]['title'] in prompt and '2026-10-01' in prompt
    assert records == before


def test_old_or_future_index_publication_never_fetches_article_bodies():
    from bs4 import BeautifulSoup
    for stamp, reason in [('10 2026 . Sep', 'historical'), ('12 2026 . Oct', 'future')]:
        http = Http()
        soup = BeautifulSoup(http.contents[INDEX], 'html.parser')
        for card in soup.select('ul.news-list > li.item'):
            if card.select_one('.tag').get_text(strip=True) == '新聞發佈':
                node = card.select_one('.date'); node.clear(); node.string = stamp
        http.contents[INDEX] = str(soup).encode()
        records, audit = get(http)
        assert records == [] and audit['status'] == 'unavailable'
        assert audit['excluded_reason_counts'][reason] == 3
        assert http.calls == [MASTER, LOCALE, INDEX]


def test_existing_source_only_report_refresh_consumes_eink_originals_and_preserves_core_fields(monkeypatch):
    import asyncio
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import issuer_news
    from report_source_refresh import fetch_report_source_data
    real = issuer_news.fetch_recent_issuer_news
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news', lambda ticker: real(ticker, now=NOW, http=Http()))
    original = deepcopy(DATA)
    original.update(current_price=123., financial_currency='TWD', years=['2021', '2022', '2023', '2024', '2025'],
                    eps_history=[1., 2., 3., 4., 5.], recent_catalysts=[], social_sentiment=[{'text': 'old social'}])
    audits = [{'source': 'market_data', 'provider': 'original quote', 'status': 'success',
               'fetched_at_epoch': NOW.timestamp() - 600, 'record_count': 1},
              {'source': 'financial_statements', 'provider': 'original finance', 'status': 'success',
               'fetched_at_epoch': NOW.timestamp() - 700, 'record_count': 5}]
    snapshot = {'ticker': '8069.TWO', 'data': original, 'source_audit': audits}
    saved = deepcopy(snapshot)
    merged = asyncio.run(fetch_report_source_data(snapshot, 'issuer_news', StockDataService()))
    assert len(merged['recent_catalysts']) == 2
    assert all(verified_issuer_news(row, DATA, today=NOW.date()) for row in merged['recent_catalysts'])
    for key in ('company_identity', 'current_price', 'financial_currency', 'years', 'eps_history', 'social_sentiment'):
        assert merged[key] == original[key]
    assert merged['source_audit'][:2] == audits
    assert snapshot == saved


def test_public_source_only_path_cannot_drop_conflicting_root_instrument_type(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import eink_issuer_news as source
    from report_source_refresh import fetch_report_source_data
    class Replay(Http):
        def __init__(self, deadline): super().__init__()
    monkeypatch.setattr(source, 'EInkHttp', Replay)
    data = deepcopy(DATA)
    data.update(instrument_type='ETF', recent_catalysts=[], current_price=123.)
    original = {'ticker': '8069.TWO', 'data': data, 'source_audit': [
        {'source': 'market_data', 'provider': 'original quote', 'status': 'success',
         'fetched_at_epoch': NOW.timestamp()-600, 'record_count': 1}]}
    with pytest.raises(HTTPException):
        asyncio.run(fetch_report_source_data(original, 'issuer_news', StockDataService()))


@pytest.mark.parametrize('changed', [{'instrument_type': 'ETF'}, {'instrument_type': False},
                                   {'instrument_type': 'unknown'}, {'quote_type': 'ETF'}])
def test_conflicting_source_only_instrument_stops_before_transport_or_audit(monkeypatch, changed):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import eink_issuer_news as source
    from report_source_refresh import fetch_report_source_data
    monkeypatch.setattr(source, 'EInkHttp', lambda *args: pytest.fail('conflicting identity must stop before HTTP'))
    data = deepcopy(DATA); data.update(changed)
    original = {'ticker': '8069.TWO', 'data': data, 'source_audit': [
        {'source': 'market_data', 'provider': 'original quote', 'status': 'success',
         'fetched_at_epoch': NOW.timestamp()-600, 'record_count': 1}]}
    with pytest.raises(HTTPException) as raised:
        asyncio.run(fetch_report_source_data(original, 'issuer_news', StockDataService()))
    assert raised.value.status_code == 400
